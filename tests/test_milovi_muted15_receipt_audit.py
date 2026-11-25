from __future__ import annotations

import json
import socket
from datetime import UTC, datetime, timedelta, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from scripts import milovi_muted15_due as due
from video_channel_manager.milovi_telegram_feed import state_check, state_init

FEED = Path("content/telegram/milovi-cake/feed")
MOSCOW = ZoneInfo("Europe/Moscow")


def _snapshot(checkout: Path) -> dict[str, bytes]:
    return {str(path.relative_to(checkout)): path.read_bytes() for path in (checkout / FEED).glob("*.json")}


def _record_synthetic_verified(checkout: Path, row: dict, *, changes: dict[str, object] | None = None) -> None:
    """Create internally consistent synthetic state only inside pytest's tmp directory."""
    pid = row["publication_id"]
    path = checkout / FEED / f"{pid}.json"
    index_path = checkout / FEED / "index.json"
    ledger = json.loads(path.read_text(encoding="utf-8"))
    index = json.loads(index_path.read_text(encoding="utf-8"))
    attempted = datetime.fromisoformat(row["scheduled_at_proposal"]) + timedelta(minutes=10)
    entry = ledger["entries"][pid]
    entry.update(
        state="published",
        provider_effect="verified",
        intent_id="a" * 32,
        dispatch_mode="scheduled",
        workflow_run_id="12345",
        workflow_run_attempt="1",
        github_sha="b" * 40,
        github_workflow_sha="c" * 40,
        attempted_at_utc=attempted.isoformat(),
        published_at_utc=(attempted + timedelta(minutes=1)).isoformat(),
        message_id=32,
        message_url="https://t.me/MiloviCake/32",
        actual_chat_id=-1002215328390,
        actual_chat_username="MiloviCake",
        bot_id=8716602202,
        bot_username="preaching_mp3_bot",
    )
    if changes:
        entry.update(changes)
    index["entries"][pid].update(
        state=entry["state"],
        provider_effect=entry["provider_effect"],
        intent_id=entry["intent_id"],
        message_id=entry["message_id"],
        message_url=entry["message_url"],
    )
    path.write_text(json.dumps(ledger), encoding="utf-8")
    index_path.write_text(json.dumps(index), encoding="utf-8")


@pytest.fixture
def two_rows(tmp_path: Path) -> list[dict]:
    rows = due.reviewed_items()[:2]
    for row in rows:
        state_init(row["publication_id"], state_checkout=tmp_path)
    return rows


def test_expired_video_audit_reads_exact_state_without_mutation_or_network(
    tmp_path: Path, two_rows: list[dict], monkeypatch: pytest.MonkeyPatch
) -> None:
    _record_synthetic_verified(tmp_path, two_rows[0])
    before = _snapshot(tmp_path)

    def no_network(*_args: object, **_kwargs: object) -> None:
        pytest.fail("The video receipt audit must never contact a provider")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    assert due.exact_state_decision(two_rows[0], checkout=tmp_path) is False
    assert due.missed_delivery_windows(datetime(2026, 11, 10, 0, 0, tzinfo=MOSCOW), two_rows, checkout=tmp_path) == [
        two_rows[1]["publication_id"]
    ]
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("surface", ["due", "audit"])
@pytest.mark.parametrize(
    "changes",
    [
        {"actual_chat_id": -1001111111111},
        {"actual_chat_username": "OtherChannel"},
        {"bot_id": 1234567},
        {"bot_username": "OtherBot"},
        {"message_url": "https://t.me/OtherChannel/32"},
        {"message_url": "https://t.me/MiloviCake/33"},
        {"message_id": True, "message_url": "https://t.me/MiloviCake/1"},
        {"actual_chat_id": "-1002215328390"},
        {"bot_id": "8716602202"},
        {
            "attempted_at_utc": "2026-11-08T18:59:59+03:00",
            "published_at_utc": "2026-11-08T19:01:00+03:00",
        },
        {
            "attempted_at_utc": "2026-11-08T21:00:00+03:00",
            "published_at_utc": "2026-11-08T21:01:00+03:00",
        },
    ],
    ids=[
        "chat-id",
        "chat-name",
        "bot-id",
        "bot-name",
        "wrong-channel-url",
        "wrong-message-url",
        "bool-id",
        "string-chat-id",
        "string-bot-id",
        "early",
        "late",
    ],
)
def test_inconsistent_published_receipt_never_silently_clears_a_video_slot(
    tmp_path: Path, two_rows: list[dict], changes: dict[str, object], surface: str
) -> None:
    row = two_rows[0]
    _record_synthetic_verified(tmp_path, row, changes=changes)
    before = _snapshot(tmp_path)
    # Generic ledger/index consistency alone does not check the target, link,
    # JSON identity types or the reviewed two-hour window.
    assert state_check(row["publication_id"], state_checkout=tmp_path)["state"] == "published"
    with pytest.raises(ValueError, match="reconcile without replay"):
        if surface == "due":
            due.exact_state_decision(row, checkout=tmp_path)
        else:
            due.missed_delivery_windows(datetime(2026, 11, 10, 0, 0, tzinfo=MOSCOW), two_rows, checkout=tmp_path)
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("minutes,seconds", [(0, 0), (119, 59)])
def test_exact_window_boundaries_allow_valid_intent_even_if_confirmation_is_later(
    tmp_path: Path, two_rows: list[dict], minutes: int, seconds: int
) -> None:
    row = two_rows[0]
    start = datetime.fromisoformat(row["scheduled_at_proposal"])
    attempted = start + timedelta(minutes=minutes, seconds=seconds)
    _record_synthetic_verified(
        tmp_path,
        row,
        changes={
            "attempted_at_utc": attempted.astimezone(UTC).isoformat(),
            "published_at_utc": (attempted + timedelta(minutes=1)).astimezone(UTC).isoformat(),
        },
    )
    # Result verification may finish after the lease, but it must already
    # exist at the observation clock, which is 21:02 in this test.
    now = datetime(2026, 11, 8, 21, 2, tzinfo=MOSCOW)
    assert due.exact_state_decision(row, checkout=tmp_path, now=now) is False
    assert due.missed_delivery_windows(now, two_rows, checkout=tmp_path) == []


