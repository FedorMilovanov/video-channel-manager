from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from video_channel_manager.telegram_publisher import (
    TargetProof,
    TelegramLedger,
    dispatch_prepared,
    initialize_ledger,
    load_queue,
    prepare_next,
    verify_persisted_intent,
)

ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = ROOT / "content/telegram/lordchrist/verified-30-posts.json"
GITHUB_SHA = "a" * 40
WORKFLOW_SHA = "b" * 40


def _target(now: datetime) -> TargetProof:
    return TargetProof(
        schema_name="video-channel-manager.telegram-target-proof",
        schema_version=2,
        bot_id=42,
        bot_username="lordchrist_publisher_bot",
        chat_id=-1001234567890,
        chat_username="lordchrist",
        chat_title="Господь Бог — Сила Моя",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=now,
    )


def _mark_manual_canary(ledger: TelegramLedger, publication_id: str, *, published_at: datetime) -> None:
    entry = ledger.entries[publication_id]
    entry.state = "published"
    entry.provider_effect = "verified"
    entry.intent_id = "manual-canary-intent"
    entry.dispatch_mode = "manual"
    entry.workflow_run_id = "manual-canary-run"
    entry.workflow_run_attempt = "1"
    entry.github_sha = GITHUB_SHA
    entry.github_workflow_sha = WORKFLOW_SHA
    entry.attempted_at_utc = published_at - timedelta(seconds=2)
    entry.published_at_utc = published_at
    entry.message_id = 1470
    entry.message_url = "https://t.me/lordchrist/1470"
    entry.actual_chat_id = -1001234567890
    entry.actual_chat_username = "lordchrist"
    entry.bot_id = 42
    entry.bot_username = "lordchrist_publisher_bot"


def _mark_prepared_as_published(ledger: TelegramLedger, publication_id: str, *, published_at: datetime) -> None:
    entry = ledger.entries[publication_id]
    entry.state = "published"
    entry.provider_effect = "verified"
    entry.published_at_utc = published_at
    entry.message_id = 2000
    entry.message_url = "https://t.me/lordchrist/2000"


def _scheduled_prepare(
    ledger: TelegramLedger,
    *,
    now: datetime,
    slot: str,
):
    queue = load_queue(QUEUE_PATH)
    return prepare_next(
        queue,
        ledger,
        run_id=f"run-{slot}-{now.hour}",
        run_attempt="1",
        github_sha=GITHUB_SHA,
        github_workflow_sha=WORKFLOW_SHA,
        mode="scheduled",
        target=_target(now),
        scheduled_moscow_date=date(2026, 9, 8),
        scheduled_slot=slot,  # type: ignore[arg-type]
        now=now,
    )


def test_legacy_ledger_without_slot_fields_remains_readable() -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = initialize_ledger(queue)
    payload = ledger.model_dump(mode="json")
    for raw_entry in payload["entries"].values():
        raw_entry.pop("scheduled_moscow_date", None)
        raw_entry.pop("scheduled_slot", None)

    restored = TelegramLedger.model_validate(payload)
    assert restored.schema_version == 3
    assert all(entry.scheduled_moscow_date is None for entry in restored.entries.values())
    assert all(entry.scheduled_slot is None for entry in restored.entries.values())


def test_exact_morning_and_evening_slots_can_publish_on_same_moscow_date() -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = initialize_ledger(queue)
    _mark_manual_canary(
        ledger,
        queue.posts[0].publication_id,
        published_at=datetime(2026, 9, 7, 6, 17, tzinfo=UTC),
    )

    morning_now = datetime(2026, 9, 8, 6, 17, tzinfo=UTC)
    morning = _scheduled_prepare(ledger, now=morning_now, slot="morning")
    assert morning.envelope is not None
    assert morning.envelope.scheduled_moscow_date == date(2026, 9, 8)
    assert morning.envelope.scheduled_slot == "morning"
    morning_id = morning.envelope.publication_id
    assert ledger.entries[morning_id].scheduled_slot == "morning"
    _mark_prepared_as_published(ledger, morning_id, published_at=morning_now + timedelta(seconds=3))

    evening_now = datetime(2026, 9, 8, 18, 17, tzinfo=UTC)
    evening = _scheduled_prepare(ledger, now=evening_now, slot="evening")
    assert evening.envelope is not None
    assert evening.envelope.publication_id != morning_id
    assert evening.envelope.scheduled_moscow_date == date(2026, 9, 8)
    assert evening.envelope.scheduled_slot == "evening"


