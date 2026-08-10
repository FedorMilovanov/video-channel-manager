"""Provider-neutral rich article domain model for the Svodka rich bridge.

This module is the single internal representation of a structured article
between the Svodka ``rich-v1`` editorial records and the Telegram Bot API 10.2
``sendRichMessage`` payloads. It is deliberately **provider-neutral**: no bot
tokens, no chat identity, no HTTP client, no publication state.

The block and inline vocabulary mirrors exactly the block shapes that the
merged fail-closed transport (``telegram_rich_provider``) validates for
``InputRichMessage`` (outgoing) and returned ``RichMessage`` (incoming), so
the renderer can map this document onto both shapes losslessly:

* paragraphs, section headings (size 1..6), preformatted blocks, footer,
  divider, mathematical expression, anchor, lists (bullet/ordered/task),
  block quotation, pull quotation, collage, slideshow, table, details, map;
* media blocks referencing a document media library (photo/video/audio/
  animation/voice-note) with an input identity (``uri``) and an optional
  resolved file (file_id + dimensions) used to build the expected returned
  ``RichMessage``;
* inline rich text: bold, italic, underline, strikethrough, spoiler, marked,
  code, subscript, superscript, url, custom emoji (Unicode alternative text —
  never a hard premium-emoji dependency), references/footnotes and inline
  math.

Design invariants (kept from the reviewed closed-PR domain model):

* frozen ``extra="forbid"`` models; a document is immutable after construction;
* every block carries a unique ``block_id``; every media entry a unique
  ``media_id``; uniqueness is document-wide and enforced at construction;
* media blocks reference the media library by ``media_id``; dangling
  references in either direction are rejected;
* empty structural blocks are rejected;
* ``canonical_json`` is deterministic (sorted keys, stable array order,
  ``None`` omitted) and the document SHA-256 digest is computed over exactly
  this canonical serialization;
* the design is additive: nothing here touches the legacy regular-message
  serialization, so frozen legacy release digests stay unchanged.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Annotated, Any, Iterator, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, model_validator

RICH_ARTICLE_SCHEMA_NAME: Literal["video-channel-manager.rich-article-document"] = (
    "video-channel-manager.rich-article-document"
)
RICH_ARTICLE_SCHEMA_VERSION: Literal[1] = 1

SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
BLOCK_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"
MEDIA_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"
DOCUMENT_ID_PATTERN = r"^[a-z0-9][a-z0-9._-]{4,95}$"
PROJECT_KEY_PATTERN = r"^[a-z0-9][a-z0-9-]{1,63}$"
LINK_PATTERN = r"^(?:https?://|tg://|mailto:|tel:)[^\s]+$"

MediaKind = Literal["photo", "video", "audio", "animation", "voice_note"]
ListLabelType = Literal["a", "A", "i", "I", "1"]
CellAlign = Literal["left", "center", "right"]
CellValign = Literal["top", "middle", "bottom"]


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _strip_none(value: object) -> object:
    """Recursively remove ``None`` values so absent optional fields are stable."""
    if isinstance(value, dict):
        return {key: _strip_none(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [_strip_none(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    """Deterministic canonical JSON: sorted keys, compact separators, no None values."""
    return json.dumps(_strip_none(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def iter_text_fragments(value: object) -> Iterator[str]:
    """Yield every text-bearing fragment of a rich text node in order.

    Plain strings are yielded as-is; custom emoji contributes its alternative
    text; inline math contributes its LaTeX source; formatting entities
    contribute their inner text.  This is the single source of truth used both
    for emptiness checks and for the official UTF-8 character count.
    """
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, tuple):
        for item in value:
            yield from iter_text_fragments(item)
        return
    if isinstance(value, RichTextMath):
        yield value.expression
        return
    if isinstance(value, RichTextCustomEmoji):
        yield value.alternative_text
        return
    if isinstance(value, _TextEntity):
        yield from iter_text_fragments(value.text)
        return
    if isinstance(value, RichTextAnchor):
        return


def rich_text_is_empty(value: object) -> bool:
    """True when a rich text node contains no visible text at all."""
    return not any(fragment.strip() for fragment in iter_text_fragments(value))


class _TextEntity(BaseModel):
    """Shared ``text`` field for inline entities that must stay visible."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: "RichTextContent"

    @model_validator(mode="after")
    def text_must_be_visible(self) -> "_TextEntity":
        if rich_text_is_empty(self.text):
            raise ValueError("inline rich text must contain visible text")
        return self


