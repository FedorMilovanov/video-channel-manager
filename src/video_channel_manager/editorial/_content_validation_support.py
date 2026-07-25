from __future__ import annotations

import re
from datetime import datetime
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

from video_channel_manager.editorial._content_types import (
    ALLOWED_FACT_TYPES,
    ALLOWED_LINK_KINDS,
    ALLOWED_PROFILES,
    ALLOWED_STATUSES,
    ALLOWED_SURFACES,
    APPROVED_PROJECT_URLS,
    BANNED_GENERIC_PHRASES,
    CANONICAL_SCHEMA_NAME,
    CANONICAL_SCHEMA_VERSION,
    DECORATIVE_MARKERS,
    LEGACY_YOUTUBE_SCHEMA_NAME,
    LEGACY_YOUTUBE_SCHEMA_VERSION,
)
from video_channel_manager.editorial._content_urls import balanced_emphasis, canonicalize_url, contains_banned_circle

_STABLE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,159}$")


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value]


def _object(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _valid_aware_datetime(value: object) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _valid_stable_id(value: object) -> bool:
    return _STABLE_ID_RE.fullmatch(str(value or "").strip()) is not None


def _unsafe_repository_path(value: str) -> bool:
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    return posix.is_absolute() or windows.is_absolute() or ".." in posix.parts or ".." in windows.parts


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
        source_id = str(raw_value.get("source_id") or "").strip()
        if not source_id:
            errors.append(f"sources[{index}].source_id cannot be blank")
            continue
        if source_id in source_by_id:
            errors.append(f"duplicate source_id: {source_id}")
            continue
        title = str(raw_value.get("title") or "").strip()
        if not title:
            errors.append(f"source {source_id} must have a title")
        url = str(raw_value.get("url") or "").strip()
        path = str(raw_value.get("path") or "").strip()
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
            platform = str(raw_platform).strip()
            if platform not in ALLOWED_SURFACES:
                errors.append(f"unsupported platform_suitability platform: {raw_platform}")
                continue
            if not isinstance(raw_surfaces, list):
                errors.append(f"platform_suitability.{platform} must be a list")
                continue
            surfaces = _string_list(raw_surfaces)
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

    rendering_metadata = payload.get("rendering_metadata", {})
    if rendering_metadata is not None and not isinstance(rendering_metadata, dict):
        errors.append("rendering_metadata must be an object")

    platform_targets = payload.get("platform_targets", {})
    if platform_targets is not None and not isinstance(platform_targets, dict):
        errors.append("platform_targets must be an object")
    elif isinstance(platform_targets, dict):
        for raw_key, raw_value in platform_targets.items():
            key = str(raw_key).strip()
            value = str(raw_value).strip()
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
            if schema_is_canonical and surface not in normalized_suitability.get(platform, set()):
                errors.append(f"platform target {key} is not enabled by platform_suitability")
    return errors

__all__ = [
    "_object",
    "_source_validation",
    "_string_list",
    "_valid_aware_datetime",
    "_valid_stable_id",
    "_validate_platform_metadata",
]
