"""Legacy Telegram HTML fallback renderer.

Renders the merged ``RichArticleDocument`` domain contract into deterministic
legacy Telegram HTML (``parse_mode="HTML"``) message chunks, for transports
that only speak the classic HTML parse mode.

The fallback is deliberately conservative and matches the official Bot API
HTML-style contract:

* only the verified tags are emitted: ``<b>``, ``<i>``, ``<u>``, ``<s>``,
  ``<tg-spoiler>``, ``<code>``, ``<pre>``, ``<pre><code
  class="language-...">``, ``<a href="...">``, ``<blockquote>``;
* all text is HTML-escaped (``&``, ``<``, ``>``, and URL attributes escaped);
* paragraphs keep their blank-line separation (``\\n\\n``) with no doubled or
  trailing blank lines;
* Unicode emoji pass through as plain text;
* premium custom emoji are never emitted as ``<tg-emoji>`` — a ``custom_emoji``
  inline entity deterministically downgrades to its alternative text and
  records a ``downgrades`` note;
* media is unsupported in legacy text mode: media blocks and collage/slideshow
  blocks are dropped with recorded deterministic ``downgrades`` notes;
* every feature the classic HTML surface cannot express (tables, formulas,
  footnotes, anchors, details, pullquote, marked/subscript/superscript,
  dividers) downgrades deterministically with an explicit note and never loses
  text content.

The visible text of the fallback is exactly
``canonical_article_text(document, include_media_captions=False)`` (media
excluded), and ``payload_sha256`` is a deterministic digest of the full
fallback payload.  No Telegram HTTP calls happen here.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from video_channel_manager.telegram_models import canonical_json, sha256_text
from video_channel_manager.telegram_rich_models import (
    RichArticleDocument,
    RichBlock,
    RichBlockCaption,
    RichBlockCollage,
    RichBlockDetails,
    RichBlockDivider,
    RichBlockFooter,
    RichBlockHeading,
    RichBlockList,
    RichBlockMath,
    RichBlockMedia,
    RichBlockParagraph,
    RichBlockPreformatted,
    RichBlockPullQuote,
    RichBlockQuote,
    RichBlockSlideshow,
    RichBlockTable,
    RichTextContent,
)
from video_channel_manager.telegram_rich_renderer import (
    SHA256_PATTERN,
    canonical_article_text,
    inline_runs,
    inline_text,
    utf16_length,
)
from video_channel_manager.telegram_rich_validation import validate_document

MAX_FALLBACK_MESSAGE_TEXT = 4096


class StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TelegramHtmlMessage(StrictFrozenModel):
    """One deterministic legacy HTML message chunk."""

    sequence: int = Field(ge=1)
    html_text: str
    visible_text: str


class TelegramHtmlFallback(StrictFrozenModel):
    """Deterministic legacy Telegram HTML fallback for one rich article document."""

    schema_name: Literal["video-channel-manager.telegram-html-fallback"] = (
        "video-channel-manager.telegram-html-fallback"
    )
    schema_version: Literal[1] = 1
    renderer_id: Literal["deterministic-html-v1"] = "deterministic-html-v1"
    parse_mode: Literal["HTML"] = "HTML"
    article_sha256: str = Field(pattern=SHA256_PATTERN)
    media_bundle_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    messages: tuple[TelegramHtmlMessage, ...] = Field(min_length=1)
    visible_text: str
    downgrades: tuple[str, ...] = ()
    payload_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_fallback_invariants(self) -> "TelegramHtmlFallback":
        expected = "\n\n".join(message.visible_text for message in self.messages if message.visible_text)
        if expected != self.visible_text:
            raise ValueError("fallback visible_text does not match the html messages")
        if self.payload_sha256 != compute_html_fallback_sha256(self):
            raise ValueError("fallback payload_sha256 does not match the deterministic payload")
        for index, message in enumerate(self.messages, start=1):
            if message.sequence != index:
                raise ValueError("fallback message sequences must be exactly 1..N in order")
            if utf16_length(message.visible_text) > MAX_FALLBACK_MESSAGE_TEXT:
                raise ValueError(f"fallback message exceeds the {MAX_FALLBACK_MESSAGE_TEXT} character limit")
            if "tg-emoji" in message.html_text:
                raise ValueError("fallback must never emit premium emoji tags")
        return self


def _span_html(
    text: str,
    *,
    bold: bool = False,
    italic: bool = False,
    underline: bool = False,
    strikethrough: bool = False,
    spoiler: bool = False,
    code: bool = False,
    url: str | None = None,
) -> str:
    escaped = html.escape(text, quote=False)
    if code:
        escaped = f"<code>{escaped}</code>"
    if bold:
        escaped = f"<b>{escaped}</b>"
    if italic:
        escaped = f"<i>{escaped}</i>"
    if underline:
        escaped = f"<u>{escaped}</u>"
    if strikethrough:
        escaped = f"<s>{escaped}</s>"
    if spoiler:
        escaped = f"<tg-spoiler>{escaped}</tg-spoiler>"
    if url is not None:
        escaped = f'<a href="{html.escape(url, quote=True)}">{escaped}</a>'
    return escaped


def _render_inline_html(value: RichTextContent, *, base_style: tuple[str, ...] = ()) -> tuple[str, set[str]]:
    """Render inline rich text to escaped HTML via the shared run flattener."""
    downgrades: set[str] = set()
    parts: list[str] = []
    for run in inline_runs(value, downgrades=downgrades):
        parts.append(
            _span_html(
                run.text,
                bold="bold" in run.kinds or "bold" in base_style,
                italic="italic" in run.kinds or "italic" in base_style,
                underline="underline" in run.kinds,
                strikethrough="strikethrough" in run.kinds,
                spoiler="spoiler" in run.kinds,
                code="code" in run.kinds and not base_style,
                url=run.url,
            )
        )
    return "".join(parts), downgrades


def _caption_text(caption: RichBlockCaption) -> str:
    text = inline_text(caption.text)
    if caption.credit is not None:
        credit = inline_text(caption.credit)
        if credit:
            return f"{text} — {credit}"
    return text


def _heading_style(size: int) -> tuple[str, ...]:
    if size <= 2:
        return ("bold",)
    if size <= 4:
        return ("bold", "italic")
    return ("italic",)


@dataclass(frozen=True)
class _HtmlUnit:
    html: str
    text: str


def _block_units(
    block: RichBlock,
    *,
    downgrades: set[str],
) -> list[_HtmlUnit]:
    """Render one domain block into ordered HTML units (media is dropped)."""
    if isinstance(block, RichBlockParagraph):
        html_text, extra = _render_inline_html(block.text)
        downgrades.update(extra)
        return [_HtmlUnit(html=html_text, text=inline_text(block.text))]
    if isinstance(block, RichBlockHeading):
        html_text, extra = _render_inline_html(block.text, base_style=_heading_style(block.size))
        downgrades.update(extra)
        return [_HtmlUnit(html=html_text, text=inline_text(block.text))]
    if isinstance(block, RichBlockPreformatted):
        text = inline_text(block.text)
        escaped = html.escape(text, quote=False)
        if block.language is not None:
            language = html.escape(block.language, quote=True)
            return [_HtmlUnit(html=f'<pre><code class="language-{language}">{escaped}</code></pre>', text=text)]
        return [_HtmlUnit(html=f"<pre>{escaped}</pre>", text=text)]
    if isinstance(block, RichBlockFooter):
        html_text, extra = _render_inline_html(block.text)
        downgrades.update(extra)
        return [_HtmlUnit(html=html_text, text=inline_text(block.text))]
    if isinstance(block, RichBlockDivider):
        return [_HtmlUnit(html="---", text="---")]
    if isinstance(block, RichBlockMath):
        return [_HtmlUnit(html=html.escape(f"$${block.expression}$$", quote=False), text=f"$${block.expression}$$")]
    if isinstance(block, RichBlockList):
        return [_render_list_block(block, downgrades=downgrades)]
    if isinstance(block, (RichBlockQuote, RichBlockPullQuote)):
        if isinstance(block, RichBlockPullQuote):
            downgrades.add(f"pullquote:{block.block_id}:blockquote")
        return [_render_quote_block(block, downgrades=downgrades)]
    if isinstance(block, (RichBlockCollage, RichBlockSlideshow)):
        for child in block.blocks:
            if isinstance(child, RichBlockMedia):
                downgrades.add(f"media:{child.block_id}:dropped_text_only_fallback")
        if isinstance(block, RichBlockCollage):
            downgrades.add(f"collage:{block.block_id}:media_dropped_text_only")
        else:
            downgrades.add(f"slideshow:{block.block_id}:media_dropped_text_only")
        units: list[_HtmlUnit] = []
        for child in block.blocks:
            if not isinstance(child, RichBlockMedia):
                units.extend(_block_units(child, downgrades=downgrades))
        return units
    if isinstance(block, RichBlockTable):
        return [_render_table_block(block, downgrades=downgrades)]
    if isinstance(block, RichBlockDetails):
        downgrades.add(f"details:{block.block_id}:expanded")
        summary_html, extra = _render_inline_html(block.summary)
        downgrades.update(extra)
        units = [_HtmlUnit(html=summary_html, text=inline_text(block.summary))]
        for child in block.blocks:
            units.extend(_block_units(child, downgrades=downgrades))
        return units
    if isinstance(block, RichBlockMedia):
        downgrades.add(f"media:{block.block_id}:dropped_text_only_fallback")
        return []
    raise TypeError(f"unexpected rich block: {type(block).__name__}")


def _render_list_block(block: RichBlockList, *, downgrades: set[str]) -> _HtmlUnit:
    lines_html: list[str] = []
    lines_text: list[str] = []
    counter = 1
    for item in block.items:
        marker: str
        if item.has_checkbox:
            marker = "[x] " if item.is_checked else "[ ] "
        elif item.label_type is None:
            marker = "• "
        elif item.value is not None:
            marker = f"{item.value}. "
        else:
            marker = f"{counter}. "
        counter += 1
        inner_units: list[_HtmlUnit] = []
        for child in item.blocks:
            inner_units.extend(_block_units(child, downgrades=downgrades))
        inner_html = "\n".join(unit.html for unit in inner_units if unit.html)
        inner_text = "\n".join(unit.text for unit in inner_units if unit.text)
        first_html, *rest_html = inner_html.splitlines() or [""]
        first_text, *rest_text = inner_text.splitlines() or [""]
        lines_html.append(marker + first_html)
        lines_text.append(marker + first_text)
        for html_line, text_line in zip(rest_html, rest_text, strict=True):
            lines_html.append("  " + html_line)
            lines_text.append("  " + text_line)
    return _HtmlUnit(html="\n".join(lines_html), text="\n".join(lines_text))


def _render_quote_block(
    block: RichBlockQuote | RichBlockPullQuote,
    *,
    downgrades: set[str],
) -> _HtmlUnit:
    units: list[_HtmlUnit] = []
    if isinstance(block, RichBlockQuote):
        for child in block.blocks:
            units.extend(_block_units(child, downgrades=downgrades))
    else:  # RichBlockPullQuote
        html_text, extra = _render_inline_html(block.text)
        downgrades.update(extra)
        units.append(_HtmlUnit(html=html_text, text=inline_text(block.text)))
    if block.credit is not None:
        credit_text = inline_text(block.credit)
        if credit_text:
            units.append(_HtmlUnit(html=html.escape("— " + credit_text, quote=False), text="— " + credit_text))
    inner_html = "\n\n".join(unit.html for unit in units if unit.html)
    inner_text = "\n\n".join(unit.text for unit in units if unit.text)
    return _HtmlUnit(html=f"<blockquote>{inner_html}</blockquote>", text=inner_text)


def _render_table_block(block: RichBlockTable, *, downgrades: set[str]) -> _HtmlUnit:
    downgrades.add(f"table:{block.block_id}:plain_text")
    lines_html: list[str] = []
    lines_text: list[str] = []
    if block.caption is not None:
        caption_html, extra = _render_inline_html(block.caption)
        downgrades.update(extra)
        lines_html.append(caption_html)
        lines_text.append(inline_text(block.caption))
    for row in block.cells:
        cells_html: list[str] = []
        cells_text: list[str] = []
        for cell in row:
            if cell.text is not None:
                cell_html, extra = _render_inline_html(cell.text)
                downgrades.update(extra)
                cells_html.append(cell_html)
                cells_text.append(inline_text(cell.text))
            else:
                cells_html.append("")
                cells_text.append("")
        lines_html.append("| " + " | ".join(cells_html) + " |")
        lines_text.append("| " + " | ".join(cells_text) + " |")
    return _HtmlUnit(html="\n".join(lines_html), text="\n".join(lines_text))


def _media_bundle_sha256(document: RichArticleDocument) -> str | None:
    """Deterministic digest of the document media library (sorted by media_id)."""
    if not document.media:
        return None
    library = [
        {
            "media_id": entry.media_id,
            "kind": entry.kind,
            "uri": entry.uri,
            "alt_text": entry.alt_text,
        }
        for entry in sorted(document.media, key=lambda item: item.media_id)
    ]
    return sha256_text(canonical_json(library))


def compute_html_fallback_sha256(fallback: TelegramHtmlFallback) -> str:
    """Deterministic ``sha256:`` digest of the full fallback payload."""
    payload: dict[str, Any] = {
        "schema_name": fallback.schema_name,
        "schema_version": fallback.schema_version,
        "renderer_id": fallback.renderer_id,
        "parse_mode": fallback.parse_mode,
        "article_sha256": fallback.article_sha256,
        "media_bundle_sha256": fallback.media_bundle_sha256,
        "messages": [
            {"sequence": message.sequence, "html_text": message.html_text, "visible_text": message.visible_text}
            for message in fallback.messages
        ],
        "visible_text": fallback.visible_text,
        "downgrades": list(fallback.downgrades),
    }
    return sha256_text(canonical_json(payload))


def render_html_fallback(
    document: RichArticleDocument,
) -> TelegramHtmlFallback:
    """Render a rich article document into deterministic legacy Telegram HTML messages."""
    validate_document(document)

    downgrades: set[str] = set()
    units: list[_HtmlUnit] = []
    units.append(
        _HtmlUnit(
            html=f"<b>{html.escape(document.metadata.title, quote=False)}</b>",
            text=document.metadata.title,
        )
    )
    for block in document.blocks:
        units.extend(_block_units(block, downgrades=downgrades))

    messages: list[TelegramHtmlMessage] = []
    pending: list[_HtmlUnit] = []
    pending_length = 0

    def flush() -> None:
        nonlocal pending, pending_length
        if not pending:
            return
        html_text = "\n\n".join(unit.html for unit in pending)
        visible_text = "\n\n".join(unit.text for unit in pending)
        messages.append(TelegramHtmlMessage(sequence=len(messages) + 1, html_text=html_text, visible_text=visible_text))
        pending = []
        pending_length = 0

    for unit in units:
        length = utf16_length(unit.text)
        if length > MAX_FALLBACK_MESSAGE_TEXT:
            raise ValueError(f"a single article block exceeds the {MAX_FALLBACK_MESSAGE_TEXT} character limit")
        if pending and pending_length + 2 + length > MAX_FALLBACK_MESSAGE_TEXT:
            flush()
        separator = 2 if pending else 0
        pending.append(unit)
        pending_length += separator + length
    flush()

    visible_text = "\n\n".join(message.visible_text for message in messages if message.visible_text)
    expected_text = canonical_article_text(document, include_media_captions=False)
    if visible_text != expected_text:
        raise ValueError("fallback visible text differs from the canonical article projection")

    payload_object: dict[str, Any] = {
        "schema_name": "video-channel-manager.telegram-html-fallback",
        "schema_version": 1,
        "renderer_id": "deterministic-html-v1",
        "parse_mode": "HTML",
        "article_sha256": document.digest,
        "media_bundle_sha256": _media_bundle_sha256(document),
        "messages": [
            {"sequence": message.sequence, "html_text": message.html_text, "visible_text": message.visible_text}
            for message in messages
        ],
        "visible_text": visible_text,
        "downgrades": list(sorted(downgrades)),
    }
    return TelegramHtmlFallback(
        schema_name="video-channel-manager.telegram-html-fallback",
        schema_version=1,
        renderer_id="deterministic-html-v1",
        parse_mode="HTML",
        article_sha256=document.digest,
        media_bundle_sha256=payload_object["media_bundle_sha256"],
        messages=tuple(messages),
        visible_text=visible_text,
        downgrades=tuple(sorted(downgrades)),
        payload_sha256=sha256_text(canonical_json(payload_object)),
    )


__all__ = [
    "MAX_FALLBACK_MESSAGE_TEXT",
    "TelegramHtmlFallback",
    "TelegramHtmlMessage",
    "compute_html_fallback_sha256",
    "render_html_fallback",
]
