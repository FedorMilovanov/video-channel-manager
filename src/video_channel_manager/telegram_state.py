from __future__ import annotations

import json
import os
import secrets
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ValidationError

from video_channel_manager.telegram_models import (
    CHANNEL_USERNAME,
    PROJECT_KEY,
    PUBLICATION_TIMEZONE,
    DispatchEnvelope,
    DispatchMode,
    LedgerEntry,
    PreparedDispatch,
    ScheduledSlot,
    TargetProof,
    TelegramLedger,
    TelegramPost,
    TelegramQueue,
)


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


def initialize_ledger(queue: TelegramQueue) -> TelegramLedger:
    return TelegramLedger(
        schema_name="video-channel-manager.telegram-publication-ledger",
        schema_version=3,
        project_key=PROJECT_KEY,
        channel_username=CHANNEL_USERNAME,
        queue_digest=queue.digest,
        entries={
            post.publication_id: LedgerEntry(
                publication_id=post.publication_id,
                payload_sha256=post.payload_sha256,
            )
            for post in queue.posts
        },
    )


def initialize_ledger_file(path: Path, queue: TelegramQueue) -> TelegramLedger:
    if path.exists():
        raise ValueError(f"refusing to overwrite existing Telegram ledger: {path}")
    ledger = initialize_ledger(queue)
    save_ledger(path, ledger)
    return ledger


def load_ledger(path: Path, queue: TelegramQueue) -> TelegramLedger:
    """Load production state strictly; missing or partial state is never regenerated."""

    if not path.is_file():
        raise ValueError(f"Telegram ledger is missing: {path}; production state must never be auto-initialized")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        ledger = TelegramLedger.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"invalid Telegram ledger {path}: {exc}") from exc

    if ledger.queue_digest != queue.digest:
        raise ValueError("queue digest differs from the immutable digest recorded in the ledger")

    queue_by_id = {post.publication_id: post for post in queue.posts}
    ledger_ids = set(ledger.entries)
    queue_ids = set(queue_by_id)
    missing_ids = sorted(queue_ids - ledger_ids)
    extra_ids = sorted(ledger_ids - queue_ids)
    if missing_ids or extra_ids:
        raise ValueError(
            f"ledger publication coverage differs from immutable queue; missing={missing_ids}, extra={extra_ids}"
        )

    for publication_id, post in queue_by_id.items():
        entry = ledger.entries[publication_id]
        if entry.payload_sha256 != post.payload_sha256:
            raise ValueError(f"payload changed after ledger initialization: {publication_id}")
    return ledger


def load_or_initialize_ledger(path: Path, queue: TelegramQueue) -> TelegramLedger:
    """Backward-compatible name with intentionally strict production semantics."""

    return load_ledger(path, queue)


def save_ledger(path: Path, ledger: TelegramLedger) -> None:
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
    path.write_text(model.model_dump_json(indent=2) + "\n", encoding="utf-8")


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


def _published_author_history(queue: TelegramQueue, ledger: TelegramLedger) -> list[str]:
    history: list[tuple[datetime, int, str]] = []
    for post in queue.posts:
        entry = ledger.entries[post.publication_id]
        if entry.state == "published" and entry.provider_effect == "verified" and entry.published_at_utc is not None:
            history.append((entry.published_at_utc.astimezone(UTC), post.sequence, post.source.author))
    history.sort(key=lambda item: (item[0], item[1]))
    return [author for _, _, author in history]


def _requires_editorial_author_rotation(queue: TelegramQueue, ledger: TelegramLedger) -> bool:
    authors = _published_author_history(queue, ledger)
    return any(previous == current for previous, current in zip(authors, authors[1:], strict=False))


def _author_round_robin(queue: TelegramQueue) -> list[TelegramPost]:
    author_order: list[str] = []
    by_author: dict[str, list[TelegramPost]] = {}
    for post in queue.posts:
        author = post.source.author
        if author not in by_author:
            author_order.append(author)
            by_author[author] = []
        by_author[author].append(post)

    ordered: list[TelegramPost] = []
    round_index = 0
    while True:
        added = False
        for author in author_order:
            posts = by_author[author]
            if round_index < len(posts):
                ordered.append(posts[round_index])
                added = True
        if not added:
            break
        round_index += 1
    return ordered


