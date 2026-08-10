"""Deterministic Telegram rich-message renderer.

Consumes the merged provider-neutral rich article domain contract
(``RichArticleDocument`` from ``telegram_rich_models``) and emits a
provider-inert, HTTP-free Telegram Bot API request plan built strictly on the
stable classic Bot API surface:

* ``sendMessage`` with explicit UTF-16 ``entities`` (bold / italic / underline
  / strikethrough / spoiler / code / pre / text_link / blockquote);
* ``sendPhoto`` / ``sendVideo`` / ``sendAnimation`` / ``sendAudio`` /
  ``sendVoice`` for standalone and slideshow media blocks;
* ``sendMediaGroup`` for collage blocks (2-10 items per the official API; a
  single-item collage downgrades deterministically to a single media message;
  voice notes cannot be sent in a media group).

The domain document is validated with ``telegram_rich_validation.validate_document``
(official Bot API 10.1/10.2 limits) before rendering.  The renderer then maps
the verified domain block vocabulary onto the classic request surface:

* paragraph / footer → text message paragraph;
* heading (size 1..6) → bold-styled paragraph (deterministic size policy);
* pre → ``pre`` entity with language; list → marker-prefixed lines
  (``• `` bullets, ``1. `` ordered, ``[x] ``/``[ ] `` task items, explicit
  ``value`` labels honoured);
* blockquote → ``blockquote`` entities; pullquote → ``blockquote`` entities;
* media block → one full-width media message at its document position;
* collage block → one ``sendMediaGroup`` (caption on the first item);
  slideshow block → sequential media messages (all per-block captions kept).

Features the classic surface cannot express downgrade deterministically with
an explicit ``downgrades`` note and never lose text: tables (``| a | b |``
rows), block/inline formulas (LaTeX source kept verbatim), footnotes and
anchors (visible text kept), marked/subscript/superscript (visible text kept),
details (expanded), dividers (``---``), and premium custom emoji (Unicode
alternative text — never a fake ``custom_emoji`` entity).

Guarantees:

* deterministic payload serialization (canonical compact JSON) and a
  ``rich_payload_sha256`` digest over the full plan;
* UTF-16 entity offsets computed and validated against the official Bot API
  rules (offsets in UTF-16 code units, entities nested or disjoint, no partial
  overlaps, blockquote never nested, no fake premium emoji);
* ``plan.visible_text`` is exactly the renderer's canonical article projection
  (``canonical_article_text``), which preserves every text fragment of the
  document in order — so the rich visible text is semantically equivalent to
  the canonical article (also covered by a fragment-preservation test that
  walks the domain document with ``iter_text_fragments``).

No Telegram HTTP calls happen here: the plan is a pure request structure and
the transport layer injects ``chat_id`` and resolves media ``uri`` values.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, cast

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
    RichMediaRef,
    RichTextContent,
    iter_blocks,
)
from video_channel_manager.telegram_rich_validation import validate_document

MAX_MESSAGE_TEXT = 4096
MAX_CAPTION_TEXT = 1024
MIN_MEDIA_GROUP_ITEMS = 2
MAX_MEDIA_GROUP_ITEMS = 10
SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"

EntityType = Literal[
    "bold",
    "italic",
    "underline",
    "strikethrough",
    "spoiler",
    "code",
    "pre",
    "text_link",
    "blockquote",
]

RequestMethod = Literal[
    "sendMessage",
    "sendPhoto",
    "sendVideo",
    "sendAnimation",
    "sendAudio",
    "sendVoice",
    "sendMediaGroup",
]

HeadingStyle = Literal["bold", "italic"]


class StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# Entities that may appear nested inside another entity (outer -> inner).
# bold/italic/underline/strikethrough/spoiler can be part of any other entity
# except pre and code; text_link must never nest inside text_link; blockquote
# is always top-level; code and pre are always standalone.
_NESTING_ALLOWED: dict[str, frozenset[str]] = {
    "blockquote": frozenset({"bold", "italic", "underline", "strikethrough", "spoiler"}),
    "text_link": frozenset({"bold", "italic", "underline", "strikethrough", "spoiler"}),
    "bold": frozenset({"bold", "italic", "underline", "strikethrough", "spoiler", "text_link"}),
    "italic": frozenset({"bold", "italic", "underline", "strikethrough", "spoiler", "text_link"}),
    "underline": frozenset({"bold", "italic", "underline", "strikethrough", "spoiler", "text_link"}),
    "strikethrough": frozenset({"bold", "italic", "underline", "strikethrough", "spoiler", "text_link"}),
    "spoiler": frozenset({"bold", "italic", "underline", "strikethrough", "spoiler", "text_link"}),
}
_STANDALONE_ENTITIES = frozenset({"code", "pre"})

_SINGLE_MEDIA_METHOD: dict[str, tuple[str, str]] = {
    "photo": ("sendPhoto", "photo"),
    "video": ("sendVideo", "video"),
    "animation": ("sendAnimation", "animation"),
    "audio": ("sendAudio", "audio"),
    "voice_note": ("sendVoice", "voice_note"),
}


def utf16_length(value: str) -> int:
    """Return the length of ``value`` in UTF-16 code units (Telegram units)."""
    return len(value.encode("utf-16-le")) // 2


def _heading_style(size: int) -> tuple[HeadingStyle, ...]:
    """Deterministic presentation policy: size 1-2 bold, 3-4 bold italic, 5-6 italic."""
    if size <= 2:
        return ("bold",)
    if size <= 4:
        return ("bold", "italic")
    return ("italic",)


def _entity_sort_key(entity: TelegramRichEntity) -> tuple[int, int, str, str, str]:
    return (entity.offset, -entity.length, entity.type, entity.url or "", entity.language or "")


class TelegramRichEntity(StrictFrozenModel):
    """One MessageEntity exactly as the Bot API expects it (UTF-16 offsets)."""

    type: EntityType
    offset: int = Field(ge=0)
    length: int = Field(gt=0)
    url: str | None = None
    language: str | None = None

    @model_validator(mode="after")
    def validate_entity_fields(self) -> "TelegramRichEntity":
        if self.type == "text_link":
            if not self.url:
                raise ValueError("text_link entity requires a URL")
            if self.language is not None:
                raise ValueError("text_link entity must not carry a language")
        elif self.type == "pre":
            if self.url is not None:
                raise ValueError("pre entity must not carry a URL")
        else:
            if self.url is not None:
                raise ValueError(f"{self.type} entity must not carry a URL")
            if self.language is not None:
                raise ValueError(f"{self.type} entity must not carry a language")
        return self


class TelegramRichRequest(StrictFrozenModel):
    """One deterministic Bot API request (``chat_id`` is injected by the transport)."""

    sequence: int = Field(ge=1)
    method: RequestMethod
    payload: dict[str, Any]


class TelegramRichPlan(StrictFrozenModel):
    """Deterministic rich-message request plan for one rich article document."""

    schema_name: Literal["video-channel-manager.telegram-rich-plan"] = "video-channel-manager.telegram-rich-plan"
    schema_version: Literal[1] = 1
    renderer_id: Literal["deterministic-rich-v1"] = "deterministic-rich-v1"
    article_sha256: str = Field(pattern=SHA256_PATTERN)
    media_bundle_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    requests: tuple[TelegramRichRequest, ...] = Field(min_length=1)
    visible_text: str
    downgrades: tuple[str, ...] = ()
    rich_payload_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_plan_invariants(self) -> "TelegramRichPlan":
        if extract_visible_text(self) != self.visible_text:
            raise ValueError("plan visible_text does not match the request payloads")
        if self.rich_payload_sha256 != compute_rich_payload_sha256(self):
            raise ValueError("plan rich_payload_sha256 does not match the deterministic payload")
        for index, request in enumerate(self.requests, start=1):
            if request.sequence != index:
                raise ValueError("request sequences must be exactly 1..N in order")
            validate_request_payload(request)
        return self


def _entities_from_payload(payload: dict[str, Any]) -> tuple[TelegramRichEntity, ...]:
    raw = payload.get("entities") or ()
    if not isinstance(raw, list):
        return ()
    return tuple(TelegramRichEntity.model_validate(entity) for entity in raw)


_SINGLE_MEDIA_METHODS = frozenset({"sendPhoto", "sendVideo", "sendAnimation", "sendAudio", "sendVoice"})


def validate_request_payload(request: TelegramRichRequest) -> None:
    """Validate one request payload against the official Bot API field contracts."""
    method = request.method
    payload = request.payload
    if method == "sendMessage":
        text = payload.get("text")
        if not isinstance(text, str):
            raise ValueError("sendMessage payload requires a text field")
        entities = _entities_from_payload(payload)
        validate_message_text(text, entities)
        return
    if method in _SINGLE_MEDIA_METHODS:
        media_key = _media_key_for_method(method)
        if not isinstance(payload.get(media_key), str):
            raise ValueError(f"{method} payload requires a {media_key} field")
        caption = payload.get("caption")
        if caption is not None:
            if not isinstance(caption, str):
                raise ValueError(f"{method} caption must be a string")
            validate_message_text(caption, (), caption=True)
        return
    if method == "sendMediaGroup":
        media = payload.get("media")
        if not isinstance(media, list) or not media:
            raise ValueError("sendMediaGroup payload requires a non-empty media array")
        if not MIN_MEDIA_GROUP_ITEMS <= len(media) <= MAX_MEDIA_GROUP_ITEMS:
            raise ValueError(f"sendMediaGroup requires {MIN_MEDIA_GROUP_ITEMS}-{MAX_MEDIA_GROUP_ITEMS} items")
        for index, entry in enumerate(media):
            if not isinstance(entry, dict) or entry.get("type") not in {"photo", "video", "animation", "audio"}:
                raise ValueError("sendMediaGroup entries must be photo/video/animation/audio input media objects")
            if not isinstance(entry.get("media"), str):
                raise ValueError("sendMediaGroup entry requires a media field")
            if index == 0:
                caption = entry.get("caption")
                if caption is not None:
                    if not isinstance(caption, str):
                        raise ValueError("sendMediaGroup first caption must be a string")
                    validate_message_text(caption, (), caption=True)
            elif entry.get("caption") is not None:
                raise ValueError("sendMediaGroup captions are only rendered on the first item")
        return
    raise ValueError(f"unsupported Telegram request method: {method}")


def _media_key_for_method(method: str) -> str:
    for _media_kind, (candidate, key) in _SINGLE_MEDIA_METHOD.items():
        if candidate == method:
            return key
    raise ValueError(f"unsupported single-media request method: {method}")


def _utf16_boundaries(text: str) -> frozenset[int]:
    boundaries = {0}
    position = 0
    for char in text:
        position += utf16_length(char)
        boundaries.add(position)
    return frozenset(boundaries)


def validate_message_text(
    text: str,
    entities: Sequence[TelegramRichEntity],
    *,
    caption: bool = False,
) -> None:
    """Validate one message/caption text against the official Bot API rules.

    Enforces the 4096/1024 character limits, NUL prohibition, UTF-16 code
    point alignment of entity offsets, and the documented entity nesting
    restrictions (no partial overlaps, blockquote never nested, code/pre
    standalone, text_link not nested inside text_link).
    """
    limit = MAX_CAPTION_TEXT if caption else MAX_MESSAGE_TEXT
    if len(text) > limit:
        raise ValueError(f"Telegram text exceeds the {limit} character limit")
    if "\x00" in text:
        raise ValueError("Telegram text contains a NUL character")
    boundaries = _utf16_boundaries(text)
    total = max(boundaries)
    for entity in entities:
        end = entity.offset + entity.length
        if entity.offset not in boundaries or end not in boundaries:
            raise ValueError("entity offset/length must align to UTF-16 code point boundaries")
        if end > total:
            raise ValueError("entity extends beyond the message text")

    ordered = sorted(entities, key=_entity_sort_key)
    for index, entity in enumerate(ordered):
        if index == 0:
            continue
        previous = ordered[index - 1]
        prev_end = previous.offset + previous.length
        if entity.offset < prev_end:
            if entity.offset < previous.offset or entity.offset + entity.length > prev_end:
                raise ValueError("entities must be fully nested or disjoint, never partially overlapping")
            if entity.type in _STANDALONE_ENTITIES or previous.type in _STANDALONE_ENTITIES:
                raise ValueError("code/pre entities must not be nested inside other entities")
            if entity.type == "blockquote":
                raise ValueError("blockquote entities cannot be nested")
            if entity.type not in _NESTING_ALLOWED[previous.type]:
                raise ValueError(f"{entity.type} entity cannot be nested inside {previous.type}")


@dataclass(frozen=True)
class _InlineRun:
    """One flat text run produced by flattening the nested domain rich text."""

    text: str
    kinds: frozenset[str] = frozenset()
    url: str | None = None


def _walk_inline(
    value: RichTextContent,
    *,
    active: frozenset[str],
    url: str | None,
    out: list[_InlineRun],
    downgrades: set[str],
) -> None:
    """Flatten a nested ``RichTextContent`` node into non-overlapping runs."""
    if isinstance(value, str):
        if value:
            out.append(_InlineRun(text=value, kinds=active, url=url))
        return
    if isinstance(value, tuple):
        for item in value:
            _walk_inline(item, active=active, url=url, out=out, downgrades=downgrades)
        return
    match value.type:
        case "bold":
            _walk_inline(value.text, active=active | {"bold"}, url=url, out=out, downgrades=downgrades)
        case "italic":
            _walk_inline(value.text, active=active | {"italic"}, url=url, out=out, downgrades=downgrades)
        case "underline":
            _walk_inline(value.text, active=active | {"underline"}, url=url, out=out, downgrades=downgrades)
        case "strikethrough":
            _walk_inline(value.text, active=active | {"strikethrough"}, url=url, out=out, downgrades=downgrades)
        case "spoiler":
            _walk_inline(value.text, active=active | {"spoiler"}, url=url, out=out, downgrades=downgrades)
        case "marked":
            downgrades.add("marked:plain_text")
            _walk_inline(value.text, active=active, url=url, out=out, downgrades=downgrades)
        case "code":
            if active or url is not None:
                downgrades.add("code:nested:plain_text")
                _walk_inline(value.text, active=active, url=url, out=out, downgrades=downgrades)
            else:
                _walk_inline(value.text, active=active | {"code"}, url=url, out=out, downgrades=downgrades)
        case "subscript":
            downgrades.add("subscript:plain_text")
            _walk_inline(value.text, active=active, url=url, out=out, downgrades=downgrades)
        case "superscript":
            downgrades.add("superscript:plain_text")
            _walk_inline(value.text, active=active, url=url, out=out, downgrades=downgrades)
        case "url":
            _walk_inline(value.text, active=active, url=value.url, out=out, downgrades=downgrades)
        case "anchor":
            return  # anchors carry no visible text
        case "anchor_link":
            downgrades.add("anchor_link:plain_text")
            _walk_inline(value.text, active=active, url=url, out=out, downgrades=downgrades)
        case "reference" | "reference_link":
            downgrades.add("footnote:plain_text")
            _walk_inline(value.text, active=active, url=url, out=out, downgrades=downgrades)
        case "mathematical_expression":
            downgrades.add("formula:plain_text")
            if value.expression:
                out.append(_InlineRun(text=value.expression, kinds=active, url=url))
        case "custom_emoji":
            downgrades.add(f"custom_emoji:{value.custom_emoji_id}:unicode_fallback")
            out.append(_InlineRun(text=value.alternative_text, kinds=active, url=url))


def inline_runs(value: RichTextContent, *, downgrades: set[str]) -> list[_InlineRun]:
    out: list[_InlineRun] = []
    _walk_inline(value, active=frozenset(), url=None, out=out, downgrades=downgrades)
    return out


def inline_text(value: RichTextContent) -> str:
    return "".join(run.text for run in inline_runs(value, downgrades=set()))


class _SpanBuilder:
    """Builds single-line text plus entities, tracking UTF-16 offsets from zero."""

    def __init__(self) -> None:
        self.parts: list[str] = []
        self.entities: list[TelegramRichEntity] = []
        self._offset = 0

    def add_raw(self, value: str) -> None:
        self.parts.append(value)
        self._offset += utf16_length(value)

    def add_runs(
        self,
        runs: Sequence[_InlineRun],
        *,
        base_style: tuple[HeadingStyle, ...] = (),
    ) -> None:
        for run in runs:
            start = self._offset
            length = utf16_length(run.text)
            styles: list[EntityType] = []
            if "code" in run.kinds:
                if base_style:
                    # code cannot be nested inside other entities: a code run
                    # inside a styled context renders as plain text
                    styles = []
                else:
                    styles.append("code")
            else:
                for base in base_style:
                    styles.append(cast(EntityType, base))
                for kind in ("bold", "italic", "underline", "strikethrough", "spoiler"):
                    if kind in run.kinds:
                        styles.append(cast(EntityType, kind))
            self.add_raw(run.text)
            for entity_style in styles:
                self.entities.append(TelegramRichEntity(type=entity_style, offset=start, length=length))
            if run.url is not None:
                self.entities.append(TelegramRichEntity(type="text_link", offset=start, length=length, url=run.url))

    def finish(self) -> tuple[str, tuple[TelegramRichEntity, ...]]:
        unique = {_entity_sort_key(entity): entity for entity in self.entities}
        return "".join(self.parts), tuple(sorted(unique.values(), key=_entity_sort_key))


class _LineAssembler:
    """Assembles multi-line text with entities, tracking UTF-16 offsets across lines."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.entities: list[TelegramRichEntity] = []
        self._cursor = 0

    def add_line(self, text: str, entities: Sequence[TelegramRichEntity]) -> None:
        if self.lines:
            self._cursor += 1  # the "\n" separator
        base = self._cursor
        self.entities.extend(
            TelegramRichEntity(
                type=entity.type,
                offset=entity.offset + base,
                length=entity.length,
                url=entity.url,
                language=entity.language,
            )
            for entity in entities
        )
        self.lines.append(text)
        self._cursor += utf16_length(text)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    @property
    def finished_entities(self) -> tuple[TelegramRichEntity, ...]:
        return tuple(sorted(self.entities, key=_entity_sort_key))


