from __future__ import annotations

from datetime import UTC, datetime, timedelta
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


def test_legacy_slotless_scheduled_prepare_cannot_reach_provider_transport() -> None:
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
    assert prepared.envelope.scheduled_slot is None

    provider_called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal provider_called
        provider_called = True
        return httpx.Response(500)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="scheduled provider dispatch requires exact editorial slot"):
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
