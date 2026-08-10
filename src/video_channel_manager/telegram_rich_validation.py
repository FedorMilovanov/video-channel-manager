"""Official Bot API limit enforcement and plain-text extraction for rich articles.

Limits mirror the official Telegram Bot API Rich Messages documentation
(Bot API 10.1, June 11, 2026, and Bot API 10.2, July 14, 2026;
https://core.telegram.org/bots/api):

* up to 32 768 UTF-8 characters in the rich message text, including custom
  emoji alternative text and formula source;
* up to 500 blocks, including nested blocks, list items, ordered list items,
  table rows, quotation blocks, and details blocks;
* up to 16 levels of nested formatting and blocks;
* up to 50 media attachments in total (photos, videos, audio files);
* up to 20 columns in a table.

Assumptions recorded for the PR (conservative readings where the official text
is silent):

* "UTF-8 characters" is interpreted as Unicode code points (``len()``), which
  matches how message text length is measured elsewhere in this repository.
* Media block *alt_text* (accessibility metadata) is not counted toward the
  32 768-character limit; visible captions, credits, and table captions are.
* Media blocks are only placed at the document top level or as direct children
  of collage/slideshow blocks ("media blocks can only be specified as separate
  blocks" in the official docs, and collages/slideshows are explicitly defined
  as collections of media blocks).  Media nested inside list items, quotations,
  or details blocks is rejected.
* The block count includes the block itself, every list item, and every table
  row, per the official wording.

The module performs no HTTP calls, no file I/O, and no provider writes.
"""

from __future__ import annotations

from typing import Iterator