def _render_inline(
    value: RichTextContent,
    *,
    base_style: tuple[HeadingStyle, ...] = (),
    downgrades: set[str],
) -> tuple[str, tuple[TelegramRichEntity, ...]]:
    builder = _SpanBuilder()
    builder.add_runs(inline_runs(value, downgrades=downgrades), base_style=base_style)
    return builder.finish()


def _caption_text(caption: RichBlockCaption) -> str:
    text = inline_text(caption.text)
    if caption.credit is not None:
        credit = inline_text(caption.credit)
        if credit:
            return f"{text} — {credit}"
    return text


def _shift_entities(
    entities: Sequence[TelegramRichEntity],
    delta: int,
) -> tuple[TelegramRichEntity, ...]:
    return tuple(
        TelegramRichEntity(
            type=entity.type,
            offset=entity.offset + delta,
            length=entity.length,
            url=entity.url,
            language=entity.language,
        )
        for entity in entities
    )


@dataclass(frozen=True)
class _Unit:
    """One render unit: text content or a media placement signal."""

    text: str = ""
    entities: tuple[TelegramRichEntity, ...] = ()
    media_block_ids: tuple[str, ...] = ()
    media_group: bool = False


def _text_unit(text: str, entities: tuple[TelegramRichEntity, ...] = ()) -> _Unit:
    return _Unit(text=text, entities=entities)


