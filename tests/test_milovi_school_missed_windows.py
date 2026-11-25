from __future__ import annotations

import json
import socket
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from scripts import milovi_school_reading_due as school
from video_channel_manager.milovi_telegram_feed import state_init
from video_channel_manager.telegram_multichannel_release import load_release

LOCAL = ZoneInfo("Europe/Moscow")
EARLY = school.OWNER_EARLY_PARIS_BREST
ORIGINAL = school.ORIGINAL_PARIS_BREST
CROISSANT = "milovi-feed-20261121-002"
STOHRER = "milovi-feed-20261125-001"
FEED = Path("content/telegram/milovi-cake/feed")


def _initialized(checkout: Path, *, early: bool = True) -> None:
    school.initialize_all(checkout)
    if early:
        state_init(EARLY, state_checkout=checkout)


def _set_state(checkout: Path, pid: str, *, state: str, message_id: int | None = None) -> None:
    """Build synthetic, internally consistent generic-ledger evidence for tests."""
    ledger_path = checkout / FEED / f"{pid}.json"
    index_path = checkout / FEED / "index.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    index = json.loads(index_path.read_text(encoding="utf-8"))
    entry = ledger["entries"][pid]
    published = state == "published"
    effect = "verified" if published else "may_exist"
    url = f"https://t.me/MiloviCake/{message_id}" if published else None
    release = load_release(school.ROOT / "releases" / f"{pid}-runtime.json")
    attempted_at = release.items[0].scheduled_at + timedelta(minutes=10)
    entry.update(
        state=state,
        provider_effect=effect,
        intent_id="a" * 32,
        dispatch_mode="manual",
        workflow_run_id="12345",
        workflow_run_attempt="1",
        github_sha="b" * 40,
        github_workflow_sha="c" * 40,
        attempted_at_utc=attempted_at.isoformat(),
        published_at_utc=(attempted_at + timedelta(minutes=1)).isoformat() if published else None,
        message_id=message_id,
        message_url=url,
        actual_chat_id=-1002215328390,
        actual_chat_username="MiloviCake",
        bot_id=8716602202,
        bot_username="preaching_mp3_bot",
    )
    index["entries"][pid].update(
        state=state,
        provider_effect=effect,
        intent_id=entry["intent_id"],
        message_id=message_id,
        message_url=url,
    )
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    index_path.write_text(json.dumps(index), encoding="utf-8")


def _verified_early(checkout: Path) -> None:
    _set_state(checkout, EARLY, state="published", message_id=27)
    assert school._early_paris_brest_verified(checkout, school._load_state_index(checkout))


def _snapshot(checkout: Path) -> dict[str, bytes]:
    return {str(p.relative_to(checkout)): p.read_bytes() for p in (checkout / FEED).glob("*.json")}


def test_overdue_school_audit_is_read_only_and_understands_verified_early_duplicate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _initialized(tmp_path)
    _verified_early(tmp_path)
    before = _snapshot(tmp_path)

    def no_network(*_args: object, **_kwargs: object) -> None:
        pytest.fail("The missed-window audit must never contact a provider")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    report = school.audit_expired(datetime(2026, 11, 22, 0, 35, tzinfo=LOCAL), checkout=tmp_path)
    assert report == {
        "missed_windows": [CROISSANT],
        "suppressed_early_duplicate": [ORIGINAL],
        "verified": [],
        "provider_access_performed": False,
        "provider_mutation_performed": False,
    }
    assert _snapshot(tmp_path) == before


def test_audit_uses_exact_end_of_moscow_window_and_never_looks_ahead(tmp_path: Path) -> None:
    # Before the first deadline, no protected-state checkout is needed at all.
    before_first = school.audit_expired(datetime(2026, 11, 17, 14, 29, 59, tzinfo=LOCAL), checkout=tmp_path)
    assert before_first["missed_windows"] == []
    _initialized(tmp_path)
    _verified_early(tmp_path)
    before = school.audit_expired(datetime(2026, 11, 21, 14, 29, 59, tzinfo=LOCAL), checkout=tmp_path)
    at = school.audit_expired(datetime(2026, 11, 21, 14, 30, tzinfo=LOCAL), checkout=tmp_path)
    assert before["missed_windows"] == []
    assert at["missed_windows"] == [CROISSANT]
    utc_equivalent = school.audit_expired(datetime(2026, 11, 21, 11, 30, tzinfo=timezone.utc), checkout=tmp_path)
    assert utc_equivalent == at
    later = school.audit_expired(datetime(2026, 11, 25, 14, 30, tzinfo=LOCAL), checkout=tmp_path)
    assert later["missed_windows"] == [CROISSANT, STOHRER]
    next_year = school.audit_expired(datetime(2027, 11, 17, 14, 30, tzinfo=LOCAL), checkout=tmp_path)
    assert next_year["missed_windows"] == [CROISSANT, STOHRER]
    with pytest.raises(ValueError, match="timezone-aware"):
        school.audit_expired(datetime(2026, 11, 22, 0, 0), checkout=tmp_path)