def strict_next_post(queue: TelegramQueue, ledger: TelegramLedger) -> tuple[TelegramPost | None, str]:
    rotate_authors = _requires_editorial_author_rotation(queue, ledger)
    if rotate_authors:
        for post in queue.posts:
            entry = ledger.entries[post.publication_id]
            if entry.state not in {"published", "skipped", "pending"}:
                return None, f"strict queue blocked by {post.publication_id} in state {entry.state}"
        candidates = _author_round_robin(queue)
    else:
        candidates = list(queue.posts)

    for post in candidates:
        entry = ledger.entries[post.publication_id]
        if entry.state in {"published", "skipped"}:
            continue
        if entry.state != "pending":
            return None, f"strict queue blocked by {post.publication_id} in state {entry.state}"
        reason = "next pending publication"
        if rotate_authors:
            reason += " (editorial author rotation)"
        return post, reason
    return None, "queue complete"


def preview_next(queue: TelegramQueue, ledger: TelegramLedger) -> PreparedDispatch:
    post, reason = strict_next_post(queue, ledger)
    return PreparedDispatch(envelope=None, reason=reason, post=post)


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


def verify_persisted_intent(
    queue: TelegramQueue,
    ledger: TelegramLedger,
    envelope: DispatchEnvelope,
) -> LedgerEntry:
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
    if entry.workflow_run_attempt != envelope.workflow_run_attempt:
        raise ValueError("persisted ledger run attempt differs from prepared dispatch")
    if entry.github_sha != envelope.github_sha or entry.github_workflow_sha != envelope.github_workflow_sha:
        raise ValueError("persisted ledger GitHub provenance differs from prepared dispatch")
    if entry.payload_sha256 != envelope.payload_sha256:
        raise ValueError("persisted ledger payload fingerprint differs from prepared dispatch")
    if entry.dispatch_mode != envelope.dispatch_mode:
        raise ValueError("persisted ledger dispatch mode differs from prepared dispatch")
    if entry.scheduled_moscow_date != envelope.scheduled_moscow_date or entry.scheduled_slot != envelope.scheduled_slot:
        raise ValueError("persisted ledger scheduled slot provenance differs from prepared dispatch")
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


def _require_provenance(*, run_id: str, run_attempt: str, github_sha: str, github_workflow_sha: str) -> None:
    if not run_id or not run_attempt or not github_sha or not github_workflow_sha:
        raise ValueError("dispatch requires complete GitHub execution provenance")


def _already_published_on_date(
    ledger: TelegramLedger,
    *,
    local_date: date,
    publication_timezone: str,
) -> bool:
    return any(
        entry.state == "published"
        and entry.provider_effect == "verified"
        and entry.published_at_utc is not None
        and publication_local_date(entry.published_at_utc, publication_timezone) == local_date
        for entry in ledger.entries.values()
    )