def _block_units(
    block: RichBlock,
    *,
    downgrades: set[str],
    include_media: bool,
) -> list[_Unit]:
    """Render one domain block into ordered render units."""
    if isinstance(block, RichBlockParagraph):
        text, entities = _render_inline(block.text, downgrades=downgrades)
        return [_text_unit(text, entities)]
    if isinstance(block, RichBlockHeading):
        text, entities = _render_inline(
            block.text,
            base_style=_heading_style(block.size),
            downgrades=downgrades,
        )
        return [_text_unit(text, entities)]
    if isinstance(block, RichBlockPreformatted):
        text = inline_text(block.text)
        entity = TelegramRichEntity(type="pre", offset=0, length=utf16_length(text), language=block.language)
        return [_text_unit(text, (entity,))]
    if isinstance(block, RichBlockFooter):
        text, entities = _render_inline(block.text, downgrades=downgrades)
        return [_text_unit(text, entities)]
    if isinstance(block, RichBlockDivider):
        return [_text_unit("---")]
    if isinstance(block, RichBlockMath):
        return [_text_unit(f"$${block.expression}$$")]
    if isinstance(block, RichBlockList):
        return [_render_list_block(block, downgrades=downgrades)]
    if isinstance(block, (RichBlockQuote, RichBlockPullQuote)):
        if isinstance(block, RichBlockPullQuote):
            downgrades.add(f"pullquote:{block.block_id}:blockquote")
        return [_render_quote_block(block, downgrades=downgrades)]
    if isinstance(block, RichBlockCollage):
        return _render_collage(block, downgrades=downgrades, include_media=include_media)
    if isinstance(block, RichBlockSlideshow):
        return _render_slideshow(block, downgrades=downgrades, include_media=include_media)
    if isinstance(block, RichBlockTable):
        return [_render_table(block, downgrades=downgrades)]
    if isinstance(block, RichBlockDetails):
        downgrades.add(f"details:{block.block_id}:expanded")
        return _render_details(block, downgrades=downgrades)
    if isinstance(block, RichBlockMedia):
        if not include_media:
            return []
        caption_text = _caption_text(block.caption) if block.caption is not None else ""
        return [_Unit(text=caption_text, media_block_ids=(block.block_id,))]
    raise TypeError(f"unexpected rich block: {type(block).__name__}")


