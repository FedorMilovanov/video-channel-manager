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


def test_human_release_v2_is_exactly_sealed_and_two_phase() -> None:
    release, queue, _registry, _profile, aux = load_release(RELEASE, ROOT)

    assert release["release_id"] == "lordchrist-history-cycle-2026-09-14-human-v2-live-v1"
    assert release["cycle_id"] == "history-cycle-2026-09-14-v2"
    assert release["editorial_approval_required"] is True
    assert release["canary_publication_id"] == "lordchrist-history-spurgeon-down-grade-1887-v2"
    assert tuple(aux["planned_dates"]) == (
        "2026-09-14",
        "2026-09-16",
        "2026-09-19",
        "2026-09-21",
        "2026-09-23",
        "2026-09-26",
        "2026-09-28",
        "2026-09-30",
        "2026-10-03",
    )
    assert tuple(release["publication_ids"]) == tuple(post.publication_id for post in queue.posts)

    ledger = new_ledger(release, queue, tuple(aux["planned_dates"]))
    assert ledger["canary_verified_at_utc"] is None
    assert ledger[TRANSPORT_VERIFIED_FIELD] is None
    assert ledger[EDITORIAL_APPROVED_FIELD] is None
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
