from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from video_channel_manager import milovi_telegram_bootstrap_rollout as rollout

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/telegram-milovi-bootstrap-rollout.yml"


def test_without_exact_approval_plan_is_provider_inert(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rollout, "APPROVAL_PATH", ROOT / "definitely-missing-milovi-approval.json")
    plan = rollout.evaluate_plan(datetime(2026, 8, 16, 10, 30, tzinfo=timezone(timedelta(hours=3))))
    assert plan == {"execute": False, "reason": "approval_missing", "provider_access_allowed": False}


def test_quiet_hours_block_before_provider_access(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rollout, "_approval", lambda: {"provider_mutation_allowed": True})
    monkeypatch.setattr(
        rollout,
        "_frozen_data",
        lambda: (
            {},
            [{"sequence": 1, "publication_id": "milovi-bootstrap-001", "operation": "sendPhoto", "planned_local": "2026-08-16T10:30:00+03:00"}],
            {},
            {},
        ),
    )
    monkeypatch.setattr(rollout, "_state", lambda: None)
    plan = rollout.evaluate_plan(datetime(2026, 8, 16, 4, 0, tzinfo=timezone(timedelta(hours=3))))
    assert plan["execute"] is False
    assert plan["reason"] == "quiet_hours"
    assert plan["provider_access_allowed"] is False


def test_due_slot_allows_only_strict_next(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rollout, "_approval", lambda: {"provider_mutation_allowed": True})
    items = [
        {"sequence": 1, "publication_id": "milovi-bootstrap-001", "operation": "sendPhoto", "planned_local": "2026-08-16T10:30:00+03:00"},
        {"sequence": 2, "publication_id": "milovi-bootstrap-002", "operation": "sendPhoto", "planned_local": "2026-08-16T20:00:00+03:00"},
    ]
    monkeypatch.setattr(rollout, "_frozen_data", lambda: ({}, items, {}, {}))
    monkeypatch.setattr(rollout, "_state", lambda: None)
    plan = rollout.evaluate_plan(datetime(2026, 8, 16, 10, 31, tzinfo=timezone(timedelta(hours=3))))
    assert plan["execute"] is True
    assert plan["sequence"] == 1
    assert plan["publication_id"] == "milovi-bootstrap-001"


def test_unresolved_dispatch_blocks_successor() -> None:
    state = {
        "items": [
            {
                "sequence": 1,
                "status": "dispatch_started",
                "message_id": None,
            }
        ]
    }
    with pytest.raises(SystemExit, match="blocked by unresolved item 1"):
        rollout._next_sequence(state)


def test_verified_receipts_advance_exactly_one_sequence() -> None:
    state = {
        "items": [
            {"sequence": 1, "status": "verified", "message_id": 101},
            {"sequence": 2, "status": "verified", "message_id": 102},
        ]
    }
    assert rollout._next_sequence(state) == 3


def test_workflow_provider_path_is_schedule_only_and_daylight_cron() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'cron: "30 7 * * *"' in text
    assert 'cron: "0 17 * * *"' in text
    assert "github.event_name == 'schedule'" in text
    assert "workflow_dispatch" in text
    assert "milovi-telegram-publisher" in text
    assert "cancel-in-progress: false" in text
    assert "persist-credentials: false" in text
    assert "Persist strict-next dispatch-started barrier before provider mutation" in text
    assert "Dispatch one exact strict-next Telegram item with zero retry" in text
    assert "LORDCHRIST_TELEGRAM_BOT_TOKEN" in text
    assert "rerun forbidden" in (ROOT / "src/video_channel_manager/milovi_telegram_bootstrap_rollout.py").read_text(encoding="utf-8")
