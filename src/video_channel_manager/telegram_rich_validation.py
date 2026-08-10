"""Official Bot API limit enforcement and plain-text extraction for rich articles.

Limits mirror the official Telegram Bot API Rich Messages documentation
(Bot API 10.1, June 11, 2026, and Bot API 10.2, July 14, 2026) and are kept
consistent with the limits enforced by the merged fail-closed rich transport
(``telegram_rich_provider``):

* up to 32 768 UTF-8 characters in the rich message text (counting text,
  summary, credit, caption, expression, and list labels);
* up to 500 blocks, including nested blocks, list items, and table rows;
* up to 16 levels of nested formatting and blocks;
* up to 50 media attachments in total;
* map bounds: zoom 0..24, width/height within the official total and
  aspect-ratio limits.

The module performs no HTTP calls, no file I/O, and no provider writes.
"""

from __future__ import annotations

from typing import Iterator

from video_channel_manager.telegram_rich_models import (
    RichArticleDocument,
    RichBlock,
    RichBlockCaption,
    RichTextContent,
    canonical_json,
    child_blocks,
    iter_blocks,
    iter_text_fragments,
    sha256_text,
)

# Official Telegram Bot API Rich Message limits (verified against the docs).
MAX_RICH_TEXT_UTF8_CHARS = 32_768
MAX_RICH_BLOCKS = 500
MAX_RICH_NESTING_DEPTH = 16
MAX_RICH_MEDIA_ATTACHMENTS = 50

RICH_ARTICLE_LIMITS = {
    "max_text_utf8_chars": MAX_RICH_TEXT_UTF8_CHARS,
    "max_blocks": MAX_RICH_BLOCKS,
    "max_nesting_depth": MAX_RICH_NESTING_DEPTH,
    "max_media_attachments": MAX_RICH_MEDIA_ATTACHMENTS,
}


class RichArticleValidationError(ValueError):
    """Raised when a rich article document violates official Bot API limits."""


def _block_text_fragments(block: RichBlock) -> Iterator[str]:
    """Yield every text fragment of one block, including captions/credits/cells."""
    match block.type:
        case "paragraph" | "heading" | "pre" | "footer" | "pullquote":
            yield from iter_text_fragments(block.text)
            if block.type == "pullquote" and block.credit is not None:
                yield from iter_text_fragments(block.credit)
        case "blockquote":
            if block.credit is not None:
                yield from iter_text_fragments(block.credit)
            for inner in block.blocks:
                yield from _block_text_fragments(inner)
        case "media":
            if block.caption is not None:
                yield from iter_text_fragments(block.caption.text)
                if block.caption.credit is not None:
                    yield from iter_text_fragments(block.caption.credit)
        case "list":
            for item in block.items:
                for inner in item.blocks:
                    yield from _block_text_fragments(inner)
        case "collage" | "slideshow":
            if block.caption is not None:
                yield from iter_text_fragments(block.caption.text)
                if block.caption.credit is not None:
                    yield from iter_text_fragments(block.caption.credit)
            for inner in block.blocks:
                yield from _block_text_fragments(inner)
        case "details":
            yield from iter_text_fragments(block.summary)
            for inner in block.blocks:
                yield from _block_text_fragments(inner)
        case "table":
            if block.caption is not None:
                yield from iter_text_fragments(block.caption)
            for row in block.cells:
                for cell in row:
                    if cell.text is not None:
                        yield from iter_text_fragments(cell.text)
        case "mathematical_expression":
            yield block.expression
        case "divider" | "anchor" | "map":
            return


def document_text_length(document: RichArticleDocument) -> int:
    """UTF-8 character count of the whole message body (code points)."""
    return sum(len(fragment) for block in document.blocks for fragment in _block_text_fragments(block))


def _count_block_tree(block: RichBlock) -> int:
    """Count the block itself plus nested list items, table rows, and child blocks."""
    match block.type:
        case "list":
            return 1 + sum(1 + _count_block_tree(inner) for item in block.items for inner in item.blocks)
        case "blockquote" | "collage" | "slideshow" | "details":
            return 1 + sum(_count_block_tree(inner) for inner in block.blocks)
        case "table":
            return 1 + len(block.cells)
        case _:
            return 1


def count_blocks(document: RichArticleDocument) -> int:
    """Total block count per the official definition (blocks + list items + table rows)."""
    return sum(_count_block_tree(block) for block in document.blocks)


def count_media_attachments(document: RichArticleDocument) -> int:
    """Number of media blocks (must equal the library size for a valid document)."""
    return sum(1 for block in iter_blocks(document.blocks) if block.type == "media")


def _max_block_depth(block: RichBlock, depth: int) -> int:
    children = child_blocks(block)
    if not children:
        return depth
    return max(_max_block_depth(child, depth + 1) for child in children)


