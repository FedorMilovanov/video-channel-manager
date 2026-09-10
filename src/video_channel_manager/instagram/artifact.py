from __future__ import annotations

from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from video_channel_manager.instagram.production import InstagramPublishManifest
from video_channel_manager.local_media.artifact import (
    MediaArtifactEvidence,
    MediaProbeEvidence,
    validate_media_artifact_evidence,
)

InstagramContainer = Literal["mp4", "mov"]
InstagramMediaContentType = Literal["video/mp4", "video/quicktime"]
InstagramVideoCodec = Literal["h264", "hevc"]

_MAX_FILE_SIZE_BYTES = 1_000_000_000
_MAX_VIDEO_BITRATE_BPS = 25_000_000
_MIN_DURATION_SECONDS = 3.0
_MAX_DURATION_SECONDS = 15.0 * 60.0
_MIN_FRAME_RATE_FPS = 23.0
_MAX_FRAME_RATE_FPS = 60.0
_REQUIRED_AUDIO_SAMPLE_RATE_HZ = 48_000
_RECOMMENDED_AUDIO_BITRATE_BPS = 128_000
_MAX_HORIZONTAL_PIXELS = 1_920
_ALLOWED_VIDEO_CODECS = frozenset({"h264", "hevc"})
_ALLOWED_AUDIO_CODECS = frozenset({"aac"})
_ALLOWED_CONTAINER_SUFFIXES: dict[str, InstagramContainer] = {".mp4": "mp4", ".mov": "mov"}
_CONTAINER_CONTENT_TYPES: dict[InstagramContainer, InstagramMediaContentType] = {
    "mp4": "video/mp4",
    "mov": "video/quicktime",
}
_FFPROBE_CONTAINER_ALIASES = frozenset({"mp4", "mov"})


class InstagramArtifactCompatibilityError(ValueError):
    """Canonical media evidence is insufficient or incompatible with Instagram Reels."""

    def __init__(self, reasons: tuple[str, ...]) -> None:
        self.reasons = reasons
        super().__init__(f"Instagram Reel artifact is incompatible: {', '.join(reasons)}")


class InstagramArtifactIdentityError(ValueError):
    """A provider manifest does not identify the artifact that passed local compatibility checks."""

    def __init__(self, mismatches: tuple[str, ...]) -> None:
        self.mismatches = mismatches
        super().__init__(f"Instagram publish manifest media identity mismatch: {', '.join(mismatches)}")