def test_future_receipt_is_not_treated_as_already_verified(tmp_path: Path, two_rows: list[dict]) -> None:
    row = two_rows[0]
    _record_synthetic_verified(tmp_path, row, changes={"published_at_utc": "2026-11-10T00:01:00+03:00"})
    now = datetime(2026, 11, 10, 0, 0, tzinfo=MOSCOW)
    with pytest.raises(ValueError, match="reconcile without replay"):
        due.exact_state_decision(row, checkout=tmp_path, now=now)
    with pytest.raises(ValueError, match="reconcile without replay"):
        due.missed_delivery_windows(now, two_rows, checkout=tmp_path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("scheduled_at_proposal", "2026-11-07T19:00:00+03:00"),
        ("release_digest", "sha256:" + "f" * 64),
        ("release_candidate_sha256", "sha256:" + "f" * 64),
        ("provider_payload_sha256", "sha256:" + "f" * 64),
    ],
)
def test_published_receipt_must_match_release_and_reviewed_slot(
    tmp_path: Path, two_rows: list[dict], field: str, value: str
) -> None:
    _record_synthetic_verified(tmp_path, two_rows[0])
    drifted = {**two_rows[0], field: value}
    with pytest.raises(ValueError, match="reconcile without replay"):
        due.exact_state_decision(drifted, checkout=tmp_path)
    with pytest.raises(ValueError, match="reconcile without replay"):
        due.missed_delivery_windows(datetime(2026, 11, 10, 0, 0, tzinfo=MOSCOW), [drifted], checkout=tmp_path)


@pytest.mark.parametrize("surface", ["due", "audit"])
@pytest.mark.parametrize(
    "field,value",
    [
        ("dispatch_mode", "scheduled"),
        ("workflow_run_id", "12345"),
        ("workflow_run_attempt", "1"),
        ("github_sha", "b" * 40),
        ("github_workflow_sha", "c" * 40),
        ("attempted_at_utc", "2026-11-08T19:10:00+03:00"),
        ("published_at_utc", "2026-11-08T19:11:00+03:00"),
        ("actual_chat_id", -1002215328390),
        ("actual_chat_username", "MiloviCake"),
        ("bot_id", 8716602202),
        ("bot_username", "preaching_mp3_bot"),
        ("last_error", "previous send status unknown"),
    ],
)
def test_pending_impossible_with_stale_attempt_evidence_never_dispatches_or_silently_audits(
    tmp_path: Path, two_rows: list[dict], field: str, value: object, surface: str
) -> None:
    row = two_rows[0]
    path = tmp_path / FEED / f"{row['publication_id']}.json"
    ledger = json.loads(path.read_text(encoding="utf-8"))
    ledger["entries"][row["publication_id"]][field] = value
    path.write_text(json.dumps(ledger), encoding="utf-8")
    before = _snapshot(tmp_path)
    assert state_check(row["publication_id"], state_checkout=tmp_path)["state"] == "pending"
    with pytest.raises(ValueError, match="reconcile without replay"):
        if surface == "due":
            due.exact_state_decision(row, checkout=tmp_path)
        else:
            due.missed_delivery_windows(datetime(2026, 11, 10, 0, 0, tzinfo=MOSCOW), two_rows, checkout=tmp_path)
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("surface", ["due", "audit"])
def test_pending_impossible_requires_complete_explicit_null_attempt_evidence(
    tmp_path: Path, two_rows: list[dict], surface: str
) -> None:
    row = two_rows[0]
    path = tmp_path / FEED / f"{row['publication_id']}.json"
    ledger = json.loads(path.read_text(encoding="utf-8"))
    del ledger["entries"][row["publication_id"]]["attempted_at_utc"]
    path.write_text(json.dumps(ledger), encoding="utf-8")
    with pytest.raises(ValueError, match="reconcile without replay"):
        if surface == "due":
            due.exact_state_decision(row, checkout=tmp_path)
        else:
            due.missed_delivery_windows(datetime(2026, 11, 10, 0, 0, tzinfo=MOSCOW), two_rows, checkout=tmp_path)