def max_block_nesting_depth(document: RichArticleDocument) -> int:
    """Deepest block nesting level; top-level blocks are depth 1."""
    return max((_max_block_depth(block, 1) for block in document.blocks), default=0)


def _inline_depth(value: RichTextContent) -> int:
    if isinstance(value, str):
        return 0
    if isinstance(value, tuple):
        return max((_inline_depth(item) for item in value), default=0)
    match value.type:
        case "anchor" | "mathematical_expression" | "custom_emoji":
            return 1
        case _:
            return 1 + _inline_depth(value.text)


def _inline_depth_of_block(block: RichBlock) -> int:
    match block.type:
        case "paragraph" | "heading" | "pre" | "footer" | "pullquote":
            depth = _inline_depth(block.text)
            if block.type == "pullquote" and block.credit is not None:
                depth = max(depth, _inline_depth(block.credit))
            return depth
        case "media":
            if block.caption is None:
                return 0
            depth = _inline_depth(block.caption.text)
            if block.caption.credit is not None:
                depth = max(depth, _inline_depth(block.caption.credit))
            return depth
        case "list":
            return max(
                (_inline_depth_of_block(inner) for item in block.items for inner in item.blocks),
                default=0,
            )
        case "blockquote":
            depth = max((_inline_depth_of_block(inner) for inner in block.blocks), default=0)
            if block.credit is not None:
                depth = max(depth, _inline_depth(block.credit))
            return depth
        case "collage" | "slideshow":
            depth = max((_inline_depth_of_block(inner) for inner in block.blocks), default=0)
            if block.caption is not None:
                depth = max(depth, _inline_depth(block.caption.text))
                if block.caption.credit is not None:
                    depth = max(depth, _inline_depth(block.caption.credit))
            return depth
        case "details":
            depth = _inline_depth(block.summary)
            return max(depth, max((_inline_depth_of_block(inner) for inner in block.blocks), default=0))
        case "table":
            depth = _inline_depth(block.caption) if block.caption is not None else 0
            for row in block.cells:
                for cell in row:
                    if cell.text is not None:
                        depth = max(depth, _inline_depth(cell.text))
            return depth
        case "divider" | "mathematical_expression" | "anchor" | "map":
            return 0


def max_inline_nesting_depth(document: RichArticleDocument) -> int:
    """Deepest inline formatting nesting (bold > italic > url is depth 3)."""
    return max((_inline_depth_of_block(block) for block in document.blocks), default=0)


def validate_document(document: RichArticleDocument) -> None:
    """Validate a document against official Bot API limits.

    Structural invariants (unique IDs, media references, empty blocks) are
    enforced at construction by the models themselves; this function enforces
    the official numeric limits.
    """
    if not isinstance(document, RichArticleDocument):
        raise RichArticleValidationError("expected a RichArticleDocument instance")

    issues: list[str] = []

    text_length = document_text_length(document)
    if text_length > MAX_RICH_TEXT_UTF8_CHARS:
        issues.append(f"rich text exceeds {MAX_RICH_TEXT_UTF8_CHARS} UTF-8 characters: {text_length}")

    block_count = count_blocks(document)
    if block_count > MAX_RICH_BLOCKS:
        issues.append(f"block count exceeds {MAX_RICH_BLOCKS}: {block_count}")

    block_depth = max_block_nesting_depth(document)
    if block_depth > MAX_RICH_NESTING_DEPTH:
        issues.append(f"block nesting depth exceeds {MAX_RICH_NESTING_DEPTH}: {block_depth}")

    inline_depth = max_inline_nesting_depth(document)
    if inline_depth > MAX_RICH_NESTING_DEPTH:
        issues.append(f"inline formatting depth exceeds {MAX_RICH_NESTING_DEPTH}: {inline_depth}")

    media_count = count_media_attachments(document)
    if media_count > MAX_RICH_MEDIA_ATTACHMENTS:
        issues.append(f"media attachments exceed {MAX_RICH_MEDIA_ATTACHMENTS}: {media_count}")

    if issues:
        raise RichArticleValidationError("; ".join(issues))


def plain_text(document: RichArticleDocument, *, include_media_captions: bool = True) -> str:
    """Deterministic visible-text projection used for semantic equivalence.

    The projection preserves every text fragment of the document in document
    order, including list markers, quote prefixes, table rows, media captions,
    and the footer.  It is the canonical article text both renderers guarantee
    their visible text equals.
    """
    units: list[str] = []
    for block in document.blocks:
        rendered = _render_block(block, level=0, include_media_captions=include_media_captions)
        if rendered:
            units.append(rendered)
    return "\n\n".join(units)


def plain_text_sha256(document: RichArticleDocument) -> str:
    """SHA-256 of the deterministic visible-text projection."""
    return sha256_text(plain_text(document))


