"""Native Telegram Bot API 10.2 rich-message renderer.

Bridges the provider-neutral ``RichArticleDocument`` to the exact document
shape consumed by the merged fail-closed transport (``telegram_rich_provider``):
``TelegramRichMessageDocument`` with

* ``input_rich_message`` — the exact ``InputRichMessage`` (``blocks`` form)
  that ``sendRichMessage`` receives;
* ``expected_returned_rich_message`` — the normalized ``RichMessage`` shape
  Telegram is expected to return in ``Message.rich_message`` (media blocks
  resolved to Bot API file objects, returned list items carry a ``label``,
  returned map zoom is clamped to the returned range).

Both shapes are validated by the transport's own validators at construction
time, so a renderer output that the transport rejects can never be published.

Mapping rules (deterministic, lossless for the supported vocabulary):

* paragraph/heading/pre/footer/divider/mathematical_expression/anchor/list/
  blockquote/pullquote/collage/slideshow/table/details/map/media are mapped
  onto their official ``InputRichBlock`` shapes;
* inline rich text is mapped onto official ``RichText`` entities (bold,
  italic, underline, strikethrough, spoiler, marked, code, subscript,
  superscript, url, custom emoji, reference/reference-link, anchor/
  anchor-link, math);
* media blocks use the media-library ``uri`` (file id, public URL, or
  ``attach://`` reference) for the input payload; the expected returned
  payload normally uses ``RichResolvedFile`` data.  A media block **without**
  a resolved file fails closed unless either (a) test-only expected
  placeholders are enabled, or (b) its exact HTTPS photo id is explicitly
  selected as provider-assigned URL media. The latter emits a reviewed
  sentinel plus exact recursive media paths for the transport's normalized
  evidence mode; callers must separately bind and re-prove the URL bytes.

The renderer performs no HTTP calls and no provider writes.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from video_channel_manager.telegram_rich_models import (
    RichArticleDocument,
    RichBlock,
    RichBlockAnchor,
    RichBlockCaption,
    RichBlockCollage,
    RichBlockDetails,
    RichBlockDivider,
    RichBlockFooter,
    RichBlockHeading,
    RichBlockList,
    RichBlockMap,
    RichBlockMath,
    RichBlockMedia,
    RichBlockParagraph,
    RichBlockPreformatted,
    RichBlockPullQuote,
    RichBlockQuote,
    RichBlockSlideshow,
    RichBlockTable,
    RichMediaItem,
    RichResolvedFile,
    RichTextContent,
    canonical_json,
    sha256_text,
)
from video_channel_manager.telegram_rich_provider import TelegramRichMessageDocument, TelegramRichTargetBinding
from video_channel_manager.telegram_rich_validation import plain_text, validate_document


class RichRenderResult(BaseModel):
    """Deterministic render output of one rich article document."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.rich-render-result"] = "video-channel-manager.rich-render-result"
    schema_version: Literal[1] = 1
    article_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    visible_text: str
    media_placeholders: tuple[str, ...] = ()
    provider_assigned_media: tuple[str, ...] = ()
    render_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


def _inline(value: RichTextContent) -> object:
    """Map one inline rich text node onto the official RichText shape."""
    if isinstance(value, str):
        return value
    if isinstance(value, tuple):
        return [_inline(item) for item in value]
    match value.type:
        case "bold":
            return {"type": "bold", "text": _inline(value.text)}
        case "italic":
            return {"type": "italic", "text": _inline(value.text)}
        case "underline":
            return {"type": "underline", "text": _inline(value.text)}
        case "strikethrough":
            return {"type": "strikethrough", "text": _inline(value.text)}
        case "spoiler":
            return {"type": "spoiler", "text": _inline(value.text)}
        case "marked":
            return {"type": "marked", "text": _inline(value.text)}
        case "code":
            return {"type": "code", "text": _inline(value.text)}
        case "subscript":
            return {"type": "subscript", "text": _inline(value.text)}
        case "superscript":
            return {"type": "superscript", "text": _inline(value.text)}
        case "url":
            return {"type": "url", "text": _inline(value.text), "url": value.url}
        case "custom_emoji":
            return {
                "type": "custom_emoji",
                "custom_emoji_id": value.custom_emoji_id,
                "alternative_text": value.alternative_text,
            }
        case "reference":
            return {"type": "reference", "name": value.name, "text": _inline(value.text)}
        case "reference_link":
            return {"type": "reference_link", "reference_name": value.reference_name, "text": _inline(value.text)}
        case "anchor":
            return {"type": "anchor", "name": value.name}
        case "anchor_link":
            return {"type": "anchor_link", "anchor_name": value.anchor_name, "text": _inline(value.text)}
        case "mathematical_expression":
            return {"type": "mathematical_expression", "expression": value.expression}
    raise ValueError(f"unsupported inline rich text entity: {getattr(value, 'type', type(value).__name__)}")


