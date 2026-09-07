from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from video_channel_manager.telegram_historical_production import (
    SUCCESSOR_BINDING_SCHEMA,
    _guard_unresolved,
    _validate_second_pass,
    build_document,
    coverage_status,
    decide_scheduled,
    load_release,
    new_ledger,
    release_digest,
)

ROOT = Path(__file__).resolve().parents[1]
RELEASE_PATH = ROOT / "content/telegram/lordchrist/historical-editorial/v1/production-release-2026-09-cycle-01.json"
WORKFLOW_PATH = ROOT / ".github/workflows/lordchrist-telegram-poster.yml"
MOSCOW = ZoneInfo("Europe/Moscow")


def _loaded():
    release, queue, registry, profile_path, aux = load_release(RELEASE_PATH, ROOT)
    return release, queue, registry, profile_path, aux


def _bind_verified_successor_state(ledger: dict, release: dict) -> None:
    ledger["successor_cycle_binding"] = {
        "schema_name": SUCCESSOR_BINDING_SCHEMA,
        "schema_version": 1,
        "current_release_id": release["release_id"],
        "current_release_sha256": release_digest(release),
        "current_cycle_id": release["cycle_id"],
        "successor_cycle_id": "2026-10-cycle-01",
        "successor_manifest_path": "content/telegram/lordchrist/historical-editorial/v1/cycles/2026-10-cycle-01/manifest.json",
        "successor_manifest_git_blob_sha": "0" * 40,
        "successor_queue_sha256": "sha256:" + "1" * 64,
        "successor_source_registry_sha256": "sha256:" + "2" * 64,
        "successor_theology_profile_sha256": "sha256:" + "3" * 64,
        "verified_at_utc": "2026-09-24T10:00:00+00:00",
        "verified_by": "test-suite",
        "provider_write_performed": False,
    }


def test_historical_production_release_is_exact_and_second_pass_is_50_urls() -> None:
    release, queue, registry, profile_path, aux = _loaded()

    assert release["owning_issue"] == 561
    assert release["provider_writes_authorized"] is True
    assert release["activation_policy"] == "verified_canary_then_exact_schedule"
    assert release["max_provider_attempts_per_publication"] == 1
    assert release["blind_mutation_retries"] == 0
    assert release["backfill_policy"] == "none"
    assert release["media_policy"] == "text_only_until_exact_transport_bytes_are_bound"
    assert tuple(release["publication_ids"]) == tuple(post.publication_id for post in queue.posts)
    assert len(queue.posts) == 9
    assert len(registry.sources) == 52
    verification = aux["verification"]
    assert verification["second_pass_reviewed_urls"] == 50
    assert verification["second_pass_unique_urls"] == 50
    assert len(verification["entries"]) == 50
    assert len({entry["url"] for entry in verification["entries"]}) == 50
    assert verification["impact_counts"] == {"confirm": 31, "deepen": 16, "qualify": 3}
    assert tuple(aux["planned_dates"]) == (
        "2026-09-07",
        "2026-09-09",
        "2026-09-12",
        "2026-09-14",
        "2026-09-16",
        "2026-09-19",
        "2026-09-21",
        "2026-09-23",
        "2026-09-26",
    )
    assert profile_path.name == "lordchrist-rich.json"


def test_second_pass_fails_closed_on_duplicate_or_unreviewed_url() -> None:
    release, _queue, _registry, _profile_path, aux = _loaded()
    publication_ids = tuple(release["publication_ids"])
    verification = json.loads(json.dumps(aux["verification"]))
    verification["entries"][1]["url"] = verification["entries"][0]["url"]
    with pytest.raises(ValueError, match="not unique"):
        _validate_second_pass(verification, publication_ids)

    verification = json.loads(json.dumps(aux["verification"]))
    verification["entries"][0]["review_status"] = "discovery_only"
    with pytest.raises(ValueError, match="below A/B\\+ or not reviewed"):
        _validate_second_pass(verification, publication_ids)


def test_first_historical_rich_document_uses_existing_transport_without_media() -> None:
    release, queue, registry, profile_path, aux = _loaded()
    document, render = build_document(
        ROOT,
        release,
        queue,
        registry,
        profile_path,
        aux["target_binding_path"],
        release["canary_publication_id"],
    )

    assert document.publication_id == "lordchrist-history-spurgeon-down-grade"
    assert document.target.chat_id == -1001295216957
    assert document.target.bot_id == 8716602202
    assert document.provider_assigned_media_paths == ()
    assert document.expected_media_sha256 is None
    assert render.media_placeholders == ()
    assert render.provider_assigned_media == ()
    assert render.render_sha256.startswith("sha256:")


def test_scheduler_is_inert_until_canary_is_verified() -> None:
    release, queue, _registry, _profile_path, aux = _loaded()
    planned = tuple(aux["planned_dates"])
    ledger = new_ledger(release, queue, planned)
    decision = decide_scheduled(
        release,
        ledger,
        tuple(release["publication_ids"]),
        planned,
        now=datetime(2026, 9, 9, 19, 20, tzinfo=MOSCOW),
    )
    assert decision.active is False
    assert decision.reason == "canary_not_verified"


