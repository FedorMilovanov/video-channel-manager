from __future__ import annotations

import re
from datetime import datetime
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

from video_channel_manager.editorial._content_types import (
    ALLOWED_LINK_KINDS,
    ALLOWED_SURFACES,
)
from video_channel_manager.editorial._content_urls import canonicalize_url

_STABLE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,159}$")
_INSTAGRAM_PROVIDER_ID_RE = re.compile(r"^[0-9]+$")


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str)]


def _object(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _valid_aware_datetime(value: object) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text:
        return False
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _valid_stable_id(value: object) -> bool:
    return isinstance(value, str) and _STABLE_ID_RE.fullmatch(value.strip()) is not None


def _unsafe_repository_path(value: str) -> bool:
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    return posix.is_absolute() or windows.is_absolute() or ".." in posix.parts or ".." in windows.parts


def _string_field(
    payload: dict[str, Any],
    key: str,
    *,
    location: str,
    errors: list[str],
    optional: bool = False,
) -> str:
    value = payload.get(key)
    if value is None and optional:
        return ""
    if not isinstance(value, str):
        suffix = " or null" if optional else ""
        errors.append(f"{location}.{key} must be a string{suffix}")
        return ""
    return value.strip()


def _validate_string_list(
    value: object,
    *,
    location: str,
    errors: list[str],
) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{location} must be a list")
        return []
    if any(not isinstance(item, str) for item in value):
        errors.append(f"{location} must contain only strings")
    return _string_list(value)


def _source_validation(payload: dict[str, Any]) -> tuple[list[str], dict[str, dict[str, Any]], set[str]]:
    errors: list[str] = []
    raw_sources = payload.get("sources")
    if not isinstance(raw_sources, list):
        return ["sources must be a list"], {}, set()
    source_by_id: dict[str, dict[str, Any]] = {}
    source_urls: set[str] = set()
    for index, raw_value in enumerate(raw_sources):
        if not isinstance(raw_value, dict):
            errors.append(f"sources[{index}] must be an object")
            continue
        location = f"sources[{index}]"
        source_id = _string_field(
            raw_value,
            "source_id",
            location=location,
            errors=errors,
        )
        if not source_id:
            errors.append(f"{location}.source_id cannot be blank")
            continue
        if not _valid_stable_id(source_id):
            errors.append(f"{location}.source_id must be a stable identifier")
        if source_id in source_by_id:
            errors.append(f"duplicate source_id: {source_id}")
            continue
        title = _string_field(
            raw_value,
            "title",
            location=location,
            errors=errors,
        )
        if not title:
            errors.append(f"source {source_id} must have a title")
        url = _string_field(
            raw_value,
            "url",
            location=location,
            errors=errors,
            optional=True,
        )
        path = _string_field(
            raw_value,
            "path",
            location=location,
            errors=errors,
            optional=True,
        )
        if bool(url) == bool(path):
            errors.append(f"source {source_id} must declare exactly one of url or path")
        if url:
            try:
                source_urls.add(canonicalize_url(url))
            except ValueError as exc:
                errors.append(f"source {source_id}: {exc}")
        if path and _unsafe_repository_path(path):
            errors.append(f"source {source_id} has an unsafe repository path")
        source_by_id[source_id] = raw_value
    return errors, source_by_id, source_urls


def _validate_link_order(value: object, *, location: str, errors: list[str]) -> None:
    order = _validate_string_list(value, location=location, errors=errors)
    if any(not item for item in order):
        errors.append(f"{location} cannot contain blanks")
    if len(order) != len(set(order)):
        errors.append(f"{location} cannot contain duplicates")
    unknown = sorted(set(order).difference(ALLOWED_LINK_KINDS))
    if unknown:
        errors.append(f"{location} contains unsupported link kinds: {', '.join(unknown)}")


def _validate_rendering_metadata(value: object) -> list[str]:
    errors: list[str] = []
    if value is None:
        return errors
    if not isinstance(value, dict):
        return ["rendering_metadata must be an object"]
    preferred = value.get("preferred_link_order")
    if preferred is None:
        return errors
    if isinstance(preferred, list):
        _validate_link_order(
            preferred,
            location="rendering_metadata.preferred_link_order",
            errors=errors,
        )
        return errors
    if not isinstance(preferred, dict):
        return ["rendering_metadata.preferred_link_order must be a list or object"]
    for raw_key, raw_order in preferred.items():
        if not isinstance(raw_key, str) or not raw_key.strip():
            errors.append("rendering_metadata.preferred_link_order keys must be nonblank strings")
            continue
        key = raw_key.strip()
        if key != "default" and key not in ALLOWED_SURFACES:
            if "." not in key:
                errors.append(f"unsupported preferred_link_order target: {key}")
                continue
            platform, surface = key.split(".", 1)
            if surface not in ALLOWED_SURFACES.get(platform, frozenset()):
                errors.append(f"unsupported preferred_link_order target: {key}")
                continue
        _validate_link_order(
            raw_order,
            location=f"rendering_metadata.preferred_link_order.{key}",
            errors=errors,
        )
    return errors


def _validate_platform_metadata(payload: dict[str, Any], *, schema_is_canonical: bool) -> list[str]:
    errors: list[str] = []
    suitability = payload.get("platform_suitability")
    normalized_suitability: dict[str, set[str]] = {}
    if schema_is_canonical and not isinstance(suitability, dict):
        errors.append("canonical content requires explicit platform_suitability")
    elif suitability is not None and not isinstance(suitability, dict):
        errors.append("platform_suitability must be an object")
    elif isinstance(suitability, dict):
        if schema_is_canonical and not suitability:
            errors.append("canonical platform_suitability cannot be empty")
        for raw_platform, raw_surfaces in suitability.items():
            if not isinstance(raw_platform, str):
                errors.append("platform_suitability keys must be strings")
                continue
            platform = raw_platform.strip()
            if platform not in ALLOWED_SURFACES:
                errors.append(f"unsupported platform_suitability platform: {raw_platform}")
                continue
            surfaces = _validate_string_list(
                raw_surfaces,
                location=f"platform_suitability.{platform}",
                errors=errors,
            )
            if any(not surface for surface in surfaces):
                errors.append(f"platform_suitability.{platform} cannot contain blanks")
            if len(surfaces) != len(set(surfaces)):
                errors.append(f"platform_suitability.{platform} cannot contain duplicates")
            unknown = sorted(set(surfaces).difference(ALLOWED_SURFACES[platform]))
            if unknown:
                errors.append(f"unsupported {platform} surfaces: {', '.join(unknown)}")
            if schema_is_canonical and not surfaces:
                errors.append(f"platform_suitability.{platform} cannot be empty")
            normalized_suitability[platform] = set(surfaces)

    errors.extend(_validate_rendering_metadata(payload.get("rendering_metadata", {})))

    platform_targets = payload.get("platform_targets", {})
    if platform_targets is not None and not isinstance(platform_targets, dict):
        errors.append("platform_targets must be an object")
    elif isinstance(platform_targets, dict):
        for raw_key, raw_value in platform_targets.items():
            if not isinstance(raw_key, str):
                errors.append("platform_targets keys must be strings")
                continue
            if not isinstance(raw_value, str):
                errors.append(f"platform target {raw_key} must be a string")
                continue
            key = raw_key.strip()
            value = raw_value.strip()
            if not key or not value:
                errors.append("platform_targets cannot contain blank keys or values")
                continue
            if any(character.isspace() for character in value):
                errors.append(f"platform target {key} cannot contain whitespace")
            if "." not in key:
                if schema_is_canonical:
                    errors.append(f"canonical platform target must use platform.surface: {key}")
                elif key not in ALLOWED_SURFACES:
                    errors.append(f"unsupported platform target: {key}")
                continue
            platform, surface = key.split(".", 1)
            allowed_surfaces = ALLOWED_SURFACES.get(platform)
            if allowed_surfaces is None:
                errors.append(f"unsupported platform target platform: {platform}")
                continue
            if surface not in allowed_surfaces:
                errors.append(f"unsupported platform target surface: {key}")
                continue
            if platform == "instagram" and _INSTAGRAM_PROVIDER_ID_RE.fullmatch(value) is None:
                errors.append(
                    f"platform target {key} must use an exact numeric Instagram provider account ID; "
                    "usernames and public handles are non-authoritative"
                )
            if schema_is_canonical and surface not in normalized_suitability.get(platform, set()):
                errors.append(f"platform target {key} is not enabled by platform_suitability")
    return errors


__all__ = [
    "_object",
    "_source_validation",
    "_string_field",
    "_string_list",
    "_valid_aware_datetime",
    "_valid_stable_id",
    "_validate_platform_metadata",
    "_validate_string_list",
]
