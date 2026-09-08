from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from video_channel_manager.domain.enums import PlatformName
from video_channel_manager.instagram.artifact import (
    InstagramArtifactCompatibilityError,
    InstagramArtifactIdentityError,
    assert_instagram_publish_manifest_identity,
    bind_instagram_reel_artifact,
)
from video_channel_manager.instagram.production import InstagramPublishManifest
from video_channel_manager.local_media.artifact import (
    MediaAcquisitionEvidence,
    MediaArtifactError,
    MediaArtifactEvidence,
    MediaCompatibilityProfile,
    MediaProbeEvidence,
    MediaSourceIdentity,
    calculate_media_manifest_sha256,
)

_SHA256 = "sha256:" + "1" * 64
_PATH = r"C:\media\reel.mp4"


def _artifact(
    *,
    path: str = _PATH,
    probe_overrides: Mapping[str, Any] | None = None,
) -> MediaArtifactEvidence:
    probe_payload: dict[str, Any] = {
        "path": path,
        "size_bytes": 50_000_000,
        "sha256": _SHA256,
        "duration_seconds": 60.0,
        "format_names": ("mov", "mp4", "m4a", "3gp", "3g2", "mj2"),
        "video_stream_count": 1,
        "audio_stream_count": 1,
        "video_codec": "h264",
        "audio_codec": "aac",
        "width": 1080,
        "height": 1920,
        "sample_rate_hz": 48_000,
        "audio_channels": 2,
        "video_frame_rate_fps": 30.0,
        "video_bitrate_bps": 8_000_000,
        "audio_bitrate_bps": 128_000,
    }
    if probe_overrides:
        probe_payload.update(probe_overrides)
    probe = MediaProbeEvidence(**probe_payload)

    first_format = probe.format_names[0] if probe.format_names else "unknown"
    profile = MediaCompatibilityProfile(
        profile_name="instagram-artifact-test-input-v1",
        required_format_names=(first_format,),
        allowed_video_codecs=((probe.video_codec or "unknown"),),
        allowed_audio_codecs=((probe.audio_codec or "unknown"),),
        minimum_sample_rate_hz=1,
        minimum_width=1,
        minimum_height=1,
        minimum_audio_channels=1,
    )
    source = MediaSourceIdentity(
        project_key="legendary-poet",
        platform=PlatformName.YOUTUBE,
        source_channel_id="UC-78ys2S3cQ3lpqgXfo-SvQ",
        source_id="source-video-1",
    )
    acquisition = MediaAcquisitionEvidence(
        method="controlled_master",
        path_authority="controlled_master",
        requested_output_path=path,
        authoritative_final_path=path,
        tool_name="test-fixture",
    )
    provisional = MediaArtifactEvidence(
        source=source,
        acquisition=acquisition,
        profile=profile,
        probe=probe,
        manifest_sha256="sha256:" + "0" * 64,
    )
    return provisional.model_copy(update={"manifest_sha256": calculate_media_manifest_sha256(provisional)})


def _publish_manifest(binding_media_type: str = "video/mp4", **overrides: Any) -> InstagramPublishManifest:
    payload: dict[str, Any] = {
        "publication_key": "instagram-artifact-test-1",
        "account_id": "17841400000000000",
        "video_url": "https://cdn.example.com/reel.mp4",
        "media_sha256": _SHA256,
        "media_size_bytes": 50_000_000,
        "media_content_type": binding_media_type,
        "caption": "",
    }
    payload.update(overrides)
    return InstagramPublishManifest(**payload)


def test_valid_mp4_h264_binding_is_provider_inert_proof() -> None:
    evidence = _artifact()

    binding = bind_instagram_reel_artifact(evidence)

    assert binding.media_manifest_sha256 == evidence.manifest_sha256
    assert binding.media_sha256 == evidence.probe.sha256
    assert binding.media_size_bytes == evidence.probe.size_bytes
    assert binding.container == "mp4"
    assert binding.media_content_type == "video/mp4"
    assert binding.video_codec == "h264"
    assert binding.advisories == ()


def test_valid_mov_hevc_with_ffprobe_alias_string_passes() -> None:
    evidence = _artifact(
        path=r"C:\media\reel.MOV",
        probe_overrides={
            "format_names": ("mov,mp4,m4a,3gp,3g2,mj2",),
            "video_codec": "hevc",
        },
    )

    binding = bind_instagram_reel_artifact(evidence)

    assert binding.container == "mov"
    assert binding.media_content_type == "video/quicktime"
    assert binding.video_codec == "hevc"