def test_scheduler_uses_exact_slot_and_never_backfills_stale_run() -> None:
    release, queue, _registry, _profile_path, aux = _loaded()
    planned = tuple(aux["planned_dates"])
    ids = tuple(release["publication_ids"])
    ledger = new_ledger(release, queue, planned)
    ledger["canary_verified_at_utc"] = "2026-09-07T09:30:00+00:00"
    ledger["entries"][ids[0]].update(
        {
            "state": "published",
            "provider_effect": "verified",
            "published_at_utc": "2026-09-07T09:30:00+00:00",
            "message_id": 2000,
            "message_url": "https://t.me/lordchrist/2000",
        }
    )

    active = decide_scheduled(
        release,
        ledger,
        ids,
        planned,
        now=datetime(2026, 9, 9, 19, 20, tzinfo=MOSCOW),
    )
    assert active.active is True
    assert active.publication_id == ids[1]
    assert active.reason == "active_exact_historical_slot"

    stale = decide_scheduled(
        release,
        ledger,
        ids,
        planned,
        now=datetime(2026, 9, 9, 21, 18, tzinfo=MOSCOW),
    )
    assert stale.active is False
    assert stale.publication_id == ids[1]
    assert stale.reason == "slot_expired_no_backfill"


def test_unresolved_historical_effect_blocks_every_follow_on() -> None:
    release, queue, _registry, _profile_path, aux = _loaded()
    ledger = new_ledger(release, queue, tuple(aux["planned_dates"]))
    first = release["publication_ids"][0]
    ledger["entries"][first].update({"state": "may_exist", "provider_effect": "may_exist"})
    with pytest.raises(ValueError, match="unresolved historical provider state blocks writer"):
        _guard_unresolved(ledger)


def test_confirmed_no_effect_is_terminal_for_identity_but_not_global_writer_block() -> None:
    release, queue, _registry, _profile_path, aux = _loaded()
    ledger = new_ledger(release, queue, tuple(aux["planned_dates"]))
    second = release["publication_ids"][1]
    ledger["entries"][second].update(
        {
            "state": "failed_no_effect",
            "provider_effect": "confirmed_absent",
            "error": "provider proved no effect",
        }
    )

    _guard_unresolved(ledger)
    assert ledger["entries"][second]["state"] == "failed_no_effect"


def test_replenishment_gate_uses_durable_successor_binding_without_mutating_release() -> None:
    release, queue, _registry, _profile_path, aux = _loaded()
    planned = tuple(aux["planned_dates"])
    ids = tuple(release["publication_ids"])
    ledger = new_ledger(release, queue, planned)
    ledger["canary_verified_at_utc"] = "2026-09-07T09:30:00+00:00"
    for index, publication_id in enumerate(ids[:-1], start=1):
        ledger["entries"][publication_id].update(
            {
                "state": "published",
                "provider_effect": "verified",
                "published_at_utc": f"2026-09-{7 + index:02d}T10:00:00+00:00",
                "message_id": 2000 + index,
                "message_url": f"https://t.me/lordchrist/{2000 + index}",
            }
        )

    original_release_digest = release_digest(release)
    coverage = coverage_status(release, ledger)
    assert coverage["pending_count"] == 1
    assert coverage["exhaustion_block_active"] is True

    blocked = decide_scheduled(
        release,
        ledger,
        ids,
        planned,
        now=datetime(2026, 9, 26, 19, 20, tzinfo=MOSCOW),
    )
    assert blocked.active is False
    assert blocked.reason == "successor_cycle_required_before_exhaustion"

    _bind_verified_successor_state(ledger, release)
    unblocked = decide_scheduled(
        release,
        ledger,
        ids,
        planned,
        now=datetime(2026, 9, 26, 19, 20, tzinfo=MOSCOW),
    )
    assert unblocked.active is True
    assert unblocked.publication_id == ids[-1]
    assert release_digest(release) == original_release_digest
    assert coverage_status(release, ledger)["successor_cycle_verified"] is True


def test_non_slot_day_is_provider_inert() -> None:
    release, queue, _registry, _profile_path, aux = _loaded()
    planned = tuple(aux["planned_dates"])
    ledger = new_ledger(release, queue, planned)
    ledger["canary_verified_at_utc"] = "2026-09-07T09:30:00+00:00"
    decision = decide_scheduled(
        release,
        ledger,
        tuple(release["publication_ids"]),
        planned,
        now=datetime(2026, 9, 10, 19, 20, tzinfo=MOSCOW),
    )
    assert decision.active is False
    assert decision.reason == "no_historical_slot_today"


def test_historical_lane_is_routed_through_existing_single_writer_workflow() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "group: lordchrist-telegram-publisher" in workflow
    assert workflow.count("group: lordchrist-telegram-publisher") == 1
    assert '- cron: "17 9 * * *"' in workflow
    assert '- cron: "17 19 * * 1,3,6"' in workflow
    assert '- cron: "17 21 * * 2,5,0"' in workflow
    assert "historical-rich:" in workflow
    assert "telegram_historical_production prepare" in workflow
    assert "telegram_historical_production send" in workflow
    assert "telegram_historical_production apply" in workflow
    assert "startsWith(inputs.publication_id, 'lordchrist-history-')" in workflow
    assert "Persist historical intent before sendRichMessage" in workflow
    assert "Archive exact historical provider outcome before durable result mutation" in workflow
    assert "blind retry is forbidden" in workflow.lower()
