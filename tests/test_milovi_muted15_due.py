from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from scripts import milovi_muted15_due as due


def test_every_approved_muted_release_has_exact_date_source_and_owner_scope() -> None:
    rows = due.reviewed_items()
    assert len(rows) == 15
    assert rows[0]["publication_id"] == due.EXACT_FIRST
    assert rows[-1]["publication_id"] == due.EXACT_LAST
    assert len({row["sha256"] for row in rows}) == 15


def test_due_dates_one_each_day_and_absolute_year_gate() -> None:
    rows = due.reviewed_items()
    tz = ZoneInfo("Europe/Moscow")
    for day in range(8, 23):
        start = datetime(2026, 11, day, 19, 0, tzinfo=tz)
        assert due.due_row(start + timedelta(minutes=7), rows)["publication_id"] == (
            f"milovi-feed-202611{day:02d}-001"
        )
        assert due.due_row(start - timedelta(seconds=1), rows) is None
        assert due.due_row(start + timedelta(hours=2), rows) is None
    for wrong in (
        datetime(2026, 11, 7, 19, 7, tzinfo=tz),
        datetime(2026, 11, 23, 19, 7, tzinfo=tz),
        datetime(2027, 11, 8, 19, 7, tzinfo=tz),
    ):
        assert due.due_row(wrong, rows) is None


def test_refuses_clock_without_timezone() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        due.due_row(datetime(2026, 11, 8, 19, 7), due.reviewed_items())


def test_provider_inert_schedule_requires_actual_publishable_protected_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = due.reviewed_items()[0]
    pid = row["publication_id"]
    state_file = tmp_path / "content/telegram/milovi-cake/feed" / (pid + ".json")
    state_file.parent.mkdir(parents=True)
    data = {"entries": {pid: {
        "state": "pending", "provider_effect": "impossible",
        "intent_id": None, "message_id": None,
    }}}
    state_file.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(
        due, "state_check",
        lambda name, *, state_checkout, require_publishable=False: {
            "valid": True, "state": "pending", "provider_effect": "impossible"
        },
    )
    assert due.exact_state_decision(row, checkout=tmp_path) is True
    data["entries"][pid]["intent_id"] = "already-attempted"
    state_file.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="unresolved provider intent"):
        due.exact_state_decision(row, checkout=tmp_path)


def test_terminal_receipt_is_never_dispatched_twice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = due.reviewed_items()[0]
    pid = row["publication_id"]
    state_file = tmp_path / "content/telegram/milovi-cake/feed" / (pid + ".json")
    state_file.parent.mkdir(parents=True)
    state_file.write_text(json.dumps({"entries": {pid: {
        "state": "published", "provider_effect": "verified",
        "message_id": 32, "message_url": "https://t.me/MiloviCake/32",
    }}}), encoding="utf-8")
    monkeypatch.setattr(
        due, "state_check",
        lambda name, *, state_checkout, require_publishable=False: {
            "valid": True, "state": "published", "provider_effect": "verified"
        },
    )
    assert due.exact_state_decision(row, checkout=tmp_path) is False


def test_unknown_result_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    row = due.reviewed_items()[0]
    pid = row["publication_id"]
    file = tmp_path / "content/telegram/milovi-cake/feed" / (pid + ".json")
    file.parent.mkdir(parents=True)
    file.write_text(json.dumps({"entries": {pid: {
        "state": "unknown", "provider_effect": "may_exist",
    }}}), encoding="utf-8")
    monkeypatch.setattr(
        due, "state_check",
        lambda name, *, state_checkout, require_publishable=False: {
            "valid": True, "state": "unknown", "provider_effect": "may_exist"
        },
    )
    with pytest.raises(ValueError, match="unresolved"):
        due.exact_state_decision(row, checkout=tmp_path)


def test_workflow_serializes_shared_state_and_does_not_send_directly() -> None:
    src = Path(".github/workflows/milovi-telegram-muted15-due-20261108.yml").read_text(
        encoding="utf-8"
    )
    assert "7 16 8-22 11 *" in src
    assert "Milovi Telegram feed quality" in src
    assert "workflow_run" in src
    assert "group: milovi-cake-telegram-publisher" in src
    assert "milovi-telegram-feed-publisher.yml" in src
    assert "initialize-all" in src
    assert "state/milovi-cake-telegram" in src
    assert 'steps.due.outputs.dispatch == ' + "'true'" in src
    assert "operation=publish" in src
    assert "sendVideo" not in src
    assert "MILOVI_CAKE_TELEGRAM_BOT_TOKEN" not in src
