from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PROJECT_KEY = "lord-god-strength"
CHANNEL_USERNAME = "@lordchrist"
PUBLICATION_TIMEZONE = "Europe/Moscow"
DEFAULT_API_BASE = "https://api.telegram.org"
MAX_TELEGRAM_TEXT_LENGTH = 4096
SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
GITHUB_SHA_PATTERN = r"^[0-9a-f]{40}$"
TELEGRAM_USERNAME_PATTERN = r"^[A-Za-z0-9_]+$"
PRIMARY_SOURCE_HOSTS = frozenset(
    {
        "ccel.org",
        "www.ccel.org",
        "spurgeon.org",
        "www.spurgeon.org",
        "ota.bodleian.ox.ac.uk",
    }
)


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _timezone_aware(value: datetime | None) -> bool:
    return value is not None and value.tzinfo is not None


def _valid_run_attempt(value: str | None) -> bool:
    return bool(value and re.fullmatch(r"[1-9][0-9]*", value))


def _valid_github_sha(value: str | None) -> bool:
    return bool(value and re.fullmatch(r"[0-9a-f]{40}", value))


class SourceProof(BaseModel):
    """Offline proof for one manually verified contiguous primary-source passage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    author: str = Field(min_length=2, max_length=120)
    work: str = Field(min_length=2, max_length=240)
    location: str = Field(min_length=2, max_length=300)
    url: str = Field(pattern=r"^https://")
    anchor_start: str = Field(min_length=8, max_length=300)
    anchor_end: str = Field(min_length=8, max_length=300)
    source_type: Literal["primary"] = "primary"
    copyright_status: Literal["public_domain"] = "public_domain"
    original_language: Literal["en"] = "en"
    translation_language: Literal["ru"] = "ru"
    selection_policy: Literal["contiguous_complete_no_omissions"] = "contiguous_complete_no_omissions"
    verification_status: Literal["accepted"] = "accepted"
    verified_on: date

    @field_validator("url")
    @classmethod
    def primary_host_only(cls, value: str) -> str:
        host = (urlparse(value).hostname or "").casefold()
        if host not in PRIMARY_SOURCE_HOSTS:
            raise ValueError(f"source host is not on the primary-source allowlist: {host}")
        return value

    @field_validator("anchor_start", "anchor_end")
    @classmethod
    def short_plain_anchors(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized.split()) > 28:
            raise ValueError("source anchors must be short exact locator phrases")
        return normalized

    @property
    def proof_sha256(self) -> str:
        return sha256_text(canonical_json(self.model_dump(mode="json")))


class TelegramPost(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: int = Field(ge=1)
    publication_id: str = Field(pattern=r"^lordchrist-[a-z0-9][a-z0-9-]{4,80}$")
    title: str = Field(min_length=2, max_length=160)
    text: str = Field(min_length=100, max_length=MAX_TELEGRAM_TEXT_LENGTH)
    source: SourceProof

    @field_validator("text")
    @classmethod
    def validate_text_structure(cls, value: str) -> str:
        normalized = value.replace("\r\n", "\n").strip()
        forbidden = (
            "контекст редактора",
            "не цитата",
            "резерв",
            "gracegems",
            "пересказ",
            "синтез",
            "адаптация",
            "вольный перевод",
        )
        folded = normalized.casefold()
        if any(marker in folded for marker in forbidden):
            raise ValueError("publication contains editorial, reserve, or composite material")

        blocks = [block.strip() for block in normalized.split("\n\n") if block.strip()]
        if len(blocks) < 4:
            raise ValueError("publication must contain quote paragraphs, attribution, and hashtags")
        quote_blocks = blocks[:-2]
        if not 2 <= len(quote_blocks) <= 3:
            raise ValueError("publication quotation must contain exactly 2 or 3 dense paragraphs")
        if any(len(block) < 80 for block in quote_blocks):
            raise ValueError("each quotation paragraph must be substantial, not a slogan")
        if not blocks[-2].startswith("© "):
            raise ValueError("penultimate block must be the attribution")
        if not blocks[-1].startswith("#"):
            raise ValueError("last block must contain hashtags")
        return normalized

    @model_validator(mode="after")
    def attribution_matches_source(self) -> "TelegramPost":
        expected = f"© {self.source.author}, «{self.source.work}»"
        blocks = [block.strip() for block in self.text.split("\n\n") if block.strip()]
        if blocks[-2] != expected:
            raise ValueError(f"attribution must exactly equal: {expected}")
        return self

    @property
    def payload_sha256(self) -> str:
        payload = {
            "publication_id": self.publication_id,
            "sequence": self.sequence,
            "title": self.title,
            "text": self.text,
            "source_proof_sha256": self.source.proof_sha256,
        }
        return sha256_text(canonical_json(payload))


class TelegramQueue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-quote-queue"]
    schema_version: Literal[3]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    content_scope: Literal["public_domain_primary_sources_only"]
    verification_policy: Literal["primary_source_contiguous_complete_no_composites"]
    posts: tuple[TelegramPost, ...]

    @model_validator(mode="after")
    def validate_queue(self) -> "TelegramQueue":
        if len(self.posts) != 30:
            raise ValueError("the verified monthly queue must contain exactly 30 posts")
        sequences = [post.sequence for post in self.posts]
        if sequences != list(range(1, 31)):
            raise ValueError("post sequences must be exactly 1..30")
        ids = [post.publication_id for post in self.posts]
        if len(ids) != len(set(ids)):
            raise ValueError("publication_id values must be unique")
        return self

    @property
    def digest(self) -> str:
        payload = {
            "schema_version": self.schema_version,
            "project_key": self.project_key,
            "channel_username": self.channel_username,
            "content_scope": self.content_scope,
            "verification_policy": self.verification_policy,
            "posts": [
                {
                    "sequence": post.sequence,
                    "publication_id": post.publication_id,
                    "payload_sha256": post.payload_sha256,
                }
                for post in self.posts
            ],
        }
        return sha256_text(canonical_json(payload))


StateName = Literal["pending", "dispatching", "published", "unknown", "failed", "skipped"]
ProviderEffect = Literal["impossible", "not_dispatched", "confirmed_absent", "may_exist", "verified"]
DispatchMode = Literal["manual", "scheduled"]


class TargetProof(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-target-proof"]
    schema_version: Literal[2]
    bot_id: int = Field(gt=0)
    bot_username: str = Field(min_length=2, max_length=64, pattern=TELEGRAM_USERNAME_PATTERN)
    chat_id: int = Field(lt=0)
    chat_username: Literal["lordchrist"]
    chat_title: str = Field(min_length=1, max_length=255)
    chat_type: Literal["channel"]
    member_status: Literal["administrator", "creator"]
    can_post_messages: bool
    checked_at_utc: datetime

    @model_validator(mode="after")
    def validate_target_proof(self) -> "TargetProof":
        if self.checked_at_utc.tzinfo is None:
            raise ValueError("target proof timestamp must be timezone-aware")
        if self.chat_username != CHANNEL_USERNAME.removeprefix("@"):
            raise ValueError("target proof must resolve @lordchrist")
        if not self.can_post_messages:
            raise ValueError("target proof must include posting permission")
        return self


class LedgerEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    publication_id: str = Field(pattern=r"^lordchrist-[a-z0-9][a-z0-9-]{4,80}$")
    payload_sha256: str = Field(pattern=SHA256_PATTERN)
    state: StateName = "pending"
    provider_effect: ProviderEffect = "impossible"
    intent_id: str | None = None
    dispatch_mode: DispatchMode | None = None
    workflow_run_id: str | None = None
    workflow_run_attempt: str | None = None
    github_sha: str | None = None
    github_workflow_sha: str | None = None
    attempted_at_utc: datetime | None = None
    published_at_utc: datetime | None = None
    resolved_at_utc: datetime | None = None
    resolved_by: str | None = None
    reconciliation_note: str | None = None
    message_id: int | None = None
    message_url: str | None = None
    actual_chat_id: int | None = None
    actual_chat_username: str | None = None
    bot_id: int | None = None
    bot_username: str | None = None
    last_error: str | None = None

    def _require_dispatch_provenance(self) -> None:
        if not self.intent_id:
            raise ValueError(f"{self.state} entries require a durable intent_id")
        if not self.workflow_run_id or not _valid_run_attempt(self.workflow_run_attempt):
            raise ValueError(f"{self.state} entries require exact workflow run provenance")
        if not _valid_github_sha(self.github_sha) or not _valid_github_sha(self.github_workflow_sha):
            raise ValueError(f"{self.state} entries require exact GitHub SHA provenance")
        if self.dispatch_mode is None or not _timezone_aware(self.attempted_at_utc):
            raise ValueError(f"{self.state} entries require dispatch mode and attempted timestamp")
        if self.actual_chat_id is None or self.actual_chat_id >= 0:
            raise ValueError(f"{self.state} entries require the exact negative channel id")
        if self.actual_chat_username != CHANNEL_USERNAME.removeprefix("@"):
            raise ValueError(f"{self.state} entries require the canonical channel username")
        if self.bot_id is None or self.bot_id <= 0 or not self.bot_username:
            raise ValueError(f"{self.state} entries require exact bot identity")

    @model_validator(mode="after")
    def validate_state_evidence(self) -> "LedgerEntry":
        if self.state == "published":
            if self.provider_effect != "verified":
                raise ValueError("published entries require provider_effect=verified")
            self._require_dispatch_provenance()
            if self.message_id is None or self.message_id <= 0:
                raise ValueError("published entries require a positive message_id")
            expected_url = f"https://t.me/{CHANNEL_USERNAME.removeprefix('@')}/{self.message_id}"
            if self.message_url != expected_url:
                raise ValueError("published entries require the canonical public message URL")
            if not _timezone_aware(self.published_at_utc):
                raise ValueError("published entries require a timezone-aware publication timestamp")
            if self.published_at_utc < self.attempted_at_utc:  # type: ignore[operator]
                raise ValueError("published timestamp cannot precede the dispatch attempt")
        elif self.state in {"dispatching", "unknown"}:
            if self.provider_effect != "may_exist":
                raise ValueError(f"{self.state} entries require provider_effect=may_exist")
            self._require_dispatch_provenance()
            if self.message_id is not None or self.message_url is not None or self.published_at_utc is not None:
                raise ValueError(f"{self.state} entries cannot claim a verified message identity")
        elif self.state == "failed":
            if self.provider_effect not in {"not_dispatched", "confirmed_absent"}:
                raise ValueError("failed entries require proof that no provider message was created")
            if self.intent_id is not None:
                raise ValueError("failed entries cannot retain a live dispatch intent")
            if self.message_id is not None or self.message_url is not None or self.published_at_utc is not None:
                raise ValueError("failed entries cannot retain a published message identity")
        elif self.state == "skipped":
            if self.provider_effect != "impossible":
                raise ValueError("skipped entries require provider_effect=impossible")
            if self.intent_id is not None:
                raise ValueError("skipped entries cannot retain a dispatch intent")
            if self.message_id is not None or self.message_url is not None or self.published_at_utc is not None:
                raise ValueError("skipped entries cannot retain a published message identity")
        elif self.state == "pending":
            if self.provider_effect not in {"impossible", "not_dispatched", "confirmed_absent"}:
                raise ValueError("pending entries cannot retain a possible or verified provider effect")
            if self.intent_id is not None:
                raise ValueError("pending entries cannot retain a dispatch intent")
            if self.message_id is not None or self.message_url is not None or self.published_at_utc is not None:
                raise ValueError("pending entries cannot retain a published message identity")
        return self


class TelegramLedger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_name: Literal["video-channel-manager.telegram-publication-ledger"]
    schema_version: Literal[3]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    queue_digest: str = Field(pattern=SHA256_PATTERN)
    entries: dict[str, LedgerEntry]

    @model_validator(mode="after")
    def validate_entry_identity(self) -> "TelegramLedger":
        intent_ids: list[str] = []
        for key, entry in self.entries.items():
            if key != entry.publication_id:
                raise ValueError(f"ledger key does not match publication_id: {key}")
            if entry.intent_id is not None:
                intent_ids.append(entry.intent_id)
        if len(intent_ids) != len(set(intent_ids)):
            raise ValueError("ledger intent_id values must be unique")
        return self


class DispatchEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-dispatch"]
    schema_version: Literal[4]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    queue_digest: str = Field(pattern=SHA256_PATTERN)
    publication_id: str = Field(pattern=r"^lordchrist-[a-z0-9][a-z0-9-]{4,80}$")
    sequence: int = Field(ge=1, le=30)
    intent_id: str = Field(min_length=16, max_length=128)
    workflow_run_id: str = Field(min_length=1, max_length=128)
    workflow_run_attempt: str = Field(pattern=r"^[1-9][0-9]*$")
    github_sha: str = Field(pattern=GITHUB_SHA_PATTERN)
    github_workflow_sha: str = Field(pattern=GITHUB_SHA_PATTERN)
    payload_sha256: str = Field(pattern=SHA256_PATTERN)
    text: str = Field(min_length=100, max_length=MAX_TELEGRAM_TEXT_LENGTH)
    dispatch_mode: DispatchMode
    target: TargetProof
    prepared_at_utc: datetime

    @model_validator(mode="after")
    def validate_dispatch_timestamp(self) -> "DispatchEnvelope":
        if self.prepared_at_utc.tzinfo is None:
            raise ValueError("dispatch prepared timestamp must be timezone-aware")
        return self


@dataclass(frozen=True)
class PreparedDispatch:
    envelope: DispatchEnvelope | None
    reason: str
    post: TelegramPost | None = None
