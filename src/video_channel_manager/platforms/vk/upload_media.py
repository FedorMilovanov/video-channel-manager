from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from video_channel_manager.domain.enums import PlatformName
from video_channel_manager.editorial._project_profiles import (
    PROJECT_CHANNEL_IDS,
    resolve_project_key,
)
from video_channel_manager.local_media.artifact import (
    MediaArtifactError,
    MediaArtifactEvidence,
    MediaProbe,
    validate_cached_media_artifact,
)
from video_channel_manager.local_media.quality import probe_media


class UploadMediaAuthorityError(RuntimeError):
    """Upload media cannot be bound to exact project/source/artifact evidence."""


def _exact_project_channel_id(project_key: str) -> str:
    channel_ids = PROJECT_CHANNEL_IDS.get(project_key, frozenset())
    if len(channel_ids) != 1:
        raise UploadMediaAuthorityError(
            f"project {project_key!r} does not have exactly one registered source channel"
        )
    return next(iter(channel_ids))


def verify_upload_media_authority(
    record: Mapping[str, Any],
    *,
    community_id: int,
    media_path: Path,
    media_artifact: MediaArtifactEvidence | Mapping[str, Any] | None,
    previous_media: Mapping[str, Any] | None,
    probe: MediaProbe = probe_media,
) -> MediaArtifactEvidence:
    if media_artifact is None:
        raise UploadMediaAuthorityError("authoritative media artifact evidence is required")
    project_key = resolve_project_key({"community_id": community_id})
    if project_key is None:
        raise UploadMediaAuthorityError(
            f"community_id {community_id} does not resolve to one registered project"
        )
    source_video_id = record.get("source_video_id")
    if not isinstance(source_video_id, str) or not source_video_id.strip():
        raise UploadMediaAuthorityError("upload journal has no exact source_video_id")
    raw_duration = record.get("source_duration_seconds")
    source_duration = float(raw_duration) if isinstance(raw_duration, int | float) and raw_duration > 0 else None
    try:
        evidence = validate_cached_media_artifact(
            media_artifact,
            expected_project_key=project_key,
            expected_source_platform=PlatformName.YOUTUBE,
            expected_source_channel_id=_exact_project_channel_id(project_key),
            expected_source_id=source_video_id,
            expected_source_duration_seconds=source_duration,
            expected_path=media_path,
            probe=probe,
        )
    except MediaArtifactError as exc:
        raise UploadMediaAuthorityError(str(exc)) from exc

    if previous_media is not None:
        previous_payload = previous_media.get("artifact")
        if not isinstance(previous_payload, Mapping):
            raise UploadMediaAuthorityError(
                "verified upload journal contains legacy media evidence without an artifact manifest"
            )
        try:
            previous = MediaArtifactEvidence.model_validate(previous_payload)
        except Exception as exc:
            raise UploadMediaAuthorityError(f"journaled media artifact is invalid: {exc}") from exc
        if previous.manifest_sha256 != evidence.manifest_sha256:
            raise UploadMediaAuthorityError(
                "media artifact manifest changed after MEDIA_VERIFIED"
            )
    return evidence


def journal_media_evidence(evidence: MediaArtifactEvidence) -> dict[str, object]:
    return {
        "schema_name": "video-manager.vk-upload-media-evidence",
        "schema_version": 2,
        "manifest_sha256": evidence.manifest_sha256,
        "path": evidence.acquisition.authoritative_final_path,
        "size_bytes": evidence.probe.size_bytes,
        "sha256": evidence.probe.sha256,
        "profile_name": evidence.profile.profile_name,
        "artifact": evidence.model_dump(mode="json"),
    }


__all__ = [
    "UploadMediaAuthorityError",
    "journal_media_evidence",
    "verify_upload_media_authority",
]
