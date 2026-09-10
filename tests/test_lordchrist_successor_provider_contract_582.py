from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from video_channel_manager.telegram_lordchrist_outcome import capture_lordchrist_provider_outcome
from video_channel_manager.telegram_models import LedgerEntry, TargetProof
from video_channel_manager.telegram_presentation import load_presentation_policy, render_post
from video_channel_manager.telegram_quote_runtime import (
    build_successor_runtime_queue,
    prepare_with_history,
)
from video_channel_manager.telegram_state import initialize_ledger, load_queue, prepare_next

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content/telegram/lordchrist"
PREDECESSOR_QUEUE = CONTENT / "verified-30-posts.json"
CANDIDATE = CONTENT / "successor-quotes-v1.json"
TRANSLATION = CONTENT / "successor-translation-ledger-v1.json"
AMENDMENTS = CONTENT / "successor-integrity-amendments-v1.json"
RELEASE = CONTENT / "successor-release-v2.json"
ACTIVATION = CONTENT / "successor-activation-v1.json"
POLICY = CONTENT / "presentation-policy.json"
CHAT_ID = -1001295216957
BOT_ID = 8716602202
BOT_USERNAME = "preaching_mp3_bot"


def test_successor_runs_through_existing_render_and_outcome_contract_without_provider_access() -> None:
    policy = load_presentation_policy(POLICY)
    queue = build_successor_runtime_queue(
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
    successor = initialize_ledger(queue)  # type: ignore[arg-type]

    predecessor = load_queue(PREDECESSOR_QUEUE)
    history = initialize_ledger(predecessor)
    canary = predecessor.posts[0]
    canary_attempt = datetime(2026, 9, 8, 7, 0, tzinfo=UTC)
    history.entries[canary.publication_id] = LedgerEntry(
        publication_id=canary.publication_id,
        payload_sha256=canary.payload_sha256,
        state="published",
        provider_effect="verified",
        intent_id="a" * 32,
        dispatch_mode="manual",
        workflow_run_id="1",
        workflow_run_attempt="1",
        github_sha="a" * 40,
        github_workflow_sha="b" * 40,
        attempted_at_utc=canary_attempt,
        published_at_utc=canary_attempt + timedelta(seconds=5),
        message_id=1470,
        message_url="https://t.me/lordchrist/1470",
        actual_chat_id=CHAT_ID,
        actual_chat_username="lordchrist",
        bot_id=BOT_ID,
        bot_username=BOT_USERNAME,
    )

    now = datetime(2026, 9, 10, 9, 30, tzinfo=UTC)
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
        queue,
        successor,
        history,
        prepare_next,
        run_id="582",
        run_attempt="1",
        github_sha="c" * 40,
        github_workflow_sha="d" * 40,
        mode="scheduled",
        target=target,
        scheduled_slot="morning",
        now=now,
    )
    assert prepared.envelope is not None
    envelope = prepared.envelope
    post = next(item for item in queue.posts if item.publication_id == envelope.publication_id)
    rendered = render_post(post, policy)  # type: ignore[arg-type]
    assert rendered.publication_id == envelope.publication_id
    assert rendered.source_payload_sha256 == envelope.payload_sha256
    assert "© " not in rendered.text

    # Model an ambiguous completed provider attempt entirely in memory. This does
    # not call Telegram; it proves the exact successor identity can be archived by
    # the same outcome contract used after a real guarded send.
    entry = successor.entries[envelope.publication_id]
    entry.state = "unknown"
    entry.provider_effect = "may_exist"
    outcome = capture_lordchrist_provider_outcome(
        queue,  # type: ignore[arg-type]
        envelope,
        rendered,
        policy,
        entry,
    )
    assert outcome.publication_id == envelope.publication_id
    assert outcome.entry.state == "unknown"
    assert outcome.entry.provider_effect == "may_exist"