def test_same_date_and_slot_is_single_use_even_after_verified_publication() -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = initialize_ledger(queue)
    _mark_manual_canary(
        ledger,
        queue.posts[0].publication_id,
        published_at=datetime(2026, 9, 7, 6, 17, tzinfo=UTC),
    )
    now = datetime(2026, 9, 8, 6, 17, tzinfo=UTC)

    first = _scheduled_prepare(ledger, now=now, slot="morning")
    assert first.envelope is not None
    _mark_prepared_as_published(ledger, first.envelope.publication_id, published_at=now + timedelta(seconds=3))

    duplicate = _scheduled_prepare(ledger, now=now + timedelta(minutes=1), slot="morning")
    assert duplicate.envelope is None
    assert "already claimed" in duplicate.reason
    assert first.envelope.publication_id in duplicate.reason


def test_evening_slot_does_not_backfill_a_missing_morning_slot() -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = initialize_ledger(queue)
    _mark_manual_canary(
        ledger,
        queue.posts[0].publication_id,
        published_at=datetime(2026, 9, 7, 6, 17, tzinfo=UTC),
    )

    evening_now = datetime(2026, 9, 8, 18, 17, tzinfo=UTC)
    evening = _scheduled_prepare(ledger, now=evening_now, slot="evening")
    assert evening.envelope is not None
    assert evening.envelope.scheduled_slot == "evening"
    claimed = [
        entry
        for entry in ledger.entries.values()
        if entry.scheduled_moscow_date == date(2026, 9, 8) and entry.scheduled_slot is not None
    ]
    assert len(claimed) == 1
    assert claimed[0].scheduled_slot == "evening"


def test_mismatched_scheduled_date_fails_closed_without_mutating_state() -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = initialize_ledger(queue)
    _mark_manual_canary(
        ledger,
        queue.posts[0].publication_id,
        published_at=datetime(2026, 9, 7, 6, 17, tzinfo=UTC),
    )
    now = datetime(2026, 9, 8, 6, 17, tzinfo=UTC)
    before = ledger.model_dump(mode="json")

    result = prepare_next(
        queue,
        ledger,
        run_id="wrong-date",
        run_attempt="1",
        github_sha=GITHUB_SHA,
        github_workflow_sha=WORKFLOW_SHA,
        mode="scheduled",
        target=_target(now),
        scheduled_moscow_date=date(2026, 9, 9),
        scheduled_slot="morning",
        now=now,
    )
    assert result.envelope is None
    assert "scheduled Moscow date mismatch" in result.reason
    assert ledger.model_dump(mode="json") == before


def test_persisted_intent_rejects_slot_tampering() -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = initialize_ledger(queue)
    _mark_manual_canary(
        ledger,
        queue.posts[0].publication_id,
        published_at=datetime(2026, 9, 7, 6, 17, tzinfo=UTC),
    )
    now = datetime(2026, 9, 8, 6, 17, tzinfo=UTC)
    prepared = _scheduled_prepare(ledger, now=now, slot="morning")
    assert prepared.envelope is not None

    tampered = prepared.envelope.model_copy(update={"scheduled_slot": "evening"})
    with pytest.raises(ValueError, match="scheduled slot provenance"):
        verify_persisted_intent(queue, ledger, tampered)


def test_legacy_slotless_scheduled_prepare_is_provider_inert() -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = initialize_ledger(queue)
    _mark_manual_canary(
        ledger,
        queue.posts[0].publication_id,
        published_at=datetime(2026, 9, 7, 6, 17, tzinfo=UTC),
    )
    now = datetime(2026, 9, 8, 6, 17, tzinfo=UTC)
    prepared = prepare_next(
        queue,
        ledger,
        run_id="legacy-scheduled",
        run_attempt="1",
        github_sha=GITHUB_SHA,
        github_workflow_sha=WORKFLOW_SHA,
        mode="scheduled",
        target=_target(now),
        now=now,
    )
    assert prepared.envelope is not None
    assert prepared.envelope.scheduled_moscow_date is None
    assert prepared.envelope.scheduled_slot is None

    provider_called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal provider_called
        provider_called = True
        return httpx.Response(500)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="scheduled provider dispatch requires exact Moscow date"):
            dispatch_prepared(
                queue,
                prepared.envelope,
                ledger,
                token="secret",
                api_base="https://api.telegram.test",
                client=client,
                now=now + timedelta(seconds=1),
            )
    assert provider_called is False
