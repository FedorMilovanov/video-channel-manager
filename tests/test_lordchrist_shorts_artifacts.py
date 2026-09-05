from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from video_channel_manager.domain.enums import ChannelKind, PlatformName
from video_channel_manager.domain.models import ChannelRecord, RemoteRef, VideoRecord
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.lordchrist_shorts import (
    YOUTUBE_CHANNEL_ID,
    HistoricalDurationBaseline,
    HistoricalDurationBaselineItem,
)
from video_channel_manager.lordchrist_shorts_artifacts import build_wave

AS_OF = datetime(2026, 8, 20, 18, 0, tzinfo=UTC)
EXPECTED_FILES = {
    "snapshot-readiness.json",
    "shorts-inventory.json",
    "baseline-reconciliation.json",
    "backlog-status.json",
    "manifest.json",
}


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _video(
    video_id: str,
    *,
    duration_seconds: int,
    width: int,
    height: int,
    creation_time: str,
    with_file_details: bool = True,
) -> VideoRecord:
    metadata: dict[str, object] = {}
    if with_file_details:
        metadata["fileDetails"] = {
            "durationMs": duration_seconds * 1000,
            "creationTime": creation_time,
            "videoStreams": [
                {
                    "widthPixels": width,
                    "heightPixels": height,
                    "rotation": "none",
                }
            ],
        }
    return VideoRecord(
        ref=RemoteRef(
            platform=PlatformName.YOUTUBE,
            channel_id=YOUTUBE_CHANNEL_ID,
            remote_id=video_id,
        ),
        title=video_id,
        duration_seconds=duration_seconds,
        published_at=datetime(2026, 1, 10, tzinfo=UTC),
        revision=f"sha256:{video_id}",
        metadata=metadata,
    )


def _audit(
    *,
    generated_at: datetime = datetime(2026, 8, 20, 16, 0, tzinfo=UTC),
    complete_file_details: bool = True,
) -> AuditPackage:
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
        generated_at=generated_at,
        videos=[
            _video(
                "AbCdEf12345",
                duration_seconds=60,
                width=1080,
                height=1920,
                creation_time="2026-01-02T00:00:00Z",
                with_file_details=complete_file_details,
            ),
            _video(
                "QwErTy67890",
                duration_seconds=45,
                width=1080,
                height=1920,
                creation_time="2024-01-02T00:00:00Z",
            ),
            _video(
                "LmNoPq13579",
                duration_seconds=50,
                width=1920,
                height=1080,
                creation_time="2026-01-02T00:00:00Z",
            ),
        ],
    )


def _baseline() -> HistoricalDurationBaseline:
    return HistoricalDurationBaseline(
        schema_name="video-channel-manager.lordchrist-shorts-historical-duration-baseline",
        schema_version=1,
        project_key="lord-god-strength",
        youtube_channel_id=YOUTUBE_CHANNEL_ID,
        youtube_oauth_alias="fedor-milovanov",
        evidence_scope="historical_duration_only_not_current_provider_state",
        provider_effect="impossible",
        provider_writes_authorized=False,
        source_snapshot_id="11111111-1111-4111-8111-111111111111",
        source_generated_at=datetime(2026, 7, 29, 12, 0, tzinfo=UTC),
        source_package_filename="historical-audit.json",
        source_record_count=1,
        source_channel_video_count=3,
        selection_rule="published_on_or_after_2025-12-08_and_duration_le_180s",
        owner_file_details_present=False,
        proven_shorts=False,
        items=(
            HistoricalDurationBaselineItem(
                youtube_video_id="QwErTy67890",
                published_on=date(2026, 1, 10),
                duration_seconds=45,
            ),
        ),
    )


def _write_inputs(tmp_path: Path, audit: AuditPackage | None = None) -> tuple[Path, Path]:
    audit_path = tmp_path / "audit.json"
    baseline_path = tmp_path / "baseline.json"
    audit_path.write_text((audit or _audit()).model_dump_json(indent=2) + "\n", encoding="utf-8")
    baseline_path.write_text(_baseline().model_dump_json(indent=2) + "\n", encoding="utf-8")
    return audit_path, baseline_path


