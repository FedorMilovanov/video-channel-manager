"""Non-provider editorial regressions for the 18 pending v6 English/Russian previews.

Only verifies structural provenance, safety and presentation invariants.
It does NOT certify bilingual equivalence, rights, independent approval or dispatch.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs/audits/2026-11-20-lordchrist-quote-v6-18-bilingual-lexical-and-format-previews-inert.json"
SOURCE = ROOT / "docs/audits/2026-11-06-lordchrist-quote-v6-provider-payload-candidate-inert.json"
EXPECTED = {9, 12, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30}
NEW_TRANSLATIONS = {9, 20, 21, 22, 23, 30}
DERIVATIVE_LEGACY_EDITS: set[int] = set()
ARTICLE_L1 = {16, 22, 27}


def _data() -> tuple[dict, dict]:
    return json.loads(AUDIT.read_text(encoding="utf-8")), json.loads(
        SOURCE.read_text(encoding="utf-8")
    )


def test_exact_18_pending_revisions_bind_to_frozen_original_identity() -> None:
    audit, frozen = _data()
    entries = audit["entries"]
    by_id = {entry["publication_id"]: entry for entry in frozen["items"]}

    assert audit["testable_count"] == 18
    assert len(entries) == 18
    assert {item["sequence"] for item in entries} == EXPECTED
    assert len({item["publication_id"] for item in entries}) == 18
    assert audit["completion_level"] == "EDITORIAL_DRAFT_ONLY_NOT_CLEARED"

    for entry in entries:
        original = by_id[entry["publication_id"]]
        assert original["sequence"] == entry["sequence"]
        assert entry["original_source_url"] == original["source_url"]
        assert entry["original_english_start"] == original["source_anchors"]["start"]
        assert entry["original_english_end"] == original["source_anchors"]["end"]
        assert entry["historical_english_span_sha256"] == original["historical_english_span_sha256"]
        assert entry["legacy_russian_sha256"] == original["quoted_russian_sha256"]
        assert entry["legacy_payload_sha256"] == original["candidate_payload_sha256"]
        assert len(entry["selected_lexical_checkpoints"]) == 3
        assert entry["selected_english_excerpt_anchors"]["start"]
        assert entry["selected_english_excerpt_anchors"]["end"]
        assert all(check["english"] and check["proposed_russian"] for check in entry["selected_lexical_checkpoints"])


def test_previews_are_separate_from_provider_and_independent_human_authority() -> None:
    audit, _ = _data()
    assert audit["provider_posts_sent"] == 0
    assert audit["immutable_candidate_changed"] is False
    assert audit["protected_ledger_changed"] is False
    assert audit["formatted_previews_only"] is True
    assert audit["pending_human_and_owner_gates"]

    for item in audit["entries"]:
        assert item["observed_state"] == "pending"
        assert item["independent_approved"] is False
        assert item["complete_word_by_word_signed_human_translation_review"] is False
        assert item["rights_cleared"] is False
        assert item["translated_text_provenance_verified"] is False
        assert item["publisher_activation_authorized"] is False
        assert item["legacy_ledger_write_authorized"] is False
        assert not any(key in item for key in ("scheduled_at", "message_id", "intent_id", "release_authorized"))
        assert len(item["reader_preview_markdown_ru"]) < 4000


def test_russian_retranslating_is_explicit_and_not_disguised_as_old_quote() -> None:
    audit, frozen = _data()
    by_num = {item["sequence"]: item for item in audit["entries"]}
    old_by_num = {item["sequence"]: item for item in frozen["items"]}
    actual_new = {
        number for number, item in by_num.items()
        if item["quote_provenance"] == "new_editorial_translation_from_english_reference_requires_new_digest"
    }
    assert actual_new == NEW_TRANSLATIONS
    assert {n for n, item in by_num.items() if item["quote_provenance"] == "legacy_russian_span_with_targeted_unapproved_edits_rights_and_new_digest_required"} == DERIVATIVE_LEGACY_EDITS
    assert {n for n, item in by_num.items() if item["legacy_russian_dependency_remains"] is False} == NEW_TRANSLATIONS

    for number, item in by_num.items():
        old_text = html.unescape(re.sub(r"<[^>]+>", "", old_by_num[number]["html_text"]))
        if number not in NEW_TRANSLATIONS | DERIVATIVE_LEGACY_EDITS:
            assert item["proposed_quote_text_ru"] in old_text

    assert by_num[22]["proposed_quote_text_ru"].startswith("Христианское довольство —")
    assert "заклятых лицемеров" not in by_num[23]["proposed_quote_text_ru"]
    assert "проклятых лицемеров" in by_num[23]["proposed_quote_text_ru"]
    assert "проницательный наблюдатель" in by_num[23]["proposed_quote_text_ru"]
    assert "версту к скорби" not in by_num[21]["proposed_quote_text_ru"]
    assert "простым оком" not in by_num[30]["proposed_quote_text_ru"]
    assert "ум Бога описан" not in by_num[20]["proposed_quote_text_ru"]


def test_short_and_l1_layout_keep_editor_outside_the_author_quote() -> None:
    audit, _ = _data()
    by_num = {item["sequence"]: item for item in audit["entries"]}

    assert {
        number for number, item in by_num.items()
        if item["format_lane"] == "separate_L1_editorial_article_not_quote_v6"
    } == ARTICLE_L1

    for item in audit["entries"]:
        preview = item["reader_preview_markdown_ru"]
        quote = item["proposed_quote_text_ru"]
        attribution = item["attribution_ru"]
        tags = item["hashtags_ru"]
        assert not quote.startswith("«") and not quote.endswith("»")
        assert item["highlight_bold_ru"] in quote
        assert item["highlight_italic_ru"] in quote
        assert "**" + item["highlight_bold_ru"] + "**" in preview
        assert "*" + item["highlight_italic_ru"] + "*" in preview
        assert "\n*" + attribution + "*\n\n" + tags in preview
        assert attribution.startswith("— ")
        assert "«" in attribution and "»" in attribution
        assert "\n" not in tags
        assert "_" not in tags
        assert all(tag.startswith("#") for tag in tags.split())

        intro = item["editor_intro_outside_quote_ru"]
        if item["sequence"] in ARTICLE_L1:
            assert intro and intro in preview
            assert intro not in quote
            assert preview.startswith("**")
            assert "**\n\n" in preview
            assert item["native_telegram_quote_entity_required"] is True
            assert item["native_telegram_quote_entity_payload_ready"] is False
            assert "\u2060\n> " in preview
        else:
            assert intro is None
            assert item["native_telegram_quote_entity_required"] is False
            assert "\u2060" not in preview
            assert preview.replace("*", "").startswith(quote[:4])
            assert not preview.startswith("«")
