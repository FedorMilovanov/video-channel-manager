"""The thirty-card source-review reading deck is inert and fully reproducible."""

from __future__ import annotations

import hashlib
import json
import runpy
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "content/telegram/lordchrist/verified-30-posts.json"
FILE = ROOT / "docs/audits/2026-11-04-lordchrist-30-card-editorial-preview-inert.json"
BUILDER = ROOT / "scripts/build_lordchrist_quote_editorial_preview.py"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _hash(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def test_reading_deck_is_identity_bound_to_exact_immutable_v4() -> None:
    signed_text = QUEUE.read_text(encoding="utf-8")
    signed = _load(QUEUE)
    preview = _load(FILE)
    assert preview["schema_name"] == "video-channel-manager.lordchrist-nonpublishing-editorial-preview"
    assert preview["schema_name"] != signed["schema_name"]
    assert preview["schema_version"] == 1
    assert preview["original_queue_sha256"] == _hash(signed_text)
    assert preview["release_id"] is None
    assert preview["release_digest"] is None
    assert preview["editorial_approval"] is False
    assert preview["provider_write_authorization"] is False
    assert preview["protected_ledger_write_authorization"] is False
    assert preview["full_bilingual_review_complete"] is False
    assert preview["rights_review_complete"] is False
    assert preview["drafted_count"] == 20
    assert preview["conditionally_retained_count"] == 10
    assert len(preview["posts"]) == len(signed["posts"]) == 30
    assert FILE.is_relative_to(ROOT / "docs/audits")
    assert BUILDER.is_relative_to(ROOT / "scripts")

    old_ids = [p["publication_id"] for p in signed["posts"]]
    new_ids = [p["publication_id"] for p in preview["posts"]]
    assert new_ids == old_ids
    assert len(set(new_ids)) == 30

    modes = Counter()
    applied = Counter()
    for i, (old, post) in enumerate(zip(signed["posts"], preview["posts"], strict=True), 1):
        assert old["sequence"] == post["sequence"] == i
        assert post["original_full_post_sha256"] == _hash(old["text"])
        assert post["candidate_full_post_sha256"] == _hash(post["text"])
        assert post["editorial_preview_status"] == "editorial_preview_unapproved_no_provider_mutations"
        assert post["editorial_approval"] is False
        assert post["provider_write_authorization"] is False
        assert post["bilingual_alignment_status"] == "pending_complete_sentence_alignment"
        assert post["edition_specific_rights_status"] == "pending_independent_review"
        assert post["original_editorial_finding"]
        assert post["original_preliminary_risk"] in {"screened", "review", "major", "critical"}
        assert "accepted" not in post["source"].get("translation_review_status", "")
        assert "verification_status" not in post["source"]
        assert "copyright_status" not in post["source"]
        assert len(post["text"]) <= 4096
        assert post["text"].startswith(chr(171))
        assert post["text"].count("©") == 1
        assert post["text"].count("\n\n© ") == 1
        assert "\n\n#" in post["text"]
        assert post["source"]["url"].startswith("https://")
        assert post["source"]["anchor_start"]
        assert post["source"]["anchor_end"]
        assert post["source"]["edition_rights_status"] == "requires_edition_specific_review"

        applied.update([i] * len(post["applied_original_field_proposals"]))
        modes.update(["redraft" if post["evidence_file"].startswith("docs/") else "retained"])

    assert modes == {"redraft": 20, "retained": 10}
    assert sum(applied.values()) == 10
    assert applied == {3: 1, 4: 2, 9: 1, 20: 1, 23: 1, 24: 1, 28: 1, 29: 1, 30: 1}


def test_original_field_proposals_are_reflected_without_changing_signed_queue() -> None:
    posts = _load(FILE)["posts"]
    originals = _load(QUEUE)["posts"]

    assert posts[2]["source"]["anchor_end"] == "It is God upon his throne whom we trust."
    assert originals[2]["source"]["anchor_end"] != posts[2]["source"]["anchor_end"]
    assert "Послании к Колоссянам" in posts[3]["text"]
    assert "Так говорит апостол в Колоссянам" in originals[3]["text"]
    assert posts[3]["source"]["location"].startswith("глава II")
    assert "наша единственная защита" in posts[8]["text"]
    assert "единственное наше спасение" in originals[8]["text"]
    assert "бедным и несовершенным наброском" in posts[19]["text"]
    assert "bedным" not in posts[19]["text"]
    assert posts[22]["source"]["anchor_end"].startswith("Oh that my head were waters")
    assert posts[23]["source"]["anchor_end"] == "he is never the better, but rather the worse for them."
    assert posts[27]["source"]["url"].endswith("/kuyper/near.ii.html")
    assert posts[28]["source"]["url"].endswith("/bavinck/revelation/revelation.ii.html")
    assert "sincere intentions" in posts[29]["source"]["anchor_start"]


def test_drafts_have_unique_standalone_metadata_and_never_inherit_acceptance() -> None:
    posts = _load(FILE)["posts"]
    critical = {6, 8, 10, 12, 14, 15, 18, 19, 21, 22}
    remaining = {1, 5, 7, 11, 13, 16, 17, 25, 26, 27}
    for n in critical | remaining:
        card = posts[n - 1]
        assert card["title"].startswith(chr(171))
        assert card["source"]["translation_language"] == "ru"
        assert card["source"]["translation_review_status"] == "pending_full_bilingual_check"
        assert card["source"]["primary_source_type"] == "historical_primary"
        assert len(card["source"]["anchor_start"]) > 15
        assert len(card["source"]["anchor_end"]) > 15
        assert card["evidence_file"].startswith("docs/audits/")
        assert card["candidate_full_post_sha256"] != card["original_full_post_sha256"]
    augustine = posts[5]
    assert augustine["source"]["original_language"] == "la"
    assert "sophiascriptura.com" in augustine["source"]["latin_original_url"]
    assert "1838" in augustine["source"]["source_edition"]
    assert augustine["edition_specific_rights_status"] == "pending_independent_review"


def test_builder_recomputes_exact_file_without_involving_runtime_or_network() -> None:
    builder = runpy.run_path(str(BUILDER))
    generated = builder["build"]()
    expected = _load(FILE)
    assert generated == expected
    assert builder["OUTPUT"] == FILE
    assert builder["SCHEMA"] == expected["schema_name"]


def test_builder_refuses_an_approved_or_modified_evidence_package() -> None:
    builder = runpy.run_path(str(BUILDER))
    build = builder["build"]
    globals_dict = build.__globals__
    original_loader = globals_dict["_load"]

    def changed_loader(path: Path) -> dict:
        document = original_loader(path)
        if path == builder["INDEX"]:
            document["approved_new_queue"] = True
        return document

    globals_dict["_load"] = changed_loader
    try:
        import pytest

        with pytest.raises(ValueError, match="unapproved"):
            build()
    finally:
        globals_dict["_load"] = original_loader


def test_nested_original_scriptural_quotes_are_rendered_at_distinct_levels() -> None:
    builder = runpy.run_path(str(BUILDER))
    nest = builder["_nest_original_speech_quotes"]
    inner = chr(171) + "A " + chr(8222) + "B" + chr(8220) + " C" + chr(187)
    expected = chr(8222) + "A " + chr(8216) + "B" + chr(8217) + " C" + chr(8220)
    assert nest(inner) == expected

    import pytest

    with pytest.raises(ValueError, match="Unclosed"):
        nest(chr(171) + "unclosed")
    with pytest.raises(ValueError, match="Unmatched"):
        nest("unexpected " + chr(187))
    with pytest.raises(ValueError, match="third level"):
        nest(chr(171) + chr(8222) + chr(171) + "nested" + chr(187) + chr(8220) + chr(187))

    # Whitefield #25 quotes Jeremiah and has a third-level biblical speech.
    card = _load(FILE)["posts"][24]
    assert chr(8216) + "мир! мир!" + chr(8217) in card["text"]
    assert card["text"].count(chr(8222)) == card["text"].count(chr(8220))
    assert card["text"].count(chr(8216)) == card["text"].count(chr(8217))


def test_preview_is_rejected_by_the_actual_telegram_publisher_queue_schema() -> None:
    import pytest
    from pydantic import ValidationError
    from video_channel_manager.telegram_models import TelegramQueue

    preview = _load(FILE)
    with pytest.raises(ValidationError):
        TelegramQueue.model_validate(preview)
    assert preview["schema_name"] != "video-channel-manager.telegram-quote-queue"


def test_every_quote_obeys_paragraph_contract_without_losing_draft_words() -> None:
    import re

    preview = _load(FILE)["posts"]
    older = _load(ROOT / "docs/audits/2026-11-04-lordchrist-contiguous-quote-redrafts.json")
    newer = _load(ROOT / "docs/audits/2026-11-04-lordchrist-remaining-10-contiguous-redrafts.json")
    drafts = {row["sequence"]: row for doc in (older, newer) for row in doc["drafts"]}
    revision_doc = _load(ROOT / "docs/audits/2026-11-04-lordchrist-quote-semantic-revisions-inert.json")
    revisions = {row["sequence"]: row for row in revision_doc["revisions"]}
    assert set(revisions) == {7, 25, 29}

    folded = []
    for card in preview:
        blocks = [chunk.strip() for chunk in card["text"].split("\n\n") if chunk.strip()]
        quote_blocks = blocks[:-2]
        assert 2 <= len(quote_blocks) <= 3
        assert all(len(chunk) >= 80 for chunk in quote_blocks)
        assert blocks[-2].startswith("© ")
        assert blocks[-1].startswith("#")
        if card["sequence"] not in drafts:
            assert card["preview_paragraph_normalization"] is None
            continue

        draft = drafts[card["sequence"]]
        revised = revisions.get(card["sequence"])
        quoted = "\n\n".join(quote_blocks)
        assert quoted.startswith(chr(171)) and quoted.endswith(chr(187))
        authoritative_draft_body = revised["new_translation_ru"] if revised else draft["translation_ru"]
        assert re.findall(r"\w+", quoted) == re.findall(r"\w+", authoritative_draft_body)
        if card["preview_paragraph_normalization"]:
            folded.append(card["sequence"])
            assert len(draft["translation_ru"].split("\n\n")) == 4
        else:
            assert 2 <= len(draft["translation_ru"].split("\n\n")) <= 3

    assert folded == [14, 18, 21]


def test_three_semantic_revisions_bind_primary_spans_and_are_not_approvals() -> None:
    import re

    doc = _load(ROOT / "docs/audits/2026-11-04-lordchrist-quote-semantic-revisions-inert.json")
    posts = _load(FILE)["posts"]
    original = _load(QUEUE)["posts"]
    assert doc["schema_name"] == "video-channel-manager.lordchrist-nonpublishing-semantic-revisions"
    assert doc["schema_version"] == 1
    assert doc["original_queue_sha256"] == _hash(QUEUE.read_text(encoding="utf-8"))
    assert doc["editorial_approval"] is False
    assert doc["full_bilingual_review_complete"] is False
    assert doc["rights_review_complete"] is False
    assert doc["provider_write_authorization"] is False
    assert doc["protected_ledger_write_authorization"] is False
    assert [row["sequence"] for row in doc["revisions"]] == [7, 25, 29]

    preview = _load(FILE)
    assert preview["semantic_revision_applied_count"] == 3
    assert preview["effective_contiguous_draft_count"] == 21
    assert preview["effective_retained_for_context_count"] == 9

    for revision in doc["revisions"]:
        n = revision["sequence"]
        p = posts[n - 1]
        source = original[n - 1]
        assert p["publication_id"] == source["publication_id"] == revision["original_publication_id"]
        assert revision["original_full_post_sha256"] == _hash(source["text"])
        assert revision["new_russian_body_sha256"] == _hash(revision["new_translation_ru"])
        assert revision["new_russian_word_count"] == len(re.findall(r"\w+", revision["new_translation_ru"]))
        assert revision["russian_paragraph_count"] in (2, 3)
        assert revision["final_editorial_approval"] is False
        assert p["candidate_full_post_sha256"] == _hash(p["text"])
        assert p["source"]["anchor_start"] == revision["new_source_anchor_start"]
        assert p["source"]["anchor_end"] == revision["new_source_anchor_end"]
        assert p["source"]["url"] == revision["source_url"]
        assert p["semantic_revision_status"] == "pending_independent_bilingual_and_rights_approval"
        assert p["semantic_revision_evidence_file"].endswith("quote-semantic-revisions-inert.json")
        assert p["editorial_approval"] is False
        assert p["provider_write_authorization"] is False
        assert p["candidate_full_post_sha256"] != revision["expected_prior_preview_full_post_sha256"]
        source_check = revision["source_probe"]
        assert source_check["http_status"] == 200
        assert source_check["source_opening_exact"] is True
        assert source_check["source_closing_exact"] is True
        assert source_check["forward_order"] is True
        assert source_check["source_review_not_full_translation_certification"] is True
        assert source_check["english_source_span_words"] >= 120

    assert "блоха или муха" in posts[6]["text"]
    assert "чем солнце" in posts[6]["text"]
    assert "разумение быстрее" in posts[6]["text"]
    assert "тронет сердце Бога" not in posts[6]["text"]
    assert "величайшее проклятие" in posts[24]["text"]
    assert "едва ли возможно представить большее бедствие" not in posts[24]["text"]
    assert posts[28]["text"].startswith(chr(171) + "Поскольку исторические")
    assert posts[28]["preview_selection_change"] == "retained_source_replaced_by_context_complete_candidate"
    assert "религии Израиля и христианства" in posts[28]["text"]


def test_semantic_revision_rejects_stale_input_and_fake_editorial_approval() -> None:
    import pytest

    builder = runpy.run_path(str(BUILDER))
    build = builder["build"]
    globals_dict = build.__globals__
    original_loader = globals_dict["_load"]
    revision_path = builder["SEMANTIC_REVISIONS"]

    def changed_loader(path: Path) -> dict:
        doc = original_loader(path)
        if path == revision_path:
            doc["revisions"][0]["expected_prior_preview_full_post_sha256"] = "sha256:" + "0" * 64
        return doc

    globals_dict["_load"] = changed_loader
    try:
        with pytest.raises(ValueError, match="Unsafe or stale"):
            build()
    finally:
        globals_dict["_load"] = original_loader

    def authorized_loader(path: Path) -> dict:
        doc = original_loader(path)
        if path == revision_path:
            doc["provider_write_authorization"] = True
        return doc

    globals_dict["_load"] = authorized_loader
    try:
        with pytest.raises(ValueError, match="not safe"):
            build()
    finally:
        globals_dict["_load"] = original_loader


def test_retained_typography_is_nested_without_changing_quote_words() -> None:
    import re

    builder = runpy.run_path(str(BUILDER))
    normalize = builder["_normalize_retained_quotation_depth"]
    posts = _load(FILE)["posts"]
    repaired = []
    for n in (2, 3, 4, 9, 20, 23, 24, 28, 30):
        card = posts[n - 1]
        normalized = card["text"]
        assert normalize(normalized) == normalized
        assert normalized.count("\n\n" + chr(169) + " ") == 1
        quoted = normalized.split("\n\n" + chr(169) + " ", 1)[0]
        assert quoted.startswith(chr(171)) and quoted.endswith(chr(187))
        assert quoted.count(chr(171)) == 1
        assert quoted.count(chr(187)) == 1
        assert quoted.count(chr(8222)) == quoted.count(chr(8220))
        assert quoted.count(chr(8216)) == quoted.count(chr(8217))
        if card.get("retained_quote_depth_normalization") is not None:
            repaired.append(n)
            assert card["retained_quote_depth_normalization"] == "typography_only_no_word_changes"
    assert repaired == [2, 4, 24]

    original = _load(QUEUE)["posts"]
    for n in (2, 24):
        raw_text = original[n - 1]["text"]
        clean_text = posts[n - 1]["text"]
        assert re.findall(r"\w+", raw_text) == re.findall(r"\w+", clean_text)

    import pytest

    with pytest.raises(ValueError, match="attribution"):
        normalize("not a Telegram post")
    with pytest.raises(ValueError, match="top-level"):
        normalize("Unquoted" + "\n\n" + chr(169) + " attribution")
    with pytest.raises(ValueError, match="Unclosed"):
        normalize(chr(171) + chr(171) + "not closed" + chr(187) + "\n\n" + chr(169) + " attribution")


def test_retained_luke_verse_22_is_distinguished_from_verse_23_without_false_preface() -> None:
    doc = _load(ROOT / "docs/audits/2026-11-04-lordchrist-retained-verse-and-quotation-review.json")
    deck = _load(FILE)
    card = deck["posts"][29]
    old_queue = _load(QUEUE)["posts"][29]
    assert doc["schema_name"] == "video-channel-manager.lordchrist-nonpublishing-retained-verse-review"
    assert doc["schema_version"] == 1
    assert doc["original_queue_sha256"] == _hash(QUEUE.read_text(encoding="utf-8"))
    assert doc["editorial_approval"] is False
    assert doc["full_bilingual_review_complete"] is False
    assert doc["rights_review_complete"] is False
    assert doc["provider_write_authorization"] is False
    assert doc["protected_ledger_write_authorization"] is False
    assert deck["retained_verse_amendment_count"] == 1
    assert len(doc["revisions"]) == 1
    revision = doc["revisions"][0]
    assert revision["sequence"] == 30
    assert revision["original_publication_id"] == old_queue["publication_id"]
    assert revision["original_full_post_sha256"] == _hash(old_queue["text"])
    assert card["candidate_full_post_sha256"] == revision["candidate_full_post_sha256"]
    assert card["candidate_full_post_sha256"] == _hash(card["text"])
    assert card["retained_verse_review_status"] == "pending_full_bilingual_and_rights_approval"
    assert card["editorial_approval"] is False
    assert card["provider_write_authorization"] is False
    assert card["text"].startswith(chr(171) + "Кто читает Евангелие")
    assert "Он говорит им в 22-м стихе, что" in card["text"]
    assert "Он говорит им в этом стихе, что" not in card["text"]
    assert "Лк. 9:23" not in card["text"]
    assert "если кто хочет идти за Мною, отвергнись себя" in card["text"]
    assert revision["source_probe"]["source_explicit_22nd_verse"] is True
    assert revision["source_probe"]["full_translation_certified"] is False
    assert [e["field"] for e in revision["corrections"]] == ["text", "text"]
    assert all(e["rationale"] for e in revision["corrections"])


def test_retained_verse_review_cannot_be_replayed_or_authorized() -> None:
    import pytest

    builder = runpy.run_path(str(BUILDER))
    build = builder["build"]
    globals_dict = build.__globals__
    original_loader = globals_dict["_load"]

    def stale_loader(path: Path) -> dict:
        doc = original_loader(path)
        if path == builder["RETAINED_VERSE_REVIEW"]:
            doc["revisions"][0]["expected_prior_preview_full_post_sha256"] = "sha256:" + "0" * 64
        return doc

    globals_dict["_load"] = stale_loader
    try:
        with pytest.raises(ValueError, match="does not match exact old candidate"):
            build()
    finally:
        globals_dict["_load"] = original_loader

    def permit_loader(path: Path) -> dict:
        doc = original_loader(path)
        if path == builder["RETAINED_VERSE_REVIEW"]:
            doc["provider_write_authorization"] = True
        return doc

    globals_dict["_load"] = permit_loader
    try:
        with pytest.raises(ValueError, match="unsafe authority"):
            build()
    finally:
        globals_dict["_load"] = original_loader