def test_build_wave_publishes_complete_snapshot_bound_artifact_set(tmp_path: Path) -> None:
    audit_path, baseline_path = _write_inputs(tmp_path)
    output_dir = tmp_path / "wave"

    summary = build_wave(
        audit_path=audit_path,
        baseline_path=baseline_path,
        output_dir=output_dir,
        as_of=AS_OF,
    )

    assert {item.name for item in output_dir.iterdir()} == EXPECTED_FILES
    assert summary["output_dir"] == str(output_dir)
    assert summary["inventory_item_count"] == 2
    assert summary["accepted"] == 0
    assert summary["media_missing"] == 1
    assert summary["candidate_unconfirmed"] == 1
    assert summary["provider_access_performed"] is False
    assert summary["provider_write_performed"] is False
    assert summary["release_authorized"] is False

    readiness = json.loads((output_dir / "snapshot-readiness.json").read_text(encoding="utf-8"))
    inventory = json.loads((output_dir / "shorts-inventory.json").read_text(encoding="utf-8"))
    reconciliation = json.loads((output_dir / "baseline-reconciliation.json").read_text(encoding="utf-8"))
    backlog = json.loads((output_dir / "backlog-status.json").read_text(encoding="utf-8"))
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))

    snapshot_id = readiness["source_snapshot_id"]
    assert inventory["source_snapshot_id"] == snapshot_id
    assert reconciliation["compared_snapshot_id"] == snapshot_id
    assert backlog["inventory_snapshot_id"] == snapshot_id
    assert manifest["source_snapshot_id"] == snapshot_id
    assert manifest["sources"]["audit"]["sha256"] == _digest(audit_path.read_bytes())
    assert manifest["sources"]["baseline"]["sha256"] == _digest(baseline_path.read_bytes())

    for filename in EXPECTED_FILES - {"manifest.json"}:
        metadata = manifest["artifacts"][filename]
        data = (output_dir / filename).read_bytes()
        assert metadata["sha256"] == _digest(data)
        assert metadata["byte_size"] == len(data)

    assert not list(tmp_path.glob(".wave.staging-*"))


def test_build_wave_stale_snapshot_fails_without_output(tmp_path: Path) -> None:
    audit = _audit(generated_at=AS_OF - timedelta(hours=49))
    audit_path, baseline_path = _write_inputs(tmp_path, audit)
    output_dir = tmp_path / "wave"

    with pytest.raises(ValueError, match="fresh_enough=False"):
        build_wave(
            audit_path=audit_path,
            baseline_path=baseline_path,
            output_dir=output_dir,
            as_of=AS_OF,
        )

    assert not output_dir.exists()
    assert not list(tmp_path.glob(".wave.staging-*"))


def test_build_wave_incomplete_owner_file_details_fails_without_output(tmp_path: Path) -> None:
    audit_path, baseline_path = _write_inputs(tmp_path, _audit(complete_file_details=False))
    output_dir = tmp_path / "wave"

    with pytest.raises(ValueError, match="owner_file_details_count=2/3"):
        build_wave(
            audit_path=audit_path,
            baseline_path=baseline_path,
            output_dir=output_dir,
            as_of=AS_OF,
        )

    assert not output_dir.exists()
    assert not list(tmp_path.glob(".wave.staging-*"))


def test_build_wave_invalid_baseline_fails_without_output(tmp_path: Path) -> None:
    audit_path, baseline_path = _write_inputs(tmp_path)
    baseline_path.write_text("{}\n", encoding="utf-8")
    output_dir = tmp_path / "wave"

    with pytest.raises(ValueError, match="invalid HistoricalDurationBaseline"):
        build_wave(
            audit_path=audit_path,
            baseline_path=baseline_path,
            output_dir=output_dir,
            as_of=AS_OF,
        )

    assert not output_dir.exists()
    assert not list(tmp_path.glob(".wave.staging-*"))


def test_build_wave_refuses_existing_destination_without_touching_it(tmp_path: Path) -> None:
    audit_path, baseline_path = _write_inputs(tmp_path)
    output_dir = tmp_path / "wave"
    output_dir.mkdir()
    sentinel = output_dir / "keep.txt"
    sentinel.write_text("existing evidence\n", encoding="utf-8")

    with pytest.raises(ValueError, match="already exists"):
        build_wave(
            audit_path=audit_path,
            baseline_path=baseline_path,
            output_dir=output_dir,
            as_of=AS_OF,
        )

    assert sentinel.read_text(encoding="utf-8") == "existing evidence\n"
    assert {item.name for item in output_dir.iterdir()} == {"keep.txt"}
