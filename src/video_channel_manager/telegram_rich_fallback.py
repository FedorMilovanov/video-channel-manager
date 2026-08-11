"""Legacy Telegram HTML fallback for rich articles.

Produces one deterministic legacy ``parse_mode="HTML"`` message payload from a
``RichArticleDocument`` for transports that only speak the classic HTML parse
mode.  The fallback is chosen **before** any rich mutation; it is never
followed after an ambiguous ``sendRichMessage`` (the fail-closed transport
already enforces that).

Rendering rules:

* verified legacy tags only: ``<b>``, ``<i>``, ``<u>``, ``<s>``,
  ``<tg-spoiler>``, ``<code>``, ``<pre>`` (+ language), ``<a href>``,
  ``<blockquote>``;
* all text and URL attributes are HTML-escaped;
* paragraphs keep their blank-line separation with no doubled/trailing blank
  lines;
* Unicode emoji pass through as plain text; premium custom emoji downgrade to
  their Unicode alternative text and are recorded as a downgrade note
  (``<tg-emoji>`` is never emitted);
* media blocks are unsupported in legacy text mode and are dropped with a
  recorded downgrade note (the fallback is a plain-text backup only);
* every feature the classic surface cannot express (tables, formulas,
  footnotes, details, dividers, marked/subscript/superscript, maps) downgrades
  deterministically with an explicit note and never loses text content.

The plain text of the fallback is exactly the document's visible-text
projection without media captions (``plain_text(..., include_media_captions=False)``),
and the entities are derived by the repository's canonical
``parse_telegram_html`` parser, so the fallback payload is consistent with the
existing legacy message pipeline.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from video_channel_manager.telegram_html_entities import GenericMessageEntity, parse_telegram_html
from video_channel_manager.telegram_rich_models import (
    RichArticleDocument,
    RichBlock,
    RichBlockAnchor,
    RichBlockTable,
    RichBlockSlideshow,
    RichBlockQuote,
    RichBlockPullQuote,
    RichBlockPreformatted,
    RichBlockParagraph,
    RichBlockMath,
    RichBlockMap,
    RichBlockList,
    RichBlockHeading,
    RichBlockFooter,
    RichBlockDivider,
    RichBlockDetails,
    RichBlockCollage,
    RichBlockMedia,
    RichTextContent,
    canonical_json,
    sha256_text,
)
from video_channel_manager.telegram_rich_validation import inline_plain_text, plain_text

MAX_LEGACY_TEXT = 4096


class RichHtmlFallback(BaseModel):
    """Deterministic legacy HTML fallback structure for one rich article."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.rich-html-fallback"] = "video-channel-manager.rich-html-fallback"
    schema_version: Literal[1] = 1
    article_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    publication_id: str = Field(min_length=1, max_length=96)
    html_text: str
    expected_plain_text: str
    expected_entities: tuple[GenericMessageEntity, ...]
    downgrades: tuple[str, ...] = ()
    fallback_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_fallback(self) -> "RichHtmlFallback":
        if len(self.expected_plain_text) > MAX_LEGACY_TEXT:
            raise ValueError(f"legacy fallback exceeds {MAX_LEGACY_TEXT} plain-text characters")
        reparsed_plain, reparsed_entities = parse_telegram_html(self.html_text)
        if reparsed_plain != self.expected_plain_text:
            raise ValueError("fallback html does not round-trip to its expected plain text")
        if tuple(reparsed_entities) != tuple(self.expected_entities):
            raise ValueError("fallback html entities differ from the expected entities")
        if "tg-emoji" in self.html_text:
            raise ValueError("legacy fallback must never emit premium emoji tags")
        return self


