from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

import video_channel_manager.milovi_telegram_due_dispatch as due

WORKFLOW = Path(".github/workflows/milovi-telegram-exact-due-20261107.yml")


def _state() -> tuple[dict, dict]:
    index = {
        "project_key": "milovi-cake",
        "channel_username": "@MiloviCake",
        "entries": {
            due.PUBLICATION_ID: {
                "release_candidate_sha256": due.EXPECTED_CANDIDATE_DIGEST,
                "provider_payload_sha256": due.EXPECTED_PAYLOAD_SHA256,
                "state": "pending",
                "provider_effect": "impossible",
                "intent_id": None,
                "message_id": None,
            }
        },
    }
    ledger = {
        "release_id": due.PUBLICATION_ID,
        "release_digest": due.EXPECTED_RELEASE_DIGEST,
        "entries": {
            due.PUBLICATION_ID: {
                "provider_payload_sha256": due.EXPECTED_PAYLOAD_SHA256,
                "state": "pending",
                "provider_effect": "impossible",
                "intent_id": None,
                "message_id": None,
            }
        },
    }
    return ledger, index


def test_exact_authorized_release_is_pinned_without_provider_access() -> None:
    due.require_exact_release()
    assert due.EXPECTED_RELEASE_DIGEST.startswith("sha256:")
    assert due.EXPECTED_MEDIA_SHA256 == ("sha256:3b680fe94b5007daea9860eeaf16159abf17712887fa3b1714511b48b84143d7")


def test_manual_test_event_is_permanently_provider_inert() -> None:
    ledger, index = _state()
    assert due.dispatch_decision(ledger, index, event="workflow_dispatch", now=due.SLOT_UTC) is False


def test_schedule_only_dispatches_inside_exact_window() -> None:
    ledger, index = _state()
    assert due.dispatch_decision(ledger, index, event="schedule", now=due.SLOT_UTC + timedelta(minutes=7)) is True
    for now in (due.SLOT_UTC - timedelta(seconds=1), due.EXPIRY_UTC):
        with pytest.raises(ValueError, match="window is not open"):
            due.dispatch_decision(ledger, index, event="schedule", now=now)


@pytest.mark.parametrize("bad", ["unknown", "dispatching", "failed", "skipped"])
def test_no_unverified_or_started_state_can_dispatch(bad: str) -> None:
    ledger, index = _state()
    ledger["entries"][due.PUBLICATION_ID]["state"] = bad
    with pytest.raises(ValueError, match="unknown effect"):
        due.dispatch_decision(ledger, index, event="schedule", now=due.SLOT_UTC + timedelta(minutes=7))


def test_existing_verified_provider_receipt_is_idempotent() -> None:
    ledger, index = _state()
    for entry in (
        ledger["entries"][due.PUBLICATION_ID],
        index["entries"][due.PUBLICATION_ID],
    ):
        entry["state"] = "published"
        entry["provider_effect"] = "verified"
        entry["message_id"] = 27
    assert due.dispatch_decision(ledger, index, event="schedule", now=due.SLOT_UTC + timedelta(minutes=10)) is False


def test_inconsistent_receipt_refuses_dispatch() -> None:
    ledger, index = _state()
    entry = ledger["entries"][due.PUBLICATION_ID]
    entry["state"] = "published"
    entry["provider_effect"] = "verified"
    entry["message_id"] = 27
    with pytest.raises(ValueError, match="no exact confirmed Telegram receipt"):
        due.dispatch_decision(ledger, index, event="schedule", now=due.SLOT_UTC + timedelta(minutes=7))


def test_state_hash_change_refuses_dispatch() -> None:
    ledger, index = _state()
    index["entries"][due.PUBLICATION_ID]["provider_payload_sha256"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="binding drifted"):
        due.dispatch_decision(ledger, index, event="schedule", now=due.SLOT_UTC + timedelta(minutes=7))


def test_one_shot_workflow_contains_no_direct_provider_dispatch() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "cron:" in text and "7 8 7 11 *" in text
    assert "on:" in text and "workflow_dispatch:" in text
    assert "github.event_name == 'schedule'" in text
    assert "steps.gate.outputs.dispatch == 'true'" in text
    assert "milovi-telegram-feed-publisher.yml" in text
    assert "operation=publish" in text
    assert "PUBLISH:@MiloviCake:milovi-feed-20261107-002" in text
    assert "state/milovi-cake-telegram" in text
    assert "telegram_multichannel_cli send-once" not in text
    assert "MILOVI_CAKE_TELEGRAM_BOT_TOKEN" not in text
    assert "curl api.telegram.org" not in text
