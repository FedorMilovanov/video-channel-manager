from __future__ import annotations

import json
import os
import re
import secrets
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from video_channel_manager.telegram_channel_profile import TelegramChannelProfile
from video_channel_manager.telegram_multichannel_release import GenericReleaseItem, GenericReleaseQueue
from video_channel_manager.telegram_multichannel_transport import GenericSendReceipt, GenericTargetProof

GenericStateName = Literal["pending", "dispatching", "published", "unknown", "failed", "skipped"]
GenericProviderEffect = Literal["impossible", "not_dispatched", "confirmed_absent", "may_exist", "verified"]
GenericDispatchMode = Literal["manual", "scheduled"]


class GenericLedgerEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    publication_id: str = Field(min_length=5, max_length=96)
    provider_payload_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    state: GenericStateName = "pending"
    provider_effect: GenericProviderEffect = "impossible"
    intent_id: str | None = None
    dispatch_mode: GenericDispatchMode | None = None
    workflow_run_id: str | None = None
    workflow_run_attempt: str | None = None
    github_sha: str | None = None
    github_workflow_sha: str | None = None
    attempted_at_utc: datetime | None = None
    published_at_utc: datetime | None = None
    message_id: int | None = None
    message_url: str | None = None
    actual_chat_id: int | None = None
    actual_chat_username: str | None = None
    bot_id: int | None = None
    bot_username: str | None = None
    last_error: str | None = None

    def _require_dispatch_provenance(self) -> None:
        if not self.intent_id or len(self.intent_id) < 16:
            raise ValueError(f"{self.state} entries require a durable intent_id")
        if not self.workflow_run_id or not self.workflow_run_attempt:
            raise ValueError(f"{self.state} entries require exact workflow run provenance")
        if re.fullmatch(r"[1-9][0-9]*", self.workflow_run_attempt) is None:
            raise ValueError(f"{self.state} entries require a valid workflow run attempt")
        if self.github_sha is None or re.fullmatch(r"[0-9a-f]{40}", self.github_sha) is None:
            raise ValueError(f"{self.state} entries require an exact GitHub SHA")
        if self.github_workflow_sha is None or re.fullmatch(r"[0-9a-f]{40}", self.github_workflow_sha) is None:
            raise ValueError(f"{self.state} entries require an exact workflow SHA")
        if self.dispatch_mode is None or self.attempted_at_utc is None or self.attempted_at_utc.tzinfo is None:
            raise ValueError(f"{self.state} entries require dispatch mode and attempted timestamp")
        if self.actual_chat_id is None or self.actual_chat_id >= 0 or not self.actual_chat_username:
            raise ValueError(f"{self.state} entries require exact channel identity")
        if self.bot_id is None or self.bot_id <= 0 or not self.bot_username:
            raise ValueError(f"{self.state} entries require exact bot identity")

    @model_validator(mode="after")
    def validate_state_evidence(self) -> "GenericLedgerEntry":
        if self.state == "published":
            if self.provider_effect != "verified":
                raise ValueError("published entries require provider_effect=verified")
            self._require_dispatch_provenance()
            if self.message_id is None or self.message_id <= 0 or not self.message_url:
                raise ValueError("published entries require a verified message identity")
            if self.published_at_utc is None or self.published_at_utc.tzinfo is None:
                raise ValueError("published entries require a timezone-aware published timestamp")
            if self.published_at_utc < self.attempted_at_utc:  # type: ignore[operator]
                raise ValueError("published timestamp cannot precede dispatch attempt")
        elif self.state in {"dispatching", "unknown"}:
            if self.provider_effect != "may_exist":
                raise ValueError(f"{self.state} entries require provider_effect=may_exist")
            self._require_dispatch_provenance()
            if self.message_id is not None or self.message_url is not None or self.published_at_utc is not None:
                raise ValueError(f"{self.state} entries cannot claim a verified message identity")
        elif self.state == "failed":
            if self.provider_effect not in {"not_dispatched", "confirmed_absent"}:
                raise ValueError("failed entries require proof that no provider message was created")
            if self.intent_id is not None or self.message_id is not None or self.message_url is not None:
                raise ValueError("failed entries cannot retain live dispatch or message identity")
        elif self.state == "skipped":
            if self.provider_effect != "impossible":
                raise ValueError("skipped entries require provider_effect=impossible")
            if self.intent_id is not None or self.message_id is not None or self.message_url is not None:
                raise ValueError("skipped entries cannot retain dispatch or message identity")
        elif self.state == "pending":
            if self.provider_effect not in {"impossible", "not_dispatched", "confirmed_absent"}:
                raise ValueError("pending entries cannot retain a possible or verified provider effect")
            if self.intent_id is not None or self.message_id is not None or self.message_url is not None:
                raise ValueError("pending entries cannot retain dispatch or message identity")
        return self


