from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from video_channel_manager.telegram_lordchrist_outcome import (
    apply_lordchrist_provider_outcome,
    capture_lordchrist_provider_outcome,
)
from video_channel_manager.telegram_models import TargetProof
from video_channel_manager.telegram_presentation import load_presentation_policy, render_post
from video_channel_manager.telegram_publisher import load_queue
from video_channel_manager.telegram_state import initialize_ledger, prepare_next

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "content/telegram/lordchrist/verified-30-posts.json"
POLICY = ROOT / "content/telegram/lordchrist/presentation-policy.json"
GITHUB_SHA = "a" * 40
WORKFLOW_SHA = "b" * 40


def _target(now: datetime) -> TargetProof:
    return TargetProof(
        schema_name="video-channel-manager.telegram-target-proof",
        schema_version=2,
        bot_id=8716602202,
        bot_username="preaching_mp3_bot",
        chat_id=-1001295216957,
        chat_username="lordchrist",
        chat_title="Господь Бог — Сила Моя",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=now,
    )


def _prepared_fixture():
    queue = load_queue(QUEUE)
    policy = load_presentation_policy(POLICY)
    ledger = initialize_ledger(queue)
    now = datetime(2026, 8, 9, 6, 17, tzinfo=UTC)
    prepared = prepare_next(
        queue,
        ledger,
        run_id="123456",
        run_attempt="1",
        github_sha=GITHUB_SHA,
        github_workflow_sha=WORKFLOW_SHA,
        mode="manual",
        target=_target(now),
        expected_publication_id=queue.posts[0].publication_id,
        now=now,
    )
    assert prepared.envelope is not None
    assert prepared.post is not None
    rendered = render_post(prepared.post, policy)
    return queue, policy, ledger, prepared.envelope, rendered, now


def test_verified_provider_outcome_round_trips_into_the_exact_durable_intent() -> None:
    queue, policy, live_ledger, envelope, rendered, now = _prepared_fixture()
    persisted_intent = live_ledger.model_copy(deep=True)

    entry = live_ledger.entries[envelope.publication_id]
    entry.state = "published"
    entry.provider_effect = "verified"
    entry.message_id = 1555
    entry.message_url = "https://t.me/lordchrist/1555"
    entry.published_at_utc = now + timedelta(seconds=3)
    entry.last_error = None

    outcome = capture_lordchrist_provider_outcome(queue, envelope, rendered, policy, entry)
    recovered = apply_lordchrist_provider_outcome(
        queue,
        persisted_intent,
        envelope,
        rendered,
        outcome,
    )

    assert recovered.state == "published"
    assert recovered.provider_effect == "verified"
    assert recovered.message_id == 1555
    assert recovered.message_url == "https://t.me/lordchrist/1555"
    assert recovered.published_at_utc == now + timedelta(seconds=3)
    assert persisted_intent.entries[envelope.publication_id] == recovered


def test_proven_no_effect_outcome_can_restore_pending_without_losing_exact_binding() -> None:
    queue, policy, live_ledger, envelope, rendered, _ = _prepared_fixture()
    persisted_intent = live_ledger.model_copy(deep=True)

    entry = live_ledger.entries[envelope.publication_id]
    entry.state = "pending"
    entry.provider_effect = "not_dispatched"
    entry.intent_id = None
    entry.last_error = "Telegram connection failure: ConnectError"

    outcome = capture_lordchrist_provider_outcome(queue, envelope, rendered, policy, entry)
    recovered = apply_lordchrist_provider_outcome(
        queue,
        persisted_intent,
        envelope,
        rendered,
        outcome,
    )

    assert recovered.state == "pending"
    assert recovered.provider_effect == "not_dispatched"
    assert recovered.intent_id is None
    assert recovered.workflow_run_id == envelope.workflow_run_id
    assert recovered.actual_chat_id == envelope.target.chat_id


def test_outcome_from_another_intent_is_rejected_before_state_replacement() -> None:
    queue, policy, live_ledger, envelope, rendered, now = _prepared_fixture()
    persisted_intent = live_ledger.model_copy(deep=True)

    entry = live_ledger.entries[envelope.publication_id]
    entry.state = "published"
    entry.provider_effect = "verified"
    entry.message_id = 1556
    entry.message_url = "https://t.me/lordchrist/1556"
    entry.published_at_utc = now + timedelta(seconds=2)
    outcome = capture_lordchrist_provider_outcome(queue, envelope, rendered, policy, entry)
    wrong = outcome.model_copy(update={"dispatch_intent_id": "f" * 32})

    with pytest.raises(ValueError, match="intent differs"):
        apply_lordchrist_provider_outcome(
            queue,
            persisted_intent,
            envelope,
            rendered,
            wrong,
        )

    blocked = persisted_intent.entries[envelope.publication_id]
    assert blocked.state == "dispatching"
    assert blocked.provider_effect == "may_exist"
    assert blocked.intent_id == envelope.intent_id
