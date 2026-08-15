from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from video_channel_manager.platforms.vk.milovi_issue323_finalize import (
    MiloviFinalizerBlocked,
    _assert_native_clip,
    _clip_copy_state,
    _copy_state,
    _promote_asset,
)
from video_channel_manager.platforms.vk.milovi_issue323_status_probe import _probe_batch
from video_channel_manager.platforms.vk.milovi_rollout_sources import (
    ROLL_OUT_IDS,
    SourceAsset,
    build_description,
    build_wall_message,
)
from video_channel_manager.platforms.vk.upload_lifecycle import UploadStage
from video_channel_manager.platforms.vk.wall_safety import VkWallSnapshot

REMOTE_ID = "-68859909_456239233"


def _assets() -> list[SourceAsset]:
    assets: list[SourceAsset] = []
    for index, source_id in enumerate(ROLL_OUT_IDS, start=1):
        title = f"Milovi source {index}"
        assets.append(
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
    return assets


def _projection(text: str) -> str:
    assert len(text) > 140
    return text[:140].rstrip() + ".."


def _slots() -> dict[str, datetime]:
    start = datetime(2026, 8, 14, 19, 0, tzinfo=UTC)
    return {source_id: start + timedelta(days=index) for index, source_id in enumerate(ROLL_OUT_IDS)}


def _snapshot() -> VkWallSnapshot:
    return VkWallSnapshot(
        community_id=68859909,
        captured_at="2026-08-15T11:00:00+00:00",
        complete=True,
        published_pages=1,
        postponed_pages=1,
        posts=(),
    )


class _Provider:
    def __init__(self, video: dict[str, Any]) -> None:
        self.video = video

    def read_video(self, *, owner_id: int, video_id: int) -> dict[str, Any] | None:
        assert owner_id == -68859909
        assert video_id == 456239233
        return dict(self.video)

    def read_post(self, *, community_id: int, post_id: int) -> dict[str, Any] | None:
        return None


def test_processing_promoted_prefix_is_classified_but_exact_copy_gate_stays_strict() -> None:
    promoted = "P" * 200
    legacy = "L" * 200
    current = _projection(promoted)

    assert (
        _clip_copy_state(
            current=current,
            legacy=legacy,
            promoted=promoted,
            source_id=ROLL_OUT_IDS[8],
            field="Clip description",
            provider_item={"processing": 1},
        )
        == "provider_processing_promoted_projection"
    )

    with pytest.raises(MiloviFinalizerBlocked, match="neither exact reviewed legacy nor exact promoted copy"):
        _copy_state(
            current=current,
            legacy=legacy,
            promoted=promoted,
            source_id=ROLL_OUT_IDS[8],
            field="Clip description",
        )


def test_processing_flag_does_not_excuse_unrelated_third_copy() -> None:
    with pytest.raises(MiloviFinalizerBlocked, match="neither exact reviewed legacy nor exact promoted copy"):
        _clip_copy_state(
            current="operator-edited unrelated text " * 5 + "..",
            legacy="legacy reviewed copy " * 10,
            promoted="promoted reviewed copy " * 10,
            source_id=ROLL_OUT_IDS[8],
            field="Clip description",
            provider_item={"processing": 1},
        )


def test_projection_requires_provider_busy_flag() -> None:
    promoted = "P" * 200
    current = _projection(promoted)
    with pytest.raises(MiloviFinalizerBlocked, match="neither exact reviewed legacy nor exact promoted copy"):
        _clip_copy_state(
            current=current,
            legacy="L" * 200,
            promoted=promoted,
            source_id=ROLL_OUT_IDS[8],
            field="Clip description",
            provider_item={"processing": 0, "converting": 0},
        )


def test_promoted_mode_remains_exact_even_for_processing_projection() -> None:
    asset = _promote_asset(_assets()[8])
    provider = _Provider(
        {
            "owner_id": -68859909,
            "id": 456239233,
            "type": "short_video",
            "processing": 1,
            "description": _projection(asset.description),
        }
    )

    with pytest.raises(MiloviFinalizerBlocked, match="public description differs from promotion plan"):
        _assert_native_clip(  # type: ignore[arg-type]
            provider,
            asset,
            REMOTE_ID,
            description_mode="promoted",
            durable_verified=True,
        )


def test_readonly_status_protects_verified_source9_processing_projection_from_reupload() -> None:
    assets = _assets()
    source_id = ROLL_OUT_IDS[8]
    promoted = _promote_asset(assets[8])
    journal: dict[str, Any] = {"items": {item: {"status": "pending"} for item in ROLL_OUT_IDS}}
    journal["items"][source_id] = {
        "status": "upload_in_progress",
        "upload_record": {
            "stage": UploadStage.VERIFIED.value,
            "reservation": {"remote_id": REMOTE_ID},
        },
    }
    provider = _Provider(
        {
            "owner_id": -68859909,
            "id": 456239233,
            "type": "short_video",
            "processing": 1,
            "title": None,
            "description": _projection(promoted.description),
        }
    )

    payload = _probe_batch(
        assets=assets,
        journal=journal,
        slots=_slots(),
        provider=provider,  # type: ignore[arg-type]
        client=object(),  # type: ignore[arg-type]
        snapshot=_snapshot(),
        existing_clip_lookup=lambda _client, _asset: None,
        now_epoch=1786791600,
    )

    row = payload["items"][8]
    assert payload["status"] == "verified_read_only"
    assert row["clip_remote_id"] == REMOTE_ID
    assert row["upload_stage"] == UploadStage.VERIFIED.value
    assert row["provider_effect_durable"] is True
    assert row["clip_copy_state"] == "provider_processing_promoted_projection"
    assert row["safe_next_action"] == "resume_from_verified_clip_without_reupload_then_wall"
    assert row["reupload_authorized_by_probe"] is False
    assert row["repost_authorized_by_probe"] is False
    assert source_id in payload["protected_no_reupload_source_ids"]
