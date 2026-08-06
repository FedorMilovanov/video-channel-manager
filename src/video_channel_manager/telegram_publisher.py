from __future__ import annotations

import hashlib
import json
import os
import secrets
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

PROJECT_KEY = "lord-god-strength"
CHANNEL_USERNAME = "@lordchrist"
PUBLICATION_TIMEZONE = "Europe/Moscow"
DEFAULT_API_BASE = "https://api.telegram.org"
MAX_TELEGRAM_TEXT_LENGTH = 4096
PRIMARY_SOURCE_HOSTS = frozenset(
    {
        "ccel.org",
        "www.ccel.org",
        "spurgeon.org",
        "www.spurgeon.org",
        "ota.bodleian.ox.ac.uk",
    }
)


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class SourceProof(BaseModel):
    """Offline proof for a manually verified, contiguous primary-source passage."""

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
    def anchors_must_be_short_plain_source_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized.split()) > 28:
            raise ValueError("source anchors must be short exact locator phrases")
        return normalized

    @property
    def proof_sha256(self) -> str:
        return _sha256_text(_canonical_json(self.model_dump(mode="json")))


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
        return _sha256_text(_canonical_json(payload))


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
        return _sha256_text(_canonical_json(payload))


StateName = Literal["pending", "dispatching", "published", "unknown", "failed", "skipped"]
ProviderEffect = Literal["impossible", "not_dispatched", "confirmed_absent", "may_exist", "verified"]
DispatchMode = Literal["manual", "scheduled"]


class TargetProof(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-target-proof"]
    schema_version: Literal[1]
    bot_id: int = Field(gt=0)
    bot_username: str = Field(min_length=2, max_length=64)
    chat_id: int = Field(lt=0)
    chat_username: Literal["lordchrist"]
    chat_title: str = Field(min_length=1, max_length=255)
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

    publication_id: str
    payload_sha256: str
    state: StateName = "pending"
    provider_effect: ProviderEffect = "impossible"
    intent_id: str | None = None
    dispatch_mode: DispatchMode | None = None
    workflow_run_id: str | None = None
    attempted_at_utc: datetime | None = None
    published_at_utc: datetime | None = None
    resolved_at_utc: datetime | None = None
    resolved_by: str | None = None
    reconciliation_note: str | None = None
    message_id: int | None = None
    actual_chat_id: int | None = None
    actual_chat_username: str | None = None
    bot_id: int | None = None
    bot_username: str | None = None
    last_error: str | None = None

    @model_validator(mode="after")
    def validate_state_evidence(self) -> "LedgerEntry":
        if self.state == "published":
            if self.provider_effect != "verified":
                raise ValueError("published entries require provider_effect=verified")
            if self.message_id is None or self.message_id <= 0:
                raise ValueError("published entries require a positive message_id")
            if self.actual_chat_id is None or self.actual_chat_id >= 0 or self.bot_id is None or self.bot_id <= 0:
                raise ValueError("published entries require exact channel and bot identities")
        elif self.state in {"dispatching", "unknown"}:
            if self.provider_effect != "may_exist" or not self.intent_id:
                raise ValueError(f"{self.state} entries require may_exist and a durable intent_id")
        elif self.state == "failed":
            if self.provider_effect not in {"not_dispatched", "confirmed_absent"}:
                raise ValueError("failed entries require proof that no provider message was created")
        elif self.state == "skipped":
            if self.provider_effect != "impossible":
                raise ValueError("skipped entries require provider_effect=impossible")
        elif self.state == "pending":
            if self.provider_effect not in {"impossible", "not_dispatched", "confirmed_absent"}:
                raise ValueError("pending entries cannot retain a possible or verified provider effect")
            if self.message_id is not None:
                raise ValueError("pending entries cannot retain a message_id")
        return self


class TelegramLedger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_name: Literal["video-channel-manager.telegram-publication-ledger"]
    schema_version: Literal[3]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    queue_digest: str
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
    schema_version: Literal[3]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    queue_digest: str
    publication_id: str
    sequence: int
    intent_id: str
    workflow_run_id: str
    payload_sha256: str
    text: str
    dispatch_mode: DispatchMode
    target: TargetProof
    prepared_at_utc: datetime


@dataclass(frozen=True)
class PreparedDispatch:
    envelope: DispatchEnvelope | None
    reason: str


class TelegramApiError(RuntimeError):
    def __init__(self, message: str, *, provider_effect: ProviderEffect) -> None:
        super().__init__(message)
        self.provider_effect = provider_effect


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def publication_local_date(value: datetime, timezone_name: str = PUBLICATION_TIMEZONE) -> date:
    if value.tzinfo is None:
        raise ValueError("publication timestamps must be timezone-aware")
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown publication timezone: {timezone_name}") from exc
    return value.astimezone(zone).date()


def load_queue(path: Path) -> TelegramQueue:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return TelegramQueue.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"invalid Telegram queue {path}: {exc}") from exc


