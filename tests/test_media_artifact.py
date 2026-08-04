from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from video_channel_manager.domain.enums import PlatformName
from video_channel_manager.local_media.artifact import (
    MediaAcquisitionEvidence,
    MediaArtifactError,
    MediaCompatibilityProfile,
    MediaSourceIdentity,
    acquisition_from_structured_result,
    build_media_artifact_evidence,
    controlled_master_acquisition,
    load_media_artifact_manifest,
    validate_cached_media_artifact,
    validate_media_artifact_evidence,
    write_media_artifact_manifest,
)
from video_channel_manager.local_media.quality import MediaQualityReport, sha256_file


def _source(*, duration: float = 42.5, source_url: str | None = "https://youtu.be/yt-1") -> MediaSourceIdentity:
    return MediaSourceIdentity(
        project_key="legendary-poet",
        platform=PlatformName.YOUTUBE,
        source_channel_id="UC-78ys2S3cQ3lpqgXfo-SvQ",
        source_id="yt-1",
        source_url=source_url,
        source_revision="etag-1",
        expected_duration_seconds=duration,
    )


def _report(
    path: Path,
    *,
    duration: float = 42.5,
    formats: tuple[str, ...] = ("mov", "mp4", "m4a"),
    video_codec: str = "h264",
    audio_codec: str = "aac",
    width: int = 1920,
    height: int = 1080,
) -> MediaQualityReport:
    resolved = path.resolve()
    return MediaQualityReport(
        path=str(resolved),
        size_bytes=resolved.stat().st_size,
        sha256=sha256_file(resolved),
        duration_seconds=duration,
        format_names=formats,
        video_stream_count=1,
        audio_stream_count=1,
        video_codec=video_codec,
        audio_codec=audio_codec,
        width=width,
        height=height,
        sample_rate_hz=48000,
        audio_channels=2,
    )


def _evidence(path: Path):
    return build_media_artifact_evidence(
        source=_source(),
        acquisition=controlled_master_acquisition(path),
        profile=MediaCompatibilityProfile(),
        report=_report(path),
    )


def _validate(path: Path, evidence, *, fresh_report: MediaQualityReport | None = None):
    return validate_cached_media_artifact(
        evidence,
        expected_project_key="legendary-poet",
        expected_source_platform=PlatformName.YOUTUBE,
        expected_source_channel_id="UC-78ys2S3cQ3lpqgXfo-SvQ",
        expected_source_id="yt-1",
        expected_source_duration_seconds=42.5,
        expected_path=path,
        probe=lambda _: fresh_report or _report(path),
    )


def test_authoritative_manifest_validates_exact_file_source_and_probe(tmp_path: Path) -> None:
    media = tmp_path / "video.mp4"
    media.write_bytes(b"authoritative-video")
    evidence = _evidence(media)

    validated = _validate(media, evidence.model_dump(mode="json"))

    assert validated.manifest_sha256.startswith("sha256:")
    assert validated.source.source_id == "yt-1"
    assert validated.acquisition.path_authority == "controlled_master"
    assert validated.probe.video_codec == "h264"
    assert validated.probe.audio_codec == "aac"


def test_manifest_digest_detects_tampering(tmp_path: Path) -> None:
    media = tmp_path / "video.mp4"
    media.write_bytes(b"authoritative-video")
    evidence = _evidence(media)
    tampered = evidence.model_copy(update={"manifest_sha256": "sha256:" + "0" * 64})

    with pytest.raises(MediaArtifactError, match="digest"):
        validate_media_artifact_evidence(tampered)


def test_cache_reuse_rejects_changed_file_bytes(tmp_path: Path) -> None:
    media = tmp_path / "video.mp4"
    media.write_bytes(b"authoritative-video")
    evidence = _evidence(media)
    media.write_bytes(b"changed-video-bytes")

    with pytest.raises(MediaArtifactError, match="size|SHA-256"):
        _validate(media, evidence)


def test_cache_reuse_rejects_renamed_or_substituted_path(tmp_path: Path) -> None:
    media = tmp_path / "video.mp4"
    other = tmp_path / "other.mp4"
    media.write_bytes(b"same-bytes")
    other.write_bytes(b"same-bytes")
    evidence = _evidence(media)

    with pytest.raises(MediaArtifactError, match="authoritative final path"):
        _validate(other, evidence, fresh_report=_report(other))


def test_cache_reuse_rejects_stale_ffprobe_evidence(tmp_path: Path) -> None:
    media = tmp_path / "video.mp4"
    media.write_bytes(b"authoritative-video")
    evidence = _evidence(media)
    stale = _report(media, width=1280, height=720)

    with pytest.raises(MediaArtifactError, match="fresh ffprobe evidence"):
        _validate(media, evidence, fresh_report=stale)