def _render_list_block(block: RichBlockList, *, downgrades: set[str]) -> _Unit:
    assembler = _LineAssembler()
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
        inner_units: list[_Unit] = []
        for child in item.blocks:
            inner_units.extend(_block_units(child, downgrades=downgrades, include_media=False))
        inner_text = "\n".join(unit.text for unit in inner_units if unit.text)
        first_line_entities: tuple[TelegramRichEntity, ...] = ()
        for unit in inner_units:
            if unit.text:
                first_line_entities = unit.entities
                break
        lines = inner_text.splitlines() or [""]
        assembler.add_line(marker + lines[0], _shift_entities(first_line_entities, utf16_length(marker)))
        for line in lines[1:]:
            assembler.add_line("  " + line, ())
    return _text_unit(assembler.text, assembler.finished_entities)


def _render_quote_block(
    block: RichBlockQuote | RichBlockPullQuote,
    *,
    downgrades: set[str],
) -> _Unit:
    inner_units: list[_Unit] = []
    if isinstance(block, RichBlockQuote):
        for child in block.blocks:
            inner_units.extend(_block_units(child, downgrades=downgrades, include_media=False))
    else:  # RichBlockPullQuote
        text, entities = _render_inline(block.text, downgrades=downgrades)
        inner_units.append(_text_unit(text, entities))
    if block.credit is not None:
        credit_text = inline_text(block.credit)
        if credit_text:
            inner_units.append(_text_unit("— " + credit_text))

    assembler = _LineAssembler()
    for unit in inner_units:
        if not unit.text:
            continue
        quote_entity = TelegramRichEntity(type="blockquote", offset=0, length=utf16_length(unit.text))
        assembler.add_line(unit.text, (quote_entity,) + tuple(unit.entities))
    return _text_unit(assembler.text, assembler.finished_entities)


