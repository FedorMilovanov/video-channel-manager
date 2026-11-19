"""Provider-inert reader-context repair proposals for the other 11 pending quote-v6 cards."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT
    / "docs/audits/2026-11-06-lordchrist-quote-v6-provider-payload-candidate-inert.json"
)
REPAIR = (
    ROOT
    / "docs/audits/2026-11-20-lordchrist-v6-11-remaining-meaning-repair-proposals-inert.json"
)
ELEVEN = {12, 15, 17, 19, 20, 23, 24, 25, 26, 28, 29}
OTHER_FOUR = {16, 18, 22, 27}
OTHER_THREE = {9, 21, 30}


def test_remaining_eleven_exact_contiguous_source_quotes_keep_editorial_text_separate() -> (
    None
):
    data = json.loads(REPAIR.read_text(encoding="utf-8"))
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    raw = SOURCE.read_bytes().replace(b"\r\n", b"\n")
    blob = hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()
    assert data["source_candidate_blob_sha"] == blob
    assert data["expected_sequences"] == sorted(ELEVEN)
    assert data["entry_count"] == len(data["entries"]) == 11
    assert {v["sequence"] for v in data["entries"]} == ELEVEN
    assert {v["publication_id"] for v in data["entries"]} == {
        x["publication_id"] for x in source["items"] if x["sequence"] in ELEVEN
    }
    assert not ELEVEN.intersection(OTHER_FOUR | OTHER_THREE)
    assert ELEVEN | OTHER_FOUR | OTHER_THREE == {9, 12, *range(15, 31)}
    assert data["published_records_mutated"] is False
    assert data["protected_ledger_mutated"] is False
    assert data["publisher_modified"] is False
    assert data["rights_clearance_complete"] is False
    assert data["full_bilingual_review_complete"] is False
    assert data["independent_editorial_signoff"] is False
    assert data["activation_authorized"] is False

    by_source = {x["publication_id"]: x for x in source["items"]}
    for entry in data["entries"]:
        original = by_source[entry["publication_id"]]
        assert entry["sequence"] == original["sequence"]
        assert entry["source_english_url"] == original["source_url"]
        assert entry["source_anchor_start"] == original["source_anchors"]["start"]
        assert entry["source_anchor_end"] == original["source_anchors"]["end"]
        assert entry["source_russian_quote_sha256"] == original["quoted_russian_sha256"]
        assert (
            entry["source_english_span_sha256"]
            == original["historical_english_span_sha256"]
        )
        assert (
            entry["legacy_candidate_payload_sha256"]
            == original["candidate_payload_sha256"]
        )
        match = re.fullmatch(
            r"<blockquote>«([\s\S]+)»</blockquote>[\s\S]*", original["html_text"]
        )
        assert match is not None
        body = match.group(1)
        selected = entry["source_contiguous_russian_excerpt"]
        assert body.count(selected) == 1
        assert (
            len(selected.encode("utf-16-le")) // 2
            == entry["source_excerpt_utf16_units"]
        )
        assert 120 <= entry["source_excerpt_utf16_units"] <= 4096
        assert (selected == body) is entry["selection"][
            "complete_original_russian_excerpt"
        ]
        assert len(entry["editor_intro_outside_author_quote_ru"]) > 100
        assert len(entry["reader_thesis_ru"]) > 100
        assert len(entry["reader_misreading_ru"]) > 90
        assert len(entry["next_editorial_action_ru"]) > 100
        assert entry["rights_clearance"] == "not_cleared"
        assert entry["full_bilingual_approval"] is False
        assert entry["independent_editor_approved"] is False
        assert entry["new_release_authorized"] is False
        assert entry["telegram_send_authorized"] is False

    by_num = {e["sequence"]: e for e in data["entries"]}
    assert "Пс. 118:45" in by_num[15]["source_contiguous_russian_excerpt"]
    assert "2 Тим. 4:6" in by_num[19]["editor_intro_outside_author_quote_ru"]
    assert "Иер. 6:14" in by_num[25]["editor_intro_outside_author_quote_ru"]
    assert "но наш Бог" in by_num[28]["source_contiguous_russian_excerpt"]
    assert by_num[20]["editable_original_translation_status"] == (
        "editorial_retranslation_draft_not_exact_existing_quote"
    )
    draft = by_num[20]["editable_original_translation_draft_ru"]
    assert isinstance(draft, str) and "Божьей волей" not in draft
    assert "ум Бога описан" not in draft
    assert draft != by_num[20]["source_contiguous_russian_excerpt"]
    assert (
        sum(bool(x["editable_original_translation_draft_ru"]) for x in data["entries"])
        == 1
    )
