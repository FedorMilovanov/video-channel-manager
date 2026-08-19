from __future__ import annotations

import re
from collections.abc import Collection, Mapping
from typing import Any

from video_channel_manager.domain.enums import PlatformName
from video_channel_manager.editorial._project_profiles import PROJECT_CHANNEL_IDS, PROJECT_KEYS
from video_channel_manager.exchange.audit_package import AuditPackage


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

    The function intentionally does not classify YouTube Shorts from duration. The
    YouTube Data API snapshot used by AuditPackage proves duration and metadata but
    not the Shorts surface/source aspect ratio needed by this project's fail-closed
    media policy.
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

    records: list[dict[str, Any]] = []
    for video in audit.videos:
        video_id = video.ref.remote_id
        records.append(
            {
                "youtube_video_id": video_id,
                "title": video.title,
                "duration_seconds": video.duration_seconds,
                "published_at": video.published_at.isoformat() if video.published_at else None,
                "privacy_status": video.privacy_status,
                "tags": list(video.tags),
                "thumbnail_url": video.thumbnail_url,
                "revision": video.revision,
                "present_in_frozen_mapping": video_id in mapped_ids,
                "exact_vk_video_id": frozen_youtube_vk_mapping.get(video_id),
                "reviewed_editorial_record": (
                    f"content/youtube-comments/{video_id}.json" if video_id in reviewed_ids else None
                ),
                "youtube_format_status": "unknown",
                "source_aspect_ratio": None,
                "clean_master_status": "unbound",
                "instagram_route": "source_binding_required",
                "provider_writes_authorized": False,
            }
        )

    return {
        "schema_name": "video-manager.instagram-youtube-video-intake",
        "schema_version": 1,
        "status": "provider-inert",
        "provider_effect": "impossible",
        "provider_writes_authorized": False,
        "project_key": normalized_project,
        "channel_id": channel_ref.channel_id,
        "source_snapshot_id": str(audit.snapshot_id),
        "source_generated_at": audit.generated_at.isoformat(),
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
            "confirmed_short": 0,
            "confirmed_longform": 0,
            "format_unknown": len(current_ids),
        },
        "reconciliation": {
            "new_current_ids": sorted(current_ids - mapped_ids),
            "historical_mapped_missing_from_current_snapshot": sorted(mapped_ids - current_ids),
            "reviewed_missing_from_current_snapshot": sorted(reviewed_ids - current_ids),
        },
        "classification_policy": {
            "shorts": "fail-closed: duration alone is not accepted as Shorts proof",
            "longform": "fail-closed until format/source geometry is bound",
            "unknown_is_not_excluded": True,
            "social_delivery_encoding_is_not_source_master": True,
        },
        "records": records,
    }