@pytest.mark.parametrize("state", ["unknown", "dispatching"])
def test_real_uncertain_ledger_blocks_both_paths_without_modification(
    tmp_path: Path, two_rows: list[dict], state: str
) -> None:
    row = two_rows[0]
    _record_synthetic_verified(
        tmp_path,
        row,
        changes={
            "state": state,
            "provider_effect": "may_exist",
            "message_id": None,
            "message_url": None,
            "published_at_utc": None,
        },
    )
    before = _snapshot(tmp_path)
    with pytest.raises(ValueError, match="unresolved"):
        due.exact_state_decision(row, checkout=tmp_path)
    with pytest.raises(ValueError, match="unsafe or inconsistent"):
        due.missed_delivery_windows(datetime(2026, 11, 10, 0, 0, tzinfo=MOSCOW), two_rows, checkout=tmp_path)
    assert _snapshot(tmp_path) == before


def test_index_ledger_disagreement_never_becomes_a_green_receipt(tmp_path: Path, two_rows: list[dict]) -> None:
    row = two_rows[0]
    _record_synthetic_verified(tmp_path, row)
    index_path = tmp_path / FEED / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["entries"][row["publication_id"]]["message_url"] = "https://t.me/MiloviCake/33"
    index_path.write_text(json.dumps(index), encoding="utf-8")
    before = _snapshot(tmp_path)
    with pytest.raises(ValueError, match="differs from exact durable release ledger"):
        due.exact_state_decision(row, checkout=tmp_path)
    with pytest.raises(ValueError, match="differs from exact durable release ledger"):
        due.missed_delivery_windows(datetime(2026, 11, 10, 0, 0, tzinfo=MOSCOW), two_rows, checkout=tmp_path)
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("surface", ["due", "audit"])
def test_boolean_index_message_identity_is_not_a_raw_integer_receipt(
    tmp_path: Path, two_rows: list[dict], surface: str
) -> None:
    row = two_rows[0]
    _record_synthetic_verified(tmp_path, row, changes={"message_id": 1, "message_url": "https://t.me/MiloviCake/1"})
    index_path = tmp_path / FEED / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["entries"][row["publication_id"]]["message_id"] = True
    index_path.write_text(json.dumps(index), encoding="utf-8")
    before = _snapshot(tmp_path)
    assert state_check(row["publication_id"], state_checkout=tmp_path)["state"] == "published"
    with pytest.raises(ValueError, match="reconcile without replay"):
        if surface == "due":
            due.exact_state_decision(row, checkout=tmp_path)
        else:
            due.missed_delivery_windows(datetime(2026, 11, 10, 0, 0, tzinfo=MOSCOW), two_rows, checkout=tmp_path)
    assert _snapshot(tmp_path) == before


def test_missing_ledger_never_becomes_a_green_receipt(tmp_path: Path, two_rows: list[dict]) -> None:
    row = two_rows[0]
    (tmp_path / FEED / f"{row['publication_id']}.json").unlink()
    before = _snapshot(tmp_path)
    with pytest.raises(ValueError, match="ledger is missing"):
        due.exact_state_decision(row, checkout=tmp_path)
    with pytest.raises(ValueError, match="ledger is missing"):
        due.missed_delivery_windows(datetime(2026, 11, 10, 0, 0, tzinfo=MOSCOW), two_rows, checkout=tmp_path)
    assert _snapshot(tmp_path) == before


class NoOffset(tzinfo):
    def utcoffset(self, dt: datetime | None) -> None:
        return None


def test_timezone_object_without_real_offset_is_still_naive(tmp_path: Path, two_rows: list[dict]) -> None:
    naive = datetime(2026, 11, 8, 21, 0, tzinfo=NoOffset())
    with pytest.raises(ValueError, match="timezone-aware"):
        due.due_row(naive, two_rows)
    with pytest.raises(ValueError, match="timezone-aware"):
        due.exact_state_decision(two_rows[0], checkout=tmp_path, now=naive)
    with pytest.raises(ValueError, match="timezone-aware"):
        due.missed_delivery_windows(naive, two_rows, checkout=tmp_path)