def test_mp4_container_does_not_prove_h264_aac_compatibility(tmp_path: Path) -> None:
    media = tmp_path / "video.mp4"
    media.write_bytes(b"vp9-opus-in-mp4")

    with pytest.raises(MediaArtifactError, match="video_codec_not_allowed|audio_codec_not_allowed"):
        build_media_artifact_evidence(
            source=_source(),
            acquisition=controlled_master_acquisition(media),
            profile=MediaCompatibilityProfile(),
            report=_report(media, video_codec="vp9", audio_codec="opus"),
        )


def test_remux_evidence_still_requires_compatible_probe(tmp_path: Path) -> None:
    media = tmp_path / "remuxed.mp4"
    media.write_bytes(b"remuxed-but-not-transcoded")
    acquisition = MediaAcquisitionEvidence(
        method="remux",
        path_authority="structured_result",
        requested_output_path=str((tmp_path / "requested.mp4").resolve()),
        authoritative_final_path=str(media.resolve()),
        tool_name="ffmpeg",
        tool_version="8.0",
        structured_result_sha256="sha256:" + "1" * 64,
        result_path_field="output.filepath",
        input_artifact_sha256="sha256:" + "2" * 64,
    )

    with pytest.raises(MediaArtifactError, match="video_codec_not_allowed|audio_codec_not_allowed"):
        build_media_artifact_evidence(
            source=_source(),
            acquisition=acquisition,
            profile=MediaCompatibilityProfile(),
            report=_report(media, video_codec="hevc", audio_codec="mp3"),
        )


def test_structured_result_uses_only_explicit_field_path(tmp_path: Path) -> None:
    media = tmp_path / "downloaded.webm"
    distractor = tmp_path / "downloaded.mp4"
    media.write_bytes(b"exact-structured-result")
    distractor.write_bytes(b"tempting-glob-result")
    result = {
        "requested_downloads": [{"filepath": str(media)}],
        "_filename": str(distractor),
    }

    resolved = acquisition_from_structured_result(
        result,
        method="yt_dlp",
        result_path=("requested_downloads", 0, "filepath"),
        requested_output_path=tmp_path / "%(id)s.%(ext)s",
        tool_name="yt-dlp",
        tool_version="2026.08.01",
    )

    assert Path(resolved.final_path) == media.resolve()
    assert resolved.acquisition.result_path_field == "requested_downloads[0].filepath"
    assert resolved.acquisition.structured_result_sha256 is not None

    with pytest.raises(MediaArtifactError, match="missing exact field"):
        acquisition_from_structured_result(
            result,
            method="yt_dlp",
            result_path=("requested_downloads", 0, "missing"),
            requested_output_path=tmp_path / "%(id)s.%(ext)s",
            tool_name="yt-dlp",
        )


def test_glob_paths_are_invalid_authority(tmp_path: Path) -> None:
    media = tmp_path / "video.mp4"
    media.write_bytes(b"video")

    with pytest.raises(ValidationError, match="glob metacharacters"):
        MediaAcquisitionEvidence(
            method="controlled_master",
            path_authority="controlled_master",
            requested_output_path=str(tmp_path / "*.mp4"),
            authoritative_final_path=str(media.resolve()),
            tool_name="legacy-glob",
        )


def test_yt_dlp_manifest_requires_source_url(tmp_path: Path) -> None:
    media = tmp_path / "video.mp4"
    media.write_bytes(b"video")
    acquisition = MediaAcquisitionEvidence(
        method="yt_dlp",
        path_authority="structured_result",
        requested_output_path=str((tmp_path / "requested.mp4").resolve()),
        authoritative_final_path=str(media.resolve()),
        tool_name="yt-dlp",
        structured_result_sha256="sha256:" + "3" * 64,
        result_path_field="requested_downloads[0].filepath",
    )

    with pytest.raises(ValidationError, match="requires source_url"):
        build_media_artifact_evidence(
            source=_source(source_url=None),
            acquisition=acquisition,
            profile=MediaCompatibilityProfile(),
            report=_report(media),
        )


def test_cache_reuse_rejects_wrong_project_or_source(tmp_path: Path) -> None:
    media = tmp_path / "video.mp4"
    media.write_bytes(b"video")
    evidence = _evidence(media)

    with pytest.raises(MediaArtifactError, match="source identity mismatch"):
        validate_cached_media_artifact(
            evidence,
            expected_project_key="lord-god-strength",
            expected_source_platform=PlatformName.YOUTUBE,
            expected_source_channel_id="UCeSJsC6go2c9pdJCuUI1BYA",
            expected_source_id="yt-1",
            expected_source_duration_seconds=42.5,
            expected_path=media,
            probe=lambda _: _report(media),
        )


def test_manifest_round_trip_preserves_digest(tmp_path: Path) -> None:
    media = tmp_path / "video.mp4"
    manifest = tmp_path / "video.media.json"
    media.write_bytes(b"video")
    evidence = _evidence(media)

    write_media_artifact_manifest(evidence, manifest)
    loaded = load_media_artifact_manifest(manifest)

    assert loaded == evidence
    assert loaded.manifest_sha256 == evidence.manifest_sha256
