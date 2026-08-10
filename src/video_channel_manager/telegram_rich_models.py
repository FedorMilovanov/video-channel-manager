"""Provider-neutral rich article domain model.

This module is the single internal representation of a structured article that
later renderers will turn into a Telegram Rich Message (``sendRichMessage`` /
``InputRichMessage``), a plain Telegram HTML fallback message, and a local
preview.  It is deliberately **provider-neutral**: it contains no bot tokens,
no chat identity, no HTTP client, and no publication state.

Capabilities are restricted to block and inline types verified against the
official Telegram Bot API Rich Messages documentation (Bot API 10.1, June 11,
2026, and Bot API 10.2, July 14, 2026; https://core.telegram.org/bots/api).
Nothing beyond ``RichBlock`` / ``RichText`` members present in that
documentation is modeled here.

Design invariants
-----------------
* Frozen, ``extra="forbid"`` models everywhere; a document is immutable after
  construction.
* Every block carries a unique ``block_id``; every media entry carries a
  unique ``media_id``.  Uniqueness is document-wide (including nested blocks)
  and is enforced at construction.
* Media is modeled as a document-level media library plus ``media`` blocks that
  reference it by ``media_id``.  A reference that does not resolve, or a
  library entry that is never referenced, is rejected at construction (no
  dangling media refs in either direction).
* Empty structural blocks are rejected at construction: text-bearing blocks
  must contain visible text, containers must contain at least one block, and
  every table row must contain at least one visible cell.
* ``canonical_json`` is deterministic: object keys are sorted, arrays keep
  their explicit order (stable ordering), and ``None`` values are omitted so
  that adding a new optional field with a ``None`` default in a future schema
  version cannot change the serialization of existing documents.  The document
  SHA-256 digest is computed over exactly this canonical serialization.
* The design is additive: adding new block/inline members to the unions later
  cannot change the serialized bytes of existing documents because the
  canonical JSON is derived from the model dump of each instance, never from a
  shared registry or versioned enumeration.

The repository-level official Bot API limit enforcement (32 768 UTF-8
characters, 500 blocks, 16 nesting levels, 50 media attachments, 20 table
columns) lives in ``telegram_rich_validation``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Annotated, Any, Iterator, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, model_validator

RICH_ARTICLE_SCHEMA_NAME: Literal["video-channel-manager.telegram-rich-article"] = (
    "video-channel-manager.telegram-rich-article"
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
    """Yield every text-bearing fragment of a rich text node.

    Plain strings are yielded as-is; custom emoji contributes its alternative
    text; inline and block formulas contribute their LaTeX source.  Formatting
    entities contribute their inner text.  This is the single source of truth
    used both for emptiness checks and for the official UTF-8 character count.
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
    """Custom emoji; corresponds to ``RichTextCustomEmoji``."""

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
    """Caption of a media, collage, or slideshow block; corresponds to ``RichBlockCaption``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: RichTextContent
    credit: RichTextContent | None = None


class RichListItem(BaseModel):
    """One list item; corresponds to ``InputRichBlockListItem``.

    ``label_type`` selects the label style for ordered lists ("a", "A", "i",
    "I", "1"); ``None`` renders a plain bullet.  ``value`` sets an explicit
    numeric label value for ordered lists.
    """

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
    """Table cell; corresponds to ``RichBlockTableCell``.

    Cells contain inline formatting only (official constraint).  ``text=None``
    makes the cell invisible.
    """

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


class RichBlockMedia(BaseModel):
    """Media block referencing the document media library by ``media_id``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["media"] = "media"
    block_id: str = Field(pattern=BLOCK_ID_PATTERN)
    media_id: str = Field(pattern=MEDIA_ID_PATTERN)
    has_spoiler: bool = False
    caption: RichBlockCaption | None = None


RichBlock: TypeAlias = Annotated[
    RichBlockParagraph
    | RichBlockHeading
    | RichBlockPreformatted
    | RichBlockFooter
    | RichBlockDivider
    | RichBlockMath
    | RichBlockList
    | RichBlockQuote
    | RichBlockPullQuote
    | RichBlockCollage
    | RichBlockSlideshow
    | RichBlockTable
    | RichBlockDetails
    | RichBlockMedia,
    Field(discriminator="type"),
]


class RichMediaRef(BaseModel):
    """One entry of the document media library."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    media_id: str = Field(pattern=MEDIA_ID_PATTERN)
    kind: MediaKind
    uri: str = Field(min_length=1, max_length=2048)
    file_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    alt_text: str | None = Field(default=None, min_length=1, max_length=300)


class RichArticleMetadata(BaseModel):
    """Editorial metadata of the article document."""

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


class RichArticleDocument(BaseModel):
    """Provider-neutral structured article.

    ``blocks`` preserve document order; ``media`` is the shared media library.
    The document is immutable, structurally self-consistent (unique IDs, no
    dangling media refs, no empty structural blocks), and produces a
    deterministic canonical JSON plus a SHA-256 digest.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-rich-article"]
    schema_version: Literal[1]
    document_id: str = Field(pattern=DOCUMENT_ID_PATTERN)
    project_key: str = Field(pattern=PROJECT_KEY_PATTERN)
    metadata: RichArticleMetadata
    blocks: tuple[RichBlock, ...] = Field(min_length=1)
    media: tuple[RichMediaRef, ...] = Field(default=())

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
            match block.type:
                case "media":
                    if block.media_id not in library_ids:
                        raise ValueError(f"media block references unknown media_id: {block.media_id}")
                    used_ids.add(block.media_id)
                case _:
                    pass
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
        case "paragraph" | "heading" | "pre" | "footer":
            if rich_text_is_empty(block.text):
                raise ValueError(f"{block.type} block {block.block_id} must contain visible text")
        case "pullquote":
            if rich_text_is_empty(block.text):
                raise ValueError(f"pullquote block {block.block_id} must contain visible text")
            if block.credit is not None and rich_text_is_empty(block.credit):
                raise ValueError(f"pullquote block {block.block_id} credit must contain visible text")
        case "media":
            if block.caption is not None:
                _require_visible_caption(block.block_id, block.caption)
        case "blockquote":
            if block.credit is not None and rich_text_is_empty(block.credit):
                raise ValueError(f"blockquote block {block.block_id} credit must contain visible text")
        case "collage" | "slideshow":
            if block.caption is not None:
                _require_visible_caption(block.block_id, block.caption)
        case "details":
            if rich_text_is_empty(block.summary):
                raise ValueError(f"details block {block.block_id} summary must contain visible text")
        case "table":
            for row_index, row in enumerate(block.cells):
                if not any(cell.text is not None and not rich_text_is_empty(cell.text) for cell in row):
                    raise ValueError(f"table block {block.block_id} row {row_index} has no visible cells")
            if block.caption is not None and rich_text_is_empty(block.caption):
                raise ValueError(f"table block {block.block_id} caption must contain visible text")
        case "list" | "divider" | "mathematical_expression":
            return


def _require_visible_caption(block_id: str, caption: RichBlockCaption) -> None:
    if rich_text_is_empty(caption.text):
        raise ValueError(f"media caption of block {block_id} must contain visible text")
    if caption.credit is not None and rich_text_is_empty(caption.credit):
        raise ValueError(f"media caption credit of block {block_id} must contain visible text")


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


# Recursive unions reference each other through forward references; pydantic
# resolves them explicitly after all types are defined so imports are safe.
RichArticleDocument.model_rebuild()
