from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from video_channel_manager.platforms.vk.milovi_issue323_status_probe import (
    _ReadOnlyVkProvider,
    _load_prepared_assets,
    _probe_batch,
)
from video_channel_manager.platforms.vk.milovi_rollout_sources import (
    PREPARED_SCHEMA,
    ROLL_OUT_IDS,
    SOURCE_SNAPSHOT_ID,
    SourceAsset,
    build_description,
    build_wall_message,
)
from video_channel_manager.platforms.vk.upload_lifecycle import UploadStage
from video_channel_manager.platforms.vk.wall_safety import VkWallSnapshot


class _ReadOnlyFakeProvider:
    def __init__(self, videos: dict[str, dict[str, Any]]) -> None:
        self.videos = videos
        self.read_video_calls: list[str] = []
        self.read_post_calls: list[int] = []

    def read_video(self, *, owner_id: int, video_id: int) -> dict[str, Any] | None:
        remote_id = f"{owner_id}_{video_id}"
        self.read_video_calls.append(remote_id)
        value = self.videos.get(remote_id)
        return dict(value) if value is not None else None

    def read_post(self, *, community_id: int, post_id: int) -> dict[str, Any] | None:
        self.read_post_calls.append(post_id)
        return None


def _assets() -> list[SourceAsset]:
    result: list[SourceAsset] = []
    for index, source_id in enumerate(ROLL_OUT_IDS, start=1):
        title = f"Milovi source {index}"
        result.append(
            SourceAsset(
                source_id=source_id,
                source_url=f"https://www.youtube.com/shorts/{source_id}",
                title=title,
                duration_seconds=30,
                media_path=f"Z:/missing/{source_id}.mp4",
                media_sha256="0" * 64,
                width=1080,
                height=1920,
                description=build_description(title, source_id),
                wall_message=build_wall_message(title, source_id),
            )
        )
    return result


def _slots() -> dict[str, datetime]:
    start = datetime(2026, 8, 14, 19, 0, tzinfo=UTC)
    return {source_id: start + timedelta(days=index) for index, source_id in enumerate(ROLL_OUT_IDS)}


def _journal() -> dict[str, Any]:
    return {"items": {source_id: {"status": "pending"} for source_id in ROLL_OUT_IDS}}


def _empty_snapshot() -> VkWallSnapshot:
    return VkWallSnapshot(
        community_id=68859909,
        captured_at="2026-08-15T02:00:00+00:00",
        complete=True,
        published_pages=1,
        postponed_pages=1,
        posts=(),
    )


def test_prepared_manifest_loader_is_metadata_only(tmp_path: Path) -> None:
    assets = _assets()
    manifest = tmp_path / "prepared-sources.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_name": PREPARED_SCHEMA,
                "schema_version": 1,
                "source_snapshot_id": SOURCE_SNAPSHOT_ID,
                "media_profile": "vk-h264-aac-v1",
                "assets": [asdict(asset) for asset in assets],
            }
        ),
        encoding="utf-8",
    )

    loaded = _load_prepared_assets(manifest)

    assert tuple(asset.source_id for asset in loaded) == ROLL_OUT_IDS
    assert all(not Path(asset.media_path).exists() for asset in loaded)


def test_verified_upload_record_is_protected_from_reupload() -> None:
    assets = _assets()
    journal = _journal()
    source_id = ROLL_OUT_IDS[8]
    remote_id = "-68859909_456239233"
    journal["items"][source_id] = {
        "status": "upload_in_progress",
        "upload_record": {
            "stage": UploadStage.VERIFIED.value,
            "reservation": {"remote_id": remote_id},
        },
    }
    asset = assets[8]
    provider = _ReadOnlyFakeProvider(
        {
            remote_id: {
                "owner_id": -68859909,
                "id": 456239233,
                "type": "short_video",
                "description": asset.description,
            }
        }
    )

    payload = _probe_batch(
        assets=assets,
        journal=journal,
        slots=_slots(),
        provider=provider,  # type: ignore[arg-type]
        client=object(),  # type: ignore[arg-type]
        snapshot=_empty_snapshot(),
        existing_clip_lookup=lambda _client, _asset: None,
        now_epoch=1786759200,
    )

    row = payload["items"][8]
    assert row["source_id"] == source_id
    assert row["clip_remote_id"] == remote_id
    assert row["clip_identity_origin"] == "upload_record"
    assert row["upload_stage"] == UploadStage.VERIFIED.value
    assert row["provider_effect_durable"] is True
    assert row["clip_copy_state"] == "legacy"
    assert row["safe_next_action"] == "resume_from_verified_clip_without_reupload_then_wall"
    assert row["reupload_authorized_by_probe"] is False
    assert source_id in payload["protected_no_reupload_source_ids"]
    assert provider.read_video_calls == [remote_id]


def test_unreviewed_clip_copy_blocks_instead_of_overwriting() -> None:
    assets = _assets()
    journal = _journal()
    source_id = ROLL_OUT_IDS[8]
    remote_id = "-68859909_456239233"
    journal["items"][source_id] = {
        "status": "upload_in_progress",
        "upload_record": {
            "stage": UploadStage.VERIFIED.value,
            "reservation": {"remote_id": remote_id},
        },
    }
    provider = _ReadOnlyFakeProvider(
        {
            remote_id: {
                "owner_id": -68859909,
                "id": 456239233,
                "type": "short_video",
                "description": "operator-edited third state",
            }
        }
    )

    payload = _probe_batch(
        assets=assets,
        journal=journal,
        slots=_slots(),
        provider=provider,  # type: ignore[arg-type]
        client=object(),  # type: ignore[arg-type]
        snapshot=_empty_snapshot(),
        existing_clip_lookup=lambda _client, _asset: None,
        now_epoch=1786759200,
    )

    row = payload["items"][8]
    assert payload["status"] == "blocked"
    assert row["safe_next_action"] == "stop_conflict"
    assert "neither exact reviewed legacy nor exact promoted copy" in row["stop_reason"]
    assert row["reupload_authorized_by_probe"] is False
    assert row["repost_authorized_by_probe"] is False


def test_provider_facade_exposes_no_mutation_methods() -> None:
    forbidden = {
        "_call",
        "begin_upload",
        "upload_file",
        "wait_until_available",
        "edit_video",
        "edit_post",
        "delete_post",
        "create_post",
    }

    assert forbidden.isdisjoint(dir(_ReadOnlyVkProvider))
    public_methods = {name for name in dir(_ReadOnlyVkProvider) if not name.startswith("_")}
    assert public_methods == {"capture_wall_snapshot", "read_post", "read_video"}