def _inline_content(value: RichTextContent) -> object:
    """Map a rich text content (str, entity, or tuple) onto the official shape."""
    if isinstance(value, tuple):
        if len(value) == 1:
            return _inline(value[0])
        return [_inline(item) for item in value]
    return _inline(value)


def _caption(caption: RichBlockCaption | None) -> dict[str, object] | None:
    if caption is None:
        return None
    payload: dict[str, object] = {"text": _inline_content(caption.text)}
    if caption.credit is not None:
        payload["credit"] = _inline_content(caption.credit)
    return payload


def _media_input(media: RichMediaItem) -> dict[str, object]:
    return {"type": media.kind, "media": media.uri}


def _media_returned(media: RichMediaItem, resolved: RichResolvedFile) -> dict[str, object]:
    if media.kind == "photo":
        photo_size: dict[str, object] = {
            "file_id": resolved.file_id,
            "file_unique_id": resolved.file_unique_id,
            "width": resolved.width if resolved.width is not None else 0,
            "height": resolved.height if resolved.height is not None else 0,
        }
        if resolved.file_size is not None:
            photo_size["file_size"] = resolved.file_size
        return {"type": "photo", "photo": [photo_size]}
    file_object: dict[str, object] = {
        "file_id": resolved.file_id,
        "file_unique_id": resolved.file_unique_id,
    }
    if media.kind in {"video", "animation"}:
        file_object["width"] = resolved.width if resolved.width is not None else 0
        file_object["height"] = resolved.height if resolved.height is not None else 0
    if media.kind in {"video", "animation", "audio", "voice_note"}:
        file_object["duration"] = resolved.duration if resolved.duration is not None else 0
    return {"type": media.kind, media.kind: file_object}


def _placeholder_resolved(media: RichMediaItem) -> RichResolvedFile:
    """Deterministic placeholder file identity for expected-structure tests."""
    marker = sha256_text(media.media_id).removeprefix("sha256:")[:16]
    return RichResolvedFile(
        file_id=f"expected://{media.media_id}",
        file_unique_id=f"expected_{marker}",
        width=1,
        height=1,
        duration=0,
    )


def _provider_assigned_resolved(media: RichMediaItem) -> RichResolvedFile:
    """Reviewed sentinel for URL photos whose file objects only exist after fetch."""
    if media.kind != "photo" or not media.uri.startswith("https://"):
        raise ValueError("provider-assigned media evidence currently requires an HTTPS photo")
    return RichResolvedFile(
        file_id="<provider-assigned-file-id>",
        file_unique_id="<provider-assigned-file-unique-id>",
        width=1,
        height=1,
    )


def _list_marker_label(item: object, *, counter: int) -> str:
    if getattr(item, "has_checkbox", False):
        return "[x]" if getattr(item, "is_checked", False) else "[ ]"
    if getattr(item, "label_type", None) is None:
        return "•"
    number = getattr(item, "value", None)
    if number is None:
        number = counter
    return f"{number}."