def load_or_initialize_ledger(path: Path, queue: TelegramQueue) -> TelegramLedger:
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            ledger = TelegramLedger.model_validate(payload)
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            raise ValueError(f"invalid Telegram ledger {path}: {exc}") from exc
        if ledger.queue_digest != queue.digest:
            raise ValueError("queue digest differs from the immutable digest recorded in the ledger")
    else:
        ledger = TelegramLedger(
            schema_name="video-channel-manager.telegram-publication-ledger",
            schema_version=3,
            project_key=PROJECT_KEY,
            channel_username=CHANNEL_USERNAME,
            queue_digest=queue.digest,
            entries={},
        )

    queue_by_id = {post.publication_id: post for post in queue.posts}
    extra_ids = set(ledger.entries) - set(queue_by_id)
    if extra_ids:
        raise ValueError(f"ledger contains publications absent from immutable queue: {sorted(extra_ids)}")

    for post in queue.posts:
        entry = ledger.entries.setdefault(
            post.publication_id,
            LedgerEntry(publication_id=post.publication_id, payload_sha256=post.payload_sha256),
        )
        if entry.payload_sha256 != post.payload_sha256:
            raise ValueError(f"payload changed after ledger initialization: {post.publication_id}")
    return ledger


def save_ledger(path: Path, ledger: TelegramLedger) -> None:
    # Revalidate the complete state graph after in-memory transitions. Pydantic
    # assignment validation is intentionally not used because one transition
    # updates several mutually dependent fields.
    validated = TelegramLedger.model_validate(ledger.model_dump(mode="json"))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(validated.model_dump_json(indent=2))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def save_model(path: Path, model: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(model.model_dump_json(indent=2), encoding="utf-8")


def load_dispatch(path: Path) -> DispatchEnvelope:
    try:
        return DispatchEnvelope.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid dispatch envelope {path}: {exc}") from exc


def load_target_proof(path: Path) -> TargetProof:
    try:
        return TargetProof.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid target proof {path}: {exc}") from exc


def verify_dispatch_against_queue(queue: TelegramQueue, envelope: DispatchEnvelope) -> TelegramPost:
    if envelope.queue_digest != queue.digest:
        raise ValueError("dispatch queue digest differs from the immutable queue")
    post = next((item for item in queue.posts if item.publication_id == envelope.publication_id), None)
    if post is None:
        raise ValueError("dispatch publication is absent from the immutable queue")
    if envelope.sequence != post.sequence:
        raise ValueError("dispatch sequence differs from the immutable queue")
    if envelope.payload_sha256 != post.payload_sha256:
        raise ValueError("dispatch payload fingerprint differs from the immutable queue")
    if envelope.text != post.text:
        raise ValueError("dispatch text differs from the immutable queue")
    return post


def verify_persisted_intent(queue: TelegramQueue, ledger: TelegramLedger, envelope: DispatchEnvelope) -> LedgerEntry:
    verify_dispatch_against_queue(queue, envelope)
    if ledger.queue_digest != envelope.queue_digest:
        raise ValueError("persisted ledger queue digest differs from prepared dispatch")
    entry = ledger.entries.get(envelope.publication_id)
    if entry is None:
        raise ValueError("persisted ledger does not contain the prepared publication")
    if entry.state != "dispatching" or entry.provider_effect != "may_exist":
        raise ValueError("persisted ledger is not in the conservative dispatching state")
    if entry.intent_id != envelope.intent_id:
        raise ValueError("persisted ledger intent_id differs from prepared dispatch")
    if entry.workflow_run_id != envelope.workflow_run_id:
        raise ValueError("persisted ledger workflow_run_id differs from prepared dispatch")
    if entry.payload_sha256 != envelope.payload_sha256:
        raise ValueError("persisted ledger payload fingerprint differs from prepared dispatch")
    if entry.dispatch_mode != envelope.dispatch_mode:
        raise ValueError("persisted ledger dispatch mode differs from prepared dispatch")
    if entry.bot_username is None:
        raise ValueError("persisted ledger has no bot username")
    if (
        entry.actual_chat_id != envelope.target.chat_id
        or entry.actual_chat_username != envelope.target.chat_username
        or entry.bot_id != envelope.target.bot_id
        or entry.bot_username.casefold() != envelope.target.bot_username.casefold()
    ):
        raise ValueError("persisted ledger target identity differs from prepared dispatch")
    return entry


def _safe_transport_error(prefix: str, exc: Exception) -> str:
    # Never serialize httpx exception strings or request URLs. Telegram embeds
    # the bot token in the request path, and the state branch is public.
    return f"{prefix}: {type(exc).__name__}"


def _api_call(
    client: httpx.Client,
    *,
    api_base: str,
    token: str,
    method: str,
    payload: dict[str, Any],
    mutation: bool,
) -> dict[str, Any]:
    url = f"{api_base.rstrip('/')}/bot{token}/{method}"
    effect: ProviderEffect
    try:
        response = client.post(url, json=payload)
    except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
        raise TelegramApiError(
            _safe_transport_error("Telegram connection failure", exc), provider_effect="not_dispatched"
        ) from exc
    except (httpx.ReadTimeout, httpx.WriteError, httpx.WriteTimeout, httpx.RemoteProtocolError) as exc:
        effect = "may_exist" if mutation else "not_dispatched"
        raise TelegramApiError(
            _safe_transport_error("Telegram transport outcome unavailable", exc), provider_effect=effect
        ) from exc
    except httpx.HTTPError as exc:
        effect = "may_exist" if mutation else "not_dispatched"
        raise TelegramApiError(
            _safe_transport_error("Telegram HTTP transport failure", exc), provider_effect=effect
        ) from exc

    try:
        body = response.json()
    except ValueError as exc:
        effect = "may_exist" if mutation else "not_dispatched"
        raise TelegramApiError(
            f"Telegram returned non-JSON HTTP {response.status_code}", provider_effect=effect
        ) from exc

    if not response.is_success or body.get("ok") is not True:
        description = str(body.get("description") or f"HTTP {response.status_code}")[:500]
        if mutation:
            effect = "may_exist" if response.status_code >= 500 else "confirmed_absent"
        else:
            effect = "not_dispatched"
        raise TelegramApiError(f"Telegram rejected request: {description}", provider_effect=effect)
    result = body.get("result")
    if not isinstance(result, dict):
        effect = "may_exist" if mutation else "not_dispatched"
        raise TelegramApiError("Telegram response has no result object", provider_effect=effect)
    return result


def preflight_target(
    *,
    token: str,
    expected_chat_id: int,
    expected_bot_username: str,
    api_base: str = DEFAULT_API_BASE,
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> TargetProof:
    own_client = client is None
    http_client = client or httpx.Client(timeout=httpx.Timeout(connect=15, read=30, write=30, pool=15))
    try:
        me = _api_call(http_client, api_base=api_base, token=token, method="getMe", payload={}, mutation=False)
        bot_id = int(me["id"])
        bot_username = str(me.get("username") or "")
        if bot_username.casefold() != expected_bot_username.removeprefix("@").casefold():
            raise TelegramApiError(
                "resolved bot username does not match configured bot", provider_effect="not_dispatched"
            )

        chat = _api_call(
            http_client,
            api_base=api_base,
            token=token,
            method="getChat",
            payload={"chat_id": CHANNEL_USERNAME},
            mutation=False,
        )
        actual_chat_id = int(chat["id"])
        actual_username = str(chat.get("username") or "")
        if (
            actual_chat_id != expected_chat_id
            or actual_username.casefold() != CHANNEL_USERNAME.removeprefix("@").casefold()
        ):
            raise TelegramApiError(
                "resolved Telegram channel identity does not match configured target", provider_effect="not_dispatched"
            )

        member = _api_call(
            http_client,
            api_base=api_base,
            token=token,
            method="getChatMember",
            payload={"chat_id": actual_chat_id, "user_id": bot_id},
            mutation=False,
        )
        status = str(member.get("status") or "")
        if status not in {"administrator", "creator"}:
            raise TelegramApiError("posting bot is not a channel administrator", provider_effect="not_dispatched")
        can_post = status == "creator" or member.get("can_post_messages") is True
        if not can_post:
            raise TelegramApiError("posting bot lacks can_post_messages", provider_effect="not_dispatched")

        return TargetProof(
            schema_name="video-channel-manager.telegram-target-proof",
            schema_version=1,
            bot_id=bot_id,
            bot_username=bot_username,
            chat_id=actual_chat_id,
            chat_username="lordchrist",
            chat_title=str(chat.get("title") or CHANNEL_USERNAME),
            member_status=status,
            can_post_messages=True,
            checked_at_utc=now or utc_now(),
        )
    finally:
        if own_client:
            http_client.close()


def prepare_next(
    queue: TelegramQueue,
    ledger: TelegramLedger,
    *,
    run_id: str,
    mode: DispatchMode,
    target: TargetProof,
    publication_timezone: str = PUBLICATION_TIMEZONE,
    now: datetime | None = None,
) -> PreparedDispatch:
    now = now or utc_now()
    if now.tzinfo is None:
        raise ValueError("prepare timestamp must be timezone-aware")
    proof_age = now - target.checked_at_utc.astimezone(UTC)
    if proof_age < -timedelta(minutes=1) or proof_age > timedelta(minutes=15):
        raise ValueError("target proof is stale or has an invalid future timestamp")
    if target.chat_id >= 0 or target.chat_username != CHANNEL_USERNAME.removeprefix("@"):
        raise ValueError("target proof is not for @lordchrist")

    if mode == "scheduled":
        manual_canary = any(
            entry.state == "published"
            and entry.provider_effect == "verified"
            and entry.dispatch_mode == "manual"
            and entry.message_id is not None
            and entry.message_id > 0
            and entry.actual_chat_id == target.chat_id
            and entry.bot_id == target.bot_id
            for entry in ledger.entries.values()
        )
        if not manual_canary:
            return PreparedDispatch(None, "scheduled execution requires one exact verified manual canary")

        today = publication_local_date(now, publication_timezone)
        already_published_today = any(
            entry.state == "published"
            and entry.provider_effect == "verified"
            and entry.published_at_utc is not None
            and publication_local_date(entry.published_at_utc, publication_timezone) == today
            for entry in ledger.entries.values()
        )
        if already_published_today:
            return PreparedDispatch(None, f"one publication is already verified for {today.isoformat()}")

    for post in queue.posts:
        entry = ledger.entries[post.publication_id]
        if entry.state in {"published", "skipped"}:
            continue
        if entry.state != "pending":
            return PreparedDispatch(None, f"strict queue blocked by {post.publication_id} in state {entry.state}")

        intent_id = secrets.token_hex(16)
        entry.state = "dispatching"
        # Conservative by design: after the intent is durably pushed, a runner
        # crash cannot prove whether sendMessage was reached. No blind replay.
        entry.provider_effect = "may_exist"
        entry.intent_id = intent_id
        entry.dispatch_mode = mode
        entry.workflow_run_id = run_id
        entry.attempted_at_utc = now
        entry.bot_id = target.bot_id
        entry.bot_username = target.bot_username
        entry.actual_chat_id = target.chat_id
        entry.actual_chat_username = target.chat_username
        entry.last_error = None
        envelope = DispatchEnvelope(
            schema_name="video-channel-manager.telegram-dispatch",
            schema_version=3,
            project_key=PROJECT_KEY,
            channel_username=CHANNEL_USERNAME,
            queue_digest=queue.digest,
            publication_id=post.publication_id,
            sequence=post.sequence,
            intent_id=intent_id,
            workflow_run_id=run_id,
            payload_sha256=post.payload_sha256,
            text=post.text,
            dispatch_mode=mode,
            target=target,
            prepared_at_utc=now,
        )
        return PreparedDispatch(envelope, "prepared")
    return PreparedDispatch(None, "queue complete")


def dispatch_prepared(
    queue: TelegramQueue,
    envelope: DispatchEnvelope,
    ledger: TelegramLedger,
    *,
    token: str,
    api_base: str = DEFAULT_API_BASE,
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> LedgerEntry:
    effective_now = now or utc_now()
    if effective_now.tzinfo is None:
        raise ValueError("dispatch timestamp must be timezone-aware")
    if effective_now - envelope.prepared_at_utc.astimezone(UTC) > timedelta(minutes=15):
        raise ValueError("prepared dispatch expired before provider submission")
    entry = verify_persisted_intent(queue, ledger, envelope)

    own_client = client is None
    http_client = client or httpx.Client(timeout=httpx.Timeout(connect=15, read=45, write=30, pool=15))
    try:
        message = _api_call(
            http_client,
            api_base=api_base,
            token=token,
            method="sendMessage",
            mutation=True,
            payload={
                "chat_id": envelope.target.chat_id,
                "text": envelope.text,
                "link_preview_options": {"is_disabled": True},
            },
        )
        returned_chat = message.get("chat")
        if not isinstance(returned_chat, dict) or int(returned_chat.get("id", 0)) != envelope.target.chat_id:
            raise TelegramApiError("Telegram returned a message for an unexpected chat", provider_effect="may_exist")
        if str(message.get("text") or "") != envelope.text:
            raise TelegramApiError(
                "Telegram returned text that differs from the immutable payload", provider_effect="may_exist"
            )
        message_id = int(message["message_id"])
        if message_id <= 0:
            raise TelegramApiError("Telegram returned an invalid message_id", provider_effect="may_exist")

        entry.state = "published"
        entry.provider_effect = "verified"
        entry.message_id = message_id
        entry.published_at_utc = effective_now
        entry.last_error = None
        return entry
    except TelegramApiError as exc:
        entry.provider_effect = exc.provider_effect
        entry.last_error = str(exc)[:1000]
        if exc.provider_effect == "may_exist":
            entry.state = "unknown"
        else:
            entry.state = "failed"
            entry.intent_id = None
        return entry
    finally:
        if own_client:
            http_client.close()


def resolve_entry(
    ledger: TelegramLedger,
    publication_id: str,
    *,
    resolution: Literal["confirmed_published", "confirmed_absent", "skip"],
    evidence_note: str,
    resolved_by: str,
    message_id: int | None = None,
    expected_chat_id: int | None = None,
    now: datetime | None = None,
) -> LedgerEntry:
    note = " ".join(evidence_note.split())
    if len(note) < 20:
        raise ValueError("reconciliation requires a concrete evidence note of at least 20 characters")
    entry = ledger.entries.get(publication_id)
    if entry is None:
        raise ValueError(f"unknown publication_id: {publication_id}")
    if entry.state not in {"dispatching", "unknown", "failed", "pending"}:
        raise ValueError("only pending, unresolved, or failed entries can be reconciled")
    resolved_at = now or utc_now()
    if resolution == "confirmed_published":
        if message_id is None or message_id <= 0 or expected_chat_id is None:
            raise ValueError("confirmed_published requires message_id and expected_chat_id")
        entry.state = "published"
        entry.provider_effect = "verified"
        entry.message_id = message_id
        entry.actual_chat_id = expected_chat_id
        entry.actual_chat_username = CHANNEL_USERNAME.removeprefix("@")
        entry.published_at_utc = resolved_at
        entry.last_error = "manually reconciled as published"
    elif resolution == "confirmed_absent":
        entry.state = "pending"
        entry.provider_effect = "confirmed_absent"
        entry.intent_id = None
        entry.message_id = None
        entry.published_at_utc = None
        entry.last_error = "manually reconciled as confirmed absent"
    else:
        entry.state = "skipped"
        entry.provider_effect = "impossible"
        entry.intent_id = None
        entry.message_id = None
        entry.published_at_utc = None
        entry.last_error = "manually skipped"
    entry.resolved_at_utc = resolved_at
    entry.resolved_by = resolved_by
    entry.reconciliation_note = note
    return entry


def require_execution_enabled(*, queue_digest: str, mode: DispatchMode) -> None:
    if os.environ.get("LORDCHRIST_POSTING_ENABLED", "").strip().casefold() != "true":
        raise RuntimeError("provider execution is disabled; set LORDCHRIST_POSTING_ENABLED=true")
    approved = os.environ.get("LORDCHRIST_APPROVED_QUEUE_DIGEST", "").strip()
    if approved != queue_digest:
        raise RuntimeError("immutable queue digest is not explicitly approved in repository variables")
    if mode == "scheduled" and os.environ.get("LORDCHRIST_SCHEDULE_ENABLED", "").strip().casefold() != "true":
        raise RuntimeError("scheduled execution is disabled; set LORDCHRIST_SCHEDULE_ENABLED=true after canary")