class GenericPublicationLedger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_name: Literal["video-channel-manager.telegram-generic-publication-ledger"]
    schema_version: Literal[1]
    release_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    release_id: str
    project_key: str
    channel_username: str
    profile_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    entries: dict[str, GenericLedgerEntry]

    @model_validator(mode="after")
    def validate_entry_identity(self) -> "GenericPublicationLedger":
        intents: list[str] = []
        for key, entry in self.entries.items():
            if key != entry.publication_id:
                raise ValueError(f"ledger key does not match publication_id: {key}")
            if entry.intent_id is not None:
                intents.append(entry.intent_id)
        if len(intents) != len(set(intents)):
            raise ValueError("ledger intent_id values must be unique")
        return self


class GenericDispatchEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-generic-dispatch"]
    schema_version: Literal[1]
    release_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    release_id: str
    project_key: str
    channel_username: str
    profile_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    publication_id: str
    sequence: int = Field(ge=1)
    provider_payload_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    intent_id: str = Field(min_length=16, max_length=128)
    dispatch_mode: GenericDispatchMode
    workflow_run_id: str = Field(min_length=1, max_length=128)
    workflow_run_attempt: str = Field(pattern=r"^[1-9][0-9]*$")
    github_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    github_workflow_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    target: GenericTargetProof
    prepared_at_utc: datetime

    @model_validator(mode="after")
    def timestamp_is_aware(self) -> "GenericDispatchEnvelope":
        if self.prepared_at_utc.tzinfo is None:
            raise ValueError("dispatch prepared_at_utc must be timezone-aware")
        return self


class PreparedGenericDispatch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    envelope: GenericDispatchEnvelope | None
    reason: str
    item: GenericReleaseItem | None = None


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def publication_local_date(value: datetime, timezone_name: str) -> date:
    if value.tzinfo is None:
        raise ValueError("publication timestamps must be timezone-aware")
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown publication timezone: {timezone_name}") from exc
    return value.astimezone(zone).date()


def publication_window(release: GenericReleaseQueue, publication_id: str) -> tuple[datetime, datetime]:
    index = next((offset for offset, item in enumerate(release.items) if item.publication_id == publication_id), None)
    if index is None:
        raise ValueError(f"publication is absent from immutable release: {publication_id}")

    item = release.items[index]
    start = item.scheduled_at.astimezone(UTC)
    if index + 1 < len(release.items):
        end = release.items[index + 1].scheduled_at.astimezone(UTC)
    else:
        zone = ZoneInfo(release.timezone)
        local_start = item.scheduled_at.astimezone(zone)
        end = (local_start.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).astimezone(UTC)
    if end <= start:
        raise ValueError(f"invalid publication window for {publication_id}")
    return start, end


def skip_expired_pending(
    release: GenericReleaseQueue,
    ledger: GenericPublicationLedger,
    *,
    now: datetime | None = None,
) -> tuple[str, ...]:
    effective_now = now or utc_now()
    if effective_now.tzinfo is None:
        raise ValueError("stale-publication check timestamp must be timezone-aware")
    effective_now = effective_now.astimezone(UTC)
    verify_ledger_against_release(ledger, release)

    skipped: list[str] = []
    for item in release.items:
        entry = ledger.entries[item.publication_id]
        if entry.state in {"published", "skipped"}:
            continue
        if entry.state != "pending":
            break
        _, end = publication_window(release, item.publication_id)
        if effective_now < end:
            break
        entry.state = "skipped"
        entry.provider_effect = "impossible"
        entry.last_error = f"publication window expired at {end.isoformat()} before dispatch"
        skipped.append(item.publication_id)
    return tuple(skipped)


def initialize_ledger(release: GenericReleaseQueue) -> GenericPublicationLedger:
    if not release.release_authorized:
        raise ValueError("publication ledger initialization requires an authorized immutable release")
    return GenericPublicationLedger(
        schema_name="video-channel-manager.telegram-generic-publication-ledger",
        schema_version=1,
        release_digest=release.digest,
        release_id=release.release_id,
        project_key=release.project_key,
        channel_username=release.channel_username,
        profile_sha256=release.profile_sha256,
        entries={
            item.publication_id: GenericLedgerEntry(
                publication_id=item.publication_id,
                provider_payload_sha256=item.payload.provider_payload_sha256,
            )
            for item in release.items
        },
    )