@pytest.mark.parametrize("early_registered", [False, True])
def test_pending_original_is_not_suppressed_without_a_verified_early_receipt(
    tmp_path: Path, early_registered: bool
) -> None:
    _initialized(tmp_path, early=early_registered)
    report = school.audit_expired(datetime(2026, 11, 17, 14, 30, tzinfo=LOCAL), checkout=tmp_path)
    assert report["missed_windows"] == [ORIGINAL]
    assert report["suppressed_early_duplicate"] == []


def test_early_receipt_must_predate_original_slot_and_have_both_index_and_ledger(tmp_path: Path) -> None:
    _initialized(tmp_path)
    _verified_early(tmp_path)
    ledger_path = tmp_path / FEED / f"{EARLY}.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["entries"][EARLY]["published_at_utc"] = "2026-11-18T00:00:00Z"
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    with pytest.raises(ValueError, match="not early"):
        school.audit_expired(datetime(2026, 11, 22, 0, 35, tzinfo=LOCAL), checkout=tmp_path)
    with pytest.raises(ValueError, match="not early"):
        school.due(tmp_path, now=datetime(2026, 11, 21, 12, 37, tzinfo=LOCAL))
    ledger_path.unlink()
    with pytest.raises(ValueError, match="index/ledger incomplete"):
        school.audit_expired(datetime(2026, 11, 22, 0, 35, tzinfo=LOCAL), checkout=tmp_path)


def test_exact_verified_receipts_are_not_misreported_as_missed(tmp_path: Path) -> None:
    _initialized(tmp_path)
    _verified_early(tmp_path)
    _set_state(tmp_path, CROISSANT, state="published", message_id=50)
    _set_state(tmp_path, STOHRER, state="published", message_id=51)
    report = school.audit_expired(datetime(2026, 11, 25, 14, 30, tzinfo=LOCAL), checkout=tmp_path)
    assert report["missed_windows"] == []
    assert report["suppressed_early_duplicate"] == [ORIGINAL]
    assert report["verified"] == [CROISSANT, STOHRER]


@pytest.mark.parametrize("pid", [EARLY, ORIGINAL, CROISSANT])
def test_ambiguous_provider_effect_is_never_converted_to_a_missed_or_safe_retry(tmp_path: Path, pid: str) -> None:
    _initialized(tmp_path)
    if pid != EARLY:
        _verified_early(tmp_path)
    _set_state(tmp_path, pid, state="unknown")
    before = _snapshot(tmp_path)
    with pytest.raises(ValueError, match="reconcile"):
        school.audit_expired(datetime(2026, 11, 22, 0, 35, tzinfo=LOCAL), checkout=tmp_path)
    assert _snapshot(tmp_path) == before


def test_duplicate_early_and_original_verified_receipts_are_incident_not_suppression(tmp_path: Path) -> None:
    _initialized(tmp_path)
    _verified_early(tmp_path)
    _set_state(tmp_path, ORIGINAL, state="published", message_id=28)
    with pytest.raises(ValueError, match="both.*verified"):
        school.audit_expired(datetime(2026, 11, 17, 14, 30, tzinfo=LOCAL), checkout=tmp_path)
    with pytest.raises(ValueError, match="reconcile without replay"):
        school.due(tmp_path, now=datetime(2026, 11, 17, 12, 37, tzinfo=LOCAL))