class RichTextBold(_TextEntity):
    type: Literal["bold"] = "bold"


class RichTextItalic(_TextEntity):
    type: Literal["italic"] = "italic"


class RichTextUnderline(_TextEntity):
    type: Literal["underline"] = "underline"


class RichTextStrikethrough(_TextEntity):
    type: Literal["strikethrough"] = "strikethrough"


class RichTextSpoiler(_TextEntity):
    type: Literal["spoiler"] = "spoiler"


class RichTextMarked(_TextEntity):
    type: Literal["marked"] = "marked"


class RichTextCode(_TextEntity):
    type: Literal["code"] = "code"


class RichTextSubscript(_TextEntity):
    type: Literal["subscript"] = "subscript"


class RichTextSuperscript(_TextEntity):
    type: Literal["superscript"] = "superscript"


class RichTextUrl(_TextEntity):
    """Inline link; corresponds to ``RichTextUrl`` in the official API."""

    type: Literal["url"] = "url"
    url: str = Field(min_length=1, max_length=2048, pattern=LINK_PATTERN)


class RichTextAnchor(BaseModel):
    """In-document anchor definition; corresponds to ``RichTextAnchor``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["anchor"] = "anchor"
    name: str = Field(min_length=1, max_length=64, pattern=BLOCK_ID_PATTERN)


class RichTextAnchorLink(_TextEntity):
    """In-document anchor link; corresponds to ``RichTextAnchorLink``."""

    type: Literal["anchor_link"] = "anchor_link"
    anchor_name: str = Field(min_length=0, max_length=64, pattern=BLOCK_ID_PATTERN)


class RichTextReference(_TextEntity):
    """Footnote definition; corresponds to ``RichTextReference``."""

    type: Literal["reference"] = "reference"
    name: str = Field(min_length=1, max_length=64, pattern=BLOCK_ID_PATTERN)


class RichTextReferenceLink(_TextEntity):
    """Footnote link; corresponds to ``RichTextReferenceLink``."""

    type: Literal["reference_link"] = "reference_link"
    reference_name: str = Field(min_length=1, max_length=64, pattern=BLOCK_ID_PATTERN)


class RichTextMath(BaseModel):
    """Inline formula; corresponds to ``RichTextMathematicalExpression``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["mathematical_expression"] = "mathematical_expression"
    expression: str = Field(min_length=1, max_length=32768)


class RichTextCustomEmoji(BaseModel):
    """Custom emoji; corresponds to ``RichTextCustomEmoji``.

    Rendering must always downgrade to ``alternative_text`` (Unicode) unless a
    separately verified premium-emoji capability gate is proven; this document
    never makes premium emoji a hard dependency.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["custom_emoji"] = "custom_emoji"
    custom_emoji_id: str = Field(min_length=1, max_length=64)
    alternative_text: str = Field(min_length=1, max_length=64)


RichTextEntity: TypeAlias = Annotated[
    RichTextBold
    | RichTextItalic
    | RichTextUnderline
    | RichTextStrikethrough
    | RichTextSpoiler
    | RichTextMarked
    | RichTextCode
    | RichTextSubscript
    | RichTextSuperscript
    | RichTextUrl
    | RichTextAnchor
    | RichTextAnchorLink
    | RichTextReference
    | RichTextReferenceLink
    | RichTextMath
    | RichTextCustomEmoji,
    Field(discriminator="type"),
]

RichTextNode: TypeAlias = str | RichTextEntity
RichTextContent: TypeAlias = RichTextNode | tuple[RichTextNode, ...]


class RichBlockCaption(BaseModel):
    """Caption of a media, collage, or slideshow block."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: RichTextContent
    credit: RichTextContent | None = None

    @model_validator(mode="after")
    def caption_visible(self) -> "RichBlockCaption":
        if rich_text_is_empty(self.text):
            raise ValueError("block caption must contain visible text")
        if self.credit is not None and rich_text_is_empty(self.credit):
            raise ValueError("block caption credit must contain visible text")
        return self