def _render_collage(
    block: RichBlockCollage,
    *,
    downgrades: set[str],
    include_media: bool,
) -> list[_Unit]:
    media_blocks = [child for child in block.blocks if isinstance(child, RichBlockMedia)]
    non_media = [child for child in block.blocks if not isinstance(child, RichBlockMedia)]
    if non_media:
        downgrades.add(f"collage:{block.block_id}:non_media_rendered_as_text")

    units: list[_Unit] = []
    for child in non_media:
        units.extend(_block_units(child, downgrades=downgrades, include_media=False))

    if not include_media or not media_blocks:
        if media_blocks:
            downgrades.add(f"collage:{block.block_id}:media_dropped_text_only")
        return units

    group_caption = _caption_text(block.caption) if block.caption is not None else ""
    units.append(
        _Unit(
            text=group_caption,
            media_block_ids=tuple(media_block.block_id for media_block in media_blocks),
            media_group=True,
        )
    )
    return units


def _render_slideshow(
    block: RichBlockSlideshow,
    *,
    downgrades: set[str],
    include_media: bool,
) -> list[_Unit]:
    media_blocks = [child for child in block.blocks if isinstance(child, RichBlockMedia)]
    non_media = [child for child in block.blocks if not isinstance(child, RichBlockMedia)]
    if non_media:
        downgrades.add(f"slideshow:{block.block_id}:non_media_rendered_as_text")

    units: list[_Unit] = []
    for child in non_media:
        units.extend(_block_units(child, downgrades=downgrades, include_media=False))

    if not include_media:
        if media_blocks:
            downgrades.add(f"slideshow:{block.block_id}:media_dropped_text_only")
        return units

    if block.caption is not None:
        units.append(_text_unit(_caption_text(block.caption)))
    for media_block in media_blocks:
        caption_text = _caption_text(media_block.caption) if media_block.caption is not None else ""
        units.append(_Unit(text=caption_text, media_block_ids=(media_block.block_id,)))
    return units


