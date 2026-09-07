from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from video_channel_manager.telegram_historical_production import (
    EDITORIAL_APPROVED_BY_FIELD,
    EDITORIAL_APPROVED_FIELD,
    TRANSPORT_VERIFIED_FIELD,
    approve_canary,
    decide_scheduled,
    load_release,
    new_ledger,
)

ROOT = Path(__file__).resolve().parents[1]
RELEASE_PATH = ROOT / "content/telegram/lordchrist/historical-editorial/v1/production-release-2026-09-cycle-02.json"


def _transport_verified_v2_ledger():
    release, queue, _registry, _profile_path, aux = load_release(RELEASE_PATH, ROOT)
    planned = tuple(aux["planned_dates"])
    ledger = new_ledger(release, queue, planned)
    canary_id = str(release["canary_publication_id"])
    ledger["entries"][canary_id].update(
        {
            "state": "published",
            "provider_effect": "verified",
            "dispatch_mode": "manual_canary",
            "published_at_utc": "2026-09-07T13:41:36+00:00",
            "message_id": 4242,
            "message_url": "https://t.me/lordchrist/4242",
        }
    )
    ledger[TRANSPORT_VERIFIED_FIELD] = "2026-09-07T13:41:36+00:00"
    return release, queue, planned, ledger


def test_transport_verified_canary_does_not_arm_schedule_before_editorial_approval() -> None:
    release, queue, planned, ledger = _transport_verified_v2_ledger()

    assert ledger["canary_verified_at_utc"] is None
    assert ledger[EDITORIAL_APPROVED_FIELD] is None
    decision = decide_scheduled(
        ROOT,
        release,
        ledger,
        tuple(post.publication_id for post in queue.posts),
        planned,
        now=datetime.fromisoformat("2026-09-14T19:20:00+03:00"),
    )
    assert decision.active is False
    assert decision.reason == "canary_not_verified"


def test_exact_provider_free_editorial_approval_arms_first_recurring_slot_without_backfill() -> None:
    release, queue, planned, ledger = _transport_verified_v2_ledger()

    approved = approve_canary(
        ledger,
        release,
        expected_message_id=4242,
        approved_by="owner-review",
        now=datetime.fromisoformat("2026-09-08T12:00:00+00:00"),
    )
    assert approved[EDITORIAL_APPROVED_FIELD] == "2026-09-08T12:00:00+00:00"
    assert approved[EDITORIAL_APPROVED_BY_FIELD] == "owner-review"
    assert approved["canary_verified_at_utc"] == approved[EDITORIAL_APPROVED_FIELD]

    decision = decide_scheduled(
        ROOT,
        release,
        approved,
        tuple(post.publication_id for post in queue.posts),
        planned,
        now=datetime.fromisoformat("2026-09-14T19:20:00+03:00"),
    )
    assert decision.active is True
    assert decision.publication_id == release["recurring_publication_ids"][0]
    assert decision.publication_id == "lordchrist-history-bunyan-bedford-prison-v2"
    assert decision.reason == "active_exact_historical_slot"


def test_editorial_approval_rejects_message_id_not_in_durable_provider_evidence() -> None:
    release, _queue, _planned, ledger = _transport_verified_v2_ledger()

    with pytest.raises(ValueError, match="message id differs"):
        approve_canary(
            ledger,
            release,
            expected_message_id=9999,
            approved_by="owner-review",
        )
