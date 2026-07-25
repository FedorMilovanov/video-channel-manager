from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, cast

from video_channel_manager.editorial.content import EditorialContentRecord, parse_content_record
from video_channel_manager.editorial.rendering import ContentRenderer, ContentSurface, PlatformName, RenderedContent
from video_channel_manager.platforms.vk.renderers import VKCommentRenderer, VKPostRenderer, VKVideoDescriptionRenderer
from video_channel_manager.platforms.youtube.renderers import YouTubeCommentRenderer, YouTubeDescriptionRenderer


@dataclass(frozen=True, slots=True)
class ContentPreview:
    record: EditorialContentRecord
    rendered: RenderedContent


@dataclass(frozen=True, slots=True)
class BatchPreview:
    items: tuple[ContentPreview, ...]
    errors: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return not self.errors and all(item.rendered.is_valid for item in self.items)


def renderer_for(platform: str, surface: str | None = None) -> ContentRenderer:
    normalized_platform = platform.strip().lower()
    normalized_surface = (surface or "").strip().lower()
    if normalized_platform == "youtube":
        selected = normalized_surface or "comment"
        if selected == "comment":
            return YouTubeCommentRenderer()
        if selected == "description":
            return YouTubeDescriptionRenderer()
    if normalized_platform == "vk":
        selected = normalized_surface or "video_description"
        if selected == "video_description":
            return VKVideoDescriptionRenderer()
        if selected == "post":
            return VKPostRenderer()
        if selected == "comment":
            return VKCommentRenderer()
    raise ValueError(f"Unsupported platform/surface combination: {platform}.{surface or ''}")


def preview_payload(
    payload: dict[str, Any],
    *,
    platform: str,
    surface: str | None = None,
    expected_channel_id: str | None = None,
) -> ContentPreview:
    record = parse_content_record(payload, expected_channel_id=expected_channel_id)
    renderer = renderer_for(platform, surface)
    return ContentPreview(record=record, rendered=renderer.render(record))


def preview_records(
    records: list[EditorialContentRecord],
    *,
    platform: str,
    surface: str | None = None,
) -> BatchPreview:
    renderer = renderer_for(platform, surface)
    items = tuple(ContentPreview(record=record, rendered=renderer.render(record)) for record in records)
    errors: list[str] = []
    variation_counts = Counter(item.record.variation_key for item in items)
    duplicate_variations = sorted(key for key, count in variation_counts.items() if count > 1)
    if duplicate_variations:
        errors.append(f"duplicate variation keys: {', '.join(duplicate_variations)}")
    rendered_counts = Counter(item.rendered.text for item in items)
    duplicate_texts = sum(1 for text, count in rendered_counts.items() if text and count > 1)
    if duplicate_texts:
        errors.append(f"duplicate rendered texts: {duplicate_texts}")
    content_counts = Counter(item.record.content_id for item in items)
    duplicate_content_ids = sorted(key for key, count in content_counts.items() if count > 1)
    if duplicate_content_ids:
        errors.append(f"duplicate content IDs: {', '.join(duplicate_content_ids)}")
    return BatchPreview(items=items, errors=tuple(errors))


def normalized_platform_surface(platform: str, surface: str | None) -> tuple[PlatformName, ContentSurface]:
    renderer = renderer_for(platform, surface)
    return cast(PlatformName, renderer.platform), cast(ContentSurface, renderer.surface)


__all__ = [
    "BatchPreview",
    "ContentPreview",
    "normalized_platform_surface",
    "preview_payload",
    "preview_records",
    "renderer_for",
]
