"""Provider-free backlog regressions: receipts, uncertainty, drift and spacing."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from scripts import lordchrist_telegraph_backlog as backlog


def _write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _blob(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    items = [
        {"publication_id": "a-old", "status": "ready", "scheduled_on_moscow": "2026-11-10"},
        {"publication_id": "b-held", "status": "ready", "scheduled_on_moscow": "2026-11-12"},
        {"publication_id": "c-done", "status": "ready", "scheduled_on_moscow": "2026-11-14"},
        {"publication_id": "d-undated", "status": "ready"},
        {"publication_id": "g-canary", "status": "ready", "is_canary": True},
    ]
    entries = {
        "c-done": {
            "publication_id": "c-done",
            "state": "published",
            "provider_effect": "verified",
            "telegram_provider_effect": "verified",
            "telegram_chat_id": backlog.LORDCHRIST_CHAT_ID,
            "telegram_message_id": 1,
            "telegraph_url": "https://telegra.ph/example",
            "telegram_published_at_utc": "2026-11-14T10:00:00+00:00",
        },
    }
    calendar = []
    for pid, when, original_id in (
        ("e-calendar-old", "2026-11-11", 1596),
        ("f-calendar-next", "2026-11-24", 1600),
        ("h-calendar-verified", "2026-11-20", 1599),
    ):
        article = tmp_path / f"{pid}.json"
        article.write_text(f"synthetic article for {pid}", encoding="utf-8")
        blob = _blob(article)
        url = f"https://telegra.ph/{pid}"
        source = "sha256:" + "a" * 64
        items.append(
            {
                "publication_id": pid,
                "status": "ready",
                "scheduled_on_moscow": when,
                "article": {"path": article.name, "git_blob_sha": blob},
            }
        )
        binding = {
            "publication_id": pid,
            "scheduled_on_moscow": when,
            "article_git_blob_sha": blob,
            "source_article_sha256": source,
            "verified_telegraph_url": url,
            "deleted_telegram_message_id": original_id,
        }
        calendar.append(binding)
        entries[pid] = {
            "publication_id": pid,
            "state": "published",
            "provider_effect": "verified",
            "telegram_chat_id": backlog.LORDCHRIST_CHAT_ID,
            "telegram_message_id": original_id,
            "telegraph_url": url,
            "article_sha256": source,
        }
        if pid == "h-calendar-verified":
            entries[pid]["scheduled_reissue"] = {
                "state": "verified",
                "provider_effect": "verified",
                "new_message_id": 1630,
                "scheduled_on_moscow": when,
                "original_deleted_message_id": original_id,
                "source_article_sha256": source,
                "telegraph_url": url,
                "verified_at_moscow": "2026-11-20T12:05:46+03:00",
            }
    queue = _write(tmp_path / "queue.json", {"items": items})
    ledger = _write(
        tmp_path / "ledger.json",
        {
            "schema_name": "video-channel-manager.lordchrist-telegraph-ledger",
            "schema_version": 1,
            "project_key": "lord-god-strength",
            "entries": entries,
        },
    )
    manifest = _write(
        tmp_path / "manifest.json",
        {
            "schema_name": "video-channel-manager.lordchrist-charnock-2026-reissue-v1",
            "schema_version": 1,
            "channel": "@lordchrist",
            "timezone": "Europe/Moscow",
            "release_time": "12:00",
            "items": calendar,
        },
    )
    return queue, ledger, manifest


def _plan_files(tmp_path: Path, *, today: str = "2026-11-21", gap: int = 3, priority=(), **kwargs) -> dict:
    return backlog.build_plan(
        queue_path=tmp_path / "queue.json",
        ledger_path=tmp_path / "ledger.json",
        manifest_path=tmp_path / "manifest.json",
        today=date.fromisoformat(today),
        start=date.fromisoformat(today) + timedelta(days=1),
        gap_days=gap,
        priority=priority,
        holds=frozenset({"b-held"} | set(backlog.EDITORIAL_HOLDS)),
        repo_root=tmp_path,
        **kwargs,
    )


def _plan(tmp_path: Path, **kwargs) -> dict:
    _fixture(tmp_path)
    return _plan_files(tmp_path, **kwargs)


def _record(plan: dict, group: str, pid: str) -> dict:
    return next(record for record in plan[group] if record["publication_id"] == pid)


def test_verified_reissue_wins_and_original_deleted_message_is_not_reissue(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    old = _record(plan, "calendar_owned", "e-calendar-old")
    assert old["deleted_telegram_message_id"] == 1596
    assert old["receipt_status"] == "unclaimed"
    assert old["calendar_overdue_days"] == 10
    reissued = _record(plan, "published", "h-calendar-verified")
    assert reissued["receipt_status"] == "verified"
    assert reissued["telegram_message_id"] == 1630  # never the deleted 1599
    assert "h-calendar-verified" not in [slot["publication_id"] for slot in plan["proposal"]]
    assert _record(plan, "published", "c-done")["receipt_status"] == "verified_receipt"


def test_overdue_undated_and_holds_are_separate(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    assert [r["publication_id"] for r in plan["overdue"]] == ["a-old", "b-held"]
    assert [r["publication_id"] for r in plan["undated"]] == ["d-undated", "g-canary"]
    proposed = [slot["publication_id"] for slot in plan["proposal"]]
    assert sorted(proposed) == ["a-old", "d-undated", "e-calendar-old"]
    assert "b-held" not in proposed and "g-canary" not in proposed


def test_proposal_respects_gap_from_both_past_and_future_occupied_slots(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    dates = [date.fromisoformat(slot["proposed_date"]) for slot in plan["proposal"]]
    occupied = {date(2026, 11, 20), date(2026, 11, 24)}
    assert dates[0] == date(2026, 11, 27)  # 22/23 would be too close to the 24th
    assert all(abs((proposed - booked).days) >= 3 for proposed in dates for booked in occupied)
    assert all((later - earlier).days >= 3 for earlier, later in zip(dates, dates[1:], strict=False))
    assert dates == sorted(dates)
    busy = {date(2026, 11, 24)}
    slots = backlog.propose_slots(
        [{"publication_id": "x", "source": "queue"}], start=date(2026, 11, 22), gap_days=3, busy=busy
    )
    assert slots[0]["proposed_date"] == "2026-11-27"
    assert busy == {date(2026, 11, 24)}  # no caller mutation


def test_priority_does_not_override_safety(tmp_path: Path) -> None:
    plan = _plan(tmp_path, priority=("e-calendar-old", "b-held"))
    assert plan["proposal"][0]["publication_id"] == "e-calendar-old"
    assert "b-held" not in [r["publication_id"] for r in plan["proposal"]]


@pytest.mark.parametrize(
    "partial",
    [
        None,
        {},
        {"state": "sent", "provider_effect": "may_exist"},
        {"state": "verified", "provider_effect": "verified", "new_message_id": 1630},
    ],
)
def test_any_partial_reissue_is_ambiguous_and_never_proposed(tmp_path: Path, partial) -> None:
    _, ledger_path, _ = _fixture(tmp_path)
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["entries"]["e-calendar-old"]["scheduled_reissue"] = partial
    _write(ledger_path, ledger)
    plan = _plan_files(tmp_path)
    record = _record(plan, "calendar_owned", "e-calendar-old")
    assert record["receipt_status"] == "ambiguous"
    assert "reissue_receipt_ambiguous" in record["proposal_blockers"]
    assert "e-calendar-old" not in [slot["publication_id"] for slot in plan["proposal"]]


def test_mismatched_terminal_identity_is_never_treated_as_published_or_pending(tmp_path: Path) -> None:
    _, ledger_path, _ = _fixture(tmp_path)
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["entries"]["h-calendar-verified"]["scheduled_reissue"]["source_article_sha256"] = "sha256:" + "0" * 64
    _write(ledger_path, ledger)
    plan = _plan_files(tmp_path)
    assert _record(plan, "calendar_owned", "h-calendar-verified")["receipt_status"] == "ambiguous"
    assert "h-calendar-verified" not in [slot["publication_id"] for slot in plan["proposal"]]


def test_missing_ledger_disables_every_proposal_including_charnock(tmp_path: Path) -> None:
    queue, ledger, manifest = _fixture(tmp_path)
    ledger.unlink()
    plan = backlog.build_plan(
        queue_path=queue,
        ledger_path=ledger,
        manifest_path=manifest,
        today=date(2026, 11, 21),
        start=date(2026, 11, 22),
        gap_days=3,
        repo_root=tmp_path,
    )
    assert plan["ledger_source"] == "absent"
    assert plan["proposal"] == []
    assert _record(plan, "calendar_owned", "e-calendar-old")["receipt_status"] == "unavailable"
    assert _record(plan, "needs_reconciliation", "a-old")["receipt_status"] == "unavailable"
    assert "ledger не прочитан" in backlog.render(plan)


def test_missing_original_and_ambiguous_ordinary_receipt_never_propose(tmp_path: Path) -> None:
    _, ledger_path, _ = _fixture(tmp_path)
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    del ledger["entries"]["e-calendar-old"]
    ledger["entries"]["a-old"] = {"publication_id": "a-old", "state": "dispatching", "provider_effect": "may_exist"}
    _write(ledger_path, ledger)
    plan = _plan_files(tmp_path)
    assert _record(plan, "calendar_owned", "e-calendar-old")["receipt_status"] == "ambiguous"
    assert _record(plan, "needs_reconciliation", "a-old")["receipt_status"] == "ambiguous"
    assert not {"a-old", "e-calendar-old"} & {slot["publication_id"] for slot in plan["proposal"]}


def test_source_file_queue_and_date_drift_block_calendar_proposal(tmp_path: Path) -> None:
    queue_path, _, _ = _fixture(tmp_path)
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    entry = next(r for r in queue["items"] if r["publication_id"] == "e-calendar-old")
    entry["scheduled_on_moscow"] = "2026-11-12"
    entry["article"]["git_blob_sha"] = "0" * 40
    _write(queue_path, queue)
    plan = _plan_files(tmp_path)
    blockers = _record(plan, "calendar_owned", "e-calendar-old")["proposal_blockers"]
    assert {"queue_calendar_date_mismatch", "queue_calendar_blob_mismatch", "queue_article_file_blob_mismatch"} <= set(
        blockers
    )
    assert "e-calendar-old" not in [slot["publication_id"] for slot in plan["proposal"]]


def test_legacy_receipt_requires_matching_target_and_timestamp(tmp_path: Path) -> None:
    _, ledger_path, _ = _fixture(tmp_path)
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    entry = ledger["entries"]["c-done"]
    for field in ("state", "provider_effect", "telegram_provider_effect"):
        entry.pop(field)
    _write(ledger_path, ledger)
    assert _record(_plan_files(tmp_path), "published", "c-done")["receipt_status"] == "legacy_receipt"
    entry["telegram_chat_id"] = -1001234567890
    _write(ledger_path, ledger)
    assert _record(_plan_files(tmp_path), "needs_reconciliation", "c-done")["receipt_status"] == "ambiguous"


def test_invalid_or_proposal_manifest_and_bad_ledger_fail_closed(tmp_path: Path) -> None:
    _, ledger_path, manifest_path = _fixture(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["proposal_status"] = "PROPOSAL_ONLY_NOT_APPROVED"
    _write(manifest_path, manifest)
    with pytest.raises(SystemExit, match="unreviewed"):
        _plan_files(tmp_path)
    manifest.pop("proposal_status")
    _write(manifest_path, manifest)
    _write(ledger_path, {"entries": {}})
    with pytest.raises(SystemExit, match="invalid or unbound"):
        _plan_files(tmp_path)


def test_inert_charnock_proposal_never_moves_verified_09_or_becomes_active_manifest() -> None:
    directory = backlog.ROOT / "content/telegram/lordchrist/telegraph-v1/charnock"
    proposal_path = directory / "charnock-reschedule-2026-proposal-20261121.json"
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    active = json.loads((directory / "charnock-reschedule-2026.json").read_text(encoding="utf-8"))
    by_id = lambda data: {item["publication_id"]: item for item in data["items"]}  # noqa: E731
    assert proposal["proposal_status"] == "PROPOSAL_ONLY_NOT_APPROVED"
    assert by_id(proposal)["lordchrist-telegraph-charnock-09"] == by_id(active)["lordchrist-telegraph-charnock-09"]
    for number in (10, 11, 12, 13):
        pid = f"lordchrist-telegraph-charnock-{number}"
        assert by_id(proposal)[pid] == by_id(active)[pid]
    for number, when in ((6, "2026-12-08"), (7, "2026-12-11"), (8, "2026-12-15")):
        assert by_id(proposal)[f"lordchrist-telegraph-charnock-{number:02}"]["scheduled_on_moscow"] == when
    with pytest.raises(SystemExit, match="unreviewed"):
        backlog.load_calendar_manifest(proposal_path)


def test_real_repository_without_ledger_is_inert_and_does_not_invent_publications(tmp_path: Path) -> None:
    plan = backlog.build_plan(
        queue_path=backlog.ROOT / backlog.QUEUE_PATH,
        ledger_path=tmp_path / "absent-ledger.json",
        manifest_path=backlog.ROOT / backlog.MANIFEST_PATH,
        today=date(2026, 11, 22),
        start=date(2026, 11, 23),
        gap_days=3,
    )
    assert plan["read_only"] is True
    assert plan["counts"]["published"] == 0
    assert plan["counts"]["calendar_owned"] == 8
    assert plan["proposal"] == []
    assert plan["editorial_holds"] == ["lordchrist-telegraph-charnock-13"]
    assert "Только чтение" in backlog.render(plan)


def test_default_slot_is_daytime_and_never_catches_up_after_1400_moscow() -> None:
    today = date(2026, 11, 22)
    assert backlog._default_proposal_start(today, datetime(2026, 11, 22, 2, tzinfo=UTC)) == today
    assert backlog._default_proposal_start(today, datetime(2026, 11, 22, 10, 59, tzinfo=UTC)) == today
    assert backlog._default_proposal_start(today, datetime(2026, 11, 22, 11, tzinfo=UTC)) == date(2026, 11, 23)
    assert backlog._default_proposal_start(today, datetime(2026, 11, 23, 9, tzinfo=UTC)) == date(2026, 11, 23)
    with pytest.raises(ValueError, match="timezone-aware"):
        backlog._default_proposal_start(today, datetime(2026, 11, 22, 9))


def test_output_cannot_overwrite_repo_content_or_input(tmp_path: Path) -> None:
    queue, ledger, manifest = _fixture(tmp_path)
    before = queue.read_bytes()
    with pytest.raises(SystemExit, match="cannot overwrite"):
        backlog._safe_output_path(tmp_path, queue, (queue, ledger, manifest))
    with pytest.raises(SystemExit, match="artifacts"):
        backlog._safe_output_path(tmp_path, tmp_path / "article.json", (queue, ledger, manifest))
    out = tmp_path / "artifacts" / "report.json"
    assert backlog._safe_output_path(tmp_path, out, (queue, ledger, manifest)) == out
    assert queue.read_bytes() == before


def test_main_falls_back_to_state_ref_without_claiming_freshness(tmp_path: Path, monkeypatch) -> None:
    seen: list[str] = []

    def fake_load(root, ref, ledger):
        seen.append(ref)
        return {}

    monkeypatch.setattr(backlog, "load_ledger_from_ref", fake_load)
    out = tmp_path / "plan.json"
    assert backlog.main(["--today", "2026-11-21", "--out", str(out), "--json"]) == 0
    assert seen == [backlog.DEFAULT_STATE_REMOTE_REF]
    assert "not_proven" in json.loads(out.read_text(encoding="utf-8"))["ledger_freshness"]
