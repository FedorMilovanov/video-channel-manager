from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from video_channel_manager.domain.enums import PlatformName
from video_channel_manager.editorial._project_profiles import PROJECT_KEYS, resolve_project_key
from video_channel_manager.local_media.quality import MediaQualityReport, probe_media, sha256_file

AcquisitionMethod = Literal["controlled_master", "yt_dlp", "local_copy", "transcode", "remux"]
PathAuthority = Literal["controlled_master", "structured_result"]
ResultPathSegment = str | int
MediaProbe = Callable[[Path], MediaQualityReport]

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")
_GLOB_META = frozenset("*?[]")


class MediaArtifactError(RuntimeError):
    """Authoritative media evidence is absent, inconsistent, or incompatible."""


class FrozenEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MediaSourceIdentity(FrozenEvidence):
    project_key: str = Field(min_length=1)
    platform: PlatformName
    source_channel_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    source_url: str | None = None
    source_revision: str | None = None
    expected_duration_seconds: float | None = Field(default=None, gt=0)

    @field_validator("project_key", "source_channel_id", "source_id")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("identity values cannot be blank")
        return normalized

    @field_validator("source_revision")
    @classmethod
    def strip_optional_revision(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        parsed = urlsplit(normalized)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("source_url must be an absolute HTTPS URL")
        return normalized

    @model_validator(mode="after")
    def validate_project_identity(self) -> MediaSourceIdentity:
        if self.project_key not in PROJECT_KEYS:
            raise ValueError("project_key must identify a registered project")
        resolved = resolve_project_key(
            {
                "project_key": self.project_key,
                "channel_id": self.source_channel_id,
            }
        )
        if resolved != self.project_key:
            raise ValueError("source channel does not belong to project_key")
        return self


class MediaAcquisitionEvidence(FrozenEvidence):
    method: AcquisitionMethod
    path_authority: PathAuthority
    requested_output_path: str = Field(min_length=1)
    authoritative_final_path: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    tool_version: str | None = None
    structured_result_sha256: str | None = None
    result_path_field: str | None = None
    input_artifact_sha256: str | None = None

    @field_validator("requested_output_path", "authoritative_final_path", "tool_name")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("acquisition values cannot be blank")
        return normalized

    @field_validator("tool_version", "result_path_field")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("structured_result_sha256", "input_artifact_sha256")
    @classmethod
    def validate_optional_sha256(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not _SHA256_RE.fullmatch(normalized):
            raise ValueError("digest must use sha256:<64 lowercase hex>")
        return normalized

    @model_validator(mode="after")
    def validate_authority_contract(self) -> MediaAcquisitionEvidence:
        for value in (self.requested_output_path, self.authoritative_final_path):
            if any(character in value for character in _GLOB_META):
                raise ValueError("authoritative media paths cannot contain glob metacharacters")
            if not _looks_absolute_path(value):
                raise ValueError("authoritative media paths must be absolute")
        if self.path_authority == "structured_result":
            if self.structured_result_sha256 is None or self.result_path_field is None:
                raise ValueError("structured_result authority requires result digest and exact field path")
        elif self.structured_result_sha256 is not None or self.result_path_field is not None:
            raise ValueError("controlled_master authority cannot claim a structured result")
        if self.method == "yt_dlp" and self.path_authority != "structured_result":
            raise ValueError("yt_dlp final path must come from a structured result")
        if self.method in {"transcode", "remux", "local_copy"} and self.input_artifact_sha256 is None:
            raise ValueError(f"{self.method} acquisition requires input_artifact_sha256")
        return self


class MediaCompatibilityProfile(FrozenEvidence):
    profile_name: str = Field(default="vk-h264-aac-v1", min_length=1)
    required_format_names: tuple[str, ...] = ("mp4",)
    allowed_video_codecs: tuple[str, ...] = ("h264",)
    allowed_audio_codecs: tuple[str, ...] = ("aac",)
    minimum_video_streams: int = Field(default=1, ge=1)
    maximum_video_streams: int = Field(default=1, ge=1)
    minimum_audio_streams: int = Field(default=1, ge=1)
    maximum_audio_streams: int = Field(default=1, ge=1)
    minimum_width: int = Field(default=1, ge=1)
    minimum_height: int = Field(default=1, ge=1)
    minimum_sample_rate_hz: int = Field(default=32000, ge=1)
    minimum_audio_channels: int = Field(default=1, ge=1)
    duration_tolerance_seconds: float = Field(default=3.0, ge=0)

    @field_validator("required_format_names", "allowed_video_codecs", "allowed_audio_codecs")
    @classmethod
    def normalize_allowed_values(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(sorted({value.strip().lower() for value in values if value.strip()}))
        if not normalized:
            raise ValueError("compatibility allowlists cannot be empty")
        return normalized

    @model_validator(mode="after")
    def validate_stream_ranges(self) -> MediaCompatibilityProfile:
        if self.maximum_video_streams < self.minimum_video_streams:
            raise ValueError("maximum_video_streams cannot be below minimum_video_streams")
        if self.maximum_audio_streams < self.minimum_audio_streams:
            raise ValueError("maximum_audio_streams cannot be below minimum_audio_streams")
        return self


class MediaProbeEvidence(FrozenEvidence):
    probe_ruleset: str = "ffprobe-wave-8d-v1"
    path: str
    size_bytes: int = Field(gt=0)
    sha256: str
    duration_seconds: float = Field(gt=0)
    format_names: tuple[str, ...]
    video_stream_count: int = Field(ge=0)
    audio_stream_count: int = Field(ge=0)
    video_codec: str | None = None
    audio_codec: str | None = None
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    sample_rate_hz: int | None = Field(default=None, gt=0)
    audio_channels: int | None = Field(default=None, gt=0)

    @field_validator("path")
    @classmethod
    def validate_probe_path(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or not _looks_absolute_path(normalized):
            raise ValueError("probe path must be absolute")
        if any(character in normalized for character in _GLOB_META):
            raise ValueError("probe path cannot contain glob metacharacters")
        return normalized

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _SHA256_RE.fullmatch(normalized):
            raise ValueError("sha256 must use sha256:<64 lowercase hex>")
        return normalized

    @field_validator("format_names")
    @classmethod
    def normalize_formats(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted({value.strip().lower() for value in values if value.strip()}))

    @classmethod
    def from_report(cls, report: MediaQualityReport) -> MediaProbeEvidence:
        return cls(**report.to_dict())

    def to_report(self) -> MediaQualityReport:
        payload = self.model_dump(exclude={"probe_ruleset"})
        return MediaQualityReport(**payload)


class MediaProfileAssessment(FrozenEvidence):
    compatible: bool
    reasons: tuple[str, ...] = ()


class MediaArtifactEvidence(FrozenEvidence):
    schema_name: str = "video-manager.media-artifact-evidence"
    schema_version: str = "1.0"
    ruleset_version: str = "wave-8d-v1"
    source: MediaSourceIdentity
    acquisition: MediaAcquisitionEvidence
    profile: MediaCompatibilityProfile
    probe: MediaProbeEvidence
    manifest_sha256: str

    @field_validator("manifest_sha256")
    @classmethod
    def validate_manifest_sha256(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _SHA256_RE.fullmatch(normalized):
            raise ValueError("manifest_sha256 must use sha256:<64 lowercase hex>")
        return normalized

    @model_validator(mode="after")
    def validate_cross_field_contract(self) -> MediaArtifactEvidence:
        final_path = _canonical_path_text(self.acquisition.authoritative_final_path)
        probe_path = _canonical_path_text(self.probe.path)
        if final_path != probe_path:
            raise ValueError("probe path must equal authoritative_final_path")
        if self.acquisition.method == "yt_dlp" and self.source.source_url is None:
            raise ValueError("yt_dlp evidence requires source_url")
        return self


class StructuredAcquisitionResult(FrozenEvidence):
    acquisition: MediaAcquisitionEvidence
    final_path: str


def _looks_absolute_path(value: str) -> bool:
    return os.path.isabs(value) or bool(_WINDOWS_ABSOLUTE_RE.match(value)) or value.startswith("\\\\")


def _canonical_path_text(value: str | Path) -> str:
    text = str(value)
    if _WINDOWS_ABSOLUTE_RE.match(text) or text.startswith("\\\\"):
        return os.path.normcase(os.path.normpath(text))
    return str(Path(text).expanduser().resolve())


def _canonical_sha256(payload: object) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(serialized.encode('utf-8')).hexdigest()}"


def _result_field_text(path: Sequence[ResultPathSegment]) -> str:
    if not path:
        raise ValueError("result path cannot be empty")
    parts: list[str] = []
    for segment in path:
        if isinstance(segment, int):
            if segment < 0:
                raise ValueError("result path indexes cannot be negative")
            parts.append(f"[{segment}]")
        else:
            normalized = segment.strip()
            if not normalized:
                raise ValueError("result path keys cannot be blank")
            parts.append(("." if parts else "") + normalized)
    return "".join(parts)


def _extract_exact_result_value(
    result: Mapping[str, Any],
    path: Sequence[ResultPathSegment],
) -> object:
    current: object = result
    for segment in path:
        if isinstance(segment, int):
            if not isinstance(current, list) or segment >= len(current):
                raise MediaArtifactError(f"structured result is missing exact index {segment}")
            current = current[segment]
        else:
            if not isinstance(current, Mapping) or segment not in current:
                raise MediaArtifactError(f"structured result is missing exact field {segment!r}")
            current = current[segment]
    return current


def acquisition_from_structured_result(
    result: Mapping[str, Any],
    *,
    method: Literal["yt_dlp", "local_copy", "transcode", "remux"],
    result_path: Sequence[ResultPathSegment],
    requested_output_path: Path,
    tool_name: str,
    tool_version: str | None = None,
    input_artifact_sha256: str | None = None,
) -> StructuredAcquisitionResult:
    """Resolve one authoritative output path from one exact structured-result field.

    No directory scanning, extension guessing, wildcard expansion, or first-match
    fallback is performed. Missing or malformed exact evidence fails closed.
    """

    value = _extract_exact_result_value(result, result_path)
    if not isinstance(value, str) or not value.strip():
        raise MediaArtifactError("structured result final-path field must be a non-empty string")
    final_path = Path(value).expanduser().resolve()
    if not final_path.is_file():
        raise MediaArtifactError(f"structured result final path is not a file: {final_path}")
    acquisition = MediaAcquisitionEvidence(
        method=method,
        path_authority="structured_result",
        requested_output_path=str(requested_output_path.expanduser().resolve()),
        authoritative_final_path=str(final_path),
        tool_name=tool_name,
        tool_version=tool_version,
        structured_result_sha256=_canonical_sha256(result),
        result_path_field=_result_field_text(result_path),
        input_artifact_sha256=input_artifact_sha256,
    )
    return StructuredAcquisitionResult(acquisition=acquisition, final_path=str(final_path))


def controlled_master_acquisition(
    path: Path,
    *,
    requested_output_path: Path | None = None,
    tool_name: str = "controlled-master",
    tool_version: str | None = None,
) -> MediaAcquisitionEvidence:
    final_path = path.expanduser().resolve()
    if not final_path.is_file():
        raise MediaArtifactError(f"controlled master is not a file: {final_path}")
    requested = (requested_output_path or final_path).expanduser().resolve()
    return MediaAcquisitionEvidence(
        method="controlled_master",
        path_authority="controlled_master",
        requested_output_path=str(requested),
        authoritative_final_path=str(final_path),
        tool_name=tool_name,
        tool_version=tool_version,
    )


def assess_media_profile(
    probe: MediaProbeEvidence,
    profile: MediaCompatibilityProfile,
    *,
    expected_duration_seconds: float | None,
) -> MediaProfileAssessment:
    reasons: list[str] = []
    formats = set(probe.format_names)
    if not formats.intersection(profile.required_format_names):
        reasons.append("container_format_not_allowed")
    if not (profile.minimum_video_streams <= probe.video_stream_count <= profile.maximum_video_streams):
        reasons.append("video_stream_count_out_of_range")
    if not (profile.minimum_audio_streams <= probe.audio_stream_count <= profile.maximum_audio_streams):
        reasons.append("audio_stream_count_out_of_range")
    if (probe.video_codec or "").lower() not in profile.allowed_video_codecs:
        reasons.append("video_codec_not_allowed")
    if (probe.audio_codec or "").lower() not in profile.allowed_audio_codecs:
        reasons.append("audio_codec_not_allowed")
    if probe.width is None or probe.width < profile.minimum_width:
        reasons.append("width_below_minimum")
    if probe.height is None or probe.height < profile.minimum_height:
        reasons.append("height_below_minimum")
    if probe.sample_rate_hz is None or probe.sample_rate_hz < profile.minimum_sample_rate_hz:
        reasons.append("sample_rate_below_minimum")
    if probe.audio_channels is None or probe.audio_channels < profile.minimum_audio_channels:
        reasons.append("audio_channels_below_minimum")
    if expected_duration_seconds is not None:
        delta = abs(probe.duration_seconds - expected_duration_seconds)
        if delta > profile.duration_tolerance_seconds:
            reasons.append("duration_mismatch")
    return MediaProfileAssessment(compatible=not reasons, reasons=tuple(reasons))


def calculate_media_manifest_sha256(evidence: MediaArtifactEvidence) -> str:
    payload = evidence.model_dump(mode="json", exclude={"manifest_sha256"})
    return _canonical_sha256(payload)


def build_media_artifact_evidence(
    *,
    source: MediaSourceIdentity,
    acquisition: MediaAcquisitionEvidence,
    profile: MediaCompatibilityProfile,
    report: MediaQualityReport,
) -> MediaArtifactEvidence:
    probe = MediaProbeEvidence.from_report(report)
    provisional = MediaArtifactEvidence(
        source=source,
        acquisition=acquisition,
        profile=profile,
        probe=probe,
        manifest_sha256="sha256:" + "0" * 64,
    )
    assessment = assess_media_profile(
        probe,
        profile,
        expected_duration_seconds=source.expected_duration_seconds,
    )
    if not assessment.compatible:
        raise MediaArtifactError(f"media profile is incompatible: {assessment.reasons}")
    evidence = provisional.model_copy(update={"manifest_sha256": calculate_media_manifest_sha256(provisional)})
    validate_media_artifact_evidence(evidence)
    return evidence


def probe_media_artifact(
    *,
    source: MediaSourceIdentity,
    acquisition: MediaAcquisitionEvidence,
    profile: MediaCompatibilityProfile | None = None,
    probe: MediaProbe = probe_media,
) -> MediaArtifactEvidence:
    final_path = Path(acquisition.authoritative_final_path)
    report = probe(final_path)
    return build_media_artifact_evidence(
        source=source,
        acquisition=acquisition,
        profile=profile or MediaCompatibilityProfile(),
        report=report,
    )


def validate_media_artifact_evidence(evidence: MediaArtifactEvidence) -> None:
    expected_digest = calculate_media_manifest_sha256(evidence)
    if evidence.manifest_sha256 != expected_digest:
        raise MediaArtifactError("media manifest digest does not match its contents")
    assessment = assess_media_profile(
        evidence.probe,
        evidence.profile,
        expected_duration_seconds=evidence.source.expected_duration_seconds,
    )
    if not assessment.compatible:
        raise MediaArtifactError(f"media profile is incompatible: {assessment.reasons}")


def validate_cached_media_artifact(
    evidence: MediaArtifactEvidence | Mapping[str, Any],
    *,
    expected_project_key: str,
    expected_source_platform: PlatformName,
    expected_source_channel_id: str,
    expected_source_id: str,
    expected_source_duration_seconds: float | None,
    expected_path: Path,
    probe: MediaProbe = probe_media,
) -> MediaArtifactEvidence:
    try:
        parsed = (
            evidence
            if isinstance(evidence, MediaArtifactEvidence)
            else MediaArtifactEvidence.model_validate(evidence)
        )
    except Exception as exc:
        raise MediaArtifactError(f"media manifest is invalid: {exc}") from exc
    validate_media_artifact_evidence(parsed)

    expected_identity = {
        "project_key": expected_project_key,
        "platform": expected_source_platform,
        "source_channel_id": expected_source_channel_id.strip(),
        "source_id": expected_source_id.strip(),
        "expected_duration_seconds": expected_source_duration_seconds,
    }
    actual_identity = {
        "project_key": parsed.source.project_key,
        "platform": parsed.source.platform,
        "source_channel_id": parsed.source.source_channel_id,
        "source_id": parsed.source.source_id,
        "expected_duration_seconds": parsed.source.expected_duration_seconds,
    }
    if actual_identity != expected_identity:
        raise MediaArtifactError(
            f"media source identity mismatch: expected={expected_identity!r} actual={actual_identity!r}"
        )

    final_path = Path(parsed.acquisition.authoritative_final_path).expanduser().resolve()
    supplied_path = expected_path.expanduser().resolve()
    if final_path != supplied_path:
        raise MediaArtifactError(
            f"supplied media path is not the authoritative final path: {supplied_path} != {final_path}"
        )
    if not final_path.is_file():
        raise MediaArtifactError(f"authoritative final path is missing: {final_path}")
    size_bytes = final_path.stat().st_size
    if size_bytes != parsed.probe.size_bytes:
        raise MediaArtifactError("cached media size does not match manifest")
    digest = sha256_file(final_path)
    if digest != parsed.probe.sha256:
        raise MediaArtifactError("cached media SHA-256 does not match manifest")

    fresh_report = probe(final_path)
    fresh_probe = MediaProbeEvidence.from_report(fresh_report)
    if fresh_probe != parsed.probe:
        raise MediaArtifactError("fresh ffprobe evidence does not match media manifest")
    if fresh_probe.sha256 != digest:
        raise MediaArtifactError("fresh ffprobe report SHA-256 does not match file bytes")
    assessment = assess_media_profile(
        fresh_probe,
        parsed.profile,
        expected_duration_seconds=expected_source_duration_seconds,
    )
    if not assessment.compatible:
        raise MediaArtifactError(f"cached media is not upload-compatible: {assessment.reasons}")
    return parsed


def write_media_artifact_manifest(evidence: MediaArtifactEvidence, path: Path) -> None:
    validate_media_artifact_evidence(evidence)
    destination = path.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    payload = json.dumps(evidence.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, destination)


def load_media_artifact_manifest(path: Path) -> MediaArtifactEvidence:
    source = path.expanduser().resolve()
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
        evidence = MediaArtifactEvidence.model_validate(payload)
    except Exception as exc:
        raise MediaArtifactError(f"cannot load media artifact manifest {source}: {exc}") from exc
    validate_media_artifact_evidence(evidence)
    return evidence


__all__ = [
    "MediaAcquisitionEvidence",
    "MediaArtifactError",
    "MediaArtifactEvidence",
    "MediaCompatibilityProfile",
    "MediaProbe",
    "MediaProbeEvidence",
    "MediaProfileAssessment",
    "MediaSourceIdentity",
    "StructuredAcquisitionResult",
    "acquisition_from_structured_result",
    "assess_media_profile",
    "build_media_artifact_evidence",
    "calculate_media_manifest_sha256",
    "controlled_master_acquisition",
    "load_media_artifact_manifest",
    "probe_media_artifact",
    "validate_cached_media_artifact",
    "validate_media_artifact_evidence",
    "write_media_artifact_manifest",
]
