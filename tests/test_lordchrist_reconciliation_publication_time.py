from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from video_channel_manager.telegram_cli import main as telegram_cli_main
from video_channel_manager.telegram_publisher import (
    TargetProof,
    initialize_ledger,
    load_queue,
    prepare_next,
    resolve_entry,
    save_ledger,
)

ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = ROOT / "content/telegram/lordchrist/verified-30-posts.json"
GITHUB_SHA = "a" * 40
WORKFLOW_SHA = "b" * 40


def _target(*, checked_at: datetime) -> TargetProof:
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
        checked_at_utc=checked_at,
    )


def _unresolved_dispatch(*, attempted_at: datetime):
    queue = load_queue(QUEUE_PATH)
    ledger = initialize_ledger(queue)
    prepared = prepare_next(
        queue,
        ledger,
        run_id="12345",
        run_attempt="1",
        github_sha=GITHUB_SHA,
        github_workflow_sha=WORKFLOW_SHA,
        mode="manual",
        target=_target(checked_at=attempted_at),
        expected_publication_id=queue.posts[0].publication_id,
        now=attempted_at,
    )
    assert prepared.envelope is not None
    entry = ledger.entries[prepared.envelope.publication_id]
    entry.state = "unknown"
    return queue, ledger, prepared.envelope.publication_id


def test_cross_day_confirmed_published_requires_explicit_provider_publication_time() -> None:
    attempted_at = datetime(2026, 8, 8, 17, 0, tzinfo=UTC)
    resolved_at = datetime(2026, 8, 9, 6, 0, tzinfo=UTC)
    _, ledger, publication_id = _unresolved_dispatch(attempted_at=attempted_at)

    with pytest.raises(ValueError, match="explicit evidence-backed published_at_utc"):
        resolve_entry(
            ledger,
            publication_id,
            resolution="confirmed_published",
            evidence_note="Exact Telegram message was found and its target and text were verified.",
            resolved_by="operator",
            message_id=777,
            expected_chat_id=-1001234567890,
            now=resolved_at,
        )


def test_reconciliation_preserves_actual_previous_day_for_daily_limit() -> None:
    attempted_at = datetime(2026, 8, 8, 17, 0, tzinfo=UTC)
    published_at = datetime(2026, 8, 8, 17, 1, tzinfo=UTC)
    resolved_at = datetime(2026, 8, 9, 6, 0, tzinfo=UTC)
    queue, ledger, publication_id = _unresolved_dispatch(attempted_at=attempted_at)

    entry = resolve_entry(
        ledger,
        publication_id,
        resolution="confirmed_published",
        evidence_note="Exact Telegram message was found and its target, text, and timestamp were verified.",
        resolved_by="operator",
        message_id=777,
        expected_chat_id=-1001234567890,
        published_at_utc=published_at,
        now=resolved_at,
    )

    assert entry.published_at_utc == published_at
    assert entry.resolved_at_utc == resolved_at

    today = datetime(2026, 8, 9, 9, 0, tzinfo=UTC)
    next_dispatch = prepare_next(
        queue,
        ledger,
        run_id="67890",
        run_attempt="1",
        github_sha=GITHUB_SHA,
        github_workflow_sha=WORKFLOW_SHA,
        mode="manual",
        target=_target(checked_at=today),
        expected_publication_id=queue.posts[1].publication_id,
        now=today,
    )
    assert next_dispatch.envelope is not None
    assert next_dispatch.envelope.publication_id == queue.posts[1].publication_id


def test_confirmed_publication_time_is_bounded_by_attempt_and_reconciliation() -> None:
    attempted_at = datetime(2026, 8, 8, 17, 0, tzinfo=UTC)
    resolved_at = datetime(2026, 8, 8, 18, 0, tzinfo=UTC)

    for invalid_time, message in (
        (datetime(2026, 8, 8, 16, 59, tzinfo=UTC), "cannot precede"),
        (datetime(2026, 8, 8, 18, 1, tzinfo=UTC), "cannot be later"),
    ):
        _, ledger, publication_id = _unresolved_dispatch(attempted_at=attempted_at)
        with pytest.raises(ValueError, match=message):
            resolve_entry(
                ledger,
                publication_id,
                resolution="confirmed_published",
                evidence_note="Exact Telegram message timestamp was independently verified by the operator.",
                resolved_by="operator",
                message_id=777,
                expected_chat_id=-1001234567890,
                published_at_utc=invalid_time,
                now=resolved_at,
            )

    _, ledger, publication_id = _unresolved_dispatch(attempted_at=attempted_at)
    with pytest.raises(ValueError, match="timezone-aware"):
        resolve_entry(
            ledger,
            publication_id,
            resolution="confirmed_published",
            evidence_note="Exact Telegram message timestamp was independently verified by the operator.",
            resolved_by="operator",
            message_id=777,
            expected_chat_id=-1001234567890,
            published_at_utc=datetime(2026, 8, 8, 17, 1),
            now=resolved_at,
        )


def test_cli_refuses_confirmed_published_without_exact_publication_timestamp(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    attempted_at = datetime(2026, 8, 8, 17, 0, tzinfo=UTC)
    _, ledger, publication_id = _unresolved_dispatch(attempted_at=attempted_at)
    ledger_path = tmp_path / "ledger.json"
    save_ledger(ledger_path, ledger)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "telegram_cli",
            "--queue",
            str(QUEUE_PATH),
            "--ledger",
            str(ledger_path),
            "resolve",
            "--publication-id",
            publication_id,
            "--resolution",
            "confirmed_published",
            "--evidence-note",
            "Exact Telegram message was found and its target and text were verified.",
            "--resolved-by",
            "operator",
            "--message-id",
            "777",
            "--expected-chat-id",
            "-1001234567890",
        ],
    )

    with pytest.raises(RuntimeError, match="requires exact --published-at-utc"):
        telegram_cli_main()
