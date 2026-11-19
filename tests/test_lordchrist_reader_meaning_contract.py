"""Provider-inert guard for @lordchrist reader-meaning audit and document routing.

This tests the provenance and coverage of a human-readable triage report;
it cannot automatically certify exegesis, translation, rights or publishability.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content/telegram/lordchrist"
REPORT = ROOT / "docs/audits/2026-11-19-lordchrist-quote-v6-reader-meaning-audit.json"
SOURCE = ROOT / "docs/audits/2026-11-06-lordchrist-quote-v6-provider-payload-candidate-inert.json"

ROUTED = (
    "AGENTS.md",
    "README.md",
    "QUOTE_SHORT_LANE_STANDARD.md",
    "RICH_EDITORIAL_STANDARD.md",
    "RICH_EDITOR_ARTICLE_STANDARD.md",
    "TELEGRAPH_ARTICLE_STANDARD.md",
)
ALLOWED = {"PASS_MEANING", "REVIEW_REQUIRED", "HOLD_MEANING"}


def test_all_30_active_quote_cards_are_explicitly_triaged_without_release_mutation() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    report = json.loads(REPORT.read_text(encoding="utf-8"))

    rows = report["entries"]
    assert len(source["items"]) == len(rows) == 30
    assert [x["publication_id"] for x in rows] == [x["publication_id"] for x in source["items"]]
    assert [x["sequence"] for x in rows] == list(range(1, 31))
    assert {x["semantic_triage"] for x in rows} == ALLOWED
    assert all(x["reader_finding_ru"] and x["next_editorial_action_ru"] for x in rows)
    assert all(x["independent_bilingual_review"] == "not_proven_by_this_audit" for x in rows)
    assert all(x["release_approval_from_this_audit"] is False for x in rows)

    for item, row in zip(source["items"], rows, strict=True):
        assert row["source_url"] == item["source_url"]
        assert row["source_english_anchor_start"] == item["source_anchors"]["start"]
        assert row["observed_status"] in {"published", "pending"}
        assert row["observed_provider_effect"] in {"verified", "impossible"}
        if row["observed_status"] == "published":
            assert isinstance(row["observed_message_id"], int) and row["observed_message_id"] > 0
        else:
            assert row["observed_message_id"] is None

    statuses = report["status_counts"]
    assert statuses["published_verified"] + statuses["pending"] == 30
    for verdict in ALLOWED:
        assert statuses[verdict] == sum(x["semantic_triage"] == verdict for x in rows)
    assert rows[13]["publication_id"] == "lordchrist-edwards-sinners-in-hands"
    assert rows[13]["semantic_triage"] == "HOLD_MEANING"

    data = SOURCE.read_bytes()
    actual_blob = hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data,
        usedforsecurity=False,
    ).hexdigest()
    assert report["source_candidate_blob_sha"] == actual_blob


def test_reader_meaning_contract_is_routed_to_each_editorial_lane() -> None:
    name = "SEMANTIC_CLARITY_AND_CONTEXT_STANDARD.md"
    standard = (CONTENT / name).read_text(encoding="utf-8")
    for required in (
        "PASS_MEANING",
        "REVIEW_REQUIRED",
        "HOLD_MEANING",
        "reader_thesis",
        "reasoning_link",
        "reader_misreading",
        "прав",
        "перв",
        "quote-v6",
        "L1",
        "L2",
        "L3",
    ):
        assert required in standard, required

    for file in ROUTED:
        text = (CONTENT / file).read_text(encoding="utf-8")
        assert name in text, file
    assert "source_candidate_path" in REPORT.read_text(encoding="utf-8")
