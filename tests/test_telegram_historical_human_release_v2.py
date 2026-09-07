from __future__ import annotations

from pathlib import Path

from video_channel_manager.telegram_historical_production import (
    EDITORIAL_APPROVED_FIELD,
    TRANSPORT_VERIFIED_FIELD,
    load_release,
    new_ledger,
)

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "content/telegram/lordchrist/historical-editorial/v1/production-release-2026-09-cycle-02.json"
WORKFLOW = ROOT / ".github/workflows/lordchrist-telegram-poster.yml"
APPROVAL_WORKFLOW = ROOT / ".github/workflows/lordchrist-historical-editorial-approval.yml"


def test_human_release_v2_is_exactly_sealed_and_two_phase() -> None:
    release, queue, _registry, _profile, aux = load_release(RELEASE, ROOT)

    assert release["release_id"] == "lordchrist-history-cycle-2026-09-14-human-v2-live-v1"
    assert release["cycle_id"] == "history-cycle-2026-09-14-v2"
    assert release["editorial_approval_required"] is True
    assert release["canary_out_of_band"] is True
    assert release["canary_publication_id"] == "lordchrist-history-spurgeon-down-grade-1887-v2"
    assert tuple(release["recurring_publication_ids"]) == tuple(release["publication_ids"])[1:]
    assert tuple(release["recurring_scheduled_dates_moscow"]) == (
        "2026-09-14",
        "2026-09-16",
        "2026-09-19",
        "2026-09-21",
        "2026-09-23",
        "2026-09-26",
        "2026-09-28",
        "2026-09-30",
    )
    assert tuple(aux["planned_dates"]) == (
        None,
        "2026-09-14",
        "2026-09-16",
        "2026-09-19",
        "2026-09-21",
        "2026-09-23",
        "2026-09-26",
        "2026-09-28",
        "2026-09-30",
    )
    assert tuple(release["publication_ids"]) == tuple(post.publication_id for post in queue.posts)

    ledger = new_ledger(release, queue, tuple(aux["planned_dates"]))
    assert ledger["canary_verified_at_utc"] is None
    assert ledger[TRANSPORT_VERIFIED_FIELD] is None
    assert ledger[EDITORIAL_APPROVED_FIELD] is None
    assert ledger["entries"][release["canary_publication_id"]]["scheduled_date_moscow"] is None
    assert all(entry["state"] == "pending" for entry in ledger["entries"].values())


def test_human_release_v2_second_pass_is_bound_to_all_new_publication_ids() -> None:
    release, _queue, _registry, _profile, aux = load_release(RELEASE, ROOT)
    verification = aux["verification"]

    assert verification["cycle_id"] == release["cycle_id"]
    assert verification["second_pass_reviewed_urls"] == 50
    assert verification["second_pass_unique_urls"] == 50
    assert verification["impact_counts"] == {"confirm": 31, "deepen": 16, "qualify": 3}
    assert set(verification["post_coverage"]) == set(release["publication_ids"])
    assert all(verification["post_coverage"][publication_id] >= 3 for publication_id in release["publication_ids"])


def test_unified_writer_is_bound_to_exact_v2_release_and_canary() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "production-release-2026-09-cycle-02.json" in workflow
    assert "production-release-2026-09-cycle-01.json" not in workflow
    assert '[[ "$expected_publication_id" == "lordchrist-history-spurgeon-down-grade-1887-v2" ]]' in workflow
    assert workflow.count("group: lordchrist-telegram-publisher") == 1
    assert "telegram_historical_production send" in workflow


def test_editorial_approval_workflow_is_provider_free_and_shares_writer_lock() -> None:
    workflow = APPROVAL_WORKFLOW.read_text(encoding="utf-8")
    assert "group: lordchrist-telegram-publisher" in workflow
    assert "production-release-2026-09-cycle-02.json" in workflow
    assert "telegram_historical_production approve-canary" in workflow
    assert "LORDCHRIST_TELEGRAM_BOT_TOKEN" not in workflow
    assert "telegram_historical_production send" not in workflow
    assert "sendRichMessage" not in workflow
