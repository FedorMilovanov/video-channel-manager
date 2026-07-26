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
from video_channel_manager.editorial._content_validation_support import (
    _valid_aware_datetime,
    _valid_stable_id,
)


def _optional_string(
    payload: dict[str, Any],
    key: str,
    *,
    errors: list[str],
) -> str:
    value = payload.get(key)
    if value is None:
        return ""
    if not isinstance(value, str):
        errors.append(f"{key} must be a string or null")
        return ""
    return value.strip()


def _required_string(
    payload: dict[str, Any],
    key: str,
    *,
    errors: list[str],
) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        errors.append(f"{key} must be a string")
        return ""
    return value.strip()


def validate_identity(payload: dict[str, Any], *, expected_channel_id: str | None) -> tuple[list[str], bool]:
    errors: list[str] = []
    schema_name = _required_string(payload, "schema_name", errors=errors)
    version = payload.get("schema_version")
    if type(version) is not int:
        errors.append("schema_version must be an integer")
    schema_is_canonical = (
        schema_name == CANONICAL_SCHEMA_NAME and type(version) is int and version == CANONICAL_SCHEMA_VERSION
    )
    schema_is_legacy = (
        schema_name == LEGACY_YOUTUBE_SCHEMA_NAME and type(version) is int and version == LEGACY_YOUTUBE_SCHEMA_VERSION
    )
    if not schema_is_canonical and not schema_is_legacy:
        errors.append(
            f"schema must be {CANONICAL_SCHEMA_NAME} v{CANONICAL_SCHEMA_VERSION} or "
            f"{LEGACY_YOUTUBE_SCHEMA_NAME} v{LEGACY_YOUTUBE_SCHEMA_VERSION}"
        )

    status = _required_string(payload, "status", errors=errors)
    if status not in ALLOWED_STATUSES:
        errors.append("unsupported editorial status")
    profile = _required_string(payload, "profile", errors=errors)
    if profile not in ALLOWED_PROFILES:
        errors.append("content requires a supported profile")
    variation_key = _required_string(payload, "variation_key", errors=errors)
    if not variation_key:
        errors.append("content requires variation_key")
    elif not _valid_stable_id(variation_key):
        errors.append("variation_key must be a stable 2-160 character identifier")

    content_id = _optional_string(payload, "content_id", errors=errors)
    if schema_is_canonical and not content_id:
        errors.append("canonical content requires content_id")
    elif content_id and not _valid_stable_id(content_id):
        errors.append("content_id must be a stable 2-160 character identifier")

    channel_id = _optional_string(payload, "channel_id", errors=errors)
    if expected_channel_id is not None and channel_id != expected_channel_id:
        errors.append("channel_id does not match the requested channel")
    if schema_is_legacy and not channel_id:
        errors.append("channel_id cannot be blank")

    video_id = _optional_string(payload, "video_id", errors=errors)
    if schema_is_legacy and not video_id:
        errors.append("video_id cannot be blank")
    _optional_string(payload, "video_title", errors=errors)

    reviewed_at_raw = payload.get("reviewed_at")
    if reviewed_at_raw is not None and not isinstance(reviewed_at_raw, str):
        errors.append("reviewed_at must be a string or null")
    if status == "approved" and not _valid_aware_datetime(reviewed_at_raw):
        errors.append("approved content requires a timezone-aware reviewed_at")
    return errors, schema_is_canonical


__all__ = ["validate_identity"]
