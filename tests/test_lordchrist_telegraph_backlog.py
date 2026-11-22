"""Read-only guarantees for the @lordchrist release backlog planner."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from scripts import lordchrist_telegraph_backlog as backlog


def _write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    queue = _write(
        tmp_path / "queue.json",
        {
            "items": [
                {"publication_id": "a-old", "status": "ready", "scheduled_on_moscow": "2026-11-10"},
                {"publication_id": "b-held", "status": "ready", "scheduled_on_moscow": "2026-11-12"},
                {"publication_id": "c-done", "status": "ready", "scheduled_on_moscow": "2026-11-14"},
                {"publication_id": "d-undated", "status": "ready"},
                {"publication_id": "e-calendar-old", "status": "ready", "scheduled_on_moscow": "2026-11-11"},
                {"publication_id": "f-calendar-next", "status": "ready", "scheduled_on_moscow": "2026-11-24"},
                {"publication_id": "g-canary", "status": "ready", "is_canary": True},
            ]
        },
    )
    ledger = _write(
        tmp_path / "ledger.json",
        {
            "entries": {
                "c-done": {"telegram_message_id": 1, "telegraph_path": "p"},
                # a deleted message still sits in the ledger as "published"
                "e-calendar-old": {"telegram_message_id": 1596, "telegraph_path": "p2"},
                "f-calendar-next": {"telegram_message_id": 1600, "telegraph_path": "p3"},
            }
        },
    )
    manifest = _write(
        tmp_path / "manifest.json",
        {
            "items": [
                {
                    "publication_id": "e-calendar-old",
                    "scheduled_on_moscow": "2026-11-11",
                    "deleted_telegram_message_id": 1596,
                },
                {
                    "publication_id": "f-calendar-next",
                    "scheduled_on_moscow": "2026-11-24",
                    "deleted_telegram_message_id": 1600,
                },
            ]
        },
    )
    return queue, ledger, manifest


def _plan(tmp_path: Path, *, today: str = "2026-11-21", gap: int = 3, priority=()) -> dict:
    queue, ledger, manifest = _fixture(tmp_path)
    return backlog.build_plan(
        queue_path=queue,
        ledger_path=ledger,
        manifest_path=manifest,
        today=date.fromisoformat(today),
        start=date.fromisoformat(today) + timedelta(days=1),
        gap_days=gap,
        priority=priority,
        holds=frozenset({"b-held"} | set(backlog.EDITORIAL_HOLDS)),
    )


def test_calendar_owner_wins_over_ledger_evidence(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    calendar_ids = [record["publication_id"] for record in plan["calendar_owned"]]
    assert calendar_ids == ["e-calendar-old", "f-calendar-next"]
    assert plan["calendar_owned"][0]["deleted_telegram_message_id"] == 1596
    assert plan["calendar_owned"][0]["calendar_overdue_days"] == 10
    published_ids = [record["publication_id"] for record in plan["published"]]
    assert published_ids == ["c-done"]


def test_overdue_and_undated_are_separated(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    assert [record["publication_id"] for record in plan["overdue"]] == ["a-old", "b-held"]
    assert [record["publication_id"] for record in plan["undated"]] == ["d-undated", "g-canary"]


def test_proposal_keeps_one_article_per_day_and_skips_pinned_dates(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    slots = plan["proposal"]
    dates = [date.fromisoformat(slot["proposed_date"]) for slot in slots]
    assert dates == sorted(dates)
    for earlier, later in zip(dates, dates[1:], strict=False):
        assert (later - earlier).days >= plan["gap_days"]
    assert date(2026, 11, 24) not in dates  # pinned by the reviewed calendar
    assert "b-held" not in [slot["publication_id"] for slot in slots]
    assert "g-canary" not in [slot["publication_id"] for slot in slots]


def test_every_waiting_item_gets_exactly_one_slot(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    proposed = [slot["publication_id"] for slot in plan["proposal"]]
    assert sorted(proposed) == ["a-old", "d-undated", "e-calendar-old"]


def test_priority_pulls_an_item_to_the_first_slot(tmp_path: Path) -> None:
    plan = _plan(tmp_path, priority=("e-calendar-old",))
    assert plan["proposal"][0]["publication_id"] == "e-calendar-old"


def test_render_states_that_it_is_read_only(tmp_path: Path) -> None:
    text = backlog.render(_plan(tmp_path))
    assert "ПРОСРОЧЕНО" in text
    assert "Только чтение" in text
    assert "удалённое сообщение 1596" in text


def test_real_repository_queue_is_classified_without_provider_access(tmp_path: Path) -> None:
    plan = backlog.build_plan(
        queue_path=backlog.ROOT / backlog.QUEUE_PATH,
        ledger_path=tmp_path / "absent-ledger.json",
        manifest_path=backlog.ROOT / backlog.MANIFEST_PATH,
        today=date(2026, 11, 21),
        start=date(2026, 11, 22),
        gap_days=3,
    )
    assert plan["read_only"] is True
    assert plan["counts"]["calendar_owned"] == 8
    assert {slot["proposed_date"] for slot in plan["proposal"]}
    assert plan["editorial_holds"] == ["lordchrist-telegraph-charnock-13"]
