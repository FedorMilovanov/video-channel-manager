"""Provider-inert checks for proposed new idiomatic translations of three v6 quotes."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/audits/2026-11-06-lordchrist-quote-v6-provider-payload-candidate-inert.json"
DRAFT = ROOT / "docs/audits/2026-11-20-lordchrist-v6-three-idiomatic-translation-drafts-inert.json"
CALQUES = {
    9: "Молитвою мы обязаны тем",
    21: "версту к скорби",
    30: "простым оком",
}


def test_three_drafts_are_new_editorial_text_not_legacy_payload_mutations() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    review = json.loads(DRAFT.read_text(encoding="utf-8"))
    by_id = {item["publication_id"]: item for item in source["items"]}

    assert review["historical_source_immutability"] is True
    assert review["no_existing_signed_payload_changed"] is True
    assert review["rights_review_complete"] is False
    assert review["full_bilingual_review_complete"] is False
    assert review["activation_approved"] is False
    assert review["new_release_authorized"] is False
    assert len(review["entries"]) == 3
    assert {item["sequence"] for item in review["entries"]} == set(CALQUES)
    assert len({item["publication_id"] for item in review["entries"]}) == 3

    for entry in review["entries"]:
        original = by_id[entry["publication_id"]]
        number = entry["sequence"]
        assert original["sequence"] == number
        assert entry["source_url"] == original["source_url"]
        assert entry["original_source_russian_sha256"] == original["quoted_russian_sha256"]
        assert entry["original_source_english_span_sha256"] == original["historical_english_span_sha256"]
        assert entry["original_exact_telegram_payload_sha256"] == original["candidate_payload_sha256"]
        assert CALQUES[number] in original["html_text"]
        assert CALQUES[number] not in entry["proposed_new_editorial_translation_ru"]
        assert len(entry["proposed_new_editorial_translation_ru"]) > 200
        assert len(entry["editor_comment_outside_quote_ru"]) > 80
        assert entry["new_translation_status"] == "human_translation_and_rights_review_required"
        assert entry["source_contiguity_check"] == (
            "selected_original_english_segment_is_contiguous_not_reverified_machine"
        )
        assert entry["independent_reviewed"] is False
        assert entry["rights_cleared"] is False
        assert entry["provider_authorized"] is False
        assert entry["preview_only"] is True


def test_not_a_new_signed_release_or_quote_v6_activation() -> None:
    review = json.loads(DRAFT.read_text(encoding="utf-8"))
    assert review["legacy_release_id"] == "lordchrist-quote-v6-20261106"
    for entry in review["entries"]:
        assert not any(key in entry for key in ("message_id", "scheduled_at", "run_id", "dispatch_id"))
