from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from video_channel_manager.domain.enums import ChannelKind, PlatformName
from video_channel_manager.domain.models import ChannelRecord, RemoteRef, VideoRecord
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.lordchrist_cross_track_effect_guard import (
    require_no_unresolved_provider_effects_across_tracks,
)
from video_channel_manager.lordchrist_shorts import (
    PROJECT_KEY,
    TELEGRAM_CHANNEL_USERNAME,
    YOUTUBE_CHANNEL_ID,
    CandidateApprovalManifest,
    EffectSnapshot,
    OwnerMediaBinding,
    OwnerMediaBindingManifest,
    build_inventory,
    build_provider_inert_release,
    conversion_argv,
    load_and_validate_editorial_schedule,
    load_policy,
    normalize_probe,
    prepare_owner_media,
    publication_id_for,
    require_existing_lordchrist_state_clear,
    require_lordchrist_state_root_clear,
    require_min_editorial_gap,
)
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_video import GenericVideoPayload

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "content/telegram/lordchrist/shorts-feed-policy.json"
PROFILE = ROOT / "content/telegram/channels/lordchrist.json"
EDITORIAL_SCHEDULE = ROOT / "content/telegram/lordchrist/production-schedule.json"


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _video(
    video_id: str,
    *,
    title: str,
    width: int,
    height: int,
    duration_ms: int,
    creation_time: str,
    published_at: datetime,
) -> VideoRecord:
    return VideoRecord(
        ref=RemoteRef(platform=PlatformName.YOUTUBE, channel_id=YOUTUBE_CHANNEL_ID, remote_id=video_id),
        title=title,
        duration_seconds=duration_ms // 1000,
        published_at=published_at,
        revision=f"sha256:{video_id}",
        metadata={
            "fileDetails": {
                "durationMs": duration_ms,
                "creationTime": creation_time,
                "videoStreams": [
                    {
                        "widthPixels": width,
                        "heightPixels": height,
                        "rotation": "none",
                    }
                ],
            }
        },
    )


def _audit() -> AuditPackage:
    channel = ChannelRecord(
        ref=RemoteRef(
            platform=PlatformName.YOUTUBE,
            channel_id=YOUTUBE_CHANNEL_ID,
            remote_id=YOUTUBE_CHANNEL_ID,
        ),
        title="Господь Бог - Сила Моя",
        kind=ChannelKind.VIDEO_CHANNEL,
    )
    return AuditPackage(
        channel=channel,
        generated_at=datetime(2026, 8, 20, 12, 0, tzinfo=UTC),
        videos=[
            _video(
                "AbCdEf12345",
                title="Первый Short #Shorts",
                width=1080,
                height=1920,
                duration_ms=60_000,
                creation_time="2026-01-02T00:00:00Z",
                published_at=datetime(2026, 1, 3, tzinfo=UTC),
            ),
            _video(
                "QwErTy67890",
                title="Исторический кандидат",
                width=1080,
                height=1920,
                duration_ms=45_000,
                creation_time="2024-01-02T00:00:00Z",
                published_at=datetime(2024, 1, 3, tzinfo=UTC),
            ),
            _video(
                "LmNoPq13579",
                title="Landscape",
                width=1920,
                height=1080,
                duration_ms=50_000,
                creation_time="2026-01-02T00:00:00Z",
                published_at=datetime(2026, 1, 4, tzinfo=UTC),
            ),
        ],
    )


def _probe(duration: float = 60.0) -> dict[str, object]:
    return {
        "format": {
            "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
            "duration": str(duration),
        },
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "pix_fmt": "yuv420p",
                "width": 1080,
                "height": 1920,
                "duration": str(duration),
            },
            {
                "codec_type": "audio",
                "codec_name": "aac",
            },
        ],
    }


def _binding(video_id: str, source: Path, *, source_kind: str = "google_takeout") -> OwnerMediaBinding:
    data = source.read_bytes()
    return OwnerMediaBinding(
        youtube_video_id=video_id,
        source_kind=source_kind,
        source_path=str(source),
        expected_source_sha256=_digest(data),
        expected_source_byte_size=len(data),
    )


def _bindings(*items: OwnerMediaBinding) -> OwnerMediaBindingManifest:
    return OwnerMediaBindingManifest(
        schema_name="video-channel-manager.lordchrist-shorts-owner-media-bindings",
        schema_version=1,
        project_key=PROJECT_KEY,
        youtube_channel_id=YOUTUBE_CHANNEL_ID,
        items=items,
    )


