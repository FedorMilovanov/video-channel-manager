from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from video_channel_manager.telegram_models import TargetProof, TelegramLedger
from video_channel_manager.telegram_state import initialize_ledger, load_queue, prepare_next, resolve_entry
from video_channel_manager.telegram_transport import MUTATION_TRANSPORT_RETRIES, READ_ONLY_TRANSPORT_RETRIES


ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = ROOT / "content/telegram/lordchrist/verified-30-posts.json"
NOW = datetime(2026, 8, 7, 9, 0, tzinfo=UTC)
CHAT_ID = -1001234567890
BOT_ID = 424242


def target() -> TargetProof:
    return TargetProof(
        schema_name="video-channel-manager.telegram-target-proof",
        schema_version=2,
        bot_id=BOT_ID,
        bot_username="lordchrist_publisher_bot",
        chat_id=CHAT_ID,
        chat_username="lordchrist",
        chat_title="Господь Бог — Сила Моя",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=NOW,
    )


def prepare_one():
    queue = load_queue(QUEUE_PATH)
    ledger = initialize_ledger(queue)
    prepared = prepare_next(
        queue,
        ledger,
        run_id="123",
        run_attempt="1",
        github_sha="a" * 40,
        github_workflow_sha="b" * 40,
        mode="manual",
        target=target(),
        expected_publication_id=queue.posts[0].publication_id,
        now=NOW,
    )
    assert prepared.envelope is not None
    return queue, ledger, prepared.envelope


def test_unknown_provider_effect_cannot_be_erased_by_skip() -> None:
    _, ledger, envelope = prepare_one()
    entry = ledger.entries[envelope.publication_id]
    entry.state = "unknown"

    with pytest.raises(ValueError, match="skip is forbidden"):
        resolve_entry(
            ledger,
            envelope.publication_id,
            resolution="skip",
            evidence_note="Неизвестный результат отправки нельзя превращать в отсутствие сообщения.",
            resolved_by="operator",
            now=NOW,
        )

    assert entry.state == "unknown"
    assert entry.provider_effect == "may_exist"
    assert entry.intent_id == envelope.intent_id


def test_confirmed_published_requires_an_unresolved_may_exist_dispatch() -> None:
    _, ledger, envelope = prepare_one()
    entry = ledger.entries[envelope.publication_id]
    entry.state = "failed"
    entry.provider_effect = "confirmed_absent"
    entry.intent_id = None

    with pytest.raises(ValueError, match="only for an unresolved may_exist"):
        resolve_entry(
            ledger,
            envelope.publication_id,
            resolution="confirmed_published",
            evidence_note="Telegram ранее доказал отсутствие provider effect для этой попытки.",
            resolved_by="operator",
            message_id=777,
            expected_chat_id=CHAT_ID,
            now=NOW,
        )


def test_unknown_can_be_reconciled_to_exact_canonical_published_evidence() -> None:
    _, ledger, envelope = prepare_one()
    entry = ledger.entries[envelope.publication_id]
    entry.state = "unknown"

    resolved = resolve_entry(
        ledger,
        envelope.publication_id,
        resolution="confirmed_published",
        evidence_note="Публичное сообщение открыто и exact message_id сверен с неизменным текстом очереди.",
        resolved_by="operator",
        message_id=777,
        expected_chat_id=CHAT_ID,
        now=NOW,
    )
    validated = TelegramLedger.model_validate(ledger.model_dump(mode="json"))

    assert resolved.state == "published"
    assert resolved.provider_effect == "verified"
    assert resolved.message_url == "https://t.me/lordchrist/777"
    assert validated.entries[envelope.publication_id].message_id == 777


def test_published_state_rejects_noncanonical_message_url() -> None:
    _, ledger, envelope = prepare_one()
    entry = ledger.entries[envelope.publication_id]
    entry.state = "unknown"
    resolve_entry(
        ledger,
        envelope.publication_id,
        resolution="confirmed_published",
        evidence_note="Публичное сообщение открыто и exact message_id сверен с неизменным текстом очереди.",
        resolved_by="operator",
        message_id=777,
        expected_chat_id=CHAT_ID,
        now=NOW,
    )
    entry.message_url = "https://t.me/wrong/777"

    with pytest.raises(ValidationError, match="canonical public message URL"):
        TelegramLedger.model_validate(ledger.model_dump(mode="json"))


def test_scheduled_rerun_cannot_select_or_advance_the_queue() -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = initialize_ledger(queue)
    blocked = prepare_next(
        queue,
        ledger,
        run_id="scheduled-run",
        run_attempt="2",
        github_sha="a" * 40,
        github_workflow_sha="b" * 40,
        mode="scheduled",
        target=target(),
        now=NOW,
    )

    assert blocked.envelope is None
    assert "scheduled workflow re-runs are forbidden" in blocked.reason
    assert all(entry.state == "pending" for entry in ledger.entries.values())
    assert all(entry.intent_id is None for entry in ledger.entries.values())


def test_transport_retry_policy_is_read_only_only() -> None:
    assert READ_ONLY_TRANSPORT_RETRIES == 2
    assert MUTATION_TRANSPORT_RETRIES == 0
