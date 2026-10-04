from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from video_channel_manager.telegram_models import (
    MAX_TELEGRAM_TEXT_LENGTH,
    SHA256_PATTERN,
    TelegramPost,
    canonical_json,
    sha256_text,
)

CANONICAL_PRESENTATION_POLICY_PATH = Path("content/telegram/lordchrist/presentation-policy.json")
QUOTE_V3_PRESENTATION_POLICY_PATH = Path("content/telegram/lordchrist/presentation-policy-v3.json")
QUOTE_V4_PRESENTATION_POLICY_PATH = Path("content/telegram/lordchrist/presentation-policy-v4.json")
DIRECT_QUOTE_RE = re.compile(r"«[^»\n]+»")
FormattingType = Literal["bold", "italic", "blockquote"]


class BodyQuoteEmphasisPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    bold_selection: Literal["longest_direct_quote"] = "longest_direct_quote"
    remaining_direct_quotes: Literal["italic"] = "italic"
    no_direct_quote: Literal["plain"] = "plain"


class AttributionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    copyright_prefix: Literal[False] = False
    author_style: Literal["bold"] = "bold"
    work_style: Literal["italic"] = "italic"


class SpacingPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    quote_paragraph_separator: Literal["\n\n"] = "\n\n"
    body_to_attribution: Literal["\n\n"] = "\n\n"
    attribution_to_hashtags: Literal["\n\n\n"] = "\n\n\n"


class PresentationPolicy(BaseModel):
    """Legacy/current editorial-v2 policy.

    This remains byte-for-byte compatible with the already published successor
    release. New quote-card releases opt into an explicit quote policy.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-presentation-policy"]
    schema_version: Literal[2]
    policy_id: Literal["lordchrist-editorial-v2"]
    parse_mode: Literal["HTML"]
    body_quote_emphasis: BodyQuoteEmphasisPolicy
    attribution: AttributionPolicy
    spacing: SpacingPolicy
    link_preview_disabled: Literal[True] = True

    @property
    def digest(self) -> str:
        return sha256_text(canonical_json(self.model_dump(mode="json")))


class QuotePresentationPolicyV3(BaseModel):
    """Original reader-facing policy for reviewed quote cards.

    V3 is retained as immutable presentation history for already published
    quote-card material. It deliberately used one blank line between every
    semantic block.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-presentation-policy"]
    schema_version: Literal[3]
    policy_id: Literal["lordchrist-quote-v3"]
    parse_mode: Literal["HTML"]
    quote_style: Literal["blockquote"]
    attribution_style: Literal["italic"]
    attribution_prefix: Literal["— "]
    block_separator: Literal["\n\n"]
    link_preview_disabled: Literal[True] = True

    @property
    def digest(self) -> str:
        return sha256_text(canonical_json(self.model_dump(mode="json")))


