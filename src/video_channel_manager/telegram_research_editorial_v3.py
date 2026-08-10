from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from video_channel_manager.telegram_channel_profile import TelegramChannelProfile
from video_channel_manager.telegram_html_entities import GenericMessageEntity, parse_telegram_html
from video_channel_manager.telegram_multichannel_release import GenericReleaseItem, GenericReleaseQueue
from video_channel_manager.telegram_multichannel_transport import render_message_payload
from video_channel_manager.telegram_research import (
    PUB_ID_RE,
    ResearchQueueV2,
    load_research_queue,
    sha256_json,
    sha256_text,
    validate_public_copy,
)
from video_channel_manager.telegram_target_binding import TelegramTargetBinding

SHA_RE = r"^sha256:[0-9a-f]{64}$"
BODY_PATH_RE = r"^content/telegram/lordchrist/research-posts-v3/[a-z0-9-]+\.txt$"
PRESENTATION_PATH_RE = r"^content/telegram/lordchrist/research-posts-v3/[a-z0-9-]+\.html$"
PREDECESSOR_QUEUE_PATH = "content/telegram/lordchrist/research-queues/calvin-spurgeon-macarthur-v2.json"

_FORBIDDEN_EDITORIAL_PHRASES = (
    "на деле всё интереснее",
    "выдавал шедевр",
    "наверное, именно так",
    "и тогда вопрос становится личным",
    "следует отметить",
    "данный показатель",
)


def normalize_presentation_html(value: str) -> str:
    return value.replace("\r\n", "\n").strip()