def prepare_next(
    queue: TelegramQueue,
    ledger: TelegramLedger,
    *,
    run_id: str,
    run_attempt: str,
    github_sha: str,
    github_workflow_sha: str,
    mode: DispatchMode,
    target: TargetProof,
    expected_publication_id: str | None = None,
    scheduled_moscow_date: date | None = None,
    scheduled_slot: ScheduledSlot | None = None,
    publication_timezone: str = PUBLICATION_TIMEZONE,
    now: datetime | None = None,
) -> PreparedDispatch:
    now = now or utc_now()
    if now.tzinfo is None:
        raise ValueError("prepare timestamp must be timezone-aware")
    _require_provenance(
        run_id=run_id,
        run_attempt=run_attempt,
        github_sha=github_sha,
        github_workflow_sha=github_workflow_sha,
    )
    if mode == "scheduled" and run_attempt != "1":
        return PreparedDispatch(None, "strict queue blocked: scheduled workflow re-runs are forbidden")

    proof_age = now - target.checked_at_utc.astimezone(UTC)
    if proof_age < -timedelta(minutes=1) or proof_age > timedelta(minutes=15):
        raise ValueError("target proof is stale or has an invalid future timestamp")
    if target.chat_id >= 0 or target.chat_username != CHANNEL_USERNAME.removeprefix("@"):
        raise ValueError("target proof is not for @lordchrist")
    if target.chat_type != "channel":
        raise ValueError("target proof is not a Telegram channel")

    today = publication_local_date(now, publication_timezone)
    if mode == "manual":
        if scheduled_moscow_date is not None or scheduled_slot is not None:
            raise ValueError("manual execution cannot carry scheduled slot provenance")
        if _already_published_on_date(ledger, local_date=today, publication_timezone=publication_timezone):
            return PreparedDispatch(None, f"one publication is already verified for {today.isoformat()}")
    else:
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

        has_date = scheduled_moscow_date is not None
        has_slot = scheduled_slot is not None
        if has_date != has_slot:
            return PreparedDispatch(None, "scheduled execution requires exact Moscow date and slot")
        if not has_date:
            # Backward-compatible prepare-only path for legacy library callers.
            # The provider transport rejects slot-less scheduled envelopes, and
            # the production workflow always supplies explicit date+slot.
            if _already_published_on_date(ledger, local_date=today, publication_timezone=publication_timezone):
                return PreparedDispatch(None, f"one publication is already verified for {today.isoformat()}")
        else:
            assert scheduled_moscow_date is not None
            assert scheduled_slot is not None
            if scheduled_moscow_date != today:
                return PreparedDispatch(
                    None,
                    f"scheduled Moscow date mismatch: requested {scheduled_moscow_date.isoformat()}, current {today.isoformat()}",
                )
            claimed_by = next(
                (
                    entry.publication_id
                    for entry in ledger.entries.values()
                    if entry.scheduled_moscow_date == scheduled_moscow_date and entry.scheduled_slot == scheduled_slot
                ),
                None,
            )
            if claimed_by is not None:
                return PreparedDispatch(
                    None,
                    f"scheduled slot {scheduled_moscow_date.isoformat()}/{scheduled_slot} is already claimed by {claimed_by}",
                )

    post, reason = strict_next_post(queue, ledger)
    if post is None:
        return PreparedDispatch(None, reason)

    if mode == "manual":
        if expected_publication_id is None:
            return PreparedDispatch(None, "manual execution requires an exact publication_id", post)
        if expected_publication_id != post.publication_id:
            return PreparedDispatch(
                None,
                f"manual publication_id mismatch: requested {expected_publication_id}, strict next is {post.publication_id}",
                post,
            )
    elif expected_publication_id is not None:
        return PreparedDispatch(None, "scheduled execution must not carry a manual publication_id", post)

    entry = ledger.entries[post.publication_id]
    intent_id = secrets.token_hex(16)
    entry.state = "dispatching"
    entry.provider_effect = "may_exist"
    entry.intent_id = intent_id
    entry.dispatch_mode = mode
    entry.scheduled_moscow_date = scheduled_moscow_date
    entry.scheduled_slot = scheduled_slot
    entry.workflow_run_id = run_id
    entry.workflow_run_attempt = run_attempt
    entry.github_sha = github_sha
    entry.github_workflow_sha = github_workflow_sha
    entry.attempted_at_utc = now
    entry.bot_id = target.bot_id
    entry.bot_username = target.bot_username
    entry.actual_chat_id = target.chat_id
    entry.actual_chat_username = target.chat_username
    entry.last_error = None

    envelope = DispatchEnvelope(
        schema_name="video-channel-manager.telegram-dispatch",
        schema_version=4,
        project_key=PROJECT_KEY,
        channel_username=CHANNEL_USERNAME,
        queue_digest=queue.digest,
        publication_id=post.publication_id,
        sequence=post.sequence,
        intent_id=intent_id,
        workflow_run_id=run_id,
        workflow_run_attempt=run_attempt,
        github_sha=github_sha,
        github_workflow_sha=github_workflow_sha,
        payload_sha256=post.payload_sha256,
        text=post.text,
        dispatch_mode=mode,
        scheduled_moscow_date=scheduled_moscow_date,
        scheduled_slot=scheduled_slot,
        target=target,
        prepared_at_utc=now,
    )
    return PreparedDispatch(envelope, "prepared", post)