class InstagramReelArtifactBinding(BaseModel):
    """Provider-inert proof that one canonical media artifact satisfies the Reel contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-manager.instagram-reel-artifact-binding"] = (
        "video-manager.instagram-reel-artifact-binding"
    )
    schema_version: Literal["1.0"] = "1.0"
    ruleset_version: Literal["meta-instagram-reels-2026-09-v1"] = "meta-instagram-reels-2026-09-v1"
    media_manifest_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    media_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    media_size_bytes: int = Field(gt=0)
    media_content_type: InstagramMediaContentType
    container: InstagramContainer
    duration_seconds: float = Field(ge=_MIN_DURATION_SECONDS, le=_MAX_DURATION_SECONDS)
    video_codec: InstagramVideoCodec
    video_frame_rate_fps: float = Field(ge=_MIN_FRAME_RATE_FPS, le=_MAX_FRAME_RATE_FPS)
    video_bitrate_bps: int = Field(gt=0, le=_MAX_VIDEO_BITRATE_BPS)
    width: int = Field(gt=0, le=_MAX_HORIZONTAL_PIXELS)
    height: int = Field(gt=0)
    audio_codec: Literal["aac"]
    audio_sample_rate_hz: Literal[48000]
    audio_bitrate_bps: int = Field(gt=0)
    advisories: tuple[str, ...] = ()


def _normalized_format_tokens(format_names: tuple[str, ...]) -> frozenset[str]:
    return frozenset(
        token.strip().lower() for format_name in format_names for token in format_name.split(",") if token.strip()
    )


def bind_instagram_reel_probe(
    probe: MediaProbeEvidence,
    *,
    media_manifest_sha256: str,
) -> InstagramReelArtifactBinding:
    """Validate one canonical ffprobe observation against the Reel media contract."""

    reasons: list[str] = []

    suffix = Path(probe.path).suffix.lower()
    container = _ALLOWED_CONTAINER_SUFFIXES.get(suffix)
    if container is None:
        reasons.append("container_not_mov_or_mp4")

    format_tokens = _normalized_format_tokens(probe.format_names)
    if not format_tokens.intersection(_FFPROBE_CONTAINER_ALIASES):
        reasons.append("ffprobe_container_not_mov_or_mp4")

    video_codec = (probe.video_codec or "").strip().lower()
    if video_codec not in _ALLOWED_VIDEO_CODECS:
        reasons.append("video_codec_not_h264_or_hevc")

    audio_codec = (probe.audio_codec or "").strip().lower()
    if audio_codec not in _ALLOWED_AUDIO_CODECS:
        reasons.append("audio_codec_not_aac")

    if probe.sample_rate_hz != _REQUIRED_AUDIO_SAMPLE_RATE_HZ:
        reasons.append("audio_sample_rate_not_48000_hz")

    frame_rate = probe.video_frame_rate_fps
    if frame_rate is None:
        reasons.append("video_frame_rate_missing")
    elif not _MIN_FRAME_RATE_FPS <= frame_rate <= _MAX_FRAME_RATE_FPS:
        reasons.append("video_frame_rate_out_of_range")

    if probe.width is None or probe.height is None:
        reasons.append("video_dimensions_missing")
    elif probe.width > _MAX_HORIZONTAL_PIXELS:
        reasons.append("horizontal_pixels_above_1920")

    video_bitrate = probe.video_bitrate_bps
    if video_bitrate is None:
        reasons.append("video_bitrate_missing")
    elif video_bitrate > _MAX_VIDEO_BITRATE_BPS:
        reasons.append("video_bitrate_above_25_mbps")

    audio_bitrate = probe.audio_bitrate_bps
    if audio_bitrate is None:
        reasons.append("audio_bitrate_missing")

    if not _MIN_DURATION_SECONDS <= probe.duration_seconds <= _MAX_DURATION_SECONDS:
        reasons.append("duration_out_of_range")

    if probe.size_bytes > _MAX_FILE_SIZE_BYTES:
        reasons.append("file_size_above_1_gb")

    if reasons:
        raise InstagramArtifactCompatibilityError(tuple(reasons))

    assert container is not None
    assert video_codec in _ALLOWED_VIDEO_CODECS
    assert audio_codec == "aac"
    assert frame_rate is not None
    assert probe.width is not None
    assert probe.height is not None
    assert video_bitrate is not None
    assert audio_bitrate is not None

    validated_video_codec = cast(InstagramVideoCodec, video_codec)
    advisories: list[str] = []
    if probe.width * 16 != probe.height * 9:
        advisories.append("aspect_ratio_not_exact_9_16")
    if audio_bitrate != _RECOMMENDED_AUDIO_BITRATE_BPS:
        advisories.append("audio_bitrate_not_recommended_128_kbps")

    return InstagramReelArtifactBinding(
        media_manifest_sha256=media_manifest_sha256,
        media_sha256=probe.sha256,
        media_size_bytes=probe.size_bytes,
        media_content_type=_CONTAINER_CONTENT_TYPES[container],
        container=container,
        duration_seconds=probe.duration_seconds,
        video_codec=validated_video_codec,
        video_frame_rate_fps=frame_rate,
        video_bitrate_bps=video_bitrate,
        width=probe.width,
        height=probe.height,
        audio_codec="aac",
        audio_sample_rate_hz=48_000,
        audio_bitrate_bps=audio_bitrate,
        advisories=tuple(advisories),
    )


def bind_instagram_reel_artifact(evidence: MediaArtifactEvidence) -> InstagramReelArtifactBinding:
    """Validate canonical evidence against the current server-published Reel media contract.

    This function is deliberately provider-inert. It performs no hosting, HTTP request,
    account lookup, container creation, or publication. The existing production publisher
    remains the sole owner of provider I/O and independently verifies hosted bytes.
    """

    validate_media_artifact_evidence(evidence)
    return bind_instagram_reel_probe(
        evidence.probe,
        media_manifest_sha256=evidence.manifest_sha256,
    )


def assert_instagram_publish_manifest_identity(
    binding: InstagramReelArtifactBinding,
    manifest: InstagramPublishManifest,
) -> None:
    """Fail closed unless provider-bound media identity equals the validated local artifact."""

    mismatches: list[str] = []
    if manifest.media_sha256 != binding.media_sha256:
        mismatches.append("media_sha256")
    if manifest.media_size_bytes != binding.media_size_bytes:
        mismatches.append("media_size_bytes")
    if manifest.media_content_type != binding.media_content_type:
        mismatches.append("media_content_type")
    if mismatches:
        raise InstagramArtifactIdentityError(tuple(mismatches))