def _render_table(block: RichBlockTable, *, downgrades: set[str]) -> _Unit:
    downgrades.add(f"table:{block.block_id}:plain_text")
    assembler = _LineAssembler()
    if block.caption is not None:
        caption_text, entities = _render_inline(block.caption, downgrades=downgrades)
        assembler.add_line(caption_text, entities)
    for row in block.cells:
        cells: list[str] = []
        for cell in row:
            cells.append(inline_text(cell.text) if cell.text is not None else "")
        assembler.add_line("| " + " | ".join(cells) + " |", ())
    return _text_unit(assembler.text, assembler.finished_entities)


def _render_details(block: RichBlockDetails, *, downgrades: set[str]) -> list[_Unit]:
    summary_text, summary_entities = _render_inline(block.summary, downgrades=downgrades)
    units: list[_Unit] = [_text_unit(summary_text, summary_entities)]
    for child in block.blocks:
        units.extend(_block_units(child, downgrades=downgrades, include_media=False))
    return units


def media_bundle_sha256(document: RichArticleDocument) -> str | None:
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


def canonical_article_text(
    document: RichArticleDocument,
    *,
    include_media_captions: bool = True,
) -> str:
    """Deterministic canonical text projection of a rich article document.

    The rich renderer guarantees ``plan.visible_text == canonical_article_text``
    (with ``include_media_captions=True``); the legacy HTML fallback guarantees
    the same with ``include_media_captions=False`` (media is dropped in legacy
    text mode).  The projection preserves every text fragment of the document
    in order; media captions are media metadata and contribute only when the
    media itself is rendered.
    """
    downgrades: set[str] = set()
    units: list[str] = [document.metadata.title]
    for block in document.blocks:
        for unit in _block_units(
            block,
            downgrades=downgrades,
            include_media=include_media_captions,
        ):
            if unit.text:
                units.append(unit.text)
    return "\n\n".join(units)