def resolve_entry(
    ledger: TelegramLedger,
    publication_id: str,
    *,
    resolution: Literal["confirmed_published", "confirmed_absent", "skip"],
    evidence_note: str,
    resolved_by: str,
    message_id: int | None = None,
    expected_chat_id: int | None = None,
    published_at_utc: datetime | None = None,
    now: datetime | None = None,
) -> LedgerEntry:
    note = " ".join(evidence_note.split())
    resolver = " ".join(resolved_by.split())
    if len(note) < 20:
        raise ValueError("reconciliation requires a concrete evidence note of at least 20 characters")
    if len(resolver) < 2:
        raise ValueError("reconciliation requires a concrete resolver identity")
    entry = ledger.entries.get(publication_id)
    if entry is None:
        raise ValueError(f"unknown publication_id: {publication_id}")
    resolved_at = now or utc_now()
    if resolved_at.tzinfo is None:
        raise ValueError("reconciliation timestamp must be timezone-aware")
    resolved_at = resolved_at.astimezone(UTC)

    if resolution == "confirmed_published":
        if entry.state not in {"dispatching", "unknown"} or entry.provider_effect != "may_exist":
            raise ValueError("confirmed_published is valid only for an unresolved may_exist dispatch")
        if message_id is None or message_id <= 0 or expected_chat_id is None or expected_chat_id >= 0:
            raise ValueError("confirmed_published requires message_id and an exact negative expected_chat_id")
        if entry.actual_chat_id is not None and entry.actual_chat_id != expected_chat_id:
            raise ValueError("reconciliation chat id differs from the durable dispatch target")
        if entry.bot_id is None or entry.bot_id <= 0 or not entry.bot_username:
            raise ValueError("confirmed_published requires the durable dispatch bot identity")
        publication_time = published_at_utc
        if publication_time is None:
            if entry.attempted_at_utc is None or entry.attempted_at_utc.tzinfo is None:
                raise ValueError("confirmed_published requires durable attempted_at_utc provenance")
            if publication_local_date(entry.attempted_at_utc) != publication_local_date(resolved_at):
                raise ValueError(
                    "confirmed_published requires explicit evidence-backed published_at_utc across publication dates"
                )
            publication_time = resolved_at
        if publication_time.tzinfo is None:
            raise ValueError("confirmed_published publication timestamp must be timezone-aware")
        publication_time = publication_time.astimezone(UTC)
        if entry.attempted_at_utc is None or entry.attempted_at_utc.tzinfo is None:
            raise ValueError("confirmed_published requires durable attempted_at_utc provenance")
        if publication_time < entry.attempted_at_utc.astimezone(UTC):
            raise ValueError("confirmed_published publication timestamp cannot precede the durable dispatch attempt")
        if publication_time > resolved_at:
            raise ValueError("confirmed_published publication timestamp cannot be later than reconciliation")
        entry.state = "published"
        entry.provider_effect = "verified"
        entry.message_id = message_id
        entry.actual_chat_id = expected_chat_id
        entry.actual_chat_username = CHANNEL_USERNAME.removeprefix("@")
        entry.message_url = f"https://t.me/{CHANNEL_USERNAME.removeprefix('@')}/{message_id}"
        entry.published_at_utc = publication_time
        entry.last_error = "manually reconciled as published"
    elif resolution == "confirmed_absent":
        if published_at_utc is not None:
            raise ValueError("published_at_utc is valid only for confirmed_published reconciliation")
        if entry.state not in {"dispatching", "unknown", "failed"}:
            raise ValueError("confirmed_absent is valid only for an unresolved or failed dispatch")
        if entry.state in {"dispatching", "unknown"} and entry.provider_effect != "may_exist":
            raise ValueError("unresolved confirmed_absent reconciliation requires provider_effect=may_exist")
        if entry.state == "failed" and entry.provider_effect not in {"not_dispatched", "confirmed_absent"}:
            raise ValueError("failed confirmed_absent reconciliation requires no possible provider effect")
        entry.state = "pending"
        entry.provider_effect = "confirmed_absent"
        entry.intent_id = None
        entry.message_id = None
        entry.message_url = None
        entry.published_at_utc = None
        entry.last_error = "manually reconciled as confirmed absent"
    else:
        if published_at_utc is not None:
            raise ValueError("published_at_utc is valid only for confirmed_published reconciliation")
        if entry.state not in {"pending", "failed"}:
            raise ValueError("skip is forbidden while a provider effect is unresolved")
        if entry.provider_effect not in {"impossible", "not_dispatched", "confirmed_absent"}:
            raise ValueError("skip requires proof that no provider message can exist")
        entry.state = "skipped"
        entry.provider_effect = "impossible"
        entry.intent_id = None
        entry.message_id = None
        entry.message_url = None
        entry.published_at_utc = None
        entry.last_error = "manually skipped"
    entry.resolved_at_utc = resolved_at
    entry.resolved_by = resolver
    entry.reconciliation_note = note
    return entry


def require_preflight_config(*, queue_digest: str) -> None:
    approved = os.environ.get("LORDCHRIST_APPROVED_QUEUE_DIGEST", "").strip()
    if approved != queue_digest:
        raise RuntimeError("immutable queue digest is not explicitly approved in repository variables")


def require_execution_enabled(*, queue_digest: str, mode: DispatchMode) -> None:
    require_preflight_config(queue_digest=queue_digest)
    if os.environ.get("LORDCHRIST_POSTING_ENABLED", "").strip().casefold() != "true":
        raise RuntimeError("provider execution is disabled; set LORDCHRIST_POSTING_ENABLED=true")
    if mode == "scheduled" and os.environ.get("LORDCHRIST_SCHEDULE_ENABLED", "").strip().casefold() != "true":
        raise RuntimeError("scheduled execution is disabled; set LORDCHRIST_SCHEDULE_ENABLED=true after canary")