def _inline_html(value: RichTextContent, *, downgrades: list[str]) -> str:
    if isinstance(value, str):
        return html.escape(value, quote=False)
    if isinstance(value, tuple):
        return "".join(_inline_html(item, downgrades=downgrades) for item in value)
    match value.type:
        case "bold":
            return f"<b>{_inline_html(value.text, downgrades=downgrades)}</b>"
        case "italic":
            return f"<i>{_inline_html(value.text, downgrades=downgrades)}</i>"
        case "url":
            return (
                f'<a href="{html.escape(value.url, quote=True)}">{_inline_html(value.text, downgrades=downgrades)}</a>'
            )
        case "hashtag":
            return _inline_html(value.text, downgrades=downgrades)
        case "custom_emoji":
            downgrades.append(f"custom_emoji:{value.custom_emoji_id}:unicode_fallback")
            return html.escape(value.alternative_text, quote=False)
        case "mathematical_expression":
            downgrades.append("formula:plain_text")
            return html.escape(value.expression, quote=False)
        case "anchor":
            return ""
        case "underline":
            downgrades.append("underline:plain_text")
            return _inline_html(value.text, downgrades=downgrades)
        case "strikethrough":
            downgrades.append("strikethrough:plain_text")
            return _inline_html(value.text, downgrades=downgrades)
        case "spoiler":
            downgrades.append("spoiler:plain_text")
            return _inline_html(value.text, downgrades=downgrades)
        case "code":
            downgrades.append("code:plain_text")
            return _inline_html(value.text, downgrades=downgrades)
        case "marked" | "subscript" | "superscript" | "anchor_link" | "reference" | "reference_link":
            downgrades.append(f"{value.type}:plain_text")
            return _inline_html(value.text, downgrades=downgrades)
    raise ValueError(f"unsupported inline rich text entity: {getattr(value, 'type', type(value).__name__)}")


def _inline_content(value: RichTextContent, *, downgrades: list[str]) -> str:
    if isinstance(value, tuple):
        return "".join(_inline_html(item, downgrades=downgrades) for item in value)
    return _inline_html(value, downgrades=downgrades)


@dataclass(frozen=True)
class _HtmlUnit:
    html: str
    text: str


def _render_block(block: RichBlock, *, downgrades: list[str]) -> list[_HtmlUnit]:
    if isinstance(block, (RichBlockParagraph, RichBlockHeading, RichBlockFooter, RichBlockPreformatted)):
        text = inline_plain_text(block.text)
        if isinstance(block, RichBlockHeading):
            return [_HtmlUnit(html=f"<b>{_inline_content(block.text, downgrades=downgrades)}</b>", text=text)]
        if isinstance(block, RichBlockPreformatted):
            downgrades.append(f"pre:{block.block_id}:plain_text")
            return [_HtmlUnit(html=html.escape(text, quote=False), text=text)]
        return [_HtmlUnit(html=_inline_content(block.text, downgrades=downgrades), text=text)]
    if isinstance(block, RichBlockDivider):
        return [_HtmlUnit(html="---", text="---")]
    if isinstance(block, RichBlockMath):
        return [_HtmlUnit(html=html.escape(block.expression, quote=False), text=block.expression)]
    if isinstance(block, RichBlockAnchor):
        return []
    if isinstance(block, RichBlockList):
        lines_html: list[str] = []
        lines_text: list[str] = []
        counter = 1
        for item in block.items:
            marker = (
                "[x] "
                if item.has_checkbox and item.is_checked
                else "[ ] "
                if item.has_checkbox
                else "• "
                if item.label_type is None
                else f"{item.value or counter}. "
            )
            counter += 1
            inner = [unit for child in item.blocks for unit in _render_block(child, downgrades=downgrades)]
            inner_html = "\n".join(unit.html for unit in inner if unit.html)
            inner_text = "\n".join(unit.text for unit in inner if unit.text)
            first_html, *rest_html = inner_html.splitlines() or [""]
            first_text, *rest_text = inner_text.splitlines() or [""]
            lines_html.append(marker + first_html)
            lines_text.append(marker + first_text)
            for h_line, t_line in zip(rest_html, rest_text, strict=True):
                lines_html.append("  " + h_line)
                lines_text.append("  " + t_line)
        return [_HtmlUnit(html="\n".join(lines_html), text="\n".join(lines_text))]
    if isinstance(block, RichBlockQuote):
        downgrades.append(f"blockquote:{block.block_id}:legacy_plain_text")
        inner = [unit for child in block.blocks for unit in _render_block(child, downgrades=downgrades)]
        inner_text = "\n\n".join(unit.text for unit in inner if unit.text)
        inner_html = "\n\n".join(unit.html for unit in inner if unit.html)
        if block.credit is not None:
            credit = inline_plain_text(block.credit)
            if credit:
                inner_text += "\n— " + credit
                inner_html += "\n— " + html.escape(credit, quote=False)
        return [_HtmlUnit(html=inner_html, text=inner_text)]
    if isinstance(block, RichBlockPullQuote):
        downgrades.append(f"pullquote:{block.block_id}:legacy_plain_text")
        text = inline_plain_text(block.text)
        if block.credit is not None:
            credit = inline_plain_text(block.credit)
            if credit:
                text += "\n— " + credit
        return [_HtmlUnit(html=html.escape(text, quote=False), text=text)]
    if isinstance(block, (RichBlockCollage, RichBlockSlideshow)):
        downgrades.append(f"{block.type}:{block.block_id}:media_dropped_text_only_fallback")
        units: list[_HtmlUnit] = []
        for child in block.blocks:
            if isinstance(child, RichBlockMedia):
                downgrades.append(f"media:{child.block_id}:dropped_text_only_fallback")
                continue
            units.extend(_render_block(child, downgrades=downgrades))
        return units
    if isinstance(block, RichBlockTable):
        downgrades.append(f"table:{block.block_id}:plain_text")
        table_html: list[str] = []
        table_text: list[str] = []
        if block.caption is not None:
            table_html.append(_inline_content(block.caption, downgrades=downgrades))
            table_text.append(inline_plain_text(block.caption))
        for row in block.cells:
            cells_html = [
                _inline_content(cell.text, downgrades=downgrades) if cell.text is not None else "" for cell in row
            ]
            cells_text = [inline_plain_text(cell.text) if cell.text is not None else "" for cell in row]
            table_html.append("| " + " | ".join(cells_html) + " |")
            table_text.append("| " + " | ".join(cells_text) + " |")
        return [_HtmlUnit(html="\n".join(table_html), text="\n".join(table_text))]
    if isinstance(block, RichBlockDetails):
        downgrades.append(f"details:{block.block_id}:expanded")
        units = [
            _HtmlUnit(html=_inline_content(block.summary, downgrades=downgrades), text=inline_plain_text(block.summary))
        ]
        for child in block.blocks:
            if isinstance(child, RichBlockMedia):
                downgrades.append(f"media:{child.block_id}:dropped_text_only_fallback")
                continue
            units.extend(_render_block(child, downgrades=downgrades))
        return units
    if isinstance(block, RichBlockMap):
        latitude, longitude = block.location
        text = f"map: {latitude:.6f},{longitude:.6f}"
        return [_HtmlUnit(html=html.escape(text, quote=False), text=text)]
    if isinstance(block, RichBlockMedia):
        downgrades.append(f"media:{block.block_id}:dropped_text_only_fallback")
        return []
    raise ValueError(f"unsupported document block: {type(block).__name__}")