def _approval(snapshot_id: str, *video_ids: str) -> CandidateApprovalManifest:
    return CandidateApprovalManifest(
        schema_name="video-channel-manager.lordchrist-shorts-candidate-approval",
        schema_version=1,
        project_key=PROJECT_KEY,
        youtube_channel_id=YOUTUBE_CHANNEL_ID,
        inventory_snapshot_id=snapshot_id,
        approved_video_ids=video_ids,
        reviewed_by="FedorMilovanov",
        reviewed_at=datetime(2026, 8, 20, 18, 0, tzinfo=UTC),
    )


def test_policy_is_provider_inert_exactly_bound_and_respects_editorial_gap() -> None:
    policy = load_policy(POLICY)
    assert policy.project_key == PROJECT_KEY
    assert policy.youtube_channel_id == YOUTUBE_CHANNEL_ID
    assert policy.telegram_channel_username == TELEGRAM_CHANNEL_USERNAME
    assert policy.automated_youtube_download_allowed is False
    assert policy.telegram_provider_mutation_allowed is False
    assert policy.telegram_stories_enabled is False
    assert policy.daily_short_limit == 1
    assert policy.slot_local_time == "17:17"
    assert load_and_validate_editorial_schedule(EDITORIAL_SCHEDULE, policy) == ("09:17", "21:17")

    unsafe = policy.model_copy(update={"slot_local_time": "18:17"})
    with pytest.raises(ValueError, match="only 180 minutes"):
        require_min_editorial_gap(unsafe, ("09:17", "21:17"))


def test_inventory_uses_exact_owner_metadata_and_keeps_historical_candidate() -> None:
    inventory = build_inventory(_audit())
    assert [item.youtube_video_id for item in inventory.items] == ["QwErTy67890", "AbCdEf12345"]
    by_id = {item.youtube_video_id: item for item in inventory.items}
    assert by_id["AbCdEf12345"].surface_status == "short"
    assert by_id["AbCdEf12345"].owner_confirmation_required is False
    assert by_id["QwErTy67890"].surface_status == "candidate"
    assert by_id["QwErTy67890"].owner_confirmation_required is True
    assert inventory.excluded_longform_count == 1
    assert publication_id_for("AbCdEf12345") == "lordchrist-short-AbCdEf12345"


def test_prepare_owner_media_preserves_frozen_ready_bytes(tmp_path: Path) -> None:
    inventory = build_inventory(_audit())
    source = tmp_path / "takeout.mp4"
    source.write_bytes(b"owner-video-bytes-1")

    acceptance = prepare_owner_media(
        inventory,
        _bindings(_binding("AbCdEf12345", source)),
        output_dir=tmp_path / "prepared",
        probe_runner=lambda _path: _probe(60.0),
        ffprobe_version="ffprobe-test",
    )
    assert acceptance.provider_access_performed is False
    assert acceptance.provider_write_performed is False
    assert acceptance.ffmpeg_version is None
    assert len(acceptance.items) == 1
    item = acceptance.items[0]
    assert item.transcoded is False
    assert item.source_sha256 == item.media_sha256
    assert Path(item.transport_path).read_bytes() == source.read_bytes()


def test_prepare_owner_media_rejects_binding_if_exact_bytes_changed(tmp_path: Path) -> None:
    inventory = build_inventory(_audit())
    source = tmp_path / "takeout.mp4"
    source.write_bytes(b"reviewed-owner-bytes")
    binding = _binding("AbCdEf12345", source)
    source.write_bytes(b"tampered-owner-bytes")

    with pytest.raises(ValueError, match="SHA-256 differs from frozen binding"):
        prepare_owner_media(
            inventory,
            _bindings(binding),
            output_dir=tmp_path / "prepared",
            probe_runner=lambda _path: _probe(60.0),
            ffprobe_version="ffprobe-test",
        )


def test_conversion_contract_is_local_ffmpeg_only(tmp_path: Path) -> None:
    inventory = build_inventory(_audit())
    item = next(value for value in inventory.items if value.youtube_video_id == "AbCdEf12345")
    source = tmp_path / "source.webm"
    source.write_bytes(b"x")
    summary = normalize_probe(_probe(60.0))
    argv = conversion_argv(source, tmp_path / f"{item.publication_id}.mp4", source_summary=summary)
    joined = " ".join(argv)
    assert argv[0] == "ffmpeg"
    assert "yt-dlp" not in joined
    assert "youtube.com" not in joined
    assert "-c:v libx264" in joined
    assert "-pix_fmt yuv420p" in joined
    assert "-movflags +faststart" in joined