def test_verified_receipt_with_wrong_target_and_index_ledger_drift_fail_closed(tmp_path: Path) -> None:
    _initialized(tmp_path)
    _verified_early(tmp_path)
    _set_state(tmp_path, CROISSANT, state="published", message_id=50)
    ledger_path = tmp_path / FEED / f"{CROISSANT}.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["entries"][CROISSANT]["actual_chat_id"] = -1001111111111
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    with pytest.raises(ValueError, match="target"):
        school.audit_expired(datetime(2026, 11, 22, 0, 35, tzinfo=LOCAL), checkout=tmp_path)

    ledger["entries"][CROISSANT]["actual_chat_id"] = -1002215328390
    ledger["entries"][CROISSANT]["message_id"] = 51  # index remains 50
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    with pytest.raises(ValueError, match="differs from exact durable release ledger"):
        school.audit_expired(datetime(2026, 11, 22, 0, 35, tzinfo=LOCAL), checkout=tmp_path)


def test_verified_but_wrong_message_url_never_counts_as_delivery(tmp_path: Path) -> None:
    _initialized(tmp_path)
    _verified_early(tmp_path)
    _set_state(tmp_path, CROISSANT, state="published", message_id=50)
    ledger_path = tmp_path / FEED / f"{CROISSANT}.json"
    index_path = tmp_path / FEED / "index.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    index = json.loads(index_path.read_text(encoding="utf-8"))
    wrong = "https://t.me/SomeOtherChannel/50"
    ledger["entries"][CROISSANT]["message_url"] = wrong
    index["entries"][CROISSANT]["message_url"] = wrong
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    index_path.write_text(json.dumps(index), encoding="utf-8")
    with pytest.raises(ValueError, match="target or message identity"):
        school.audit_expired(datetime(2026, 11, 22, 0, 35, tzinfo=LOCAL), checkout=tmp_path)


def test_verified_receipt_with_out_of_window_attempt_is_not_a_valid_due_delivery(tmp_path: Path) -> None:
    _initialized(tmp_path)
    _verified_early(tmp_path)
    _set_state(tmp_path, CROISSANT, state="published", message_id=50)
    ledger_path = tmp_path / FEED / f"{CROISSANT}.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["entries"][CROISSANT]["attempted_at_utc"] = "2026-11-21T14:30:00+03:00"
    ledger["entries"][CROISSANT]["published_at_utc"] = "2026-11-21T14:31:00+03:00"
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    with pytest.raises(ValueError, match="outside the scheduled window"):
        school.audit_expired(datetime(2026, 11, 22, 0, 35, tzinfo=LOCAL), checkout=tmp_path)


def test_missing_ledger_never_becomes_a_green_missed_window(tmp_path: Path) -> None:
    _initialized(tmp_path)
    _verified_early(tmp_path)
    (tmp_path / FEED / f"{CROISSANT}.json").unlink()
    with pytest.raises(ValueError, match="ledger is missing"):
        school.audit_expired(datetime(2026, 11, 22, 0, 35, tzinfo=LOCAL), checkout=tmp_path)