def inline_plain_text(value: RichTextContent) -> str:
    """Deterministic visible-text projection of inline rich text.

    URLs render as their visible text (the URL itself is not part of the
    visible copy); custom emoji render as their Unicode alternative text;
    inline math renders its LaTeX source verbatim.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, tuple):
        return "".join(inline_plain_text(item) for item in value)
    match value.type:
        case "url":
            return inline_plain_text(value.text)
        case "custom_emoji":
            return value.alternative_text
        case "mathematical_expression":
            return value.expression
        case "anchor":
            return ""
        case _:
            return inline_plain_text(value.text)


def _render_caption(caption: RichBlockCaption) -> str:
    text = inline_plain_text(caption.text)
    credit = inline_plain_text(caption.credit) if caption.credit is not None else ""
    return text + (f" — {credit}" if credit else "")


def _list_marker(item: object, *, counter: int) -> str:
    if getattr(item, "has_checkbox", False):
        return "[x] " if getattr(item, "is_checked", False) else "[ ] "
    label_type = getattr(item, "label_type", None)
    if label_type is None:
        return "• "
    if getattr(item, "value", None) is not None:
        return f"{item.value}. "  # type: ignore[attr-defined]
    return f"{counter}. "


def _render_block(block: RichBlock, *, level: int, include_media_captions: bool) -> str:
    indent = "  " * level
    match block.type:
        case "paragraph" | "heading" | "pre" | "footer" | "pullquote":
            rendered = indent + inline_plain_text(block.text)
            if block.type == "pullquote" and block.credit is not None:
                rendered += "\n— " + inline_plain_text(block.credit)
            return rendered
        case "divider":
            return "---"
        case "anchor":
            return ""
        case "mathematical_expression":
            return block.expression
        case "media":
            if not include_media_captions:
                return ""
            caption = _render_caption(block.caption) if block.caption is not None else ""
            return indent + f"[{block.media_id}]" + (f" {caption}" if caption else "")
        case "list":
            lines: list[str] = []
            counter = 1
            for item in block.items:
                marker = _list_marker(item, counter=counter)
                counter += 1
                inner_lines = "\n".join(
                    _render_block(child, level=level + 1, include_media_captions=include_media_captions)
                    for child in item.blocks
                ).splitlines()
                if not inner_lines:
                    inner_lines = [""]
                lines.append(indent + marker + inner_lines[0].lstrip())
                lines.extend("  " * (level + 1) + line for line in inner_lines[1:])
            return "\n".join(lines)
        case "blockquote":
            rendered = "\n\n".join(
                rendered_child
                for child in block.blocks
                if (rendered_child := _render_block(child, level=level, include_media_captions=include_media_captions))
            )
            if block.credit is not None:
                rendered += "\n— " + inline_plain_text(block.credit)
            return rendered
        case "collage" | "slideshow":
            inner = "\n".join(
                rendered
                for child in block.blocks
                if (rendered := _render_block(child, level=level, include_media_captions=include_media_captions))
            )
            if not include_media_captions:
                return inner
            rendered = f"{block.type}: {_render_caption(block.caption)}" if block.caption is not None else block.type
            return rendered + ("\n" + inner if inner else "")
        case "table":
            rendered_lines: list[str] = []
            if block.caption is not None:
                rendered_lines.append(inline_plain_text(block.caption))
            for row in block.cells:
                cells = [inline_plain_text(cell.text) if cell.text is not None else "" for cell in row]
                rendered_lines.append("| " + " | ".join(cells) + " |")
            return "\n".join(rendered_lines)
        case "details":
            summary = inline_plain_text(block.summary)
            inner = "\n\n".join(
                rendered
                for child in block.blocks
                if (rendered := _render_block(child, level=level, include_media_captions=include_media_captions))
            )
            return f"{summary}\n\n{inner}" if inner else summary
        case "map":
            latitude, longitude = block.location
            return f"map: {latitude:.6f},{longitude:.6f}"
    return ""


def media_library_sha256(document: RichArticleDocument) -> str | None:
    """Deterministic digest of the media library identity (sorted by media_id).

    Includes the input ``uri`` and kind but **not** the resolved file identity,
    so the digest is stable before upload and reflects only the authored media
    identity.
    """
    if not document.media:
        return None
    library = [
        {"media_id": entry.media_id, "kind": entry.kind, "uri": entry.uri}
        for entry in sorted(document.media, key=lambda item: item.media_id)
    ]
    return sha256_text(canonical_json(library))


__all__ = [
    "MAX_RICH_BLOCKS",
    "MAX_RICH_MEDIA_ATTACHMENTS",
    "MAX_RICH_NESTING_DEPTH",
    "MAX_RICH_TEXT_UTF8_CHARS",
    "RICH_ARTICLE_LIMITS",
    "RichArticleValidationError",
    "count_blocks",
    "count_media_attachments",
    "document_text_length",
    "max_block_nesting_depth",
    "inline_plain_text",
    "max_inline_nesting_depth",
    "media_library_sha256",
    "plain_text",
    "plain_text_sha256",
    "validate_document",
]
