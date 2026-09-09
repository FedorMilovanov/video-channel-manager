from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from video_channel_manager.telegram_models import LedgerEntry, TargetProof
from video_channel_manager.telegram_presentation import load_presentation_policy
from video_channel_manager.telegram_publisher import load_ledger
from video_channel_manager.telegram_quote_runtime import (
    SuccessorRuntimeQueue,
    build_successor_runtime_queue,
    initialize_successor_ledger,
    predecessor_is_complete,
    prepare_with_history,
    resolve_active_quote_release,
)
from video_channel_manager.telegram_schedule import (
    decide_scheduled_slot,
    load_production_schedule,
    require_release_binding,
)
from video_channel_manager.telegram_state import initialize_ledger, load_queue, prepare_next, save_ledger

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content/telegram/lordchrist"
PREDECESSOR_QUEUE = CONTENT / "verified-30-posts.json"
CANDIDATE = CONTENT / "successor-quotes-v1.json"
TRANSLATION = CONTENT / "successor-translation-ledger-v1.json"
AMENDMENTS = CONTENT / "successor-integrity-amendments-v1.json"
RELEASE = CONTENT / "successor-release-v2.json"
ACTIVATION = CONTENT / "successor-activation-v1.json"
POLICY = CONTENT / "presentation-policy.json"
SCHEDULE = CONTENT / "production-schedule.json"
CHAT_ID = -1001295216957
BOT_ID = 8716602202
BOT_USERNAME = "preaching_mp3_bot"
SUCCESSOR_DIGEST = "sha256:6c9835793785570311108eec21fd1468aa83e0c45cf63eb554d0f6b9cb7d0873"


def _build_runtime() -> SuccessorRuntimeQueue:
    policy = load_presentation_policy(POLICY)
    return build_successor_runtime_queue(
        candidate_path=CANDIDATE,
        translation_ledger_path=TRANSLATION,
        integrity_amendment_path=AMENDMENTS,
        release_path=RELEASE,
        activation_path=ACTIVATION,
        expected_chat_id=CHAT_ID,
        expected_bot_id=BOT_ID,
        expected_bot_username=BOT_USERNAME,
        presentation_policy_id=policy.policy_id,
        presentation_policy_sha256=policy.digest,
    )


def _write_ledger(path: Path, ledger: object) -> None:
    path.write_text(ledger.model_dump_json(indent=2) + "\n", encoding="utf-8")  # type: ignore[attr-defined]


def test_delayed_morning_schedule_remains_same_day_eligible() -> None:
    schedule = load_production_schedule(SCHEDULE)
    # 14:19 Moscow: this reproduces the September 9 delayed GitHub delivery that
    # used to green-skip under the old two-hour window.
    decision = decide_scheduled_slot(
        schedule,
        event_schedule="17 9 * * *",
        now=datetime(2026, 9, 9, 11, 19, tzinfo=UTC),
    )
    assert decision.active is True
    assert decision.slot == "morning"

    # The same morning event is not allowed to spill across the 21:17 boundary.
    expired = decide_scheduled_slot(
        schedule,
        event_schedule="17 9 * * *",
        now=datetime(2026, 9, 9, 18, 17, tzinfo=UTC),
    )
    assert expired.active is False
    assert "too stale" in expired.reason


def test_evening_schedule_expires_before_moscow_midnight() -> None:
    schedule = load_production_schedule(SCHEDULE)
    active = decide_scheduled_slot(
        schedule,
        event_schedule="17 21 * * 2,5,0",
        now=datetime(2026, 9, 8, 20, 56, tzinfo=UTC),  # 23:56 Moscow, Tuesday
    )
    assert active.active is True
    assert active.slot == "evening"

    expired = decide_scheduled_slot(
        schedule,
        event_schedule="17 21 * * 2,5,0",
        now=datetime(2026, 9, 8, 20, 57, tzinfo=UTC),
    )
    assert expired.active is False


def test_schedule_release_binding_accepts_only_predecessor_or_armed_successor() -> None:
    schedule = load_production_schedule(SCHEDULE)
    policy = load_presentation_policy(POLICY)
    for digest in (schedule.queue_digest, schedule.successor_queue_digest):
        require_release_binding(
            schedule,
            queue_digest=digest,
            chat_id=CHAT_ID,
            bot_id=BOT_ID,
            bot_username=BOT_USERNAME,
            presentation_policy_id=policy.policy_id,
            presentation_policy_sha256=policy.digest,
        )
    with pytest.raises(ValueError, match="approved quote release"):
        require_release_binding(
            schedule,
            queue_digest="sha256:" + "0" * 64,
            chat_id=CHAT_ID,
            bot_id=BOT_ID,
            bot_username=BOT_USERNAME,
            presentation_policy_id=policy.policy_id,
            presentation_policy_sha256=policy.digest,
        )


def test_real_reviewed_successor_materializes_exactly_sixty_bound_cards() -> None:
    queue = _build_runtime()
    assert len(queue.posts) == 60
    assert queue.digest == SUCCESSOR_DIGEST
    assert [post.sequence for post in queue.posts] == list(range(1, 61))
    assert all(post.payload_sha256.startswith("sha256:") for post in queue.posts)
    assert all("\n\n#" in post.text for post in queue.posts)
    assert all(post.source.author and post.source.work for post in queue.posts)