def _block_input(block: RichBlock) -> dict[str, object]:
    """Map one document block onto the outgoing InputRichBlock shape.

    Media blocks are handled by the media-aware renderer (they need the media
    library), so this function only handles non-media block types.
    """
    if isinstance(block, RichBlockParagraph):
        return {"type": "paragraph", "text": _inline_content(block.text)}
    if isinstance(block, RichBlockHeading):
        return {"type": "heading", "text": _inline_content(block.text), "size": block.size}
    if isinstance(block, RichBlockPreformatted):
        payload: dict[str, object] = {"type": "pre", "text": _inline_content(block.text)}
        if block.language is not None:
            payload["language"] = block.language
        return payload
    if isinstance(block, RichBlockFooter):
        return {"type": "footer", "text": _inline_content(block.text)}
    if isinstance(block, RichBlockDivider):
        return {"type": "divider"}
    if isinstance(block, RichBlockMath):
        return {"type": "mathematical_expression", "expression": block.expression}
    if isinstance(block, RichBlockAnchor):
        return {"type": "anchor", "name": block.name}
    if isinstance(block, RichBlockList):
        return {"type": "list"}  # items are assembled by the media-aware renderer
    if isinstance(block, RichBlockQuote):
        payload = {"type": "blockquote"}
        if block.credit is not None:
            payload["credit"] = _inline_content(block.credit)
        return payload
    if isinstance(block, RichBlockPullQuote):
        payload = {"type": "pullquote", "text": _inline_content(block.text)}
        if block.credit is not None:
            payload["credit"] = _inline_content(block.credit)
        return payload
    if isinstance(block, (RichBlockCollage, RichBlockSlideshow)):
        container_payload: dict[str, object] = {"type": block.type}
        caption = _caption(block.caption)
        if caption is not None:
            container_payload["caption"] = caption
        return container_payload
    if isinstance(block, RichBlockTable):
        table_payload: dict[str, object] = {
            "type": "table",
            "cells": [
                [
                    {
                        **({"text": _inline_content(cell.text)} if cell.text is not None else {}),
                        **({"is_header": True} if cell.is_header else {}),
                        **({"colspan": cell.colspan} if cell.colspan > 1 else {}),
                        **({"rowspan": cell.rowspan} if cell.rowspan > 1 else {}),
                        "align": cell.align,
                        "valign": cell.valign,
                    }
                    for cell in row
                ]
                for row in block.cells
            ],
        }
        if block.is_bordered:
            table_payload["is_bordered"] = True
        if block.is_striped:
            table_payload["is_striped"] = True
        if block.caption is not None:
            table_payload["caption"] = _inline_content(block.caption)
        return table_payload
    if isinstance(block, RichBlockDetails):
        details_payload: dict[str, object] = {"type": "details", "summary": _inline_content(block.summary)}
        if block.is_open:
            details_payload["is_open"] = True
        return details_payload
    if isinstance(block, RichBlockMap):
        latitude, longitude = block.location
        map_payload: dict[str, object] = {
            "type": "map",
            "location": {"latitude": latitude, "longitude": longitude},
            "zoom": block.zoom,
            "width": block.width,
            "height": block.height,
        }
        caption = _caption(block.caption)
        if caption is not None:
            map_payload["caption"] = caption
        return map_payload
    if isinstance(block, RichBlockMedia):
        raise ValueError("media blocks require the media library; use the media-aware renderer")
    raise ValueError(f"unsupported document block: {type(block).__name__}")


def _media_block_input(block: RichBlockMedia, media: RichMediaItem) -> dict[str, object]:
    payload: dict[str, object] = {"type": media.kind, media.kind: _media_input(media)}
    caption = _caption(block.caption)
    if caption is not None:
        payload["caption"] = caption
    return payload


def _media_block_returned(block: RichBlockMedia, media: RichMediaItem, resolved: RichResolvedFile) -> dict[str, object]:
    payload = _media_returned(media, resolved)
    caption = _caption(block.caption)
    if caption is not None:
        payload["caption"] = caption
    return payload


def _build_blocks(
    document: RichArticleDocument,
    *,
    returned: bool,
    placeholders: list[str],
    allow_placeholders: bool,
    provider_assigned_media_ids: frozenset[str],
) -> list[dict[str, object]]:
    media_by_id = {entry.media_id: entry for entry in document.media}
    blocks: list[dict[str, object]] = []

    def render_block(block: RichBlock) -> dict[str, object]:
        if isinstance(block, RichBlockMedia):
            media = media_by_id[block.media_id]
            if not returned:
                return _media_block_input(block, media)
            if media.media_id in provider_assigned_media_ids:
                return _media_block_returned(block, media, _provider_assigned_resolved(media))
            if media.resolved is not None:
                return _media_block_returned(block, media, media.resolved)
            if not allow_placeholders:
                raise ValueError(
                    f"media block {block.block_id} has no resolved file identity; "
                    "resolved media is required to build an honest expected RichMessage"
                )
            placeholders.append(media.media_id)
            return _media_block_returned(block, media, _placeholder_resolved(media))
        if isinstance(block, RichBlockList):
            items: list[dict[str, object]] = []
            counter = 1
            for item in block.items:
                entry: dict[str, object] = {
                    "blocks": [render_block(child) for child in item.blocks],
                }
                if returned:
                    entry["label"] = _list_marker_label(item, counter=counter)
                    if item.label_type is not None:
                        entry["type"] = item.label_type
                    if item.value is not None:
                        entry["value"] = item.value
                else:
                    if item.label_type is not None:
                        entry["type"] = item.label_type
                    if item.value is not None:
                        entry["value"] = item.value
                    if item.has_checkbox:
                        entry["has_checkbox"] = True
                    if item.is_checked:
                        entry["is_checked"] = True
                items.append(entry)
                counter += 1
            return {"type": "list", "items": items}
        if isinstance(block, (RichBlockQuote, RichBlockCollage, RichBlockSlideshow, RichBlockDetails)):
            payload = _block_input(block)
            children: list[dict[str, object]] = []
            for child in block.blocks:
                children.append(render_block(child))
            payload["blocks"] = children
            return payload
        if isinstance(block, RichBlockMap) and returned:
            payload = _block_input(block)
            latitude, longitude = block.location
            payload["location"] = {"latitude": latitude, "longitude": longitude}
            payload["zoom"] = max(13, min(20, block.zoom))
            return payload
        return _block_input(block)

    for block in document.blocks:
        blocks.append(render_block(block))
    return blocks