def load_ledger(path: Path, release: GenericReleaseQueue) -> GenericPublicationLedger:
    if not path.is_file():
        raise ValueError(f"Telegram generic ledger is missing: {path}; state must never be auto-initialized")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        ledger = GenericPublicationLedger.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"invalid Telegram generic ledger {path}: {exc}") from exc
    verify_ledger_against_release(ledger, release)
    return ledger


def save_ledger(path: Path, ledger: GenericPublicationLedger) -> None:
    validated = GenericPublicationLedger.model_validate(ledger.model_dump(mode="json"))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(validated.model_dump_json(indent=2))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def verify_ledger_against_release(ledger: GenericPublicationLedger, release: GenericReleaseQueue) -> None:
    if (
        ledger.release_digest != release.digest
        or ledger.release_id != release.release_id
        or ledger.project_key != release.project_key
        or ledger.channel_username.casefold() != release.channel_username.casefold()
        or ledger.profile_sha256 != release.profile_sha256
    ):
        raise ValueError("ledger identity differs from immutable release")
    release_by_id = {item.publication_id: item for item in release.items}
    if set(ledger.entries) != set(release_by_id):
        raise ValueError("ledger publication coverage differs from immutable release")
    for publication_id, item in release_by_id.items():
        if ledger.entries[publication_id].provider_payload_sha256 != item.payload.provider_payload_sha256:
            raise ValueError(f"provider payload changed after ledger initialization: {publication_id}")


def strict_next_item(
    release: GenericReleaseQueue,
    ledger: GenericPublicationLedger,
) -> tuple[GenericReleaseItem | None, str]:
    for item in release.items:
        entry = ledger.entries[item.publication_id]
        if entry.state in {"published", "skipped"}:
            continue
        if entry.state != "pending":
            return None, f"strict queue blocked by {item.publication_id} in state {entry.state}"
        return item, "next pending publication"
    return None, "release complete"


def _require_release_and_profile(profile: TelegramChannelProfile, release: GenericReleaseQueue) -> None:
    if not profile.provider_writes_authorized:
        raise ValueError("selected Telegram channel profile does not authorize provider writes")
    if not release.release_authorized:
        raise ValueError("selected Telegram release is not authorized")
    if (
        release.project_key != profile.project_key
        or release.channel_username.casefold() != profile.channel_username.casefold()
        or release.profile_sha256 != profile.digest
        or release.timezone != profile.timezone
        or release.daily_verified_limit != profile.daily_verified_limit
    ):
        raise ValueError("release contract differs from selected Telegram channel profile")


def _require_target(
    profile: TelegramChannelProfile,
    release: GenericReleaseQueue,
    target: GenericTargetProof,
    now: datetime,
) -> None:
    if target.project_key != profile.project_key or target.profile_sha256 != profile.digest:
        raise ValueError("target proof differs from selected Telegram channel profile")
    if target.channel_username.casefold() != profile.channel_username.casefold():
        raise ValueError("target proof channel differs from selected Telegram channel profile")
    if target.chat_username.casefold() != profile.bare_username.casefold() or target.chat_type != "channel":
        raise ValueError("target proof does not resolve the selected Telegram channel")
    if release.chat_id is None or release.bot_id is None or release.bot_username is None:
        raise ValueError("authorized release is missing exact Telegram target identity")
    if (
        target.chat_id != release.chat_id
        or target.bot_id != release.bot_id
        or target.bot_username.casefold() != release.bot_username.casefold()
    ):
        raise ValueError("target proof differs from release-bound Telegram target")
    age = now - target.checked_at_utc.astimezone(UTC)
    if age < -timedelta(minutes=1) or age > timedelta(minutes=15):
        raise ValueError("target proof is stale or has an invalid future timestamp")


def _require_provenance(*, run_id: str, run_attempt: str, github_sha: str, github_workflow_sha: str) -> None:
    if not run_id or re.fullmatch(r"[1-9][0-9]*", run_attempt) is None:
        raise ValueError("dispatch requires exact workflow run provenance")
    if re.fullmatch(r"[0-9a-f]{40}", github_sha) is None or re.fullmatch(r"[0-9a-f]{40}", github_workflow_sha) is None:
        raise ValueError("dispatch requires exact GitHub SHA provenance")


