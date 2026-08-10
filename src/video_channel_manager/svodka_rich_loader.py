"""Svodka ``rich-v1`` editorial loader: editorial JSON → provider-neutral document.

Reads the canonical editorial records from ``content/telegram/svodka/rich-v1/``
(schema ``video-channel-manager.svodka-rich-article`` v1) and builds
``RichArticleDocument`` instances that the renderer can turn into native
Telegram Bot API 10.2 ``sendRichMessage`` payloads.

Mapping rules (all deterministic, content-only, no provider I/O):

* ``title`` → section heading (size 1) with the article id as block id;
* ``lead`` → lead paragraph;
* each section → a heading (size 2) followed by its blocks;
* ``paragraph`` blocks: the restricted ``<b>/<i>`` HTML is parsed into inline
  rich text (bold / italic); any other tag fails closed;
* ``list`` blocks → bullet/ordered lists; ``quote`` blocks → pull quotations
  with the attribution as ``credit``;
* ``footnotes``/``sources`` → carried as document provenance (``sources``),
  never injected into the visible text (the editorial HTML contains no inline
  footnote markers, so adding them would alter the reviewed copy);
* ``media_slots`` → preserved as acquisition plans (``media_slots``), **not**
  turned into media blocks: this revision commits no image assets, so there is
  nothing to render; a future media-preparation step resolves slots into
  ``RichMediaItem`` entries;
* ``footer`` → footer block with tagline and hashtags;
* ``predecessor`` and revision identity are carried verbatim.

The loader also exposes the manifest (``rich-v1/manifest.json``) for
``old_publication_id → rich_article_id`` mapping checks.
"""

from __future__ import annotations

import json
import re
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterator

from pydantic import ValidationError

from video_channel_manager.telegram_rich_models import (
    RICH_ARTICLE_SCHEMA_NAME,
    RICH_ARTICLE_SCHEMA_VERSION,
    RichArticleDocument,
    RichArticleFooter,
    RichArticleMetadata,
    RichArticlePredecessor,
    RichArticleSource,
    RichBlockHeading,
    RichBlockList,
    RichBlockParagraph,
    RichBlockPullQuote,
    RichListItem,
    RichMediaSlot,
    RichTextBold,
    RichTextContent,
    RichTextItalic,
    RichTextNode,
    RichTextUrl,
)

SVODKA_RICH_DIR = Path("content/telegram/svodka/rich-v1")
SVODKA_RICH_ARTICLES_DIR = SVODKA_RICH_DIR / "articles"
SVODKA_RICH_MANIFEST_PATH = SVODKA_RICH_DIR / "manifest.json"

_ARTICLE_ID_PATTERN = re.compile(r"^svodka-rich-[a-z0-9-]+$")


class SvodkaRichLoadError(ValueError):
    """Raised when a rich-v1 editorial record cannot be loaded."""


class _InlineRun:
    """Flat text run with a single active formatting tag (b/i/a)."""

    __slots__ = ("text", "tag", "href")

    def __init__(self, text: str, tag: str | None, href: str | None) -> None:
        self.text = text
        self.tag = tag
        self.href = href