class RichListItem(BaseModel):
    """One list item. ``label_type`` selects the ordered label style
    (``a``/``A``/``i``/``I``/``1``); ``None`` renders a plain bullet.
    ``value`` sets an explicit numeric label for ordered lists."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    blocks: tuple["RichBlock", ...] = Field(min_length=1)
    label_type: ListLabelType | None = None
    value: int | None = Field(default=None, ge=1)
    has_checkbox: bool = False
    is_checked: bool = False

    @model_validator(mode="after")
    def item_options_are_consistent(self) -> "RichListItem":
        if self.is_checked and not self.has_checkbox:
            raise ValueError("list item is_checked requires has_checkbox=True")
        if self.value is not None and self.label_type is None:
            raise ValueError("list item value requires an ordered label_type")
        return self


class RichTableCell(BaseModel):
    """Table cell; cells contain inline formatting only (official constraint)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: RichTextContent | None = None
    is_header: bool = False
    colspan: int = Field(default=1, ge=1, le=20)
    rowspan: int = Field(default=1, ge=1, le=20)
    align: CellAlign = "left"
    valign: CellValign = "top"


class RichBlockParagraph(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["paragraph"] = "paragraph"
    block_id: str = Field(pattern=BLOCK_ID_PATTERN)
    text: RichTextContent


class RichBlockHeading(BaseModel):
    """Section heading; corresponds to ``RichBlockSectionHeading`` (size 1..6)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["heading"] = "heading"
    block_id: str = Field(pattern=BLOCK_ID_PATTERN)
    text: RichTextContent
    size: int = Field(ge=1, le=6)


class RichBlockPreformatted(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["pre"] = "pre"
    block_id: str = Field(pattern=BLOCK_ID_PATTERN)
    text: RichTextContent
    language: str | None = Field(default=None, min_length=1, max_length=40)


class RichBlockFooter(BaseModel):
    """Footer/source block; corresponds to ``RichBlockFooter``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["footer"] = "footer"
    block_id: str = Field(pattern=BLOCK_ID_PATTERN)
    text: RichTextContent


class RichBlockDivider(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["divider"] = "divider"
    block_id: str = Field(pattern=BLOCK_ID_PATTERN)


class RichBlockMath(BaseModel):
    """Block formula; corresponds to ``RichBlockMathematicalExpression``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["mathematical_expression"] = "mathematical_expression"
    block_id: str = Field(pattern=BLOCK_ID_PATTERN)
    expression: str = Field(min_length=1, max_length=32768)


class RichBlockAnchor(BaseModel):
    """In-document anchor block; corresponds to ``RichBlockAnchor``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["anchor"] = "anchor"
    block_id: str = Field(pattern=BLOCK_ID_PATTERN)
    name: str = Field(min_length=1, max_length=64, pattern=BLOCK_ID_PATTERN)


class RichBlockList(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["list"] = "list"
    block_id: str = Field(pattern=BLOCK_ID_PATTERN)
    items: tuple[RichListItem, ...] = Field(min_length=1)


class RichBlockQuote(BaseModel):
    """Block quotation; corresponds to ``RichBlockBlockQuotation``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["blockquote"] = "blockquote"
    block_id: str = Field(pattern=BLOCK_ID_PATTERN)
    blocks: tuple["RichBlock", ...] = Field(min_length=1)
    credit: RichTextContent | None = None


class RichBlockPullQuote(BaseModel):
    """Pull quotation; corresponds to ``RichBlockPullQuotation``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["pullquote"] = "pullquote"
    block_id: str = Field(pattern=BLOCK_ID_PATTERN)
    text: RichTextContent
    credit: RichTextContent | None = None


class RichBlockCollage(BaseModel):
    """Collage of media blocks; corresponds to ``RichBlockCollage``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["collage"] = "collage"
    block_id: str = Field(pattern=BLOCK_ID_PATTERN)
    blocks: tuple["RichBlock", ...] = Field(min_length=1)
    caption: RichBlockCaption | None = None


class RichBlockSlideshow(BaseModel):
    """Slideshow of media blocks; corresponds to ``RichBlockSlideshow``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["slideshow"] = "slideshow"
    block_id: str = Field(pattern=BLOCK_ID_PATTERN)
    blocks: tuple["RichBlock", ...] = Field(min_length=1)
    caption: RichBlockCaption | None = None


class RichBlockTable(BaseModel):
    """Table; corresponds to ``RichBlockTable`` (cells contain inline text only)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["table"] = "table"
    block_id: str = Field(pattern=BLOCK_ID_PATTERN)
    cells: tuple[tuple[RichTableCell, ...], ...] = Field(min_length=1)
    is_bordered: bool = False
    is_striped: bool = False
    caption: RichTextContent | None = None


class RichBlockDetails(BaseModel):
    """Collapsible section; corresponds to ``RichBlockDetails``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["details"] = "details"
    block_id: str = Field(pattern=BLOCK_ID_PATTERN)
    summary: RichTextContent
    blocks: tuple["RichBlock", ...] = Field(min_length=1)
    is_open: bool = False


class RichBlockMap(BaseModel):
    """Map block; corresponds to ``RichBlockMap``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["map"] = "map"
    block_id: str = Field(pattern=BLOCK_ID_PATTERN)
    location: tuple[float, float]  # (latitude, longitude)
    zoom: int = Field(default=13, ge=0, le=24)
    width: int = Field(default=640, ge=1, le=10000)
    height: int = Field(default=480, ge=1, le=10000)
    caption: RichBlockCaption | None = None

    @model_validator(mode="after")
    def location_is_valid(self) -> "RichBlockMap":
        latitude, longitude = self.location
        if not -90 <= latitude <= 90:
            raise ValueError("map latitude is out of range")
        if not -180 <= longitude <= 180:
            raise ValueError("map longitude is out of range")
        if self.width + self.height > 10000:
            raise ValueError("map dimensions exceed the official total limit")
        if max(self.width, self.height) / min(self.width, self.height) > 20:
            raise ValueError("map aspect ratio exceeds the official limit")
        return self


class RichBlockMedia(BaseModel):
    """Media block referencing the document media library by ``media_id``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["media"] = "media"
    block_id: str = Field(pattern=BLOCK_ID_PATTERN)
    media_id: str = Field(pattern=MEDIA_ID_PATTERN)
    caption: RichBlockCaption | None = None


RichBlock: TypeAlias = Annotated[
    RichBlockParagraph
    | RichBlockHeading
    | RichBlockPreformatted
    | RichBlockFooter
    | RichBlockDivider
    | RichBlockMath
    | RichBlockAnchor
    | RichBlockList
    | RichBlockQuote
    | RichBlockPullQuote
    | RichBlockCollage
    | RichBlockSlideshow
    | RichBlockTable
    | RichBlockDetails
    | RichBlockMap
    | RichBlockMedia,
    Field(discriminator="type"),
]


class RichResolvedFile(BaseModel):
    """Resolved Bot API file identity used to build the expected returned RichMessage.

    Values are the exact fields Telegram reports in returned media objects
    (``file_id``, ``file_unique_id``, dimensions, duration, size).  A renderer
    must never invent these; they come from an upload/``getFile`` step or from
    previously archived provider evidence.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    file_id: str = Field(min_length=1, max_length=512)
    file_unique_id: str = Field(min_length=1, max_length=512)
    width: int | None = Field(default=None, ge=0)
    height: int | None = Field(default=None, ge=0)
    duration: int | None = Field(default=None, ge=0)
    file_size: int | None = Field(default=None, ge=0)


class RichMediaItem(BaseModel):
    """One entry of the document media library."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    media_id: str = Field(pattern=MEDIA_ID_PATTERN)
    kind: MediaKind
    uri: str = Field(min_length=1, max_length=2048)
    alt_text: str | None = Field(default=None, min_length=1, max_length=300)
    resolved: RichResolvedFile | None = None


class RichArticleSource(BaseModel):
    """Source/footnote provenance carried from the editorial revision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(min_length=1, max_length=64, pattern=BLOCK_ID_PATTERN)
    label: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=1, max_length=2048, pattern=LINK_PATTERN)
    verified_on: date | None = None
    evidence: str | None = Field(default=None, max_length=1000)


class RichMediaSlot(BaseModel):
    """Editorial media acquisition plan (not an asset).

    ``rich-v1`` records describe what must be shown and why; actual assets are
    acquired separately.  Slots are preserved on the document so a future
    media-preparation step can resolve them into ``RichMediaItem`` entries.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    slot_id: str = Field(min_length=1, max_length=64, pattern=BLOCK_ID_PATTERN)
    placement: dict[str, str] = Field(default_factory=dict)
    depicts: str | None = None
    purpose: str | None = None
    preferred_source_type: str | None = None
    copyright_provenance: str | None = None
    caption: str | None = None


class RichArticleMetadata(BaseModel):
    """Editorial metadata of the rich article document."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str = Field(min_length=1, max_length=300)
    language: str = Field(min_length=2, max_length=16, pattern=r"^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
    summary: str | None = Field(default=None, min_length=1, max_length=2000)
    author: str | None = Field(default=None, min_length=1, max_length=200)
    tags: tuple[str, ...] = Field(default=(), max_length=30)
    created_at: date
    updated_at: date | None = None
    canonical_url: str | None = Field(default=None, min_length=1, max_length=2048, pattern=LINK_PATTERN)

    @model_validator(mode="after")
    def validate_metadata(self) -> "RichArticleMetadata":
        if any(not tag.strip() or len(tag) > 60 for tag in self.tags):
            raise ValueError("metadata tags must contain 1..60 visible characters")
        if len(self.tags) != len(set(self.tags)):
            raise ValueError("metadata tags must be unique")
        if self.updated_at is not None and self.updated_at < self.created_at:
            raise ValueError("metadata updated_at cannot precede created_at")
        return self


class RichArticlePredecessor(BaseModel):
    """Identity of the frozen editorial item this rich article revises."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    publication_id: str = Field(min_length=1, max_length=96)
    source_file: str = Field(min_length=1)
    source_file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    release_id: str = Field(min_length=1, max_length=96)
    source_format: str = Field(min_length=1, max_length=32)


class RichArticleFooter(BaseModel):
    """Footer content: tagline plus hashtags."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tagline: str = Field(min_length=1, max_length=300)
    hashtags: tuple[str, ...] = Field(default=(), max_length=30)

    @model_validator(mode="after")
    def validate_footer(self) -> "RichArticleFooter":
        if any(not tag.startswith("#") or len(tag) > 64 for tag in self.hashtags):
            raise ValueError("footer hashtags must start with '#' and be at most 64 characters")
        if len(self.hashtags) != len(set(self.hashtags)):
            raise ValueError("footer hashtags must be unique")
        return self


class RichArticleDocument(BaseModel):
    """Provider-neutral structured rich article.

    ``blocks`` preserve document order; ``media`` is the shared media library.
    The document is immutable, structurally self-consistent (unique IDs, no
    dangling media refs, no empty structural blocks), and produces a
    deterministic canonical JSON plus a SHA-256 digest.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.rich-article-document"]
    schema_version: Literal[1]
    document_id: str = Field(pattern=DOCUMENT_ID_PATTERN)
    project_key: str = Field(pattern=PROJECT_KEY_PATTERN)
    metadata: RichArticleMetadata
    blocks: tuple[RichBlock, ...] = Field(min_length=1)
    media: tuple[RichMediaItem, ...] = Field(default=())
    sources: tuple[RichArticleSource, ...] = Field(default=())
    media_slots: tuple[RichMediaSlot, ...] = Field(default=())
    predecessor: RichArticlePredecessor | None = None
    footer: RichArticleFooter | None = None
    revision: str | None = Field(default=None, min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_document_structure(self) -> "RichArticleDocument":
        seen_block_ids: set[str] = set()
        for block in iter_blocks(self.blocks):
            if block.block_id in seen_block_ids:
                raise ValueError(f"duplicate block_id across document: {block.block_id}")
            seen_block_ids.add(block.block_id)
            _require_visible_block_content(block)

        library_ids = {entry.media_id for entry in self.media}
        if len(library_ids) != len(self.media):
            raise ValueError("media library contains duplicate media_id values")

        used_ids: set[str] = set()
        for block in iter_blocks(self.blocks):
            if block.type == "media":
                if block.media_id not in library_ids:
                    raise ValueError(f"media block references unknown media_id: {block.media_id}")
                used_ids.add(block.media_id)
        unreferenced = library_ids - used_ids
        if unreferenced:
            raise ValueError("media library entries are never referenced: " + ", ".join(sorted(unreferenced)))
        return self

    @property
    def canonical_json(self) -> str:
        return canonical_json(self.model_dump(mode="json"))

    @property
    def digest(self) -> str:
        return sha256_text(self.canonical_json)


def _require_visible_block_content(block: RichBlock) -> None:
    """Reject empty structural blocks: text blocks need visible text, containers need content."""
    match block.type:
        case "paragraph" | "heading" | "pre" | "footer" | "pullquote":
            if rich_text_is_empty(block.text):
                raise ValueError(f"{block.type} block {block.block_id} must contain visible text")
        case "media":
            if block.caption is not None:
                if rich_text_is_empty(block.caption.text):
                    raise ValueError(f"media block {block.block_id} caption must contain visible text")
        case "blockquote":
            if block.credit is not None and rich_text_is_empty(block.credit):
                raise ValueError(f"blockquote block {block.block_id} credit must contain visible text")
        case "collage" | "slideshow":
            if block.caption is not None and rich_text_is_empty(block.caption.text):
                raise ValueError(f"{block.type} block {block.block_id} caption must contain visible text")
        case "details":
            if rich_text_is_empty(block.summary):
                raise ValueError(f"details block {block.block_id} summary must contain visible text")
        case "table":
            for row_index, row in enumerate(block.cells):
                if not any(cell.text is not None and not rich_text_is_empty(cell.text) for cell in row):
                    raise ValueError(f"table block {block.block_id} row {row_index} has no visible cells")
            if block.caption is not None and rich_text_is_empty(block.caption):
                raise ValueError(f"table block {block.block_id} caption must contain visible text")
        case "list" | "divider" | "mathematical_expression" | "anchor" | "map":
            return


def iter_blocks(blocks: tuple[RichBlock, ...]) -> Iterator[RichBlock]:
    """Yield every block in document order, including nested blocks."""
    for block in blocks:
        yield block
        match block.type:
            case "list":
                for item in block.items:
                    yield from iter_blocks(item.blocks)
            case "blockquote" | "collage" | "slideshow" | "details":
                yield from iter_blocks(block.blocks)
            case _:
                pass


def child_blocks(block: RichBlock) -> tuple[RichBlock, ...]:
    """Direct child blocks of a container block (empty tuple for leaves)."""
    match block.type:
        case "list":
            return tuple(child for item in block.items for child in item.blocks)
        case "blockquote" | "collage" | "slideshow" | "details":
            return block.blocks
        case _:
            return ()


RichArticleDocument.model_rebuild()
