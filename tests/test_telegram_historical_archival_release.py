from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from video_channel_manager.telegram_historical_archival_release import (
    EXPECTED_DATES,
    EXPECTED_PUBLICATION_IDS,
    sync_external_canary,
)
from video_channel_manager.telegram_historical_production import (
    build_document,
    decide_scheduled,
    load_ledger,
    load_release,
    new_ledger,
)

ROOT = Path(__file__).resolve().parents[1]
RELEASE_PATH = (
    ROOT
    / "content/telegram/lordchrist/historical-editorial/v1/production-release-2026-09-cycle-02-v3-archival.json"
)
WORKFLOW_PATH = ROOT / ".github/workflows/lordchrist-telegram-poster.yml"
MOSCOW = ZoneInfo("Europe/Moscow")

LEGACY_CANARY_ID = "lordchrist-history-spurgeon-down-grade-1887-v2"
LEGACY_RECURRING_IDS = (
    "lordchrist-history-bunyan-bedford-prison-v2",
    "lordchrist-history-judson-burmese-bible-v2",
    "lordchrist-history-spurgeon-cholera-1854-v2",
    "lordchrist-history-carey-enquiry-missions-v2",
    "lordchrist-history-fuller-gospel-worthy-v2",
    "lordchrist-history-tyndale-new-testament-1526-v2",
    "lordchrist-history-stam-china-december-1934-v2",
    "lordchrist-history-sattler-schleitheim-1527-v2",
)


def _loaded():
    return load_release(RELEASE_PATH, ROOT)


def _legacy_v2_ledger() -> dict[str, object]:
    entries: dict[str, object] = {
        LEGACY_CANARY_ID: {
            "publication_id": LEGACY_CANARY_ID,
            "sequence": 1,
            "scheduled_date_moscow": "2026-09-07",
            "state": "published",
            "provider_effect": "verified",
            "dispatch_mode": "manual_canary",
            "workflow_run_id": "34161758154",
            "workflow_run_attempt": "1",
            "github_sha": "9eb93e63f1b987c9e141bbb8377189f6baad313f",
            "document_sha256": "sha256:" + "1" * 64,
            "intent_created_at_utc": "2026-09-07T21:05:16+00:00",
            "published_at_utc": "2026-09-07T21:05:22+00:00",
            "message_id": 1515,
            "message_url": "https://t.me/lordchrist/1515",
            "error": None,
        }
    }
    for index, (publication_id, scheduled_date) in enumerate(
        zip(LEGACY_RECURRING_IDS, EXPECTED_DATES, strict=True),
        start=2,
    ):
        entries[publication_id] = {
            "publication_id": publication_id,
            "sequence": index,
            "scheduled_date_moscow": scheduled_date,
            "state": "pending",
            "provider_effect": "impossible",
            "dispatch_mode": None,
            "workflow_run_id": None,
            "workflow_run_attempt": None,
            "github_sha": None,
            "document_sha256": None,
            "intent_created_at_utc": None,
            "published_at_utc": None,
            "message_id": None,
            "message_url": None,
            "error": None,
        }
    return {
        "schema_name": "video-channel-manager.telegram-historical-production-ledger",
        "schema_version": 1,
        "release_id": "lordchrist-history-cycle-2026-09-14-human-v2-live-v1",
        "release_sha256": "sha256:" + "2" * 64,
        "owning_issue": 561,
        "project_key": "lord-god-strength",
        "channel_username": "@lordchrist",
        "cycle_id": "history-cycle-2026-09-14-v2",
        "canary_publication_id": LEGACY_CANARY_ID,
        "canary_verified_at_utc": None,
        "successor_cycle_binding": None,
        "entries": entries,
    }


def _canary_witness(*, approved: bool, message_id: int = 1516) -> dict[str, object]:
    approved_at = "2026-09-10T09:00:00+00:00" if approved else None
    return {
        "schema_name": "video-channel-manager.telegram-historical-production-ledger",
        "schema_version": 1,
        "release_id": "lordchrist-history-spurgeon-down-grade-1887-v3-media-live-v1",
        "owning_issue": 561,
        "project_key": "lord-god-strength",
        "channel_username": "@lordchrist",
        "cycle_id": "history-cycle-spurgeon-v3-media-canary-2026-09-08",
        "canary_publication_id": "lordchrist-history-spurgeon-down-grade-1887-v3",
        "canary_verified_at_utc": approved_at,
        "successor_cycle_binding": None,
        "entries": {
            "lordchrist-history-spurgeon-down-grade-1887-v3": {
                "publication_id": "lordchrist-history-spurgeon-down-grade-1887-v3",
                "state": "published",
                "provider_effect": "verified",
                "message_id": message_id,
            }
        },
        "canary_transport_verified_at_utc": "2026-09-08T18:20:49.312774+00:00",
        "canary_editorial_approved_at_utc": approved_at,
        "canary_editorial_approved_by": "owner" if approved else None,
    }