def _media_block_by_id(document: RichArticleDocument) -> dict[str, RichBlockMedia]:
    return {block.block_id: block for block in iter_blocks(document.blocks) if isinstance(block, RichBlockMedia)}


def _single_media_request(
    media_block: RichBlockMedia,
    media: RichMediaRef,
    caption: str | None,
) -> tuple[str, dict[str, Any]]:
    method, key = _SINGLE_MEDIA_METHOD[media.kind]
    payload: dict[str, Any] = {key: media.uri}
    if caption:
        validate_message_text(caption, (), caption=True)
        payload["caption"] = caption
    return method, payload


def _media_group_requests(
    media_blocks: tuple[RichBlockMedia, ...],
    media_by_id: dict[str, RichMediaRef],
    group_caption: str,
    downgrades: set[str],
) -> list[tuple[str, dict[str, Any]]]:
    refs = [media_by_id[block.media_id] for block in media_blocks]
    if len(refs) == 1:
        caption = group_caption or (
            _caption_text(media_blocks[0].caption) if media_blocks[0].caption is not None else ""
        )
        method, payload = _single_media_request(media_blocks[0], refs[0], caption or None)
        downgrades.add(f"collage:{media_blocks[0].block_id}:single_item:{method}")
        return [(method, payload)]
    if len(refs) > MAX_MEDIA_GROUP_ITEMS:
        raise ValueError(f"collage media group exceeds the classic Telegram limit of {MAX_MEDIA_GROUP_ITEMS} items")
    entries: list[dict[str, Any]] = []
    for index, (media_block, media) in enumerate(zip(media_blocks, refs, strict=True)):
        if media.kind == "voice_note":
            raise ValueError(
                "voice notes cannot be sent in a classic sendMediaGroup collage; "
                "use standalone or slideshow media blocks"
            )
        entry: dict[str, Any] = {"type": media.kind, "media": media.uri}
        if index == 0:
            caption = group_caption or (_caption_text(media_block.caption) if media_block.caption is not None else "")
            if caption:
                validate_message_text(caption, (), caption=True)
                entry["caption"] = caption
        elif media_block.caption is not None:
            downgrades.add(f"collage:{media_block.block_id}:caption_dropped")
        entries.append(entry)
    return [("sendMediaGroup", {"media": entries})]


def _build_requests(
    document: RichArticleDocument,
    downgrades: set[str],
) -> tuple[TelegramRichRequest, ...]:
    media_by_id = {entry.media_id: entry for entry in document.media}
    media_block_by_id = _media_block_by_id(document)

    raw: list[tuple[str, dict[str, Any]]] = []
    pending_text: list[str] = []
    pending_entities: list[TelegramRichEntity] = []
    pending_base = 0

    def flush() -> None:
        nonlocal pending_text, pending_entities, pending_base
        if not pending_text:
            return
        text = "\n\n".join(pending_text)
        entities = tuple(sorted(pending_entities, key=_entity_sort_key))
        validate_message_text(text, entities)
        payload: dict[str, Any] = {"text": text}
        if entities:
            payload["entities"] = [entity.model_dump(mode="json") for entity in entities]
        payload["link_preview_options"] = {"is_disabled": True}
        raw.append(("sendMessage", payload))
        pending_text = []
        pending_entities = []
        pending_base = 0

    def append_unit(unit: _Unit) -> None:
        nonlocal pending_text, pending_entities, pending_base
        if not unit.text:
            return
        length = utf16_length(unit.text)
        if length > MAX_MESSAGE_TEXT:
            raise ValueError("a single article block exceeds the 4096 Telegram message limit")
        if pending_text and pending_base + 2 + length > MAX_MESSAGE_TEXT:
            flush()
        base = pending_base + (2 if pending_text else 0)
        pending_entities.extend(
            TelegramRichEntity(
                type=entity.type,
                offset=entity.offset + base,
                length=entity.length,
                url=entity.url,
                language=entity.language,
            )
            for entity in unit.entities
        )
        pending_text.append(unit.text)
        pending_base = base + length

    title_builder = _SpanBuilder()
    title_builder.add_runs([_InlineRun(text=document.metadata.title)], base_style=("bold",))
    title_text, title_entities = title_builder.finish()
    append_unit(_text_unit(title_text, title_entities))

    for block in document.blocks:
        for unit in _block_units(block, downgrades=downgrades, include_media=True):
            if unit.media_block_ids:
                flush()
                media_blocks = tuple(media_block_by_id[logical_id] for logical_id in unit.media_block_ids)
                if unit.media_group:
                    raw.extend(_media_group_requests(media_blocks, media_by_id, unit.text, downgrades))
                else:
                    for media_block in media_blocks:
                        caption = unit.text or None
                        raw.append(
                            _single_media_request(
                                media_block,
                                media_by_id[media_block.media_id],
                                caption,
                            )
                        )
                continue
            append_unit(unit)
    flush()

    return tuple(
        TelegramRichRequest(sequence=index, method=method, payload=payload)
        for index, (method, payload) in enumerate(raw, start=1)
    )


