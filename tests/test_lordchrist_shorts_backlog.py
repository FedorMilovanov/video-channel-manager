from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID

import pytest

from video_channel_manager.domain.enums import ChannelKind, PlatformName
from video_channel_manager.domain.models import ChannelRecord, RemoteRef, VideoRecord
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.lordchrist_shorts import (
    HISTORICAL_DURATION_BASELINE_PATH,
    KNOWN_DURATION_ONLY_SNAPSHOT_ID,
    PROJECT_KEY,
    YOUTUBE_CHANNEL_ID,
    CandidateApprovalManifest,
    HistoricalDurationBaseline,
    OwnerMediaBinding,
    OwnerMediaBindingManifest,
    build_backlog_status,
    build_inventory,
    load_historical_baseline,
    prepare_owner_media,
    reconcile_historical_baseline,
)

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_BASELINE = ROOT / HISTORICAL_DURATION_BASELINE_PATH


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
        snapshot_id=UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
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
            _video(
                "Ln_G27bCimA",
                title="Baseline short",
                width=1080,
                height=1920,
                duration_ms=72_000,
                creation_time="2026-03-08T00:00:00Z",
                published_at=datetime(2026, 3, 8, tzinfo=UTC),
            ),
        ],
    )


def _baseline() -> HistoricalDurationBaseline:
    return HistoricalDurationBaseline(
        schema_name="video-channel-manager.lordchrist-shorts-historical-duration-baseline",
        schema_version=1,
        project_key=PROJECT_KEY,
        youtube_channel_id=YOUTUBE_CHANNEL_ID,
        youtube_oauth_alias="fedor-milovanov",
        evidence_scope="historical_duration_only_not_current_provider_state",
        provider_effect="impossible",
        provider_writes_authorized=False,
        source_snapshot_id=KNOWN_DURATION_ONLY_SNAPSHOT_ID,
        source_generated_at=datetime(2026, 7, 29, 0, 13, 56, 374225, tzinfo=UTC),
        source_package_filename="youtube-fedormilovanov-catalog-20260729-001427.json",
        source_record_count=1826,
        source_channel_video_count=1783,
        selection_rule="published_on_or_after_2025-12-08_and_duration_le_180s",
        owner_file_details_present=False,
        proven_shorts=False,
        items=(
            {
                "youtube_video_id": "Ln_G27bCimA",
                "published_on": date(2026, 3, 8),
                "duration_seconds": 72,
            },
            {
                "youtube_video_id": "j5Muf6MaqxI",
                "published_on": date(2026, 3, 9),
                "duration_seconds": 38,
            },
        ),
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


def _binding(video_id: str, source: Path) -> OwnerMediaBinding:
    data = source.read_bytes()
    return OwnerMediaBinding(
        youtube_video_id=video_id,
        source_kind="google_takeout",
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


def test_production_historical_baseline_is_duration_only_reconciliation_evidence() -> None:
    baseline, digest = load_historical_baseline(PRODUCTION_BASELINE)
    assert digest.startswith("sha256:")
    assert baseline.source_snapshot_id == KNOWN_DURATION_ONLY_SNAPSHOT_ID
    assert baseline.owner_file_details_present is False
    assert baseline.proven_shorts is False
    assert baseline.provider_writes_authorized is False
    assert baseline.provider_effect == "impossible"
    assert len(baseline.items) == 25
    ids = [item.youtube_video_id for item in baseline.items]
    assert len(ids) == len(set(ids))
    assert ids[0] == "Ln_G27bCimA"
    assert ids[-1] == "B8JV7r0vpDk"
    assert all(1 <= item.duration_seconds <= 180 for item in baseline.items)


def test_reconcile_baseline_classifies_frozen_ids_against_fresh_owner_snapshot() -> None:
    package = _audit()
    artifact = reconcile_historical_baseline(
        package,
        _baseline(),
        source_baseline_sha256="sha256:" + ("a" * 64),
        as_of=datetime(2026, 8, 20, 14, 0, tzinfo=UTC),
    )
    assert artifact.provider_write_performed is False
    assert artifact.provider_writes_authorized is False
    assert artifact.compared_snapshot_id == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert artifact.historical_snapshot_id == KNOWN_DURATION_ONLY_SNAPSHOT_ID
    by_id = {item.youtube_video_id: item for item in artifact.records}
    assert by_id["Ln_G27bCimA"].fresh_status == "present_as_short"
    assert by_id["Ln_G27bCimA"].duration_drift_seconds == 0
    assert by_id["j5Muf6MaqxI"].fresh_status == "absent_from_snapshot"
    assert artifact.counts.historical_item_count == 2
    assert artifact.counts.present_as_short == 1
    assert artifact.counts.absent_from_snapshot == 1
    assert artifact.new_short_video_ids == ("AbCdEf12345",)
    assert artifact.new_candidate_video_ids == ("QwErTy67890",)


def test_reconcile_baseline_refuses_the_frozen_duration_only_snapshot_against_itself() -> None:
    package = _audit().model_copy(update={"snapshot_id": UUID(KNOWN_DURATION_ONLY_SNAPSHOT_ID)})
    with pytest.raises(ValueError, match="against itself"):
        reconcile_historical_baseline(
            package,
            _baseline(),
            source_baseline_sha256="sha256:" + ("a" * 64),
            as_of=datetime(2026, 8, 20, 14, 0, tzinfo=UTC),
        )


def test_backlog_status_records_media_missing_and_unconfirmed_candidates() -> None:
    inventory = build_inventory(_audit())
    status = build_backlog_status(inventory)
    assert status.release_authorized is False
    assert status.provider_write_performed is False
    by_id = {item.youtube_video_id: item for item in status.items}
    assert by_id["AbCdEf12345"].backlog_state == "media_missing"
    assert by_id["AbCdEf12345"].surface_status == "short"
    assert by_id["Ln_G27bCimA"].backlog_state == "media_missing"
    assert by_id["QwErTy67890"].backlog_state == "candidate_unconfirmed"
    assert "LmNoPq13579" not in by_id
    assert status.counts.accepted == 0
    assert status.counts.media_missing == 2
    assert status.counts.candidate_unconfirmed == 1
    assert (
        status.counts.accepted + status.counts.media_missing + status.counts.candidate_unconfirmed
        == status.counts.inventory_item_count
    )


def test_backlog_status_marks_exact_accepted_media_and_keeps_unapproved_candidate(tmp_path: Path) -> None:
    inventory = build_inventory(_audit())
    exact_source = tmp_path / "exact.mp4"
    candidate_source = tmp_path / "candidate.mp4"
    exact_source.write_bytes(b"owner-video-bytes-exact")
    candidate_source.write_bytes(b"owner-video-bytes-candidate")

    def probe(path: Path) -> dict[str, object]:
        return _probe(45.0 if ("candidate" in path.name or "QwErTy67890" in path.name) else 60.0)

    acceptance = prepare_owner_media(
        inventory,
        _bindings(_binding("AbCdEf12345", exact_source), _binding("QwErTy67890", candidate_source)),
        output_dir=tmp_path / "prepared",
        probe_runner=probe,
        ffprobe_version="ffprobe-test",
    )
    status = build_backlog_status(
        inventory,
        bindings=_bindings(_binding("AbCdEf12345", exact_source), _binding("QwErTy67890", candidate_source)),
        acceptance=acceptance,
    )
    by_id = {item.youtube_video_id: item for item in status.items}
    assert by_id["AbCdEf12345"].backlog_state == "accepted"
    assert by_id["AbCdEf12345"].media_accepted is True
    assert by_id["QwErTy67890"].backlog_state == "candidate_unconfirmed"
    assert by_id["QwErTy67890"].media_bound is True
    assert by_id["Ln_G27bCimA"].backlog_state == "media_missing"
    assert status.counts.accepted == 1
    assert status.counts.candidate_unconfirmed == 1
    assert status.counts.media_missing == 1


def test_approved_candidate_without_media_is_media_missing(tmp_path: Path) -> None:
    inventory = build_inventory(_audit())
    status = build_backlog_status(
        inventory,
        candidate_approval=_approval(inventory.source_snapshot_id, "QwErTy67890"),
    )
    by_id = {item.youtube_video_id: item for item in status.items}
    assert by_id["QwErTy67890"].backlog_state == "media_missing"
    assert by_id["QwErTy67890"].candidate_approved is True
    assert status.counts.candidate_unconfirmed == 0
    assert status.counts.media_missing == 3


def test_backlog_status_rejects_bindings_outside_inventory(tmp_path: Path) -> None:
    inventory = build_inventory(_audit())
    source = tmp_path / "other.mp4"
    source.write_bytes(b"other")
    with pytest.raises(ValueError, match="outside the exact Shorts inventory"):
        build_backlog_status(inventory, bindings=_bindings(_binding("NotInInv1", source)))


def test_backlog_status_rejects_acceptance_from_another_snapshot(tmp_path: Path) -> None:
    inventory = build_inventory(_audit())
    exact_source = tmp_path / "exact.mp4"
    exact_source.write_bytes(b"owner-video-bytes-exact")
    acceptance = prepare_owner_media(
        inventory,
        _bindings(_binding("AbCdEf12345", exact_source)),
        output_dir=tmp_path / "prepared",
        probe_runner=lambda _path: _probe(60.0),
        ffprobe_version="ffprobe-test",
    )
    mutated = inventory.model_copy(update={"source_snapshot_id": "different-snapshot"})
    with pytest.raises(ValueError, match="different YouTube inventory snapshot"):
        build_backlog_status(mutated, acceptance=acceptance)


def test_historical_duration_baseline_rejects_naive_timestamp() -> None:
    payload = json.loads(PRODUCTION_BASELINE.read_text(encoding="utf-8"))
    payload["source_generated_at"] = "2026-07-29T00:13:56"
    with pytest.raises(Exception, match="timezone-aware"):
        HistoricalDurationBaseline.model_validate(payload)