def prepare_next(
    profile: TelegramChannelProfile,
    release: GenericReleaseQueue,
    ledger: GenericPublicationLedger,
    *,
    run_id: str,
    run_attempt: str,
    github_sha: str,
    github_workflow_sha: str,
    mode: GenericDispatchMode,
    target: GenericTargetProof,
    expected_publication_id: str | None = None,
    now: datetime | None = None,
) -> PreparedGenericDispatch:
    prepared_at = now or utc_now()
    if prepared_at.tzinfo is None:
        raise ValueError("prepare timestamp must be timezone-aware")
    prepared_at = prepared_at.astimezone(UTC)
    _require_release_and_profile(profile, release)
    verify_ledger_against_release(ledger, release)
    _require_target(profile, release, target, prepared_at)
    _require_provenance(
        run_id=run_id,
        run_attempt=run_attempt,
        github_sha=github_sha,
        github_workflow_sha=github_workflow_sha,
    )
    if mode == "scheduled" and run_attempt != "1":
        return PreparedGenericDispatch(envelope=None, reason="scheduled workflow re-runs are forbidden")

    today = publication_local_date(prepared_at, release.timezone)
    verified_today = sum(
        1
        for entry in ledger.entries.values()
        if entry.state == "published"
        and entry.provider_effect == "verified"
        and entry.published_at_utc is not None
        and publication_local_date(entry.published_at_utc, release.timezone) == today
    )
    if verified_today >= release.daily_verified_limit:
        return PreparedGenericDispatch(
            envelope=None, reason=f"daily verified limit already used for {today.isoformat()}"
        )

    if mode == "scheduled":
        manual_canary = any(
            entry.state == "published"
            and entry.provider_effect == "verified"
            and entry.dispatch_mode == "manual"
            and entry.actual_chat_id == target.chat_id
            and entry.bot_id == target.bot_id
            for entry in ledger.entries.values()
        )
        if not manual_canary:
            return PreparedGenericDispatch(
                envelope=None, reason="scheduled execution requires a verified manual canary"
            )

    item, reason = strict_next_item(release, ledger)
    if item is None:
        return PreparedGenericDispatch(envelope=None, reason=reason)

    if mode == "manual":
        if expected_publication_id is None:
            return PreparedGenericDispatch(
                envelope=None, reason="manual execution requires an exact publication_id", item=item
            )
        if expected_publication_id != item.publication_id:
            return PreparedGenericDispatch(
                envelope=None,
                reason=f"manual publication_id mismatch: requested {expected_publication_id}, strict next is {item.publication_id}",
                item=item,
            )
    elif expected_publication_id is not None:
        return PreparedGenericDispatch(
            envelope=None,
            reason="scheduled execution must not carry a manual publication_id",
            item=item,
        )

    window_start, window_end = publication_window(release, item.publication_id)
    if prepared_at < window_start:
        return PreparedGenericDispatch(
            envelope=None,
            reason=f"publication window does not open until {item.scheduled_at.isoformat()}",
            item=item,
        )
    if prepared_at >= window_end:
        return PreparedGenericDispatch(
            envelope=None,
            reason=f"publication window expired at {window_end.isoformat()}",
            item=item,
        )

    entry = ledger.entries[item.publication_id]
    intent_id = secrets.token_hex(16)
    entry.state = "dispatching"
    entry.provider_effect = "may_exist"
    entry.intent_id = intent_id
    entry.dispatch_mode = mode
    entry.workflow_run_id = run_id
    entry.workflow_run_attempt = run_attempt
    entry.github_sha = github_sha
    entry.github_workflow_sha = github_workflow_sha
    entry.attempted_at_utc = prepared_at
    entry.actual_chat_id = target.chat_id
    entry.actual_chat_username = target.chat_username
    entry.bot_id = target.bot_id
    entry.bot_username = target.bot_username
    entry.last_error = None

    envelope = GenericDispatchEnvelope(
        schema_name="video-channel-manager.telegram-generic-dispatch",
        schema_version=1,
        release_digest=release.digest,
        release_id=release.release_id,
        project_key=release.project_key,
        channel_username=release.channel_username,
        profile_sha256=release.profile_sha256,
        publication_id=item.publication_id,
        sequence=item.sequence,
        provider_payload_sha256=item.payload.provider_payload_sha256,
        intent_id=intent_id,
        dispatch_mode=mode,
        workflow_run_id=run_id,
        workflow_run_attempt=run_attempt,
        github_sha=github_sha,
        github_workflow_sha=github_workflow_sha,
        target=target,
        prepared_at_utc=prepared_at,
    )
    return PreparedGenericDispatch(envelope=envelope, reason="prepared", item=item)