def test_archival_v3_release_is_exact_and_canary_is_outside_recurring_queue() -> None:
    release, queue, registry, profile_path, aux = _loaded()

    assert release["schema_name"] == "video-channel-manager.telegram-historical-archival-live-release"
    assert release["provider_writes_authorized"] is True
    assert release["external_editorial_approval_required"] is True
    assert release["canary_publication_id"] == "lordchrist-history-spurgeon-down-grade-1887-v3"
    assert tuple(release["publication_ids"]) == EXPECTED_PUBLICATION_IDS
    assert tuple(release["recurring_publication_ids"]) == EXPECTED_PUBLICATION_IDS
    assert tuple(aux["planned_dates"]) == EXPECTED_DATES
    assert release["canary_publication_id"] not in release["publication_ids"]
    assert len(queue.posts) == 8
    assert tuple(post.publication_id for post in queue.posts) == EXPECTED_PUBLICATION_IDS
    assert set(registry.packages) == set(EXPECTED_PUBLICATION_IDS)
    assert all(len(package.archival_media) == 2 for package in registry.packages.values())
    assert profile_path.name == "lordchrist-rich.json"

    document, render = build_document(
        ROOT,
        release,
        queue,
        registry,
        profile_path,
        aux["target_binding_path"],
        EXPECTED_PUBLICATION_IDS[0],
    )
    assert document.publication_id == EXPECTED_PUBLICATION_IDS[0]
    assert len(document.provider_assigned_media_paths) == 2
    assert document.expected_media_sha256 is not None
    assert render.media_placeholders == ()
    assert len(render.provider_assigned_media) == 2
    assert "Граница доказательств" not in render.visible_text
    assert "Богословская оценка" not in render.visible_text
    assert queue.posts[0].evidence_boundary not in render.visible_text
    assert queue.posts[0].theology_review.editorial_evaluation in render.visible_text
    assert registry.sources[EXPECTED_PUBLICATION_IDS[0]][0].title in render.visible_text


def test_v2_state_migrates_only_when_all_recurring_rows_are_provider_inert(tmp_path: Path) -> None:
    release, queue, _registry, _profile_path, aux = _loaded()
    planned_dates = tuple(aux["planned_dates"])
    ledger_path = tmp_path / "publication-ledger.json"
    ledger_path.write_text(json.dumps(_legacy_v2_ledger(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    migrated = load_ledger(ledger_path, release, queue, planned_dates)
    assert migrated["release_id"] == release["release_id"]
    assert migrated["cycle_id"] == release["cycle_id"]
    assert migrated["canary_publication_id"] == "lordchrist-history-spurgeon-down-grade-1887-v3"
    assert migrated["canary_verified_at_utc"] is None
    assert tuple(migrated["entries"]) == EXPECTED_PUBLICATION_IDS
    assert [row["sequence"] for row in migrated["entries"].values()] == list(range(1, 9))
    assert all(row["state"] == "pending" for row in migrated["entries"].values())
    assert all(row["provider_effect"] == "impossible" for row in migrated["entries"].values())

    ledger_path.write_text(json.dumps(migrated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    reloaded = load_ledger(ledger_path, release, queue, planned_dates)
    assert reloaded == migrated

    unsafe = _legacy_v2_ledger()
    first = unsafe["entries"][LEGACY_RECURRING_IDS[0]]
    first["state"] = "published"
    first["provider_effect"] = "verified"
    first["message_id"] = 1517
    ledger_path.write_text(json.dumps(unsafe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no longer safely migratable"):
        load_ledger(ledger_path, release, queue, planned_dates)


def test_external_canary_message_1516_does_not_arm_schedule_before_editorial_approval() -> None:
    release, queue, _registry, _profile_path, aux = _loaded()
    ledger = new_ledger(release, queue, tuple(aux["planned_dates"]))

    ledger, active = sync_external_canary(ledger, release, _canary_witness(approved=False))
    assert active is False
    assert ledger["canary_verified_at_utc"] is None

    decision = decide_scheduled(
        ROOT,
        release,
        ledger,
        EXPECTED_PUBLICATION_IDS,
        EXPECTED_DATES,
        now=datetime(2026, 9, 14, 19, 20, tzinfo=MOSCOW),
    )
    assert decision.active is False
    assert decision.reason == "canary_not_verified"

    ledger, active = sync_external_canary(ledger, release, _canary_witness(approved=True))
    assert active is True
    assert ledger["canary_verified_at_utc"] == "2026-09-10T09:00:00+00:00"

    decision = decide_scheduled(
        ROOT,
        release,
        ledger,
        EXPECTED_PUBLICATION_IDS,
        EXPECTED_DATES,
        now=datetime(2026, 9, 14, 19, 20, tzinfo=MOSCOW),
    )
    assert decision.active is True
    assert decision.publication_id == EXPECTED_PUBLICATION_IDS[0]
    assert decision.reason == "active_exact_historical_slot"


def test_external_canary_gate_fails_closed_on_wrong_message_identity() -> None:
    release, queue, _registry, _profile_path, aux = _loaded()
    ledger = new_ledger(release, queue, tuple(aux["planned_dates"]))

    with pytest.raises(ValueError, match="message 1516 evidence"):
        sync_external_canary(ledger, release, _canary_witness(approved=True, message_id=1517))


def test_archival_rollout_reuses_existing_single_writer_without_new_workflow() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert workflow.count("group: lordchrist-telegram-publisher") == 1
    assert "historical-rich:" in workflow
    assert "production-release-2026-09-cycle-02.json" in workflow
    assert "telegram_historical_production prepare" in workflow
    assert "Persist historical intent before sendRichMessage" in workflow
    assert "Archive exact historical provider outcome before durable result mutation" in workflow
