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
DIRECT_QUOTE_RE = re.compile(r"«[^»\n]+»")
FormattingType = Literal["bold", "italic"]


class BodyQuoteEmphasisPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    first_direct_quote: Literal["bold"] = "bold"
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
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-presentation-policy"]
    schema_version: Literal[1]
    policy_id: Literal["lordchrist-editorial-v1"]
    parse_mode: Literal["HTML"]
    body_quote_emphasis: BodyQuoteEmphasisPolicy
    attribution: AttributionPolicy
    spacing: SpacingPolicy
    link_preview_disabled: Literal[True] = True

    @property
    def digest(self) -> str:
        return sha256_text(canonical_json(self.model_dump(mode="json")))


class TelegramTextEntity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: FormattingType
    offset: int = Field(ge=0)
    length: int = Field(gt=0)


class RenderedTelegramPost(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-rendered-post"]
    schema_version: Literal[1]
    publication_id: str = Field(pattern=r"^lordchrist-[a-z0-9][a-z0-9-]{4,80}$")
    source_payload_sha256: str = Field(pattern=SHA256_PATTERN)
    presentation_policy_id: Literal["lordchrist-editorial-v1"]
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
        if "\n\n\n#" not in self.text:
            raise ValueError("rendered Telegram publication must contain the approved extra spacing before hashtags")
        if not any(entity.type == "bold" for entity in self.expected_entities):
            raise ValueError("rendered Telegram publication must contain at least one bold entity")
        if not any(entity.type == "italic" for entity in self.expected_entities):
            raise ValueError("rendered Telegram publication must contain at least one italic entity")
        return self


DEFAULT_PRESENTATION_POLICY = PresentationPolicy(
    schema_name="video-channel-manager.telegram-presentation-policy",
    schema_version=1,
    policy_id="lordchrist-editorial-v1",
    parse_mode="HTML",
    body_quote_emphasis=BodyQuoteEmphasisPolicy(),
    attribution=AttributionPolicy(),
    spacing=SpacingPolicy(),
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
        tag = "b" if style == "bold" else "i"
        self._html.append(f"<{tag}>{escaped}</{tag}>")
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


def load_presentation_policy(path: Path = CANONICAL_PRESENTATION_POLICY_PATH) -> PresentationPolicy:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        policy = PresentationPolicy.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"invalid Telegram presentation policy {path}: {exc}") from exc

    if policy.digest != DEFAULT_PRESENTATION_POLICY.digest:
        raise ValueError("presentation policy artifact differs from the code-reviewed lordchrist-editorial-v1 contract")
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
) -> int:
    cursor = 0
    quote_index = direct_quote_index
    for match in DIRECT_QUOTE_RE.finditer(paragraph):
        builder.append(paragraph[cursor : match.start()])
        style: FormattingType = "bold" if quote_index == 0 else "italic"
        builder.append_styled(match.group(0), style)
        quote_index += 1
        cursor = match.end()
    builder.append(paragraph[cursor:])
    return quote_index


def render_post(
    post: TelegramPost,
    policy: PresentationPolicy = DEFAULT_PRESENTATION_POLICY,
) -> RenderedTelegramPost:
    if policy.digest != DEFAULT_PRESENTATION_POLICY.digest:
        raise ValueError("unsupported Telegram presentation policy")

    blocks = [block.strip() for block in post.text.split("\n\n") if block.strip()]
    quote_blocks = blocks[:-2]
    hashtags = blocks[-1]

    builder = _RenderBuilder()
    direct_quote_index = 0
    for index, paragraph in enumerate(quote_blocks):
        direct_quote_index = _render_quote_paragraph(
            builder,
            paragraph,
            direct_quote_index=direct_quote_index,
        )
        if index != len(quote_blocks) - 1:
            builder.append(policy.spacing.quote_paragraph_separator)

    builder.append(policy.spacing.body_to_attribution)
    builder.append_styled(post.source.author, "bold")
    builder.append(", ")
    builder.append_styled(f"«{post.source.work}»", "italic")
    builder.append(policy.spacing.attribution_to_hashtags)
    builder.append(hashtags)

    plain_text = builder.text
    html_text = builder.html_text
    if len(plain_text) > MAX_TELEGRAM_TEXT_LENGTH:
        raise ValueError(
            f"rendered Telegram publication exceeds {MAX_TELEGRAM_TEXT_LENGTH} characters: {post.publication_id}"
        )
    if "© " in plain_text:
        raise ValueError("rendered Telegram publication must not contain the legacy copyright prefix")
    if not plain_text.endswith(hashtags):
        raise ValueError("rendered Telegram publication must preserve the original hashtag block")
    if policy.spacing.attribution_to_hashtags not in plain_text:
        raise ValueError("rendered Telegram publication must preserve the approved hashtag spacing")

    provider_payload = {
        "publication_id": post.publication_id,
        "source_payload_sha256": post.payload_sha256,
        "presentation_policy_sha256": policy.digest,
        "parse_mode": policy.parse_mode,
        "text": plain_text,
        "html_text": html_text,
        "expected_entities": [entity.model_dump(mode="json") for entity in builder.entities],
        "link_preview_disabled": policy.link_preview_disabled,
    }
    provider_payload_sha256 = sha256_text(canonical_json(provider_payload))

    return RenderedTelegramPost(
        schema_name="video-channel-manager.telegram-rendered-post",
        schema_version=1,
        publication_id=post.publication_id,
        source_payload_sha256=post.payload_sha256,
        presentation_policy_id=policy.policy_id,
        presentation_policy_sha256=policy.digest,
        provider_payload_sha256=provider_payload_sha256,
        parse_mode=policy.parse_mode,
        text=plain_text,
        html_text=html_text,
        expected_entities=builder.entities,
        link_preview_disabled=policy.link_preview_disabled,
    )


def verify_rendered_post(
    post: TelegramPost,
    policy: PresentationPolicy,
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
    for entity in actual:
        if not isinstance(entity, dict):
            continue
        entity_type = str(entity.get("type") or "")
        if entity_type not in {"bold", "italic"}:
            continue
        try:
            offset = int(entity["offset"])
            length = int(entity["length"])
        except (KeyError, TypeError, ValueError):
            return False
        actual_formatting.append((entity_type, offset, length))

    expected_formatting = [(entity.type, entity.offset, entity.length) for entity in expected]
    return sorted(actual_formatting) == sorted(expected_formatting)