def test_release_is_unauthorized_one_per_day_and_candidate_approval_is_snapshot_bound(tmp_path: Path) -> None:
    inventory = build_inventory(_audit())
    exact_source = tmp_path / "exact.mp4"
    candidate_source = tmp_path / "candidate.mp4"
    exact_source.write_bytes(b"owner-video-bytes-exact")
    candidate_source.write_bytes(b"owner-video-bytes-candidate")

    def probe(path: Path) -> dict[str, object]:
        return _probe(45.0 if ("candidate" in path.name or "QwErTy67890" in path.name) else 60.0)

    acceptance = prepare_owner_media(
        inventory,
        _bindings(
            _binding("AbCdEf12345", exact_source),
            _binding("QwErTy67890", candidate_source, source_kind="local_master"),
        ),
        output_dir=tmp_path / "prepared",
        probe_runner=probe,
        ffprobe_version="ffprobe-test",
    )
    release = build_provider_inert_release(
        inventory,
        acceptance,
        profile=load_channel_profile(PROFILE),
        policy=load_policy(POLICY),
        start_date=date(2026, 8, 21),
        candidate_approval=_approval(inventory.source_snapshot_id, "QwErTy67890"),
    )

    assert release.release_authorized is False
    assert release.target_binding_sha256 is None
    assert release.chat_id is None
    assert len(release.items) == 2
    assert release.items[0].scheduled_at.hour == 17
    assert release.items[0].scheduled_at.minute == 17
    assert (release.items[1].scheduled_at - release.items[0].scheduled_at).days == 1
    assert all(isinstance(item.payload, GenericVideoPayload) for item in release.items)
    assert release.release_id.startswith("lordchrist-shorts-2026-08-21-")
    assert release.items[0].payload.caption.endswith(
        f"https://www.youtube.com/shorts/{release.items[0].publication_id.removeprefix('lordchrist-short-')}"
    )

    wrong_snapshot = _approval("different-snapshot", "QwErTy67890")
    with pytest.raises(ValueError, match="different YouTube inventory snapshot"):
        build_provider_inert_release(
            inventory,
            acceptance,
            profile=load_channel_profile(PROFILE),
            policy=load_policy(POLICY),
            start_date=date(2026, 8, 21),
            candidate_approval=wrong_snapshot,
        )


def test_candidate_is_excluded_without_immutable_approval_and_release_identity_tracks_content(tmp_path: Path) -> None:
    inventory = build_inventory(_audit())
    exact_source = tmp_path / "exact.mp4"
    candidate_source = tmp_path / "candidate.mp4"
    exact_source.write_bytes(b"owner-video-bytes-exact")
    candidate_source.write_bytes(b"owner-video-bytes-candidate")

    def probe(path: Path) -> dict[str, object]:
        return _probe(45.0 if ("candidate" in path.name or "QwErTy67890" in path.name) else 60.0)

    acceptance = prepare_owner_media(
        inventory,
        _bindings(
            _binding("AbCdEf12345", exact_source),
            _binding("QwErTy67890", candidate_source, source_kind="local_master"),
        ),
        output_dir=tmp_path / "prepared",
        probe_runner=probe,
        ffprobe_version="ffprobe-test",
    )
    without_candidate = build_provider_inert_release(
        inventory,
        acceptance,
        profile=load_channel_profile(PROFILE),
        policy=load_policy(POLICY),
        start_date=date(2026, 8, 21),
    )
    with_candidate = build_provider_inert_release(
        inventory,
        acceptance,
        profile=load_channel_profile(PROFILE),
        policy=load_policy(POLICY),
        start_date=date(2026, 8, 21),
        candidate_approval=_approval(inventory.source_snapshot_id, "QwErTy67890"),
    )
    assert [item.publication_id for item in without_candidate.items] == ["lordchrist-short-AbCdEf12345"]
    assert without_candidate.release_id != with_candidate.release_id

    with pytest.raises(ValueError, match="candidate approvals do not match"):
        build_provider_inert_release(
            inventory,
            acceptance,
            profile=load_channel_profile(PROFILE),
            policy=load_policy(POLICY),
            start_date=date(2026, 8, 21),
            candidate_approval=_approval(inventory.source_snapshot_id, "NotInInventory1"),
        )


