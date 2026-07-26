from __future__ import annotations

from typing import Any

from video_channel_manager.editorial._content_types import (
    ALLOWED_LINK_KINDS,
    ALLOWED_SURFACES,
    APPROVED_PROJECT_URLS,
)
from video_channel_manager.editorial._content_urls import (
    balanced_emphasis,
    canonicalize_url,
    contains_banned_circle,
)
from video_channel_manager.editorial._content_validation_support import (
    _string_field,
    _validate_string_list,
)


def validate_links(payload: dict[str, Any], *, source_urls: set[str]) -> list[str]:
    errors: list[str] = []
    raw_links = payload.get("links")
    if not isinstance(raw_links, list) or not 1 <= len(raw_links) <= 5:
        errors.append("links must contain 1-5 compact inline links")
        raw_links = []
    link_kinds: list[str] = []
    approved_urls = {canonicalize_url(item) for item in APPROVED_PROJECT_URLS}
    allowed_urls = source_urls | approved_urls
    for index, raw_value in enumerate(raw_links):
        if not isinstance(raw_value, dict):
            errors.append(f"links[{index}] must be an object")
            continue
        location = f"links[{index}]"
        kind = _string_field(
            raw_value,
            "kind",
            location=location,
            errors=errors,
        )
        label = _string_field(
            raw_value,
            "label",
            location=location,
            errors=errors,
        )
        url = _string_field(
            raw_value,
            "url",
            location=location,
            errors=errors,
        )
        link_kinds.append(kind)
        if kind not in ALLOWED_LINK_KINDS:
            errors.append(f"{location}.kind is unsupported")
        if not label or "\n" in label:
            errors.append(f"{location}.label must be one compact line")
        if not balanced_emphasis(label):
            errors.append(f"{location}.label has unbalanced emphasis")
        if contains_banned_circle(label):
            errors.append("colored circle markers are not allowed")
        try:
            canonical_url = canonicalize_url(url)
        except ValueError as exc:
            errors.append(f"{location}.url: {exc}")
            canonical_url = ""
        if canonical_url and canonical_url not in allowed_urls:
            errors.append(f"{location}.url is absent from sources/project link map: {canonical_url}")
        platforms_value = raw_value.get("platforms")
        platforms = (
            _validate_string_list(
                platforms_value,
                location=f"{location}.platforms",
                errors=errors,
            )
            if platforms_value is not None
            else []
        )
        surfaces_value = raw_value.get("surfaces")
        surfaces = (
            _validate_string_list(
                surfaces_value,
                location=f"{location}.surfaces",
                errors=errors,
            )
            if surfaces_value is not None
            else []
        )
        if any(not item for item in platforms):
            errors.append(f"{location}.platforms cannot contain blanks")
        if any(not item for item in surfaces):
            errors.append(f"{location}.surfaces cannot contain blanks")
        if len(platforms) != len(set(platforms)):
            errors.append(f"{location}.platforms cannot contain duplicates")
        if len(surfaces) != len(set(surfaces)):
            errors.append(f"{location}.surfaces cannot contain duplicates")
        for platform in platforms:
            if platform not in ALLOWED_SURFACES:
                errors.append(f"{location}.platforms contains unsupported platform: {platform}")
        if surfaces and not platforms:
            errors.append(f"{location}.surfaces requires platforms")
        for platform in platforms:
            allowed_surfaces = ALLOWED_SURFACES.get(platform)
            if allowed_surfaces is None:
                continue
            unknown_surfaces = sorted(set(surfaces).difference(allowed_surfaces))
            if unknown_surfaces:
                errors.append(
                    f"{location}.surfaces contains unsupported {platform} surfaces: "
                    f"{', '.join(unknown_surfaces)}"
                )
    if len(link_kinds) != len(set(link_kinds)):
        errors.append("links cannot repeat the same kind")
    return errors


__all__ = ["validate_links"]
