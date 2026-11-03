"""Bind the remaining twenty source reviews and thirty editorial identities to v4.

These are provenance checks of inert research files, NEVER publication permits.
The recorded live source observations still require independent bilingual review.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDITS = ROOT / "docs/audits"
QUEUE = ROOT / "content/telegram/lordchrist/verified-30-posts.json"
SCAN = AUDITS / "2026-11-04-lordchrist-remaining-20-source-audit.json"
REDAFTS = AUDITS / "2026-11-04-lordchrist-remaining-10-contiguous-redrafts.json"
OLD_REDAFTS = AUDITS / "2026-11-04-lordchrist-contiguous-quote-redrafts.json"
INDEX = AUDITS / "2026-11-04-lordchrist-30-quote-editorial-candidate-index.json"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def test_all_twenty_source_observations_bind_exact_original_cards() -> None:
    scan = _json(SCAN)
    queue_text = QUEUE.read_text(encoding="utf-8")
    posts = _json(QUEUE)["posts"]
    assert scan["schema_name"] == "video-channel-manager.lordchrist-remaining-20-live-source-audit"
    assert scan["schema_version"] == 1
    assert scan["queue_text_sha256"] == _sha(queue_text)
    assert scan["provider_write_authorization"] is False
    assert scan["rights_review_complete"] is False
    assert scan["full_original_language_collation_complete"] is False

    entries = scan["entries"]
    old_critical = {6, 8, 10, 12, 14, 15, 18, 19, 21, 22}
    assert len(entries) == 20
    assert {x["sequence"] for x in entries} == set(range(1, 31)) - old_critical
    flags = Counter()
    tracks = Counter()

    for row in entries:
        p = posts[row["sequence"] - 1]
        assert row["publication_id"] == p["publication_id"]
        assert row["original_body_sha256"] == _sha(p["text"])
        assert row["original_source_url"] == p["source"]["url"]
        assert row["author"] == p["source"]["author"]
        assert row["source_http_status"] == 200
        assert row["english_words_between_original_anchors"] > 0
        assert row["original_russian_words"] > 0
        assert row["bilingual_semantic_fidelity_verified"] is False
        assert row["release_eligible"] is False
        assert row["finding"]
        expected_flags = []
        if row["english_to_russian_word_ratio_heuristic"] > 2.3:
            expected_flags.append("large_source_interval_ratio_heuristic")
        if "\u2026" in p["text"]:
            expected_flags.append("quoted_ellipsis")
        if row["source_english_anchor_start_match"] != "exact" or row["source_english_anchor_end_match"] != "exact":
            expected_flags.append("nonexact_english_anchor")
        if row["tested_source_url"] != row["original_source_url"]:
            expected_flags.append("corrected_deep_link_proposed")
        assert row["structural_flags"] == expected_flags
        flags.update(expected_flags)
        tracks.update([row["editorial_track"]])

    assert flags == {
        "large_source_interval_ratio_heuristic": 8,
        "quoted_ellipsis": 5,
        "nonexact_english_anchor": 3,
        "corrected_deep_link_proposed": 3,
    }
    assert tracks == {
        "continuous_source_redraft_prepared": 10,
        "retain_conditionally_and_complete_source_collation": 10,
    }
    assert [x["sequence"] for x in entries if "nonexact_english_anchor" in x["structural_flags"]] == [3, 24, 30]
    assert [x["sequence"] for x in entries if "corrected_deep_link_proposed" in x["structural_flags"]] == [27, 28, 29]


def test_ten_new_redrafts_are_exact_original_bound_and_inert() -> None:
    doc = _json(REDAFTS)
    posts = _json(QUEUE)["posts"]
    assert doc["schema_name"] == "video-channel-manager.lordchrist-remaining-quote-contiguous-drafts"
    assert doc["schema_version"] == 1
    assert doc["queue_text_sha256"] == _sha(QUEUE.read_text(encoding="utf-8"))
    assert doc["editorial_approval"] is False
    assert doc["provider_write_authorization"] is False
    assert doc["full_bilingual_verification_complete"] is False
    assert doc["rights_review_complete"] is False
    assert doc["release_id"] is None
    assert doc["release_digest"] is None

    drafts = doc["drafts"]
    assert [z["sequence"] for z in drafts] == [1, 5, 7, 11, 13, 16, 17, 25, 26, 27]
    for draft in drafts:
        original = posts[draft["sequence"] - 1]
        assert draft["original_publication_id"] == original["publication_id"]
        assert draft["original_quote_sha256"] == _sha(original["text"])
        assert draft["proposed_text_sha256"] == _sha(draft["translation_ru"])
        assert draft["russian_word_count"] == len(re.findall(r"\w+", draft["translation_ru"]))
        assert draft["russian_paragraph_count"] == len(draft["translation_ru"].split("\n\n"))
        assert 95 <= draft["russian_word_count"] <= 320
        assert "\u2026" not in draft["translation_ru"]
        assert draft["editorial_status"] == "draft_requires_full_bilingual_citation_and_rights_review"
        assert draft["provider_write_authorization"] is False
        proof = draft["source_probe"]
        assert proof["http_status"] == 200
        assert proof["validation_mode"] == "token_exact_anchor_match_in_cached_primary_source_span"
        assert proof["exact_start"] is True and proof["exact_end"] is True
        assert proof["forward_order"] is True
        assert proof["english_span_words"] > 100
        assert proof["full_translation_certified"] is False


def test_all_thirty_candidate_identities_exist_but_are_not_a_release() -> None:
    manifest = _json(INDEX)
    old = {r["sequence"]: r for r in _json(OLD_REDAFTS)["drafts"]}
    new = {r["sequence"]: r for r in _json(REDAFTS)["drafts"]}
    queue = _json(QUEUE)["posts"]
    assert len(old) == len(new) == 10
    assert not (set(old) & set(new))

    assert manifest["schema_name"] == "video-channel-manager.lordchrist-quote-v5-candidate-evidence-index"
    assert manifest["schema_version"] == 1
    assert manifest["original_queue_sha256"] == _sha(QUEUE.read_text(encoding="utf-8"))
    assert manifest["new_release_id"] is None
    assert manifest["new_release_digest"] is None
    assert manifest["approved_new_queue"] is False
    assert manifest["provider_write_authorization"] is False
    assert manifest["protected_ledger_mutation_authorization"] is False
    assert manifest["full_bilingual_review_complete"] is False
    assert manifest["rights_review_complete"] is False

    entries = manifest["entries"]
    assert len(entries) == 30
    assert [entry["sequence"] for entry in entries] == list(range(1, 31))
    modes = Counter()
    for item, post in zip(entries, queue, strict=True):
        n = item["sequence"]
        assert item["original_publication_id"] == post["publication_id"]
        assert item["original_text_sha256"] == _sha(post["text"])
        assert item["original_author"] == post["source"]["author"]
        assert item["original_source_url"] == post["source"]["url"]
        assert item["full_bilingual_translation_review"] == "pending"
        assert item["text_rights_review"] == "pending"
        assert item["editorial_approval"] is False
        assert item["eligible_for_release"] is False
        modes.update([item["editorial_mode"]])

        if n in old:
            source = old[n]
            assert item["editorial_mode"] == "contiguous_redraft"
            assert item["candidate_body_sha256"] == _sha(source["translation_ru"])
            assert item["candidate_source_url"] == source["source_url"]
            assert item["candidate_evidence_file"].endswith("contiguous-quote-redrafts.json")
        elif n in new:
            source = new[n]
            assert item["editorial_mode"] == "contiguous_redraft"
            assert item["candidate_body_sha256"] == _sha(source["translation_ru"])
            assert item["candidate_source_url"] == source["source_url"]
            assert item["candidate_evidence_file"].endswith("remaining-10-contiguous-redrafts.json")
        else:
            assert item["editorial_mode"] == "retain_provisionally"
            original_body = post["text"].split("\n\n\u00a9")[0]
            assert item["candidate_body_sha256"] == _sha(original_body)
            assert item["candidate_evidence_file"] == "content/telegram/lordchrist/verified-30-posts.json"

    assert modes == {"contiguous_redraft": 20, "retain_provisionally": 10}
    assert {item["sequence"] for item in entries if item["candidate_source_url"] != item["original_source_url"]} == {
        6,
        22,
        27,
        28,
        29,
    }