@pytest.mark.parametrize(
    ("path", "probe_overrides", "reason"),
    [
        (r"C:\media\reel.mkv", {"format_names": ("matroska",)}, "container_not_mov_or_mp4"),
        (_PATH, {"format_names": ("matroska",)}, "ffprobe_container_not_mov_or_mp4"),
        (_PATH, {"video_codec": "vp9"}, "video_codec_not_h264_or_hevc"),
        (_PATH, {"audio_codec": "opus"}, "audio_codec_not_aac"),
        (_PATH, {"sample_rate_hz": 44_100}, "audio_sample_rate_not_48000_hz"),
        (_PATH, {"video_frame_rate_fps": None}, "video_frame_rate_missing"),
        (_PATH, {"video_frame_rate_fps": 22.999}, "video_frame_rate_out_of_range"),
        (_PATH, {"video_frame_rate_fps": 60.001}, "video_frame_rate_out_of_range"),
        (_PATH, {"width": None}, "video_dimensions_missing"),
        (_PATH, {"width": 1921}, "horizontal_pixels_above_1920"),
        (_PATH, {"video_bitrate_bps": None}, "video_bitrate_missing"),
        (_PATH, {"video_bitrate_bps": 25_000_001}, "video_bitrate_above_25_mbps"),
        (_PATH, {"audio_bitrate_bps": None}, "audio_bitrate_missing"),
        (_PATH, {"duration_seconds": 2.999}, "duration_out_of_range"),
        (_PATH, {"duration_seconds": 900.001}, "duration_out_of_range"),
        (_PATH, {"size_bytes": 1_000_000_001}, "file_size_above_1_gb"),
    ],
)
def test_reel_hard_limits_fail_closed(
    path: str,
    probe_overrides: Mapping[str, Any],
    reason: str,
) -> None:
    evidence = _artifact(path=path, probe_overrides=probe_overrides)

    with pytest.raises(InstagramArtifactCompatibilityError) as caught:
        bind_instagram_reel_artifact(evidence)

    assert reason in caught.value.reasons


@pytest.mark.parametrize(
    "probe_overrides",
    [
        {"video_frame_rate_fps": 23.0},
        {"video_frame_rate_fps": 60.0},
        {"video_bitrate_bps": 25_000_000},
        {"duration_seconds": 3.0},
        {"duration_seconds": 900.0},
        {"size_bytes": 1_000_000_000},
        {"width": 1920, "height": 3413},
    ],
)
def test_reel_inclusive_boundaries_pass(probe_overrides: Mapping[str, Any]) -> None:
    binding = bind_instagram_reel_artifact(_artifact(probe_overrides=probe_overrides))

    assert binding.media_sha256 == _SHA256


def test_recommended_aspect_and_audio_bitrate_are_advisory_only() -> None:
    evidence = _artifact(
        probe_overrides={
            "width": 1920,
            "height": 1080,
            "audio_bitrate_bps": 192_000,
        }
    )

    binding = bind_instagram_reel_artifact(evidence)

    assert binding.advisories == (
        "aspect_ratio_not_exact_9_16",
        "audio_bitrate_not_recommended_128_kbps",
    )


def test_corrupted_canonical_media_digest_is_rejected_before_binding() -> None:
    evidence = _artifact().model_copy(update={"manifest_sha256": "sha256:" + "f" * 64})

    with pytest.raises(MediaArtifactError, match="manifest digest"):
        bind_instagram_reel_artifact(evidence)


def test_publish_manifest_exact_media_identity_passes() -> None:
    binding = bind_instagram_reel_artifact(_artifact())
    manifest = _publish_manifest()

    assert_instagram_publish_manifest_identity(binding, manifest)


@pytest.mark.parametrize(
    ("overrides", "mismatch"),
    [
        ({"media_sha256": "sha256:" + "2" * 64}, "media_sha256"),
        ({"media_size_bytes": 49_999_999}, "media_size_bytes"),
        ({"media_content_type": "video/quicktime"}, "media_content_type"),
    ],
)
def test_publish_manifest_media_identity_mismatch_fails_closed(
    overrides: Mapping[str, Any],
    mismatch: str,
) -> None:
    binding = bind_instagram_reel_artifact(_artifact())
    manifest = _publish_manifest(**dict(overrides))

    with pytest.raises(InstagramArtifactIdentityError) as caught:
        assert_instagram_publish_manifest_identity(binding, manifest)

    assert caught.value.mismatches == (mismatch,)