def _provider_assigned_media_paths(
    blocks: list[dict[str, object]],
    *,
    selected_uris: frozenset[str],
) -> tuple[str, ...]:
    paths: list[str] = []

    def walk(value: object, path: str) -> None:
        if isinstance(value, dict):
            block_type = value.get("type")
            media = (
                value.get(str(block_type))
                if block_type in {"photo", "video", "animation", "audio", "voice_note"}
                else None
            )
            if isinstance(media, dict) and media.get("media") in selected_uris:
                paths.append(path)
            for key, child in value.items():
                walk(child, f"{path}/{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}/{index}")

    walk(blocks, "$/blocks")
    return tuple(paths)


def render_rich_document(
    document: RichArticleDocument,
    target: TelegramRichTargetBinding,
    *,
    publication_id: str | None = None,
    allow_expected_placeholders: bool = False,
    provider_assigned_media_ids: tuple[str, ...] = (),
    skip_entity_detection: bool = False,
) -> tuple[TelegramRichMessageDocument, RichRenderResult]:
    """Render a rich article document into the transport's exact document.

    Returns ``(telegram_document, render_result)`` where ``render_result``
    carries the deterministic article digest, visible-text projection, media
    placeholder notes, and a render digest over the produced input/expected
    structures.
    """
    validate_document(document)
    selected_provider_media = frozenset(provider_assigned_media_ids)
    if len(selected_provider_media) != len(provider_assigned_media_ids):
        raise ValueError("provider-assigned media ids must be unique")
    media_by_id = {entry.media_id: entry for entry in document.media}
    if not selected_provider_media.issubset(media_by_id):
        raise ValueError("provider-assigned media id is absent from the article media library")
    for media_id in selected_provider_media:
        media = media_by_id[media_id]
        if media.resolved is not None:
            raise ValueError("provider-assigned URL media must not claim a pre-existing resolved file")
        _provider_assigned_resolved(media)

    placeholders: list[str] = []
    input_blocks = _build_blocks(
        document,
        returned=False,
        placeholders=placeholders,
        allow_placeholders=allow_expected_placeholders,
        provider_assigned_media_ids=selected_provider_media,
    )
    expected_blocks = _build_blocks(
        document,
        returned=True,
        placeholders=placeholders,
        allow_placeholders=allow_expected_placeholders,
        provider_assigned_media_ids=selected_provider_media,
    )

    input_rich_message: dict[str, Any] = {"blocks": input_blocks}
    if skip_entity_detection:
        input_rich_message["skip_entity_detection"] = True
    expected_returned_rich_message: dict[str, Any] = {"blocks": expected_blocks}
    selected_uris = frozenset(media_by_id[media_id].uri for media_id in selected_provider_media)
    provider_media_paths = _provider_assigned_media_paths(input_blocks, selected_uris=selected_uris)
    if len(provider_media_paths) != len(selected_provider_media):
        raise ValueError("provider-assigned media ids do not map one-to-one onto exact rich block paths")

    effective_publication_id = publication_id or document.document_id
    telegram_document = TelegramRichMessageDocument(
        schema_name="video-channel-manager.telegram-rich-message-document",
        schema_version=1,
        publication_id=effective_publication_id,
        target=target,
        input_rich_message=input_rich_message,
        expected_returned_rich_message=expected_returned_rich_message,
        provider_assigned_media_paths=provider_media_paths,
    )

    render_payload: dict[str, Any] = {
        "article_digest": document.digest,
        "input_rich_message": telegram_document.input_rich_message,
        "expected_returned_rich_message": telegram_document.expected_returned_rich_message,
        "visible_text": plain_text(document),
        "media_placeholders": list(dict.fromkeys(placeholders)),
        "provider_assigned_media": list(provider_assigned_media_ids),
    }
    result = RichRenderResult(
        schema_name="video-channel-manager.rich-render-result",
        schema_version=1,
        article_digest=document.digest,
        visible_text=plain_text(document),
        media_placeholders=tuple(dict.fromkeys(placeholders)),
        provider_assigned_media=provider_assigned_media_ids,
        render_sha256=sha256_text(canonical_json(render_payload)),
    )
    return telegram_document, result


__all__ = [
    "RichRenderResult",
    "render_rich_document",
]