def render_rich_html_fallback(
    document: RichArticleDocument,
    *,
    publication_id: str | None = None,
) -> RichHtmlFallback:
    """Render one deterministic legacy HTML fallback for a rich article."""
    downgrades: list[str] = []
    units: list[_HtmlUnit] = []
    for block in document.blocks:
        units.extend(_render_block(block, downgrades=downgrades))

    html_text = "\n\n".join(unit.html for unit in units if unit.html)
    expected_plain_text = "\n\n".join(unit.text for unit in units if unit.text)
    _, entities = parse_telegram_html(html_text)

    canonical_text = plain_text(document, include_media_captions=False)
    if expected_plain_text != canonical_text:
        raise ValueError("legacy fallback plain text differs from the canonical article projection")

    effective_publication_id = publication_id or document.document_id
    payload: dict[str, Any] = {
        "article_digest": document.digest,
        "publication_id": effective_publication_id,
        "html_text": html_text,
        "expected_plain_text": expected_plain_text,
        "expected_entities": [entity.model_dump(mode="json") for entity in entities],
        "downgrades": list(dict.fromkeys(downgrades)),
    }
    return RichHtmlFallback(
        schema_name="video-channel-manager.rich-html-fallback",
        schema_version=1,
        article_digest=document.digest,
        publication_id=effective_publication_id,
        html_text=html_text,
        expected_plain_text=expected_plain_text,
        expected_entities=entities,
        downgrades=tuple(dict.fromkeys(downgrades)),
        fallback_sha256=sha256_text(canonical_json(payload)),
    )


__all__ = [
    "MAX_LEGACY_TEXT",
    "RichHtmlFallback",
    "render_rich_html_fallback",
]
