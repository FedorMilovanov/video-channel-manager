from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from video_channel_manager.domain.enums import PlatformName
from video_channel_manager.local_media.artifact import (
    MediaAcquisitionEvidence,
    MediaArtifactError,
    MediaArtifactEvidence,
    MediaCompatibilityProfile,
    MediaProbeEvidence,
    MediaSourceIdentity,
    calculate_media_manifest_sha256,
    validate_cached_media_artifact,
    validate_media_artifact_evidence,
)
from video_channel_manager.local_media.quality import MediaQualityReport, sha256_file


def _evidence(path: Path, *, telemetry: bool) -> MediaArtifactEvidence:
    digest = sha256_file(path)
    probe = MediaProbeEvidence(
        path=str(path.resolve()),
        size_bytes=path.stat().st_size,
        sha256=digest,
        duration_seconds=60.0,
        format_names=("mov", "mp4"),
        video_stream_count=1,
        audio_stream_count=1,
        video_codec="h264",
        audio_codec="aac",
        width=1080,
        height=1920,
        sample_rate_hz=48_000,
        audio_channels=2,
        video_frame_rate_fps=30.0 if telemetry else None,
        video_bitrate_bps=8_000_000 if telemetry else None,
        audio_bitrate_bps=128_000 if telemetry else None,
    )
    source = MediaSourceIdentity(
        project_key="legendary-poet",
        platform=PlatformName.YOUTUBE,
        source_channel_id="UC-78ys2S3cQ3lpqgXfo-SvQ",
        source_id="historical-media-1",
    )
    acquisition = MediaAcquisitionEvidence(
        method="controlled_master",
        path_authority="controlled_master",
        requested_output_path=str(path.resolve()),
        authoritative_final_path=str(path.resolve()),
        tool_name="test-fixture",
    )
    profile = MediaCompatibilityProfile()
    provisional = MediaArtifactEvidence(
        source=source,
        acquisition=acquisition,
        profile=profile,
        probe=probe,
        manifest_sha256="sha256:" + "0" * 64,
    )
    return provisional.model_copy(update={"manifest_sha256": calculate_media_manifest_sha256(provisional)})


def _fresh_report(path: Path, *, frame_rate: float = 30.0) -> MediaQualityReport:
    return MediaQualityReport(
        path=str(path.resolve()),
        size_bytes=path.stat().st_size,
        sha256=sha256_file(path),
        duration_seconds=60.0,
        format_names=("mov", "mp4"),
        video_stream_count=1,
        audio_stream_count=1,
        video_codec="h264",
        audio_codec="aac",
        width=1080,
        height=1920,
        sample_rate_hz=48_000,
        audio_channels=2,
        video_frame_rate_fps=frame_rate,
        video_bitrate_bps=8_000_000,
        audio_bitrate_bps=128_000,
    )


def test_historical_v1_payload_without_telemetry_keeps_its_digest(tmp_path: Path) -> None:
    media = tmp_path / "historical.mp4"
    media.write_bytes(b"historical-media-bytes")
    evidence = _evidence(media, telemetry=False)
    historical_payload: dict[str, Any] = evidence.model_dump(mode="json")
    raw_probe = historical_payload["probe"]
    assert isinstance(raw_probe, dict)
    raw_probe.pop("video_frame_rate_fps")
    raw_probe.pop("video_bitrate_bps")
    raw_probe.pop("audio_bitrate_bps")

    parsed = MediaArtifactEvidence.model_validate(historical_payload)

    assert parsed.manifest_sha256 == evidence.manifest_sha256
    validate_media_artifact_evidence(parsed)


def test_new_telemetry_is_covered_by_manifest_digest(tmp_path: Path) -> None:
    media = tmp_path / "new.mp4"
    media.write_bytes(b"new-media-bytes")
    evidence = _evidence(media, telemetry=True)
    changed_probe = evidence.probe.model_copy(update={"video_frame_rate_fps": 31.0})
    changed = evidence.model_copy(update={"probe": changed_probe})

    with pytest.raises(MediaArtifactError, match="manifest digest"):
        validate_media_artifact_evidence(changed)


def test_historical_cached_manifest_accepts_fresh_optional_telemetry(tmp_path: Path) -> None:
    media = tmp_path / "cached-old.mp4"
    media.write_bytes(b"cached-old-media")
    evidence = _evidence(media, telemetry=False)

    parsed = validate_cached_media_artifact(
        evidence,
        expected_project_key="legendary-poet",
        expected_source_platform=PlatformName.YOUTUBE,
        expected_source_channel_id="UC-78ys2S3cQ3lpqgXfo-SvQ",
        expected_source_id="historical-media-1",
        expected_source_duration_seconds=None,
        expected_path=media,
        probe=lambda path: _fresh_report(path),
    )

    assert parsed.manifest_sha256 == evidence.manifest_sha256


def test_new_cached_manifest_requires_its_telemetry_to_match(tmp_path: Path) -> None:
    media = tmp_path / "cached-new.mp4"
    media.write_bytes(b"cached-new-media")
    evidence = _evidence(media, telemetry=True)

    with pytest.raises(MediaArtifactError, match="fresh ffprobe evidence"):
        validate_cached_media_artifact(
            evidence,
            expected_project_key="legendary-poet",
            expected_source_platform=PlatformName.YOUTUBE,
            expected_source_channel_id="UC-78ys2S3cQ3lpqgXfo-SvQ",
            expected_source_id="historical-media-1",
            expected_source_duration_seconds=None,
            expected_path=media,
            probe=lambda path: _fresh_report(path, frame_rate=31.0),
        )