def verify_dispatch_against_release(
    release: GenericReleaseQueue,
    envelope: GenericDispatchEnvelope,
) -> GenericReleaseItem:
    if envelope.release_digest != release.digest or envelope.release_id != release.release_id:
        raise ValueError("dispatch release identity differs from immutable release")
    item = next((candidate for candidate in release.items if candidate.publication_id == envelope.publication_id), None)
    if item is None:
        raise ValueError("dispatch publication is absent from immutable release")
    if item.sequence != envelope.sequence or item.payload.provider_payload_sha256 != envelope.provider_payload_sha256:
        raise ValueError("dispatch provider payload differs from immutable release")
    return item


def verify_persisted_intent(
    release: GenericReleaseQueue,
    ledger: GenericPublicationLedger,
    envelope: GenericDispatchEnvelope,
) -> GenericLedgerEntry:
    verify_dispatch_against_release(release, envelope)
    verify_ledger_against_release(ledger, release)
    entry = ledger.entries[envelope.publication_id]
    if entry.state != "dispatching" or entry.provider_effect != "may_exist":
        raise ValueError("persisted ledger is not in conservative dispatching state")
    expected = (
        envelope.intent_id,
        envelope.workflow_run_id,
        envelope.workflow_run_attempt,
        envelope.github_sha,
        envelope.github_workflow_sha,
        envelope.provider_payload_sha256,
        envelope.dispatch_mode,
        envelope.target.chat_id,
        envelope.target.chat_username.casefold(),
        envelope.target.bot_id,
        envelope.target.bot_username.casefold(),
    )
    actual = (
        entry.intent_id,
        entry.workflow_run_id,
        entry.workflow_run_attempt,
        entry.github_sha,
        entry.github_workflow_sha,
        entry.provider_payload_sha256,
        entry.dispatch_mode,
        entry.actual_chat_id,
        (entry.actual_chat_username or "").casefold(),
        entry.bot_id,
        (entry.bot_username or "").casefold(),
    )
    if actual != expected:
        raise ValueError("persisted ledger intent differs from prepared dispatch")
    return entry


def mark_published(
    ledger: GenericPublicationLedger,
    envelope: GenericDispatchEnvelope,
    receipt: GenericSendReceipt,
) -> GenericLedgerEntry:
    entry = ledger.entries.get(envelope.publication_id)
    if entry is None:
        raise ValueError("ledger does not contain dispatched publication")
    if entry.state != "dispatching" or entry.provider_effect != "may_exist" or entry.intent_id != envelope.intent_id:
        raise ValueError("ledger is not bound to the dispatch being completed")
    if (
        receipt.project_key != envelope.project_key
        or receipt.publication_id != envelope.publication_id
        or receipt.provider_payload_sha256 != envelope.provider_payload_sha256
        or receipt.chat_id != envelope.target.chat_id
        or receipt.chat_username.casefold() != envelope.target.chat_username.casefold()
    ):
        raise ValueError("Telegram receipt differs from prepared dispatch")
    expected_url = f"https://t.me/{receipt.chat_username}/{receipt.message_id}"
    if receipt.message_url != expected_url:
        raise ValueError("Telegram receipt does not contain canonical message URL")

    entry.state = "published"
    entry.provider_effect = "verified"
    entry.message_id = receipt.message_id
    entry.message_url = receipt.message_url
    entry.published_at_utc = receipt.verified_at_utc
    entry.last_error = None
    return entry


def mark_unknown(
    ledger: GenericPublicationLedger,
    envelope: GenericDispatchEnvelope,
    *,
    error: str,
) -> GenericLedgerEntry:
    entry = ledger.entries.get(envelope.publication_id)
    if entry is None or entry.intent_id != envelope.intent_id:
        raise ValueError("ledger does not contain the unresolved dispatch intent")
    if entry.state != "dispatching" or entry.provider_effect != "may_exist":
        raise ValueError("only a live dispatching intent can become unknown")
    entry.state = "unknown"
    entry.provider_effect = "may_exist"
    entry.last_error = " ".join(error.split())[:1000]
    return entry