class QuotePresentationPolicyV4(BaseModel):
    """Hardened quote-card policy for the post-v3 future suffix.

    The reviewed title is a visible context lead immediately above the source-
    bound quotation. The source line belongs visually to the quotation and
    follows it immediately on the next line. Editorial context and hashtags
    remain distinct blocks separated by one blank line.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-presentation-policy"]
    schema_version: Literal[4]
    policy_id: Literal["lordchrist-quote-v4"]
    parse_mode: Literal["HTML"]
    title_style: Literal["bold"]
    title_to_quote_separator: Literal["\n"]
    quote_style: Literal["blockquote"]
    attribution_style: Literal["italic"]
    attribution_prefix: Literal["— "]
    quote_to_attribution_separator: Literal["\n"]
    block_separator: Literal["\n\n"]
    link_preview_disabled: Literal[True] = True

    @property
    def digest(self) -> str:
        return sha256_text(canonical_json(self.model_dump(mode="json")))


PresentationPolicyContract = PresentationPolicy | QuotePresentationPolicyV3 | QuotePresentationPolicyV4
QuoteCardPresentationPolicy = QuotePresentationPolicyV3 | QuotePresentationPolicyV4


class TelegramTextEntity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: FormattingType
    offset: int = Field(ge=0)
    length: int = Field(gt=0)


class RenderedTelegramPost(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-rendered-post"]
    schema_version: Literal[2]
    publication_id: str = Field(pattern=r"^lordchrist-[a-z0-9][a-z0-9-]{4,100}$")
    source_payload_sha256: str = Field(pattern=SHA256_PATTERN)
    presentation_policy_id: Literal["lordchrist-editorial-v2", "lordchrist-quote-v3", "lordchrist-quote-v4"]
    presentation_policy_sha256: str = Field(pattern=SHA256_PATTERN)
    provider_payload_sha256: str = Field(pattern=SHA256_PATTERN)
    parse_mode: Literal["HTML"]
    text: str = Field(min_length=100, max_length=MAX_TELEGRAM_TEXT_LENGTH)
    html_text: str = Field(min_length=100)
    expected_entities: tuple[TelegramTextEntity, ...]
    link_preview_disabled: Literal[True] = True

    @model_validator(mode="after")
    def validate_rendered_contract(self) -> "RenderedTelegramPost":
        if "© " in self.text:
            raise ValueError("rendered Telegram publication must not contain the legacy copyright prefix")
        types = {entity.type for entity in self.expected_entities}
        if self.presentation_policy_id == "lordchrist-editorial-v2":
            if "\n\n\n#" not in self.text:
                raise ValueError("editorial-v2 publication must contain approved extra spacing before hashtags")
            if not {"bold", "italic"}.issubset(types):
                raise ValueError("editorial-v2 publication requires bold and italic entities")
        else:
            if "Пояснение:" in self.text:
                raise ValueError("quote publication must not expose the editorial label")
            if "\n\n#" not in self.text:
                raise ValueError("quote publication must keep hashtags as a separate final block")
            required_types = {"blockquote", "italic"}
            if self.presentation_policy_id == "lordchrist-quote-v4":
                required_types.add("bold")
            if not required_types.issubset(types):
                raise ValueError("quote publication is missing required presentation entities")
        return self


DEFAULT_PRESENTATION_POLICY = PresentationPolicy(
    schema_name="video-channel-manager.telegram-presentation-policy",
    schema_version=2,
    policy_id="lordchrist-editorial-v2",
    parse_mode="HTML",
    body_quote_emphasis=BodyQuoteEmphasisPolicy(),
    attribution=AttributionPolicy(),
    spacing=SpacingPolicy(),
    link_preview_disabled=True,
)

DEFAULT_QUOTE_V3_PRESENTATION_POLICY = QuotePresentationPolicyV3(
    schema_name="video-channel-manager.telegram-presentation-policy",
    schema_version=3,
    policy_id="lordchrist-quote-v3",
    parse_mode="HTML",
    quote_style="blockquote",
    attribution_style="italic",
    attribution_prefix="— ",
    block_separator="\n\n",
    link_preview_disabled=True,
)

DEFAULT_QUOTE_V4_PRESENTATION_POLICY = QuotePresentationPolicyV4(
    schema_name="video-channel-manager.telegram-presentation-policy",
    schema_version=4,
    policy_id="lordchrist-quote-v4",
    parse_mode="HTML",
    title_style="bold",
    title_to_quote_separator="\n",
    quote_style="blockquote",
    attribution_style="italic",
    attribution_prefix="— ",
    quote_to_attribution_separator="\n",
    block_separator="\n\n",
    link_preview_disabled=True,
)


class _RenderBuilder:
    def __init__(self) -> None:
        self._plain: list[str] = []
        self._html: list[str] = []
        self._entities: list[TelegramTextEntity] = []
        self._utf16_offset = 0

    @staticmethod
    def _utf16_length(value: str) -> int:
        return len(value.encode("utf-16-le")) // 2

    def append(self, value: str) -> None:
        self._plain.append(value)
        self._html.append(html.escape(value, quote=False))
        self._utf16_offset += self._utf16_length(value)

    def append_styled(self, value: str, style: FormattingType) -> None:
        length = self._utf16_length(value)
        self._plain.append(value)
        escaped = html.escape(value, quote=False)
        if style == "bold":
            rendered = f"<b>{escaped}</b>"
        elif style == "italic":
            rendered = f"<i>{escaped}</i>"
        elif style == "blockquote":
            rendered = f"<blockquote>{escaped}</blockquote>"
        else:  # pragma: no cover - protected by Literal at validation boundaries
            raise ValueError(f"unsupported Telegram formatting type: {style}")
        self._html.append(rendered)
        self._entities.append(TelegramTextEntity(type=style, offset=self._utf16_offset, length=length))
        self._utf16_offset += length

    @property
    def text(self) -> str:
        return "".join(self._plain)

    @property
    def html_text(self) -> str:
        return "".join(self._html)

    @property
    def entities(self) -> tuple[TelegramTextEntity, ...]:
        return tuple(self._entities)


def load_presentation_policy(
    path: Path = CANONICAL_PRESENTATION_POLICY_PATH,
) -> PresentationPolicyContract:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        policy_id = payload.get("policy_id") if isinstance(payload, dict) else None
        if policy_id == "lordchrist-editorial-v2":
            policy: PresentationPolicyContract = PresentationPolicy.model_validate(payload)
            expected_digest = DEFAULT_PRESENTATION_POLICY.digest
        elif policy_id == "lordchrist-quote-v3":
            policy = QuotePresentationPolicyV3.model_validate(payload)
            expected_digest = DEFAULT_QUOTE_V3_PRESENTATION_POLICY.digest
        elif policy_id == "lordchrist-quote-v4":
            policy = QuotePresentationPolicyV4.model_validate(payload)
            expected_digest = DEFAULT_QUOTE_V4_PRESENTATION_POLICY.digest
        else:
            raise ValueError(f"unsupported Telegram presentation policy id: {policy_id!r}")
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise ValueError(f"invalid Telegram presentation policy {path}: {exc}") from exc

    if policy.digest != expected_digest:
        raise ValueError(f"presentation policy artifact differs from the code-reviewed {policy.policy_id} contract")
    return policy


def load_rendered_post(path: Path) -> RenderedTelegramPost:
    try:
        return RenderedTelegramPost.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid rendered Telegram post {path}: {exc}") from exc


def _render_quote_paragraph(
    builder: _RenderBuilder,
    paragraph: str,
    *,
    direct_quote_index: int,
    bold_quote_index: int | None,
) -> int:
    cursor = 0
    quote_index = direct_quote_index
    for match in DIRECT_QUOTE_RE.finditer(paragraph):
        builder.append(paragraph[cursor : match.start()])
        style: FormattingType = "bold" if quote_index == bold_quote_index else "italic"
        builder.append_styled(match.group(0), style)
        quote_index += 1
        cursor = match.end()
    builder.append(paragraph[cursor:])
    return quote_index


def _select_bold_quote_index(quote_blocks: list[str], policy: PresentationPolicy) -> int | None:
    if policy.body_quote_emphasis.bold_selection != "longest_direct_quote":
        raise ValueError("unsupported direct-quote emphasis selector")
    quotes = [match.group(0) for block in quote_blocks for match in DIRECT_QUOTE_RE.finditer(block)]
    if not quotes:
        return None
    return max(range(len(quotes)), key=lambda index: (len(quotes[index]), -index))


def _provider_payload(
    *,
    post: TelegramPost,
    policy: PresentationPolicyContract,
    builder: _RenderBuilder,
) -> RenderedTelegramPost:
    plain_text = builder.text
    html_text = builder.html_text
    if len(plain_text) > MAX_TELEGRAM_TEXT_LENGTH:
        raise ValueError(
            f"rendered Telegram publication exceeds {MAX_TELEGRAM_TEXT_LENGTH} characters: {post.publication_id}"
        )
    payload = {
        "publication_id": post.publication_id,
        "source_payload_sha256": post.payload_sha256,
        "presentation_policy_sha256": policy.digest,
        "parse_mode": policy.parse_mode,
        "text": plain_text,
        "html_text": html_text,
        "expected_entities": [entity.model_dump(mode="json") for entity in builder.entities],
        "link_preview_disabled": policy.link_preview_disabled,
    }
    return RenderedTelegramPost(
        schema_name="video-channel-manager.telegram-rendered-post",
        schema_version=2,
        publication_id=post.publication_id,
        source_payload_sha256=post.payload_sha256,
        presentation_policy_id=policy.policy_id,
        presentation_policy_sha256=policy.digest,
        provider_payload_sha256=sha256_text(canonical_json(payload)),
        parse_mode=policy.parse_mode,
        text=plain_text,
        html_text=html_text,
        expected_entities=builder.entities,
        link_preview_disabled=policy.link_preview_disabled,
    )


def _render_post_v2(post: TelegramPost, policy: PresentationPolicy) -> RenderedTelegramPost:
    blocks = [block.strip() for block in post.text.split("\n\n") if block.strip()]
    if len(blocks) < 3:
        raise ValueError("editorial-v2 source text does not contain body, attribution and hashtags")
    quote_blocks = blocks[:-2]
    hashtags = blocks[-1]
    bold_quote_index = _select_bold_quote_index(quote_blocks, policy)

    builder = _RenderBuilder()
    direct_quote_index = 0
    for index, paragraph in enumerate(quote_blocks):
        direct_quote_index = _render_quote_paragraph(
            builder,
            paragraph,
            direct_quote_index=direct_quote_index,
            bold_quote_index=bold_quote_index,
        )
        if index != len(quote_blocks) - 1:
            builder.append(policy.spacing.quote_paragraph_separator)

    builder.append(policy.spacing.body_to_attribution)
    builder.append_styled(post.source.author, "bold")
    builder.append(", ")
    builder.append_styled(f"«{post.source.work}»", "italic")
    builder.append(policy.spacing.attribution_to_hashtags)
    builder.append(hashtags)

    if "© " in builder.text:
        raise ValueError("rendered Telegram publication must not contain the legacy copyright prefix")
    if not builder.text.endswith(hashtags):
        raise ValueError("rendered Telegram publication must preserve the original hashtag block")
    if policy.spacing.attribution_to_hashtags not in builder.text:
        raise ValueError("rendered Telegram publication must preserve the approved hashtag spacing")
    return _provider_payload(post=post, policy=policy, builder=builder)


SENTENCE_TERMINATORS = (".", "!", "?", "…", ":", ";")
DANGLING_TRAILING_CONNECTORS = (
    "и",
    "а",
    "но",
    "однако",
    "что",
    "чтобы",
    "который",
    "которая",
    "которое",
    "которые",
    "если",
    "когда",
    "потому",
    "поэтому",
    "так",
)


def _require_standalone_quotation(quote: str) -> None:
    """Reject structurally incomplete quotation fragments without a length rule.

    Brevity is not a defect: a short, complete aphorism is a valid quotation.
    What is rejected here is an excerpt that cannot be a sentence on its own -
    an excerpt that starts mid-sentence or stops before its predicate - because
    such a fragment reads as torn from the preceding source context.
    """

    stripped = quote.strip()
    if not stripped:
        raise ValueError("quote quotation must not be empty")
    if not any(character.isalpha() for character in stripped):
        raise ValueError("quote quotation must contain reviewed words")
    if stripped[0].islower():
        raise ValueError("quote quotation must not start mid-sentence")
    if not stripped.endswith(SENTENCE_TERMINATORS):
        raise ValueError("quote quotation must keep the source sentence ending")
    trailing = stripped[:-1].rstrip().casefold().split()
    if trailing and trailing[-1].rstrip(",") in DANGLING_TRAILING_CONNECTORS:
        raise ValueError("quote quotation must not end on a dangling connector")


def reviewed_attribution_line(post: TelegramPost) -> str | None:
    """Return the reviewed attribution line carried by a successor runtime post.

    Successor runtime posts bind the human-reviewed attribution string next to
    the normalized evidence identity. Older ``TelegramPost`` payloads predate
    that field and keep the historical derived rendering.
    """

    value = getattr(post, "attribution_text", None)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("reviewed attribution text must be a non-empty string")
    return " ".join(value.strip().split())


def expected_attribution_line(post: TelegramPost, policy: QuoteCardPresentationPolicy) -> str:
    """The exact reader-facing attribution line for a reviewed quote card."""

    reviewed = reviewed_attribution_line(post)
    if reviewed is not None:
        return f"{policy.attribution_prefix}{reviewed}"
    return f"{policy.attribution_prefix}{post.source.author}, «{post.source.work}»"


def _quote_card_blocks(post: TelegramPost, policy: QuoteCardPresentationPolicy) -> tuple[str, str, str, str]:
    if "© " in post.text or "Пояснение:" in post.text:
        raise ValueError("quote source text must not contain legacy presentation labels")
    blocks = [block.strip() for block in post.text.replace("\r\n", "\n").strip().split("\n\n") if block.strip()]
    if len(blocks) < 4:
        raise ValueError("quote source text must contain quote, attribution, context and hashtags")

    expected_attribution = expected_attribution_line(post, policy)
    attribution_indexes = [index for index, block in enumerate(blocks[:-1]) if block == expected_attribution]
    if len(attribution_indexes) != 1:
        raise ValueError("quote source text must contain exactly one source-bound attribution block")
    attribution_index = attribution_indexes[0]
    if attribution_index < 1 or attribution_index >= len(blocks) - 2:
        raise ValueError("quote attribution must sit between quotation and editorial context")

    quote = "\n\n".join(blocks[:attribution_index]).strip()
    context = "\n\n".join(blocks[attribution_index + 1 : -1]).strip()
    hashtags = blocks[-1]
    _require_standalone_quotation(quote)
    if len(context) < 80:
        raise ValueError("quote editorial context must be substantive")
    tags = hashtags.split()
    if not 2 <= len(tags) <= 8 or any(not tag.startswith("#") or any(ch.isspace() for ch in tag) for tag in tags):
        raise ValueError("quote hashtags must be a compact final block")
    return quote, expected_attribution, context, hashtags


def _render_post_v3(post: TelegramPost, policy: QuotePresentationPolicyV3) -> RenderedTelegramPost:
    quote, attribution, context, hashtags = _quote_card_blocks(post, policy)
    sep = policy.block_separator

    builder = _RenderBuilder()
    builder.append_styled(quote, "blockquote")
    builder.append(sep)
    builder.append_styled(attribution, "italic")
    builder.append(sep)
    builder.append(context)
    builder.append(sep)
    builder.append(hashtags)

    return _provider_payload(post=post, policy=policy, builder=builder)


def _render_post_v4(post: TelegramPost, policy: QuotePresentationPolicyV4) -> RenderedTelegramPost:
    quote, attribution, context, hashtags = _quote_card_blocks(post, policy)

    builder = _RenderBuilder()
    builder.append_styled(post.title, "bold")
    builder.append(policy.title_to_quote_separator)
    builder.append_styled(quote, "blockquote")
    builder.append(policy.quote_to_attribution_separator)
    builder.append_styled(attribution, "italic")
    builder.append(policy.block_separator)
    builder.append(context)
    builder.append(policy.block_separator)
    builder.append(hashtags)

    rendered = _provider_payload(post=post, policy=policy, builder=builder)
    expected_boundary = (
        f"{post.title}{policy.title_to_quote_separator}{quote}{policy.quote_to_attribution_separator}{attribution}"
    )
    if not rendered.text.startswith(expected_boundary):
        raise ValueError("quote-v4 title, quotation and source must form one immediate reading unit")
    if f"{post.title}\n\n{quote}" in rendered.text:
        raise ValueError("quote-v4 must not insert a blank line between title and quotation")
    if f"{quote}\n\n{attribution}" in rendered.text:
        raise ValueError("quote-v4 must not insert a blank line between quotation and source attribution")
    return rendered


def render_post(
    post: TelegramPost,
    policy: PresentationPolicyContract = DEFAULT_PRESENTATION_POLICY,
) -> RenderedTelegramPost:
    if isinstance(policy, PresentationPolicy):
        if policy.digest != DEFAULT_PRESENTATION_POLICY.digest:
            raise ValueError("unsupported Telegram presentation policy")
        return _render_post_v2(post, policy)
    if isinstance(policy, QuotePresentationPolicyV3):
        if policy.digest != DEFAULT_QUOTE_V3_PRESENTATION_POLICY.digest:
            raise ValueError("unsupported Telegram quote-v3 presentation policy")
        return _render_post_v3(post, policy)
    if isinstance(policy, QuotePresentationPolicyV4):
        if policy.digest != DEFAULT_QUOTE_V4_PRESENTATION_POLICY.digest:
            raise ValueError("unsupported Telegram quote-v4 presentation policy")
        return _render_post_v4(post, policy)
    raise ValueError("unsupported Telegram presentation policy type")


def verify_rendered_post(
    post: TelegramPost,
    policy: PresentationPolicyContract,
    rendered: RenderedTelegramPost,
) -> None:
    expected = render_post(post, policy)
    if rendered.model_dump(mode="json") != expected.model_dump(mode="json"):
        raise ValueError("rendered Telegram provider payload differs from the reviewed presentation policy")


def formatting_entities_match(
    expected: tuple[TelegramTextEntity, ...],
    actual: Any,
) -> bool:
    if not isinstance(actual, list):
        return False

    actual_formatting: list[tuple[str, int, int]] = []
    allowed = {"bold", "italic", "blockquote"}
    for entity in actual:
        if not isinstance(entity, dict):
            continue
        entity_type = str(entity.get("type") or "")
        if entity_type not in allowed:
            continue
        try:
            offset = int(entity["offset"])
            length = int(entity["length"])
        except (KeyError, TypeError, ValueError):
            return False
        actual_formatting.append((entity_type, offset, length))

    expected_formatting = [(entity.type, entity.offset, entity.length) for entity in expected]
    return sorted(actual_formatting) == sorted(expected_formatting)
