from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from video_channel_manager.telegram_models import LedgerEntry, TargetProof, TelegramLedger
from video_channel_manager.telegram_state import (
    initialize_ledger,
    load_queue,
    prepare_next,
    resolve_entry,
    verify_persisted_intent,
)

ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = ROOT / "content/telegram/lordchrist/verified-30-posts.json"
GITHUB_SHA = "a" * 40
WORKFLOW_SHA = "b" * 40
CHAT_ID = -1001295216957
BOT_ID = 8716602202
BOT_USERNAME = "preaching_mp3_bot"


def target(now: datetime) -> TargetProof:
    return TargetProof(
        schema_name="video-channel-manager.telegram-target-proof",
        schema_version=2,
        bot_id=BOT_ID,
        bot_username=BOT_USERNAME,
        chat_id=CHAT_ID,
        chat_username="lordchrist",
        chat_title="Господь Бог — Сила Моя",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=now,
    )


def mark_published(
    entry: LedgerEntry,
    *,
    attempted_at: datetime,
    published_at: datetime,
    mode: str,
    message_id: int,
    scheduled_slot: str | None = None,
) -> None:
    entry.state = "published"
    entry.provider_effect = "verified"
    entry.intent_id = f"intent-{message_id}"
    entry.dispatch_mode = mode  # type: ignore[assignment]
    entry.scheduled_slot = scheduled_slot  # type: ignore[assignment]
    entry.workflow_run_id = f"run-{message_id}"
    entry.workflow_run_attempt = "1"
    entry.github_sha = GITHUB_SHA
    entry.github_workflow_sha = WORKFLOW_SHA
    entry.attempted_at_utc = attempted_at
    entry.published_at_utc = published_at
    entry.message_id = message_id
    entry.message_url = f"https://t.me/lordchrist/{message_id}"
    entry.actual_chat_id = CHAT_ID
    entry.actual_chat_username = "lordchrist"
    entry.bot_id = BOT_ID
    entry.bot_username = BOT_USERNAME


def ledger_with_manual_canary(now: datetime):
    queue = load_queue(QUEUE_PATH)
    ledger = initialize_ledger(queue)
    previous_day = now - timedelta(days=1)
    mark_published(
        ledger.entries[queue.posts[0].publication_id],
        attempted_at=previous_day - timedelta(minutes=1),
        published_at=previous_day,
        mode="manual",
        message_id=1470,
    )
    return queue, ledger


def prepare_scheduled(queue, ledger, *, now: datetime, slot: str, run_id: str):
    return prepare_next(
        queue,
        ledger,
        run_id=run_id,
        run_attempt="1",
        github_sha=GITHUB_SHA,
        github_workflow_sha=WORKFLOW_SHA,
        mode="scheduled",
        scheduled_slot=slot,  # type: ignore[arg-type]
        target=target(now),
        now=now,
    )


def test_morning_and_evening_can_publish_two_distinct_posts_on_an_eligible_day() -> None:
    morning_time = datetime(2026, 9, 8, 6, 17, tzinfo=UTC)
    evening_time = datetime(2026, 9, 8, 18, 17, tzinfo=UTC)
    queue, ledger = ledger_with_manual_canary(morning_time)

    morning = prepare_scheduled(queue, ledger, now=morning_time, slot="morning", run_id="morning-run")
    assert morning.envelope is not None
    assert morning.envelope.scheduled_slot == "morning"
    assert morning.envelope.publication_id == queue.posts[1].publication_id
    morning_entry = ledger.entries[morning.envelope.publication_id]
    mark_published(
        morning_entry,
        attempted_at=morning_time,
        published_at=morning_time + timedelta(minutes=1),
        mode="scheduled",
        scheduled_slot="morning",
        message_id=1501,
    )

    evening = prepare_scheduled(queue, ledger, now=evening_time, slot="evening", run_id="evening-run")
    assert evening.envelope is not None
    assert evening.envelope.scheduled_slot == "evening"
    assert evening.envelope.publication_id != morning.envelope.publication_id