class _HtmlToRichText(HTMLParser):
    """Parses the restricted editorial HTML (``<b>``, ``<i>``, ``<a href>``).

    The editorial contract (``SCHEMA.md``) permits only ``<b>`` and ``<i>``
    inline semantics plus links; nested formatting inside one paragraph is not
    part of the contract and fails closed.
    """

    _SUPPORTED_TAGS = {"b", "strong", "i", "em", "a"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.runs: list[_InlineRun] = []
        self._active: list[tuple[str, str | None]] = []

    @property
    def _current(self) -> tuple[str | None, str | None]:
        if not self._active:
            return None, None
        return self._active[-1]

    def handle_data(self, data: str) -> None:
        if not data:
            return
        tag, href = self._current
        self.runs.append(_InlineRun(data, tag, href))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.casefold()
        if normalized not in self._SUPPORTED_TAGS:
            raise SvodkaRichLoadError(f"unsupported editorial HTML tag: <{tag}>")
        if self._active:
            raise SvodkaRichLoadError("nested editorial HTML formatting is not supported")
        if normalized in {"b", "strong"}:
            self._active.append(("b", None))
        elif normalized in {"i", "em"}:
            self._active.append(("i", None))
        else:  # a
            href = next((value for key, value in attrs if key.casefold() == "href"), None)
            if not href:
                raise SvodkaRichLoadError("editorial link <a> requires href")
            self._active.append(("a", href))

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.casefold()
        if normalized not in self._SUPPORTED_TAGS:
            raise SvodkaRichLoadError(f"unsupported editorial HTML closing tag: </{tag}>")
        if not self._active:
            raise SvodkaRichLoadError(f"unmatched editorial HTML closing tag: </{tag}>")
        opened, _href = self._active.pop()
        if opened != normalized:
            raise SvodkaRichLoadError(f"mismatched editorial HTML closing tag: </{tag}>")

    def close(self) -> None:
        super().close()
        if self._active:
            raise SvodkaRichLoadError("unclosed editorial HTML formatting tag")


def _parse_inline_html(value: str) -> RichTextContent:
    """Parse editorial HTML into a flat rich-text tuple (no nested entities)."""
    parser = _HtmlToRichText()
    parser.feed(value)
    parser.close()
    fragments: list[RichTextNode] = []
    for run in parser.runs:
        if run.tag is None:
            if run.text:
                fragments.append(run.text)
        elif run.tag == "b":
            fragments.append(RichTextBold(text=run.text))
        elif run.tag == "i":
            fragments.append(RichTextItalic(text=run.text))
        else:  # a
            fragments.append(RichTextUrl(text=run.text, url=str(run.href)))
    if len(fragments) == 1:
        return fragments[0]
    return tuple(fragments)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SvodkaRichLoadError(f"cannot read rich-v1 record {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SvodkaRichLoadError(f"rich-v1 record {path} is not a JSON object")
    return payload


def _require_editorial_schema(payload: dict[str, Any], path: Path) -> None:
    if payload.get("schema_name") != "video-channel-manager.svodka-rich-article":
        raise SvodkaRichLoadError(f"rich-v1 record {path} has an unexpected schema_name")
    if payload.get("schema_version") != 1:
        raise SvodkaRichLoadError(f"rich-v1 record {path} has an unexpected schema_version")
    if payload.get("project_key") != "svodka":
        raise SvodkaRichLoadError(f"rich-v1 record {path} has an unexpected project_key")
    if payload.get("provider_writes_authorized") is not False:
        raise SvodkaRichLoadError(f"rich-v1 record {path} must not authorize provider writes")
    if payload.get("premium_emoji_dependency") is not False:
        raise SvodkaRichLoadError(f"rich-v1 record {path} must not depend on premium emoji")
    article_id = payload.get("article_id")
    if not isinstance(article_id, str) or _ARTICLE_ID_PATTERN.fullmatch(article_id) is None:
        raise SvodkaRichLoadError(f"rich-v1 record {path} has an invalid article_id")


def _block_paragraph(block_id: str, html: str) -> RichBlockParagraph:
    text = _parse_inline_html(html)
    if not text:
        raise SvodkaRichLoadError(f"paragraph block {block_id} has no visible text")
    return RichBlockParagraph(block_id=block_id, text=text)


def _block_quote(block_id: str, html: str, attribution: str) -> RichBlockPullQuote:
    text = _parse_inline_html(html)
    if not text:
        raise SvodkaRichLoadError(f"quote block {block_id} has no visible text")
    credit: RichTextContent | None = attribution if attribution else None
    return RichBlockPullQuote(block_id=block_id, text=text, credit=credit)


def _block_list(block_id: str, items: list[str], *, ordered: bool) -> RichBlockList:
    rich_items: list[RichListItem] = []
    for index, item in enumerate(items, start=1):
        if not item.strip():
            raise SvodkaRichLoadError(f"list block {block_id} contains an empty item")
        rich_items.append(
            RichListItem(
                blocks=(RichBlockParagraph(block_id=f"{block_id}-item-{index}", text=item),),
                label_type="1" if ordered else None,
            )
        )
    return RichBlockList(block_id=block_id, items=tuple(rich_items))


def _build_blocks(payload: dict[str, Any]) -> tuple[object, ...]:
    blocks: list[object] = []
    title = payload.get("title")
    if not isinstance(title, str) or not title.strip():
        raise SvodkaRichLoadError("rich-v1 record has no title")
    blocks.append(RichBlockHeading(block_id="h-title", text=title, size=1))

    lead = payload.get("lead")
    if isinstance(lead, str) and lead.strip():
        blocks.append(RichBlockParagraph(block_id="p-lead", text=lead))

    sections = payload.get("sections")
    if not isinstance(sections, list) or not sections:
        raise SvodkaRichLoadError("rich-v1 record has no sections")
    for _section_index, section in enumerate(sections):
        if not isinstance(section, dict):
            raise SvodkaRichLoadError("rich-v1 section must be an object")
        section_id = section.get("section_id")
        if not isinstance(section_id, str) or not section_id:
            raise SvodkaRichLoadError("rich-v1 section has no section_id")
        heading = section.get("heading")
        if isinstance(heading, str) and heading.strip():
            blocks.append(RichBlockHeading(block_id=f"h-{section_id}", text=heading, size=2))
        section_blocks = section.get("blocks")
        if not isinstance(section_blocks, list):
            raise SvodkaRichLoadError(f"section {section_id} has no blocks")
        for block_index, raw in enumerate(section_blocks):
            if not isinstance(raw, dict):
                raise SvodkaRichLoadError(f"section {section_id} block must be an object")
            block_type = raw.get("type")
            block_id = f"b-{section_id}-{block_index + 1}"
            if block_type == "paragraph":
                html = raw.get("html")
                if not isinstance(html, str):
                    raise SvodkaRichLoadError(f"paragraph block {block_id} has no html")
                blocks.append(_block_paragraph(block_id, html))
            elif block_type == "quote":
                html = raw.get("html")
                attribution = raw.get("attribution") or ""
                if not isinstance(html, str):
                    raise SvodkaRichLoadError(f"quote block {block_id} has no html")
                blocks.append(_block_quote(block_id, html, str(attribution)))
            elif block_type == "list":
                items = raw.get("items")
                if not isinstance(items, list) or not items:
                    raise SvodkaRichLoadError(f"list block {block_id} has no items")
                if not all(isinstance(item, str) for item in items):
                    raise SvodkaRichLoadError(f"list block {block_id} items must be strings")
                ordered = raw.get("ordered") is True
                blocks.append(_block_list(block_id, [str(item) for item in items], ordered=ordered))
            else:
                raise SvodkaRichLoadError(f"unsupported rich-v1 block type: {block_type!r}")

    footer = payload.get("footer")
    if isinstance(footer, dict):
        tagline = footer.get("tagline")
        hashtags = footer.get("hashtags")
        if isinstance(tagline, str) and tagline.strip():
            blocks.append(RichBlockParagraph(block_id="p-footer", text=tagline))
        if isinstance(hashtags, list) and hashtags:
            hashtag_text = " ".join(str(tag) for tag in hashtags)
            blocks.append(RichBlockParagraph(block_id="p-hashtags", text=hashtag_text))
    return tuple(blocks)


def _build_sources(payload: dict[str, Any]) -> tuple[RichArticleSource, ...]:
    sources: list[RichArticleSource] = []
    raw_sources = payload.get("sources")
    if not isinstance(raw_sources, list):
        return ()
    for raw in raw_sources:
        if not isinstance(raw, dict):
            raise SvodkaRichLoadError("rich-v1 source must be an object")
        source_id = raw.get("source_id")
        label = raw.get("label")
        url = raw.get("url")
        if not isinstance(source_id, str) or not isinstance(label, str) or not isinstance(url, str):
            raise SvodkaRichLoadError("rich-v1 source requires source_id, label and url")
        verified_on: date | None = None
        if isinstance(raw.get("verified_on"), str):
            try:
                verified_on = date.fromisoformat(raw["verified_on"])
            except ValueError as exc:
                raise SvodkaRichLoadError(f"rich-v1 source {source_id} has an invalid verified_on") from exc
        evidence = raw.get("evidence")
        sources.append(
            RichArticleSource(
                source_id=source_id,
                label=label,
                url=url,
                verified_on=verified_on,
                evidence=str(evidence) if evidence else None,
            )
        )
    return tuple(sources)


def _build_media_slots(payload: dict[str, Any]) -> tuple[RichMediaSlot, ...]:
    slots: list[RichMediaSlot] = []
    raw_slots = payload.get("media_slots")
    if not isinstance(raw_slots, list):
        return ()
    for raw in raw_slots:
        if not isinstance(raw, dict):
            raise SvodkaRichLoadError("rich-v1 media slot must be an object")
        slot_id = raw.get("slot_id")
        if not isinstance(slot_id, str) or not slot_id:
            raise SvodkaRichLoadError("rich-v1 media slot has no slot_id")
        placement = raw.get("placement")
        slots.append(
            RichMediaSlot(
                slot_id=slot_id,
                placement=placement if isinstance(placement, dict) else {},
                depicts=raw.get("depicts"),
                purpose=raw.get("purpose"),
                preferred_source_type=raw.get("preferred_source_type"),
                copyright_provenance=raw.get("copyright_provenance"),
                caption=raw.get("caption"),
            )
        )
    return tuple(slots)


def _build_predecessor(payload: dict[str, Any]) -> RichArticlePredecessor | None:
    raw = payload.get("predecessor")
    if not isinstance(raw, dict):
        return None
    try:
        return RichArticlePredecessor(
            publication_id=str(raw["publication_id"]),
            source_file=str(raw["source_file"]),
            source_file_sha256=str(raw["source_file_sha256"]),
            release_id=str(raw["release_id"]),
            source_format=str(raw["source_format"]),
        )
    except (KeyError, ValidationError) as exc:
        raise SvodkaRichLoadError(f"rich-v1 predecessor is invalid: {exc}") from exc


def _build_footer(payload: dict[str, Any]) -> RichArticleFooter | None:
    raw = payload.get("footer")
    if not isinstance(raw, dict):
        return None
    tagline = raw.get("tagline")
    hashtags = raw.get("hashtags")
    if not isinstance(tagline, str) or not tagline.strip():
        raise SvodkaRichLoadError("rich-v1 footer requires a non-empty tagline")
    if not isinstance(hashtags, list) or not all(isinstance(tag, str) for tag in hashtags):
        raise SvodkaRichLoadError("rich-v1 footer requires a hashtags list")
    return RichArticleFooter(
        tagline=tagline,
        hashtags=tuple(hashtags),
    )


def load_svodka_rich_article(path: Path) -> RichArticleDocument:
    """Load one rich-v1 editorial JSON record into a ``RichArticleDocument``."""
    path = Path(path)
    payload = _load_json(path)
    _require_editorial_schema(payload, path)

    article_id = str(payload["article_id"])
    title = str(payload["title"])
    language = "ru"  # rich-v1 records are Russian; the schema has no language field

    try:
        document = RichArticleDocument(
            schema_name=RICH_ARTICLE_SCHEMA_NAME,
            schema_version=RICH_ARTICLE_SCHEMA_VERSION,
            document_id=article_id,
            project_key="svodka",
            metadata=RichArticleMetadata(
                title=title,
                language=language,
                summary=payload.get("lead"),
                created_at=date(2026, 8, 10),
            ),
            blocks=tuple(block for block in _build_blocks(payload) if block is not None),
            media=(),
            sources=_build_sources(payload),
            media_slots=_build_media_slots(payload),
            predecessor=_build_predecessor(payload),
            footer=_build_footer(payload),
            revision=str(payload.get("revision") or "rich-v1"),
        )
    except (ValidationError, ValueError) as exc:
        raise SvodkaRichLoadError(f"rich-v1 record {path} cannot be loaded: {exc}") from exc
    return document


def load_svodka_rich_manifest(path: Path = SVODKA_RICH_MANIFEST_PATH) -> dict[str, Any]:
    """Load the rich-v1 migration manifest (read-only)."""
    payload = _load_json(path)
    if payload.get("schema_name") != "video-channel-manager.svodka-rich-migration-manifest":
        raise SvodkaRichLoadError(f"rich-v1 manifest {path} has an unexpected schema_name")
    return payload


def svodka_rich_manifest_mappings(manifest: dict[str, Any]) -> dict[str, str]:
    """Return ``old_publication_id → rich_article_id`` from the manifest."""
    mappings = manifest.get("mappings")
    if not isinstance(mappings, list):
        raise SvodkaRichLoadError("rich-v1 manifest has no mappings list")
    result: dict[str, str] = {}
    for mapping in mappings:
        if not isinstance(mapping, dict):
            continue
        old = mapping.get("old_publication_id")
        new = mapping.get("rich_article_id")
        if isinstance(old, str) and isinstance(new, str):
            result[old] = new
    return result


def iter_svodka_rich_articles(
    directory: Path = SVODKA_RICH_ARTICLES_DIR,
) -> Iterator[tuple[Path, RichArticleDocument]]:
    """Yield ``(path, document)`` for every rich-v1 article JSON in order."""
    for path in sorted(Path(directory).glob("*.json")):
        yield path, load_svodka_rich_article(path)


__all__ = [
    "SVODKA_RICH_ARTICLES_DIR",
    "SVODKA_RICH_DIR",
    "SVODKA_RICH_MANIFEST_PATH",
    "SvodkaRichLoadError",
    "iter_svodka_rich_articles",
    "load_svodka_rich_article",
    "load_svodka_rich_manifest",
    "svodka_rich_manifest_mappings",
]