from video_channel_manager.telegram_rich_models import (
    RichArticleDocument,
    RichBlock,
    RichBlockCaption,
    RichMediaRef,
    RichTextContent,
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
MAX_TABLE_COLUMNS = 20

# Conservative repository policy (see module docstring): media blocks live at
# the document top level or directly inside collage/slideshow blocks.
MEDIA_ALLOWED_PARENTS = frozenset({"document", "collage", "slideshow"})

RICH_ARTICLE_LIMITS = {
    "max_text_utf8_chars": MAX_RICH_TEXT_UTF8_CHARS,
    "max_blocks": MAX_RICH_BLOCKS,
    "max_nesting_depth": MAX_RICH_NESTING_DEPTH,
    "max_media_attachments": MAX_RICH_MEDIA_ATTACHMENTS,
    "max_table_columns": MAX_TABLE_COLUMNS,
}


class RichArticleValidationError(ValueError):
    """Raised when a rich article document violates official Bot API limits."""


def _block_text_fragments(block: RichBlock) -> Iterator[str]:
    """Yield every text fragment of one block, including captions/credits/cells."""
    match block.type:
        case "paragraph" | "heading" | "pre" | "footer":
            yield from iter_text_fragments(block.text)
        case "pullquote":
            yield from iter_text_fragments(block.text)
            if block.credit is not None:
                yield from iter_text_fragments(block.credit)
        case "media":
            if block.caption is not None:
                yield from iter_text_fragments(block.caption.text)
                if block.caption.credit is not None:
                    yield from iter_text_fragments(block.caption.credit)
        case "list":
            for item in block.items:
                for inner in item.blocks:
                    yield from _block_text_fragments(inner)
        case "blockquote":
            if block.credit is not None:
                yield from iter_text_fragments(block.credit)
            for inner in block.blocks:
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
        case "divider" | "mathematical_expression":
            return


def document_text_length(document: RichArticleDocument) -> int:
    """UTF-8 character count of the whole message body (code points).

    Counts plain text, custom emoji alternative text, formula sources, captions,
    credits, table captions, and cell text across every block.  Media ``alt_text``
    metadata is intentionally not counted (it is not rendered into the message).
    """
    return sum(len(fragment) for block in document.blocks for fragment in _block_text_fragments(block))


def _count_block_tree(block: RichBlock) -> int:
    """Count the block itself plus nested list items, table rows, and child blocks."""
    match block.type:
        case "list":
            total = 1
            for item in block.items:
                total += 1
                for inner in item.blocks:
                    total += _count_block_tree(inner)
            return total
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
    # A formatting entity contributes one level plus its inner text depth.
    match value.type:
        case "anchor" | "mathematical_expression" | "custom_emoji":
            return 1
        case _:
            return 1 + _inline_depth(value.text)


def _inline_depth_of_block(block: RichBlock) -> int:
    match block.type:
        case "paragraph" | "heading" | "pre" | "footer":
            return _inline_depth(block.text)
        case "pullquote":
            depth = _inline_depth(block.text)
            if block.credit is not None:
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
        case "divider" | "mathematical_expression":
            return 0


def max_inline_nesting_depth(document: RichArticleDocument) -> int:
    """Deepest inline formatting nesting (bold > italic > url is depth 3)."""
    return max((_inline_depth_of_block(block) for block in document.blocks), default=0)


def max_table_columns(document: RichArticleDocument) -> int:
    """Widest table row in the document."""
    width = 0
    for block in iter_blocks(document.blocks):
        match block.type:
            case "table":
                width = max(width, max(len(row) for row in block.cells))
            case _:
                pass
    return width


def _media_placement_violations(blocks: tuple[RichBlock, ...], parent: str) -> Iterator[str]:
    for block in blocks:
        if block.type == "media" and parent not in MEDIA_ALLOWED_PARENTS:
            yield block.block_id
        match block.type:
            case "list":
                for item in block.items:
                    yield from _media_placement_violations(item.blocks, "list")
            case "blockquote" | "details":
                yield from _media_placement_violations(block.blocks, block.type)
            case "collage" | "slideshow":
                yield from _media_placement_violations(block.blocks, block.type)
            case _:
                pass


def validate_document(document: RichArticleDocument) -> None:
    """Validate a document against official Bot API limits.

    Raises :class:`RichArticleValidationError` with every violation found.
    Structural invariants (unique IDs, media references, empty blocks) are
    enforced at construction by the models themselves; this function enforces
    the official numeric limits and the media placement policy.
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

    columns = max_table_columns(document)
    if columns > MAX_TABLE_COLUMNS:
        issues.append(f"table columns exceed {MAX_TABLE_COLUMNS}: {columns}")

    misplaced = sorted(_media_placement_violations(document.blocks, "document"))
    if misplaced:
        issues.append("media blocks outside top-level/collage/slideshow: " + ", ".join(misplaced))

    if issues:
        raise RichArticleValidationError("; ".join(issues))


def plain_text(document: RichArticleDocument) -> str:
    """Deterministic plain-text rendering used for fallback and semantic checks.

    The output is stable: same document, same string.  It is not a Telegram
    payload; renderers produce the actual fallback message from the model.
    """
    media_by_id = {entry.media_id: entry for entry in document.media}
    return "\n\n".join(_render_block(block, level=0, media_by_id=media_by_id) for block in document.blocks)


def plain_text_sha256(document: RichArticleDocument) -> str:
    """SHA-256 of the deterministic plain-text rendering (semantic verification)."""
    return sha256_text(plain_text(document))


def _render_inline(value: RichTextContent) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, tuple):
        return "".join(_render_inline(item) for item in value)
    match value.type:
        case "url":
            return f"{_render_inline(value.text)} ({value.url})"
        case "custom_emoji":
            return value.alternative_text
        case "mathematical_expression":
            return value.expression
        case "anchor":
            return ""
        case _:
            return _render_inline(value.text)


def _render_caption(caption: RichBlockCaption) -> str:
    text = _render_inline(caption.text)
    credit = _render_inline(caption.credit) if caption.credit is not None else ""
    return text + (f" — {credit}" if credit else "")


def _render_block(block: RichBlock, *, level: int, media_by_id: dict[str, RichMediaRef]) -> str:
    indent = "  " * level
    match block.type:
        case "paragraph" | "heading" | "pre" | "footer":
            return indent + _render_inline(block.text)
        case "pullquote":
            rendered = "> " + _render_inline(block.text)
            if block.credit is not None:
                rendered += "\n> — " + _render_inline(block.credit)
            return rendered
        case "divider":
            return "---"
        case "mathematical_expression":
            return f"$${block.expression}$$"
        case "media":
            media = media_by_id[block.media_id]
            label = f"[{media.kind}]"
            caption = _render_caption(block.caption) if block.caption is not None else ""
            alt = media.alt_text or ""
            return indent + " ".join(part for part in (label, caption or alt) if part)
        case "list":
            lines: list[str] = []
            counter = 1
            for item in block.items:
                if item.has_checkbox:
                    marker = "[x] " if item.is_checked else "[ ] "
                elif item.label_type is None:
                    marker = "- "
                elif item.value is not None:
                    marker = f"{item.value}. "
                else:
                    marker = f"{counter}. "
                counter += 1
                inner_lines = "\n".join(
                    _render_block(child, level=level + 1, media_by_id=media_by_id) for child in item.blocks
                ).splitlines()
                if not inner_lines:
                    inner_lines = [""]
                lines.append(indent + marker + inner_lines[0].lstrip())
                lines.extend("  " * (level + 1) + line for line in inner_lines[1:])
            return "\n".join(lines)
        case "blockquote":
            inner = "\n".join(_render_block(child, level=level, media_by_id=media_by_id) for child in block.blocks)
            rendered = "\n".join("> " + line for line in inner.splitlines())
            if block.credit is not None:
                rendered += "\n> — " + _render_inline(block.credit)
            return rendered
        case "collage" | "slideshow":
            inner = "\n".join(_render_block(child, level=level + 1, media_by_id=media_by_id) for child in block.blocks)
            rendered = f"{block.type}: {_render_caption(block.caption)}" if block.caption is not None else block.type
            return rendered + "\n" + inner
        case "table":
            rendered_lines: list[str] = []
            if block.caption is not None:
                rendered_lines.append(_render_inline(block.caption))
            for row in block.cells:
                cells = [_render_inline(cell.text) if cell.text is not None else "" for cell in row]
                rendered_lines.append("| " + " | ".join(cells) + " |")
            return "\n".join(rendered_lines)
        case "details":
            summary = _render_inline(block.summary)
            inner = "\n".join(_render_block(child, level=level + 1, media_by_id=media_by_id) for child in block.blocks)
            return f"{summary}\n{inner}"
    return ""