def _visible_unit(method: str, payload: dict[str, Any]) -> str:
    if method == "sendMessage":
        text = payload.get("text")
        return str(text) if isinstance(text, str) else ""
    if method in _SINGLE_MEDIA_METHODS:
        caption = payload.get("caption")
        return str(caption) if isinstance(caption, str) else ""
    if method == "sendMediaGroup":
        media = payload.get("media")
        if isinstance(media, list) and media and isinstance(media[0], dict):
            caption = media[0].get("caption")
            return str(caption) if isinstance(caption, str) else ""
        return ""
    return ""


def extract_visible_text(plan: TelegramRichPlan) -> str:
    """Extract the rendered visible text from a plan, in request order."""
    units: list[str] = []
    for request in plan.requests:
        text = _visible_unit(request.method, request.payload)
        if text:
            units.append(text)
    return "\n\n".join(units)


def compute_rich_payload_sha256(plan: TelegramRichPlan) -> str:
    """Deterministic ``sha256:`` digest of the full rich plan payload."""
    payload: dict[str, Any] = {
        "schema_name": plan.schema_name,
        "schema_version": plan.schema_version,
        "renderer_id": plan.renderer_id,
        "article_sha256": plan.article_sha256,
        "media_bundle_sha256": plan.media_bundle_sha256,
        "requests": [
            {"sequence": request.sequence, "method": request.method, "payload": request.payload}
            for request in plan.requests
        ],
        "visible_text": plan.visible_text,
        "downgrades": list(plan.downgrades),
    }
    return sha256_text(canonical_json(payload))


def render_rich_article(
    document: RichArticleDocument,
) -> TelegramRichPlan:
    """Render a rich article document into a deterministic Telegram rich plan."""
    validate_document(document)

    downgrades: set[str] = set()
    requests = _build_requests(document, downgrades)
    visible_text = "\n\n".join(text for text in (_visible_unit(r.method, r.payload) for r in requests) if text)
    if visible_text != canonical_article_text(document, include_media_captions=True):
        raise ValueError("rendered visible text differs from the canonical article projection")

    payload_object: dict[str, Any] = {
        "schema_name": "video-channel-manager.telegram-rich-plan",
        "schema_version": 1,
        "renderer_id": "deterministic-rich-v1",
        "article_sha256": document.digest,
        "media_bundle_sha256": media_bundle_sha256(document),
        "requests": [{"sequence": r.sequence, "method": r.method, "payload": r.payload} for r in requests],
        "visible_text": visible_text,
        "downgrades": list(sorted(downgrades)),
    }
    return TelegramRichPlan(
        schema_name="video-channel-manager.telegram-rich-plan",
        schema_version=1,
        renderer_id="deterministic-rich-v1",
        article_sha256=document.digest,
        media_bundle_sha256=payload_object["media_bundle_sha256"],
        requests=requests,
        visible_text=visible_text,
        downgrades=tuple(sorted(downgrades)),
        rich_payload_sha256=sha256_text(canonical_json(payload_object)),
    )


__all__ = [
    "MAX_CAPTION_TEXT",
    "MAX_MEDIA_GROUP_ITEMS",
    "MAX_MESSAGE_TEXT",
    "MIN_MEDIA_GROUP_ITEMS",
    "TelegramRichEntity",
    "TelegramRichPlan",
    "TelegramRichRequest",
    "canonical_article_text",
    "compute_rich_payload_sha256",
    "extract_visible_text",
    "inline_runs",
    "inline_text",
    "media_bundle_sha256",
    "render_rich_article",
    "validate_message_text",
    "validate_request_payload",
]
