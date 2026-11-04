"""Inert source-discovery metadata, not Instagram performance or licensing proof."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "docs/audits/2026-11-04-lord-god-20-youtube-source-views-and-duration-readonly.json"
QUEUE = ROOT / "content/instagram/lord-god-strength-shorts-sermons-intake-20261104.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_all_twenty_selected_public_sources_have_exact_playable_metadata() -> None:
    stats = load(SNAPSHOT)
    queue = load(QUEUE)
    records = stats["records"]
    cards = queue["candidates"]
    assert stats["schema_name"] == "video-manager.lordgod-public-youtube-source-stats-readonly"
    assert stats["project_key"] == queue["project_key"] == "lord-god-strength"
    assert stats["count"] == stats["complete_public_player_metadata_count"] == 20
    assert stats["unavailable_count"] == 0
    assert len(records) == len(cards) == 20
    assert len({x["id"] for x in records}) == 20
    assert [x["id"] for x in records] == [x["source_video_id"] for x in cards]
    assert [x["surface"] for x in records] == [x["source_surface"] for x in cards]
    assert Counter(x["surface"] for x in records) == {"shorts": 12, "videos": 8}
    assert queue["public_youtube_player_metadata_verified_count"] == 20
    assert queue["public_youtube_player_metadata_snapshot_file"] == SNAPSHOT.relative_to(ROOT).as_posix()
    assert stats["source_intake_file"] == QUEUE.relative_to(ROOT).as_posix()
    assert stats["observed_utc"]
    for row, card in zip(records, cards, strict=True):
        assert row["id"] == card["source_video_id"]
        assert row["http"] == 200
        assert row["playability"] == "OK"
        assert row["channel"] == "Fedor Milovanov"
        assert row["seconds"] >= 30
        assert row["viewCount"] >= 0
        assert row["date"]
        assert row["age_days_at_snapshot"] > 0
        assert row["views_per_day_proxy"] >= 0
        assert row["source_title"] == card["source_title"]
        assert not row.get("error")


def test_lifetime_youtube_views_cannot_be_read_as_instagram_results() -> None:
    stats = load(SNAPSHOT)
    records = {row["id"]: row for row in stats["records"]}
    assert records["80URgbTDMWU"]["viewCount"] == 9000
    assert records["80URgbTDMWU"]["seconds"] == 147
    assert records["lTRm2NbnIas"]["viewCount"] == 4257
    assert records["lTRm2NbnIas"]["seconds"] == 144
    assert records["HReIPJILr5E"]["seconds"] == 293
    assert records["ehIvvZsP_tQ"]["seconds"] == 385
    assert stats["ranking_method"].startswith("lifetime_views_divided_by_elapsed_days")
    assert stats["actual_engagement_on_instagram_unverified"] is True
    assert stats["instagram_post_presence_verified"] is False
    assert "NOT real-time trend or IG forecast" in stats["ranking_method"]
    assert stats["source_evidence_scope"].startswith("public first-page selected twenty")
    assert stats["owner_youtube_oauth_verification_complete"] is False


def test_social_source_metadata_is_not_a_copyright_or_upload_license() -> None:
    stats = load(SNAPSHOT)
    queue = load(QUEUE)
    assert stats["candidate_outcome"] == "read_only_evidence_only"
    assert stats["provider_writes_authorized"] is False
    assert stats["source_rights_clearance_count"] == 0
    assert queue["instagram_professional_account_id"] is None
    assert queue["provider_writes_authorized"] is False
    assert queue["ready_to_publish_count"] == 0
    assert queue["source_specific_rights_cleared_count"] == 0
    assert queue["publication_release_id"] is None
    assert all(x["ready_to_publish"] is False for x in queue["candidates"])
    assert all(x["provider_writes_authorized"] is False for x in queue["candidates"])