def test_successor_activation_digest_mismatch_fails_closed(tmp_path: Path) -> None:
    payload = json.loads(ACTIVATION.read_text(encoding="utf-8"))
    payload["successor_queue_digest"] = "sha256:" + "0" * 64
    activation = tmp_path / "activation.json"
    activation.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    policy = load_presentation_policy(POLICY)
    with pytest.raises(ValueError, match="queue digest differs"):
        build_successor_runtime_queue(
            candidate_path=CANDIDATE,
            translation_ledger_path=TRANSLATION,
            integrity_amendment_path=AMENDMENTS,
            release_path=RELEASE,
            activation_path=activation,
            expected_chat_id=CHAT_ID,
            expected_bot_id=BOT_ID,
            expected_bot_username=BOT_USERNAME,
            presentation_policy_id=policy.policy_id,
            presentation_policy_sha256=policy.digest,
        )


def test_handoff_waits_for_exact_predecessor_terminal_state(tmp_path: Path) -> None:
    predecessor = load_queue(PREDECESSOR_QUEUE)
    ledger = initialize_ledger(predecessor)
    ledger_path = tmp_path / "predecessor-ledger.json"
    _write_ledger(ledger_path, ledger)
    policy = load_presentation_policy(POLICY)

    selection = resolve_active_quote_release(
        predecessor_queue_path=PREDECESSOR_QUEUE,
        predecessor_ledger_path=ledger_path,
        candidate_path=CANDIDATE,
        translation_ledger_path=TRANSLATION,
        integrity_amendment_path=AMENDMENTS,
        release_path=RELEASE,
        activation_path=ACTIVATION,
        runtime_queue_path=tmp_path / "runtime.json",
        successor_ledger_path=tmp_path / "successor-ledger.json",
        expected_chat_id=CHAT_ID,
        expected_bot_id=BOT_ID,
        expected_bot_username=BOT_USERNAME,
        presentation_policy_id=policy.policy_id,
        presentation_policy_sha256=policy.digest,
    )
    assert selection.active_release == "predecessor"
    assert selection.predecessor_complete is False

    for entry in ledger.entries.values():
        entry.state = "skipped"
        entry.provider_effect = "impossible"
    _write_ledger(ledger_path, ledger)

    selection = resolve_active_quote_release(
        predecessor_queue_path=PREDECESSOR_QUEUE,
        predecessor_ledger_path=ledger_path,
        candidate_path=CANDIDATE,
        translation_ledger_path=TRANSLATION,
        integrity_amendment_path=AMENDMENTS,
        release_path=RELEASE,
        activation_path=ACTIVATION,
        runtime_queue_path=tmp_path / "runtime.json",
        successor_ledger_path=tmp_path / "successor-ledger.json",
        expected_chat_id=CHAT_ID,
        expected_bot_id=BOT_ID,
        expected_bot_username=BOT_USERNAME,
        presentation_policy_id=policy.policy_id,
        presentation_policy_sha256=policy.digest,
    )
    assert selection.active_release == "successor"
    assert selection.predecessor_complete is True
    assert selection.needs_ledger_initialization is True
    assert selection.queue_digest == SUCCESSOR_DIGEST


def test_nonterminal_failed_predecessor_blocks_handoff() -> None:
    predecessor = load_queue(PREDECESSOR_QUEUE)
    ledger = initialize_ledger(predecessor)
    first = predecessor.posts[0]
    ledger.entries[first.publication_id] = LedgerEntry(
        publication_id=first.publication_id,
        payload_sha256=first.payload_sha256,
        state="failed",
        provider_effect="not_dispatched",
    )
    with pytest.raises(ValueError, match="cannot hand off"):
        predecessor_is_complete(predecessor, ledger)


def test_successor_ledger_is_distinct_and_history_supplies_verified_canary(tmp_path: Path) -> None:
    predecessor = load_queue(PREDECESSOR_QUEUE)
    history = initialize_ledger(predecessor)
    canary_post = predecessor.posts[0]
    attempted = datetime(2026, 9, 8, 7, 0, tzinfo=UTC)
    history.entries[canary_post.publication_id] = LedgerEntry(
        publication_id=canary_post.publication_id,
        payload_sha256=canary_post.payload_sha256,
        state="published",
        provider_effect="verified",
        intent_id="a" * 32,
        dispatch_mode="manual",
        workflow_run_id="1",
        workflow_run_attempt="1",
        github_sha="a" * 40,
        github_workflow_sha="b" * 40,
        attempted_at_utc=attempted,
        published_at_utc=attempted + timedelta(seconds=5),
        message_id=1470,
        message_url="https://t.me/lordchrist/1470",
        actual_chat_id=CHAT_ID,
        actual_chat_username="lordchrist",
        bot_id=BOT_ID,
        bot_username=BOT_USERNAME,
    )

    runtime_path = tmp_path / "runtime.json"
    runtime = _build_runtime()
    runtime_path.write_text(runtime.model_dump_json(indent=2) + "\n", encoding="utf-8")
    successor_path = tmp_path / "successor-ledger.json"
    successor = initialize_successor_ledger(successor_path, runtime_path)
    assert set(successor.entries).isdisjoint(history.entries)

    now = datetime(2026, 9, 9, 9, 30, tzinfo=UTC)
    target = TargetProof(
        schema_name="video-channel-manager.telegram-target-proof",
        schema_version=2,
        bot_id=BOT_ID,
        bot_username=BOT_USERNAME,
        chat_id=CHAT_ID,
        chat_username="lordchrist",
        chat_title="Господь Бог — Сила моя",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=now,
    )
    prepared = prepare_with_history(
        runtime,
        successor,
        history,
        prepare_next,
        run_id="999",
        run_attempt="1",
        github_sha="c" * 40,
        github_workflow_sha="d" * 40,
        mode="scheduled",
        target=target,
        scheduled_slot="morning",
        now=now,
    )
    assert prepared.envelope is not None
    assert prepared.envelope.publication_id.startswith("lordchrist-successor-")
    assert successor.entries[prepared.envelope.publication_id].state == "dispatching"
    assert all(key.startswith("lordchrist-successor-") for key in successor.entries)
