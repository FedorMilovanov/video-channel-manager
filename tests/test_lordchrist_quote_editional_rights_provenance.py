"""Versioned edition-rights research must not implicitly authorize Telegram publication."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDITS = ROOT / "docs" / "audits"
REPORT = AUDITS / "2026-11-06-lordchrist-30-edition-rights-provenance-v1.json"
INDEX = AUDITS / "2026-11-05-lordchrist-30-quote-editorial-candidate-index-v5.json"
PREVIEW = AUDITS / "2026-11-05-lordchrist-30-card-editorial-preview-v5-inert.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def committed_blob(path: Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    return subprocess.check_output(
        ["git", "rev-parse", f"HEAD:{rel}"], cwd=ROOT, text=True
    ).strip()


def test_rights_research_binds_exact_v5_files_and_all_thirty_cards() -> None:
    report = load(REPORT)
    index = load(INDEX)
    preview = load(PREVIEW)

    assert report["basis_v5_index_git_blob_sha"] == committed_blob(INDEX)
    assert report["basis_v5_preview_git_blob_sha"] == committed_blob(PREVIEW)
    assert len(report["entries"]) == len(index["entries"]) == len(preview["posts"]) == 30
    assert [entry["sequence"] for entry in report["entries"]] == list(range(1, 31))
    assert len({entry["publication_id"] for entry in report["entries"]}) == 30

    for researched, reviewed, card in zip(
        report["entries"], index["entries"], preview["posts"], strict=True
    ):
        assert researched["sequence"] == reviewed["sequence"] == card["sequence"]
        assert researched["publication_id"] == reviewed["original_publication_id"]
        assert researched["candidate_source_url"] == reviewed["candidate_source_url"]
        assert researched["candidate_body_sha256"] == reviewed["candidate_body_sha256"]
        assert researched["work_id"] in report["groups"]
        assert researched["edition_support_url"].startswith("https://")
        assert researched["site_added_material_status"] == "do_not_copy"
        assert researched["clearance_status"] == "not_approved"
        assert researched["provider_write_authorization"] is False


def test_documented_historical_sources_cannot_clear_release_hold() -> None:
    report = load(REPORT)
    for key in (
        "rights_review_complete",
        "full_bilingual_review_complete",
        "editorial_approval",
        "approved_new_queue",
        "provider_write_authorization",
        "legacy_pending_replay_authorized",
    ):
        assert report[key] is False
    assert report["release_hold_active"] is True
    assert report["new_release_digest"] is None
    assert len(report["remaining_approval_gates"]) >= 4

    index = load(INDEX)
    assert index["approved_new_queue"] is False
    assert index["rights_review_complete"] is False
    assert index["provider_write_authorization"] is False
    assert all(entry["eligible_for_release"] is False for entry in index["entries"])


def test_sensitive_edition_and_translation_distinctions_remain_explicit() -> None:
    report = load(REPORT)
    groups = report["groups"]
    assert "1845" in groups["calvin"]["known_historical_publication"]
    assert "1838" in groups["augustine"]["known_historical_publication"]
    assert "1895" in groups["murray"]["known_historical_publication"]
    assert "1918" in groups["kuyper"]["known_historical_publication"]
    assert "1925" in groups["kuyper"]["edition_lineage"]
    assert "1909" in groups["bavinck"]["known_historical_publication"]
    for death_year in ("1912", "1926", "1949"):
        assert death_year in " ".join(report["completed_research_checks"])
    assert report["entries"][11]["work_id"] == "spurgeon-resurrection"
    assert "Acts 24:15" in groups["spurgeon-resurrection"]["edition_lineage"]
