"""Reader-meaning repair candidates must remain exact, scoped and provider-inert."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/audits/2026-11-06-lordchrist-quote-v6-provider-payload-candidate-inert.json"
PREVIEW = ROOT / "docs/audits/2026-11-20-lordchrist-v6-four-meaning-hold-repair-previews-inert.json"
NATIVE = {16, 18, 22, 27}


def test_four_critical_holds_use_contiguous_exact_russian_spans_and_separate_editor_words() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    preview = json.loads(PREVIEW.read_text(encoding="utf-8"))
    by_id = {x["publication_id"]: x for x in source["items"]}

    assert {x["sequence"] for x in preview["entries"]} == NATIVE
    assert len({x["publication_id"] for x in preview["entries"]}) == 4
    assert preview["original_source_immutability"] is True
    assert preview["telegram_messages_to_send"] == 0
    assert preview["editorial_independent_approval"] is False
    assert preview["rights_review_complete"] is False
    assert preview["translation_review_complete"] is False
    assert preview["release_authorized"] is False

    for entry in preview["entries"]:
        original = by_id[entry["publication_id"]]
        assert original["sequence"] == entry["sequence"]
        assert entry["primary_english_url"] == original["source_url"]
        assert entry["source_original_russian_quote_sha256"] == original["quoted_russian_sha256"]
        assert entry["source_historical_english_sha256"] == original["historical_english_span_sha256"]
        assert entry["primary_english_anchor_start"] == original["source_anchors"]["start"]
        assert entry["primary_english_anchor_end"] == original["source_anchors"]["end"]
        quoted = re.fullmatch(r"<blockquote>«([\s\S]+)»</blockquote>[\s\S]*", original["html_text"])
        assert quoted is not None
        body = quoted.group(1)
        start = entry["quote_russian_offset_start_utf16"]
        end = entry["quote_russian_offset_end_utf16"]
        assert body[start:end] == entry["quote_ru_contiguous_exact"]
        assert len(entry["quote_ru_contiguous_exact"]) == entry["quote_ru_utf16_units"]
        assert body.count(entry["quote_ru_contiguous_exact"]) == 1
        assert len(entry["reader_thesis_ru"]) > 45
        assert len(entry["editor_intro_outside_quote_ru"]) > 80
        assert entry["semantic_verdict"] == "HOLD_MEANING"
        assert entry["rights_clearance"] == "not_cleared"
        assert entry["bilingual_human_approval"] is False
        assert entry["provider_authorization"] is False
        assert entry["new_release_authorized"] is False


def test_context_risk_is_not_hidden_by_selection() -> None:
    entries = {
        x["sequence"]: x
        for x in json.loads(PREVIEW.read_text(encoding="utf-8"))["entries"]
    }
    assert "оправдани" in entries[16]["editor_intro_outside_quote_ru"]
    assert "духовн" in entries[18]["quote_ru_contiguous_exact"]
    assert "Это" == entries[22]["quote_ru_contiguous_exact"][:3]
    assert "not_self_standing" in entries[22]["recommended_lane"]
    assert "во сне" in entries[27]["quote_ru_contiguous_exact"]
    assert entries[27]["recommended_lane"] == "L1_literary_article_only"
