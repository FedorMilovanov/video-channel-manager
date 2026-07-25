from __future__ import annotations

from typing import Any

from video_channel_manager.editorial._content_types import (
    ALLOWED_PROFILES,
    ALLOWED_STATUSES,
    CANONICAL_SCHEMA_NAME,
    CANONICAL_SCHEMA_VERSION,
    LEGACY_YOUTUBE_SCHEMA_NAME,
    LEGACY_YOUTUBE_SCHEMA_VERSION,
)
from video_channel_manager.editorial._content_validation_support import _valid_aware_datetime, _valid_stable_id


def validate_identity(payload: dict[str, Any], *, expected_channel_id: str | None) -> tuple[list[str], bool]:
    errors: list[str] = []
    schema_name = str(payload.get("schema_name") or "")
    version = payload.get("schema_version")
    schema_is_canonical = schema_name == CANONICAL_SCHEMA_NAME and version == CANONICAL_SCHEMA_VERSION
    schema_is_legacy = schema_name == LEGACY_YOUTUBE_SCHEMA_NAME and version == LEGACY_YOUTUBE_SCHEMA_VERSION
    if not schema_is_canonical and not schema_is_legacy:
        errors.append(
            f"schema must be {CANONICAL_SCHEMA_NAME} v{CANONICAL_SCHEMA_VERSION} or "
            f"{LEGACY_YOUTUBE_SCHEMA_NAME} v{LEGACY_YOUTUBE_SCHEMA_VERSION}"
        )

    status = str(payload.get("status") or "").strip()
    if status not in ALLOWED_STATUSES:
        errors.append("unsupported editorial status")
    profile = str(payload.get("profile") or "").strip()
    if profile not in ALLOWED_PROFILES:
        errors.append("content requires a supported profile")
    variation_key = str(payload.get("variation_key") or "").strip()
    if not variation_key:
        errors.append("content requires variation_key")
    elif not _valid_stable_id(variation_key):
        errors.append("variation_key must be a stable 2-160 character identifier")
    content_id = str(payload.get("content_id") or "").strip()
    if schema_is_canonical and not content_id:
        errors.append("canonical content requires content_id")
    elif content_id and not _valid_stable_id(content_id):
        errors.append("content_id must be a stable 2-160 character identifier")
    channel_id = str(payload.get("channel_id") or "").strip()
    if expected_channel_id is not None and channel_id != expected_channel_id:
        errors.append("channel_id does not match the requested channel")
    if schema_is_legacy and not channel_id:
        errors.append("channel_id cannot be blank")
    video_id = str(payload.get("video_id") or "").strip()
    if schema_is_legacy and not video_id:
        errors.append("video_id cannot be blank")
    if status == "approved" and not _valid_aware_datetime(payload.get("reviewed_at")):
        errors.append("approved content requires a timezone-aware reviewed_at")
    return errors, schema_is_canonical


__all__ = ["validate_identity"]