def test_existing_publication_and_unresolved_effects_block_future_short_release(tmp_path: Path) -> None:
    collision = tmp_path / "collision.json"
    collision.write_text(
        json.dumps(
            {
                "entries": {
                    "lordchrist-short-AbCdEf12345": {
                        "publication_id": "lordchrist-short-AbCdEf12345",
                        "state": "published",
                        "provider_effect": "verified",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    assert require_existing_lordchrist_state_clear([collision]) == {"lordchrist-short-AbCdEf12345"}

    unresolved = tmp_path / "unresolved.json"
    unresolved.write_text(
        json.dumps(
            {
                "entries": {
                    "old-track": {
                        "publication_id": "old-track",
                        "state": "dispatching",
                        "provider_effect": "may_exist",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="blocks all writers"):
        require_existing_lordchrist_state_clear([unresolved])
    with pytest.raises(ValueError, match="at least one LordChrist durable state ledger"):
        require_existing_lordchrist_state_clear([])


def test_state_root_discovers_all_tracks_and_honors_exact_retirement(tmp_path: Path) -> None:
    root = tmp_path / "lordchrist-state"
    (root / "research-v2").mkdir(parents=True)
    (root / "rich-v1").mkdir(parents=True)
    (root / "one-off-state").mkdir(parents=True)

    (root / "publication-ledger.json").write_text(
        json.dumps(
            {
                "project_key": PROJECT_KEY,
                "channel_username": TELEGRAM_CHANNEL_USERNAME,
                "entries": {
                    "legacy-safe": {
                        "publication_id": "legacy-safe",
                        "state": "published",
                        "provider_effect": "verified",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "research-v2" / "publication-ledger.json").write_text(
        json.dumps(
            {
                "project_key": PROJECT_KEY,
                "channel_username": TELEGRAM_CHANNEL_USERNAME,
                "entries": {
                    "retired-ambiguous": {
                        "publication_id": "retired-ambiguous",
                        "state": "unknown",
                        "provider_effect": "may_exist",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "research-v2" / "retirement.json").write_text(
        json.dumps(
            {
                "schema_name": "video-channel-manager.lordchrist-research-retirement",
                "schema_version": 1,
                "project_key": PROJECT_KEY,
                "channel_username": TELEGRAM_CHANNEL_USERNAME,
                "publication_id": "retired-ambiguous",
                "disposition": "retired_no_replay",
                "provider_retry_forbidden": True,
            }
        ),
        encoding="utf-8",
    )
    (root / "rich-v1" / "live-canary-ledger.json").write_text(
        json.dumps(
            {
                "project_key": PROJECT_KEY,
                "channel_username": TELEGRAM_CHANNEL_USERNAME,
                "entries": {
                    "rich-safe": {
                        "publication_id": "rich-safe",
                        "state": "published",
                        "provider_effect": "verified",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "one-off-state" / "one-off.json").write_text(
        json.dumps(
            {
                "publication_id": "one-off-safe",
                "state": "published",
                "provider_effect": "verified",
                "target": {"chat_username": "lordchrist"},
            }
        ),
        encoding="utf-8",
    )

    assert require_lordchrist_state_root_clear(root) == {
        "legacy-safe",
        "retired-ambiguous",
        "rich-safe",
        "one-off-safe",
    }

    (root / "rich-v1" / "live-canary-ledger.json").unlink()
    with pytest.raises(ValueError, match="durable state root is incomplete"):
        require_lordchrist_state_root_clear(root)


def test_generic_cross_track_guard_can_include_future_shorts_track() -> None:
    safe = EffectSnapshot(publication_id="safe", state="published", provider_effect="verified")
    blocked = EffectSnapshot(publication_id="short-unknown", state="dispatching", provider_effect="may_exist")
    result = require_no_unresolved_provider_effects_across_tracks(
        tracks={"legacy": [safe], "research": [safe], "shorts": [safe]}
    )
    assert result == {"legacy": (), "research": (), "shorts": ()}

    with pytest.raises(ValueError, match=r"shorts=short-unknown"):
        require_no_unresolved_provider_effects_across_tracks(
            tracks={"legacy": [safe], "research": [safe], "shorts": [blocked]}
        )