def test_cli_returns_failure_annotation_for_elapsed_unverified_school_item(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _initialized(tmp_path)
    _verified_early(tmp_path)

    class FixedClock(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[no-untyped-def]
            return datetime(2026, 11, 22, 0, 35, tzinfo=LOCAL).astimezone(tz)

    monkeypatch.setattr(school, "datetime", FixedClock)
    monkeypatch.setattr(sys, "argv", ["milovi_school_reading_due", "audit-expired", "--state-checkout", str(tmp_path)])
    assert school.main() == 2
    out = capsys.readouterr().out
    assert '"missed_windows": ["' + CROISSANT + '"]' in out
    assert "MILOVI_SCHOOL_MISSED_DUE_WINDOWS" in out
    assert "never replay" in out


def test_cli_without_elapsed_window_is_green_and_does_not_open_protected_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FixedClock(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[no-untyped-def]
            return datetime(2026, 11, 17, 12, 37, tzinfo=LOCAL).astimezone(tz)

    monkeypatch.setattr(school, "datetime", FixedClock)
    monkeypatch.setattr(sys, "argv", ["milovi_school_reading_due", "audit-expired", "--state-checkout", str(tmp_path)])
    assert school.main() == 0
    assert "MILOVI_SCHOOL_MISSED_DUE_WINDOWS" not in capsys.readouterr().out


def test_workflow_audits_after_dispatch_without_new_schedule_or_writer() -> None:
    text = Path(".github/workflows/milovi-telegram-school-reading-due-20261117.yml").read_text(encoding="utf-8")
    assert 'cron: "37 9 17,21,25 11 *"' in text
    assert "group: milovi-cake-telegram-publisher" in text
    assert "always() && github.event_name == 'schedule'" in text
    assert text.index("Dispatch only existing canonical single-writer") < text.index(
        "milovi_school_reading_due audit-expired"
    )
    assert "milovi-telegram-feed-publisher.yml" in text
    assert "workflow_run:" not in text and "initialize-all" not in text
    assert "contents: write" not in text and "sendPhoto" not in text


@pytest.mark.parametrize("surface", ["due", "audit"])
@pytest.mark.parametrize(
    "field,value",
    [
        ("dispatch_mode", "scheduled"),
        ("workflow_run_id", "12345"),
        ("attempted_at_utc", "2026-11-21T12:37:00+03:00"),
        ("actual_chat_id", -1002215328390),
        ("last_error", "prior attempt unresolved"),
    ],
)
def test_school_pending_with_attempt_provenance_fails_for_reconciliation_without_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: object, surface: str
) -> None:
    _initialized(tmp_path)
    _verified_early(tmp_path)
    ledger_path = tmp_path / FEED / f"{CROISSANT}.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["entries"][CROISSANT][field] = value
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    monkeypatch.setattr(school, "require_first_ten_real_cake_videos", lambda *_args: None)
    before = _snapshot(tmp_path)
    with pytest.raises(ValueError, match="reconcile without replay"):
        if surface == "due":
            school.due(tmp_path, now=datetime(2026, 11, 21, 12, 37, tzinfo=LOCAL))
        else:
            school.audit_expired(datetime(2026, 11, 22, 0, 35, tzinfo=LOCAL), checkout=tmp_path)
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("surface", ["due", "audit"])
def test_early_pending_with_attempt_provenance_cannot_be_treated_as_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, surface: str
) -> None:
    _initialized(tmp_path)
    ledger_path = tmp_path / FEED / f"{EARLY}.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["entries"][EARLY]["last_error"] = "prior attempt unresolved"
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    monkeypatch.setattr(school, "require_first_ten_real_cake_videos", lambda *_args: None)
    before = _snapshot(tmp_path)
    with pytest.raises(ValueError, match="reconcile without replay"):
        if surface == "due":
            school.due(tmp_path, now=datetime(2026, 11, 17, 12, 37, tzinfo=LOCAL))
        else:
            school.audit_expired(datetime(2026, 11, 17, 14, 30, tzinfo=LOCAL), checkout=tmp_path)
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("field,value", [("actual_chat_id", "-1002215328390"), ("bot_id", "8716602202")])
def test_school_receipt_must_have_raw_numeric_target_identity(tmp_path: Path, field: str, value: str) -> None:
    _initialized(tmp_path)
    _verified_early(tmp_path)
    _set_state(tmp_path, CROISSANT, state="published", message_id=50)
    ledger_path = tmp_path / FEED / f"{CROISSANT}.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["entries"][CROISSANT][field] = value
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    with pytest.raises(ValueError, match="reconcile without replay"):
        school.audit_expired(datetime(2026, 11, 22, 0, 35, tzinfo=LOCAL), checkout=tmp_path)


def test_school_future_verification_does_not_clear_missed_window(tmp_path: Path) -> None:
    _initialized(tmp_path)
    _verified_early(tmp_path)
    _set_state(tmp_path, CROISSANT, state="published", message_id=50)
    ledger_path = tmp_path / FEED / f"{CROISSANT}.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["entries"][CROISSANT]["published_at_utc"] = "2026-11-22T00:36:00+03:00"
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    with pytest.raises(ValueError, match="reconcile without replay"):
        school.audit_expired(datetime(2026, 11, 22, 0, 35, tzinfo=LOCAL), checkout=tmp_path)


def test_school_rejects_boolean_raw_index_message_id(tmp_path: Path) -> None:
    _initialized(tmp_path)
    _verified_early(tmp_path)
    _set_state(tmp_path, CROISSANT, state="published", message_id=1)
    index_path = tmp_path / FEED / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["entries"][CROISSANT]["message_id"] = True
    index_path.write_text(json.dumps(index), encoding="utf-8")
    with pytest.raises(ValueError, match="reconcile without replay"):
        school.audit_expired(datetime(2026, 11, 22, 0, 35, tzinfo=LOCAL), checkout=tmp_path)


@pytest.mark.parametrize("surface", ["due", "audit"])
def test_school_pending_requires_explicit_attempt_nulls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, surface: str
) -> None:
    _initialized(tmp_path)
    _verified_early(tmp_path)
    ledger_path = tmp_path / FEED / f"{CROISSANT}.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    del ledger["entries"][CROISSANT]["attempted_at_utc"]
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    monkeypatch.setattr(school, "require_first_ten_real_cake_videos", lambda *_args: None)
    with pytest.raises(ValueError, match="reconcile without replay"):
        if surface == "due":
            school.due(tmp_path, now=datetime(2026, 11, 21, 12, 37, tzinfo=LOCAL))
        else:
            school.audit_expired(datetime(2026, 11, 22, 0, 35, tzinfo=LOCAL), checkout=tmp_path)


