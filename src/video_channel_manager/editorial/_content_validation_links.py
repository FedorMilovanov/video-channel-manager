from __future__ import annotations

from typing import Any

from video_channel_manager.editorial._content_types import (
    ALLOWED_LINK_KINDS,
    ALLOWED_SURFACES,
    APPROVED_PROJECT_URLS,
)
from video_channel_manager.editorial._content_urls import balanced_emphasis, canonicalize_url, contains_banned_circle
from video_channel_manager.editorial._content_validation_support import _string_list


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
        kind = str(raw_value.get("kind") or "").strip()
        label = str(raw_value.get("label") or "").strip()
        url = str(raw_value.get("url") or "").strip()
        link_kinds.append(kind)
        if kind not in ALLOWED_LINK_KINDS:
            errors.append(f"links[{index}].kind is unsupported")
        if not label or "\n" in label:
            errors.append(f"links[{index}].label must be one compact line")
        if not balanced_emphasis(label):
            errors.append(f"links[{index}].label has unbalanced emphasis")
        if contains_banned_circle(label):
            errors.append("colored circle markers are not allowed")
        try:
            canonical_url = canonicalize_url(url)
        except ValueError as exc:
            errors.append(f"links[{index}].url: {exc}")
            canonical_url = ""
        if canonical_url and canonical_url not in allowed_urls:
            errors.append(f"links[{index}].url is absent from sources/project link map: {canonical_url}")
        platforms = _string_list(raw_value.get("platforms"))
        surfaces = _string_list(raw_value.get("surfaces"))
        for platform in platforms:
            if platform not in ALLOWED_SURFACES:
                errors.append(f"links[{index}].platforms contains unsupported platform: {platform}")
        if surfaces and not platforms:
            errors.append(f"links[{index}].surfaces requires platforms")
        for platform in platforms:
            allowed_surfaces = ALLOWED_SURFACES.get(platform)
            if allowed_surfaces is None:
                continue
            unknown_surfaces = sorted(set(surfaces).difference(allowed_surfaces))
            if unknown_surfaces:
                errors.append(
                    f"links[{index}].surfaces contains unsupported {platform} surfaces: {', '.join(unknown_surfaces)}"
                )
    if len(link_kinds) != len(set(link_kinds)):
        errors.append("links cannot repeat the same kind")
    return errors


__all__ = ["validate_links"]