def test_same_slot_cannot_publish_twice_on_same_moscow_date() -> None:
    morning_time = datetime(2026, 9, 8, 6, 17, tzinfo=UTC)
    queue, ledger = ledger_with_manual_canary(morning_time)

    first = prepare_scheduled(queue, ledger, now=morning_time, slot="morning", run_id="morning-run")
    assert first.envelope is not None
    entry = ledger.entries[first.envelope.publication_id]
    mark_published(
        entry,
        attempted_at=morning_time,
        published_at=morning_time + timedelta(minutes=1),
        mode="scheduled",
        scheduled_slot="morning",
        message_id=1502,
    )

    duplicate = prepare_scheduled(
        queue,
        ledger,
        now=morning_time + timedelta(hours=2),
        slot="morning",
        run_id="duplicate-morning",
    )
    assert duplicate.envelope is None
    assert "slot morning is already verified" in duplicate.reason


def test_failed_morning_is_not_backfilled_with_two_evening_dispatches() -> None:
    morning_time = datetime(2026, 9, 11, 6, 17, tzinfo=UTC)
    evening_time = datetime(2026, 9, 11, 18, 17, tzinfo=UTC)
    queue, ledger = ledger_with_manual_canary(morning_time)

    morning = prepare_scheduled(queue, ledger, now=morning_time, slot="morning", run_id="morning-run")
    assert morning.envelope is not None
    failed_id = morning.envelope.publication_id
    resolve_entry(
        ledger,
        failed_id,
        resolution="confirmed_absent",
        evidence_note="Provider mutation was proven absent before send, so the morning slot produced no Telegram post.",
        resolved_by="test-suite",
        now=morning_time + timedelta(minutes=2),
    )

    evening = prepare_scheduled(queue, ledger, now=evening_time, slot="evening", run_id="evening-run")
    assert evening.envelope is not None
    assert evening.envelope.publication_id == failed_id
    assert evening.envelope.scheduled_slot == "evening"
    dispatching = [entry for entry in ledger.entries.values() if entry.state == "dispatching"]
    assert len(dispatching) == 1


def test_manual_publication_today_closes_scheduled_slots_for_that_day() -> None:
    now = datetime(2026, 9, 8, 6, 17, tzinfo=UTC)
    queue = load_queue(QUEUE_PATH)
    ledger = initialize_ledger(queue)
    mark_published(
        ledger.entries[queue.posts[0].publication_id],
        attempted_at=now - timedelta(minutes=1),
        published_at=now,
        mode="manual",
        message_id=1503,
    )

    scheduled = prepare_scheduled(queue, ledger, now=now + timedelta(hours=12), slot="evening", run_id="evening-run")
    assert scheduled.envelope is None
    assert "manual publication already verified" in scheduled.reason


def test_legacy_scheduled_publication_without_slot_closes_transition_day() -> None:
    now = datetime(2026, 9, 8, 6, 17, tzinfo=UTC)
    queue, ledger = ledger_with_manual_canary(now)
    mark_published(
        ledger.entries[queue.posts[1].publication_id],
        attempted_at=now - timedelta(minutes=1),
        published_at=now,
        mode="scheduled",
        scheduled_slot=None,
        message_id=1504,
    )

    result = prepare_scheduled(queue, ledger, now=now + timedelta(hours=12), slot="evening", run_id="transition-run")
    assert result.envelope is None
    assert "legacy scheduled publication" in result.reason
    assert "transition day is closed" in result.reason


def test_old_ledger_payload_without_scheduled_slot_remains_loadable() -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = initialize_ledger(queue)
    payload = ledger.model_dump(mode="json")
    for entry in payload["entries"].values():
        entry.pop("scheduled_slot", None)

    restored = TelegramLedger.model_validate(payload)
    assert all(entry.scheduled_slot is None for entry in restored.entries.values())


def test_persisted_intent_verification_binds_the_scheduled_slot() -> None:
    now = datetime(2026, 9, 8, 6, 17, tzinfo=UTC)
    queue, ledger = ledger_with_manual_canary(now)
    prepared = prepare_scheduled(queue, ledger, now=now, slot="morning", run_id="slot-bind-run")
    assert prepared.envelope is not None
    verify_persisted_intent(queue, ledger, prepared.envelope)

    tampered = prepared.envelope.model_copy(update={"scheduled_slot": "evening"})
    with pytest.raises(ValueError, match="scheduled slot"):
        verify_persisted_intent(queue, ledger, tampered)