def _utf16_length(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def _validate_editorial_tone(body: str) -> None:
    lowered = body.casefold()
    found = [phrase for phrase in _FORBIDDEN_EDITORIAL_PHRASES if phrase in lowered]
    if found:
        raise ValueError(f"research v3 copy contains rejected editorial cliché: {found[0]}")
    if "!!" in body or "!!!" in body:
        raise ValueError("research v3 copy must keep restrained punctuation")
    paragraphs = body.split("\n\n")
    if any(len(paragraph) > 700 for paragraph in paragraphs):
        raise ValueError("research v3 Telegram paragraphs must remain compact")
    if not paragraphs[-1].startswith("✦ ") or "бог" not in paragraphs[-1].casefold():
        raise ValueError("research v3 copy must end with a restrained God-centered reflection")


def validate_rich_presentation(body: str, presentation_html: str) -> tuple[GenericMessageEntity, ...]:
    canonical_body = validate_public_copy(body)
    canonical_html = normalize_presentation_html(presentation_html)
    plain_text, entities = parse_telegram_html(canonical_html)
    if plain_text != canonical_body:
        raise ValueError("research v3 rich presentation changes canonical reader text")
    if any(entity.type == "text_link" for entity in entities):
        raise ValueError("research v3 presentation must not introduce source links into reader copy")
    if not any(entity.type == "italic" for entity in entities):
        raise ValueError("research v3 presentation requires at least one intentional italic reflection")
    first_line = canonical_body.splitlines()[0]
    heading_length = _utf16_length(first_line)
    if not any(
        entity.type == "bold" and entity.offset == 0 and entity.length == heading_length for entity in entities
    ):
        raise ValueError("research v3 presentation must bold the exact visible heading")
    if sum(entity.type == "bold" for entity in entities) < 2:
        raise ValueError("research v3 presentation requires meaningful hierarchy beyond the heading")
    _validate_editorial_tone(canonical_body)
    return entities


class EditorialSuccessorPost(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: int = Field(ge=1, le=4)
    predecessor_sequence: int = Field(ge=2, le=5)
    predecessor_publication_id: str = Field(pattern=PUB_ID_RE)
    publication_id: str = Field(pattern=PUB_ID_RE)
    title: str = Field(min_length=5, max_length=120)
    body_path: str = Field(pattern=BODY_PATH_RE)
    body_sha256: str = Field(pattern=SHA_RE)
    presentation_path: str = Field(pattern=PRESENTATION_PATH_RE)
    presentation_sha256: str = Field(pattern=SHA_RE)
    release_offset_days: int = Field(ge=0, le=6)
    source_claim_ids: tuple[str, ...] = Field(min_length=3, max_length=12)

    @model_validator(mode="after")
    def validate_identity(self) -> "EditorialSuccessorPost":
        if self.predecessor_publication_id == self.publication_id:
            raise ValueError("research v3 successor publication_id must not reuse predecessor identity")
        if len(self.source_claim_ids) != len(set(self.source_claim_ids)):
            raise ValueError("research v3 source_claim_ids must be unique")
        return self

    @property
    def digest(self) -> str:
        return sha256_json(self.model_dump(mode="json"))


class ResearchEditorialSuccessor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-research-editorial-successor"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    state: Literal["provider_inert"]
    editorial_policy: Literal["research-v3-restrained-rich-telegram"]
    predecessor_queue_path: Literal[
        "content/telegram/lordchrist/research-queues/calvin-spurgeon-macarthur-v2.json"
    ]
    predecessor_approved_release_digest: str = Field(pattern=SHA_RE)
    posts: tuple[EditorialSuccessorPost, ...] = Field(min_length=4, max_length=4)

    @model_validator(mode="after")
    def validate_shape(self) -> "ResearchEditorialSuccessor":
        if [post.sequence for post in self.posts] != [1, 2, 3, 4]:
            raise ValueError("research v3 successor sequences must be exactly 1..4")
        if [post.predecessor_sequence for post in self.posts] != [2, 3, 4, 5]:
            raise ValueError("research v3 successor must cover exactly predecessor posts 2..5")
        if [post.release_offset_days for post in self.posts] != [0, 2, 4, 6]:
            raise ValueError("research v3 successor cadence must remain T+0/T+2/T+4/T+6")
        if len({post.publication_id for post in self.posts}) != 4:
            raise ValueError("research v3 successor publication ids must be unique")
        return self

    @property
    def digest(self) -> str:
        return sha256_json(self.model_dump(mode="json"))


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid research v3 editorial package {path}: {exc}") from exc


def _validate_against_predecessor(package: ResearchEditorialSuccessor, predecessor: ResearchQueueV2) -> None:
    if package.project_key != predecessor.project_key or package.channel_username != predecessor.channel_username:
        raise ValueError("research v3 successor identity differs from predecessor research queue")
    predecessor_by_id = {post.publication_id: post for post in predecessor.posts}
    for successor in package.posts:
        original = predecessor_by_id.get(successor.predecessor_publication_id)
        if original is None or original.sequence != successor.predecessor_sequence:
            raise ValueError(f"research v3 predecessor mapping mismatch: {successor.predecessor_publication_id}")
        expected_claim_ids = tuple(claim.claim_id for claim in original.claims)
        if successor.source_claim_ids != expected_claim_ids:
            raise ValueError(f"research v3 claim evidence drift: {successor.publication_id}")


def load_editorial_successor(path: Path) -> ResearchEditorialSuccessor:
    try:
        package = ResearchEditorialSuccessor.model_validate(_load_json(path))
    except ValidationError as exc:
        raise ValueError(f"invalid research v3 editorial package {path}: {exc}") from exc

    predecessor = load_research_queue(Path(package.predecessor_queue_path))
    _validate_against_predecessor(package, predecessor)

    for post in package.posts:
        body = validate_public_copy(Path(post.body_path).read_text(encoding="utf-8"))
        if sha256_text(body) != post.body_sha256:
            raise ValueError(f"research v3 body digest mismatch: {post.publication_id}")
        presentation = normalize_presentation_html(Path(post.presentation_path).read_text(encoding="utf-8"))
        if sha256_text(presentation) != post.presentation_sha256:
            raise ValueError(f"research v3 presentation digest mismatch: {post.publication_id}")
        validate_rich_presentation(body, presentation)
    return package


def _target_fields(
    profile: TelegramChannelProfile,
    binding: TelegramTargetBinding | None,
) -> dict[str, object | None]:
    if binding is None:
        return {
            "target_binding_sha256": None,
            "chat_id": None,
            "bot_id": None,
            "bot_username": None,
        }
    if (
        binding.project_key != profile.project_key
        or binding.channel_username.casefold() != profile.channel_username.casefold()
        or binding.profile_sha256 != profile.digest
        or binding.chat_username.casefold() != profile.bare_username.casefold()
    ):
        raise ValueError("research v3 target binding differs from selected Telegram channel profile")
    return {
        "target_binding_sha256": binding.digest,
        "chat_id": binding.chat_id,
        "bot_id": binding.bot_id,
        "bot_username": binding.bot_username,
    }


def build_editorial_successor_candidate(
    profile: TelegramChannelProfile,
    package: ResearchEditorialSuccessor,
    *,
    release_id: str,
    start_at: datetime,
    binding: TelegramTargetBinding | None = None,
) -> GenericReleaseQueue:
    if package.state != "provider_inert":
        raise ValueError("research v3 editorial package must remain provider-inert while building candidate")
    if profile.project_key != package.project_key or profile.channel_username.casefold() != package.channel_username.casefold():
        raise ValueError("research v3 package identity differs from selected Telegram channel profile")
    if start_at.tzinfo is None:
        raise ValueError("research v3 release start_at must be timezone-aware")

    zone = ZoneInfo(profile.timezone)
    local_start = start_at.astimezone(zone)
    items: list[GenericReleaseItem] = []
    for post in package.posts:
        body = validate_public_copy(Path(post.body_path).read_text(encoding="utf-8"))
        presentation = normalize_presentation_html(Path(post.presentation_path).read_text(encoding="utf-8"))
        validate_rich_presentation(body, presentation)
        payload = render_message_payload(
            profile,
            publication_id=post.publication_id,
            html_text=presentation,
        )
        if payload.expected_plain_text != body:
            raise ValueError(f"research v3 provider rendering changed reader text: {post.publication_id}")
        items.append(
            GenericReleaseItem(
                sequence=post.sequence,
                publication_id=post.publication_id,
                scheduled_at=local_start + timedelta(days=post.release_offset_days),
                source_sha256=post.digest,
                payload=payload,
            )
        )

    return GenericReleaseQueue(
        schema_name="video-channel-manager.telegram-release-queue",
        schema_version=1,
        release_id=release_id,
        project_key=profile.project_key,
        channel_username=profile.channel_username,
        profile_sha256=profile.digest,
        timezone=profile.timezone,
        daily_verified_limit=profile.daily_verified_limit,
        **_target_fields(profile, binding),
        release_authorized=False,
        reviewed_candidate_sha256=None,
        reviewed_by=None,
        reviewed_at=None,
        items=tuple(items),
    )


__all__ = [
    "EditorialSuccessorPost",
    "ResearchEditorialSuccessor",
    "build_editorial_successor_candidate",
    "load_editorial_successor",
    "normalize_presentation_html",
    "validate_rich_presentation",
]