def test_school_allows_late_verification_of_in_window_intent_when_already_observed(tmp_path: Path) -> None:
    _initialized(tmp_path)
    _verified_early(tmp_path)
    _set_state(tmp_path, CROISSANT, state="published", message_id=50)
    ledger_path = tmp_path / FEED / f"{CROISSANT}.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    entry = ledger["entries"][CROISSANT]
    entry["attempted_at_utc"] = "2026-11-21T14:29:59+03:00"
    entry["published_at_utc"] = "2026-11-21T14:31:00+03:00"
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    with pytest.raises(ValueError, match="reconcile without replay"):
        school.audit_expired(datetime(2026, 11, 21, 14, 30, tzinfo=LOCAL), checkout=tmp_path)
    report = school.audit_expired(datetime(2026, 11, 21, 14, 31, tzinfo=LOCAL), checkout=tmp_path)
    assert report["verified"] == [CROISSANT]
    assert report["missed_windows"] == []


def test_full_school_first_ten_proof_can_pass_without_provider_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _initialized(tmp_path, early=False)
    for number, pid in enumerate(school.FIRST_TEN, start=31):
        state_init(pid, state_checkout=tmp_path)
        _set_state(tmp_path, pid, state="published", message_id=number)
    before = _snapshot(tmp_path)

    def no_network(*_args: object, **_kwargs: object) -> None:
        pytest.fail("The first-ten guard and due decision must not contact a provider")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    now = datetime(2026, 11, 17, 12, 37, tzinfo=LOCAL)
    school.require_first_ten_real_cake_videos(tmp_path, school._load_state_index(tmp_path), now)
    assert school.due(tmp_path, now=now) == {
        "dispatch": "true",
        "publication_id": ORIGINAL,
        "reason": "exact_owner_approved_school_photo_due",
    }
    assert _snapshot(tmp_path) == before
    with pytest.raises(ValueError, match="timezone-aware"):
        school.due(tmp_path, now=datetime(2026, 11, 17, 12, 37))


def test_first_ten_and_predecessors_require_exact_protected_receipts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _initialized(tmp_path)
    video = school.FIRST_TEN[0]
    state_init(video, state_checkout=tmp_path)
    _set_state(tmp_path, video, state="published", message_id=30)
    ledger_path = tmp_path / FEED / f"{video}.json"
    index_path = tmp_path / FEED / "index.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    index = json.loads(index_path.read_text(encoding="utf-8"))
    ledger["entries"][video]["message_url"] = "https://t.me/OtherChannel/30"
    index["entries"][video]["message_url"] = "https://t.me/OtherChannel/30"
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    index_path.write_text(json.dumps(index), encoding="utf-8")
    monkeypatch.setattr(school, "FIRST_TEN", (video,))
    with pytest.raises(ValueError, match="reconcile without replay"):
        school.require_first_ten_real_cake_videos(tmp_path, school._load_state_index(tmp_path))

    _verified_early(tmp_path)
    _set_state(tmp_path, CROISSANT, state="published", message_id=50)
    ledger_path = tmp_path / FEED / f"{CROISSANT}.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    index = json.loads(index_path.read_text(encoding="utf-8"))
    ledger["entries"][CROISSANT]["message_url"] = "https://t.me/OtherChannel/50"
    index["entries"][CROISSANT]["message_url"] = "https://t.me/OtherChannel/50"
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    index_path.write_text(json.dumps(index), encoding="utf-8")
    monkeypatch.setattr(school, "require_first_ten_real_cake_videos", lambda *_args: None)
    with pytest.raises(ValueError, match="reconcile without replay"):
        school.due(tmp_path, now=datetime(2026, 11, 25, 12, 37, tzinfo=LOCAL))
