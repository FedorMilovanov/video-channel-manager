"""Provider-inert integrity tests for 18 quote-v6 English primary-source locators.

A located English opening anchor is not a rights clearance, a final Russian
translation check, a reviewed release or an authorization to post.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/audits/2026-11-06-lordchrist-quote-v6-provider-payload-candidate-inert.json"
TRIAGE = ROOT / "docs/audits/2026-11-19-lordchrist-quote-v6-reader-meaning-audit.json"
LOCATORS = ROOT / "docs/audits/2026-11-20-lordchrist-v6-18-pending-source-locator-audit-inert.json"
EXPECTED_PENDING = {9, 12, *range(15, 31)}


def _git_blob_hash(data: bytes) -> str:
    canonical = data.replace(b"\r\n", b"\n")
    return hashlib.sha1(
        b"blob " + str(len(canonical)).encode("ascii") + b"\0" + canonical,
        usedforsecurity=False,
    ).hexdigest()


def test_all_18_pending_citations_have_source_locator_evidence_without_false_release_approval() -> None:
    data = json.loads(LOCATORS.read_text(encoding="utf-8"))
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    triage = json.loads(TRIAGE.read_text(encoding="utf-8"))
    by_source = {item["publication_id"]: item for item in source["items"]}
    by_review = {item["publication_id"]: item for item in triage["entries"]}

    assert data["source_candidate_blob_sha"] == _git_blob_hash(SOURCE.read_bytes())
    assert data["reviewed_meaning_triage_blob_sha"] == _git_blob_hash(TRIAGE.read_bytes())
    assert data["publication_authorized"] is False
    assert data["changes_to_immutable_release"] is False
    assert data["rights_cleared_by_this_audit"] is False
    assert len(data["entries"]) == 18
    assert {item["sequence"] for item in data["entries"]} == EXPECTED_PENDING
    assert len({item["publication_id"] for item in data["entries"]}) == 18
    for entry in data["entries"]:
        orig = by_source[entry["publication_id"]]
        review = by_review[entry["publication_id"]]
        assert entry["sequence"] == orig["sequence"]
        assert entry["original_english_source_url"] == orig["source_url"]
        assert entry["original_english_opening_anchor"] == orig["source_anchors"]["start"]
        assert entry["editorial_meaning_risk"] == review["semantic_triage"]
        assert entry["opening_anchor_located_on_source_page"] is True
        assert entry["full_original_span_collated_against_russian"] is False
        assert entry["translation_authority"] == "not_documented"
        assert entry["russian_translation_rights"] == "not_cleared"
        assert entry["independent_editor_approved"] is False
        assert entry["activation_approved"] is False
        assert entry["release_mutation_authorized"] is False
        assert len(entry["reader_thesis_ru"]) > 50
        assert len(entry["revision_direction_ru"]) > 45
        canonical = urlparse(entry["verified_reader_source_url"])
        assert canonical.scheme == "https"
        assert canonical.netloc in {"ccel.org", "www.ccel.org", "www.spurgeon.org"}

    corrected = next(x for x in data["entries"] if x["publication_id"] == "lordchrist-matthew-henry-heart-work")
    assert corrected["source_url_status"] == "historical_url_and_alternative_both_retrieved_same_work_and_anchor"
    assert corrected["original_english_source_url"].endswith("/henry/mhc3.Ps.cxx.html")
    assert corrected["verified_reader_source_url"] == corrected["original_english_source_url"]
    assert corrected["alternative_retrieved_reader_source_url"].endswith("/henry/mhc3/mhc3.Ps.cxx.html")
    assert corrected["original_source_url_retrieved"] is True
    assert corrected["source_url_rebind_required"] is False
    proof = corrected["url_equivalence_evidence"]
    assert proof["original_english_anchor_matches_both"] is True
    assert proof["both_present_matthew_henry_commentary_on_psalm_119_45_48"] is True
    correction = data["correction_notice"]
    assert correction["historical_url_remains_valid"] is True
    assert correction["release_mutated"] is False
    assert correction["ledger_mutated"] is False
    assert sum(x["editorial_meaning_risk"] == "HOLD_MEANING" for x in data["entries"]) == 4
