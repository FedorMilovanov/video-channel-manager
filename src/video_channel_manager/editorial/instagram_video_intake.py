from __future__ import annotations

import re
from collections import Counter
from collections.abc import Collection, Mapping
from typing import Any

from video_channel_manager.domain.enums import PlatformName
from video_channel_manager.editorial._project_profiles import PROJECT_CHANNEL_IDS, PROJECT_KEYS
from video_channel_manager.editorial.youtube_surface_classification import classify_youtube_surface
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.exchange.instagram_video import InstagramVideoIntakeArtifact


_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class InstagramVideoIntakeError(ValueError):
    pass


def _require_sha256(value: str | None, *, field: str, allow_none: bool = False) -> None:
    if value is None and allow_none:
        return
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise InstagramVideoIntakeError(f"{field} must use the exact sha256:<64 lowercase hex> form")


def build_instagram_video_intake(
    audit: AuditPackage,
    *,
    project_key: str,
    frozen_youtube_vk_mapping: Mapping[str, str],
    reviewed_video_ids: Collection[str] = (),
    source_audit_sha256: str,
    frozen_mapping_sha256: str | None = None,
    reviewed_corpus_sha256: str | None = None,
) -> dict[str, Any]:
    """Build a provider-inert Instagram intake from one exact YouTube AuditPackage.

    Owner-only YouTube ``fileDetails`` are used when present to prove source-file
    geometry and millisecond duration. The intake may therefore confirm that a video
    is long-form when the source is landscape or exceeds three minutes. It never
    promotes a square/vertical short-duration upload to confirmed Short without an
    exact Shorts-surface proof.
    """

    normalized_project = project_key.strip()
    if normalized_project not in PROJECT_KEYS:
        raise InstagramVideoIntakeError(f"unknown project_key: {project_key}")

    channel_ref = audit.channel.ref
    if channel_ref.platform != PlatformName.YOUTUBE:
        raise InstagramVideoIntakeError("Instagram video intake requires a YouTube AuditPackage")

    expected_channels = PROJECT_CHANNEL_IDS.get(normalized_project, frozenset())
    if channel_ref.channel_id not in expected_channels:
        expected = ", ".join(sorted(expected_channels)) or "none"
        raise InstagramVideoIntakeError(
            f"unexpected YouTube channel for {normalized_project}: {channel_ref.channel_id}; expected {expected}"
        )

    _require_sha256(source_audit_sha256, field="source_audit_sha256")
    _require_sha256(frozen_mapping_sha256, field="frozen_mapping_sha256", allow_none=True)
    _require_sha256(reviewed_corpus_sha256, field="reviewed_corpus_sha256", allow_none=True)

    mapped_ids = set(frozen_youtube_vk_mapping)
    reviewed_ids = set(reviewed_video_ids)
    current_ids = {video.ref.remote_id for video in audit.videos}

    surface_counts: Counter[str] = Counter()
    short_candidates = 0
    file_details_available = 0
    source_geometry_known = 0
    records: list[dict[str, Any]] = []
    for video in audit.videos:
        video_id = video.ref.remote_id
        classification = classify_youtube_surface(video)
        source = classification.source
        surface_counts[classification.status] += 1
        short_candidates += int(classification.short_candidate)
        file_details_available += int(source.file_details_available)
        source_geometry_known += int(source.geometry != "unknown")
        records.append(
            {
                "youtube_video_id": video_id,
                "title": video.title,
                "duration_seconds": video.duration_seconds,
                "published_at": video.published_at,
                "privacy_status": video.privacy_status,
                "tags": list(video.tags),
                "thumbnail_url": video.thumbnail_url,
                "revision": video.revision,
                "present_in_frozen_mapping": video_id in mapped_ids,
                "exact_vk_video_id": frozen_youtube_vk_mapping.get(video_id),
                "reviewed_editorial_record": (
                    f"content/youtube-comments/{video_id}.json" if video_id in reviewed_ids else None
                ),
                "youtube_format_status": classification.status,
                "youtube_format_reason": classification.reason,
                "youtube_short_candidate": classification.short_candidate,
                "youtube_file_details_available": source.file_details_available,
                "youtube_source_geometry": source.geometry,
                "youtube_source_width_pixels": source.width_pixels,
                "youtube_source_height_pixels": source.height_pixels,
                "youtube_source_duration_ms": source.duration_ms,
                "youtube_source_creation_time": source.creation_time,
                "clean_master_status": "unbound",
                "instagram_route": "source_binding_required",
                "provider_writes_authorized": False,
            }
        )

    artifact = InstagramVideoIntakeArtifact.model_validate(
        {
            "project_key": normalized_project,
            "channel_id": channel_ref.channel_id,
            "source_snapshot_id": str(audit.snapshot_id),
            "source_generated_at": audit.generated_at,
            "source_evidence": {
                "audit_package_sha256": source_audit_sha256,
                "frozen_mapping_sha256": frozen_mapping_sha256,
                "reviewed_corpus_sha256": reviewed_corpus_sha256,
            },
            "counts": {
                "current_videos": len(current_ids),
                "frozen_mapping_ids": len(mapped_ids),
                "reviewed_editorial_ids": len(reviewed_ids),
                "current_also_in_frozen_mapping": len(current_ids & mapped_ids),
                "new_current_vs_frozen_mapping": len(current_ids - mapped_ids),
                "historical_mapped_missing_from_current_snapshot": len(mapped_ids - current_ids),
                "confirmed_short": surface_counts["short"],
                "confirmed_longform": surface_counts["longform"],
                "format_unknown": surface_counts["unknown"],
                "short_candidates": short_candidates,
                "file_details_available": file_details_available,
                "source_geometry_known": source_geometry_known,
            },
            "reconciliation": {
                "new_current_ids": sorted(current_ids - mapped_ids),
                "historical_mapped_missing_from_current_snapshot": sorted(mapped_ids - current_ids),
                "reviewed_missing_from_current_snapshot": sorted(reviewed_ids - current_ids),
            },
            "classification_policy": {
                "shorts": (
                    "square/vertical at or below three minutes is only a Short candidate until exact "
                    "Shorts-surface/upload evidence is bound"
                ),
                "longform": (
                    "owner fileDetails may prove long-form by landscape source geometry; duration over "
                    "three minutes also proves it cannot satisfy the current three-minute Shorts cap"
                ),
                "owner_file_details_used": True,
                "published_at_is_not_upload_time": True,
                "file_creation_time_is_not_upload_time": True,
                "unknown_is_not_excluded": True,
                "social_delivery_encoding_is_not_source_master": True,
            },
            "records": records,
        }
    )
    return artifact.model_dump(mode="json")
