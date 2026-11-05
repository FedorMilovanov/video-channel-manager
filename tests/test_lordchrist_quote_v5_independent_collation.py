"""Nonpublishing v5 regression: source-bound quotes, no mutation or implied release."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs" / "audits"
INDEX4 = "2026-11-05-lordchrist-30-quote-editorial-candidate-index-v4.json"
INDEX5 = "2026-11-05-lordchrist-30-quote-editorial-candidate-index-v5.json"
PREVIEW4 = "2026-11-05-lordchrist-30-card-editorial-preview-v4-inert.json"
PREVIEW5 = "2026-11-05-lordchrist-30-card-editorial-preview-v5-inert.json"
EVIDENCE = "2026-11-05-lordchrist-30-quote-independent-collation-v5.json"
CHANGED = {3, 4, 9, 12, 17, 23, 28, 29, 30}
CHANGED_QUOTE = {3, 4, 30}


def load(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def quote(text: str) -> str:
    q = text.split("\n\n©", 1)[0]
    assert q.startswith("«") and q.endswith("»")
    return q[1:-1]


def test_independent_collation_has_exact_source_evidence_and_never_authorizes_release() -> None:
    index4, index5 = load(INDEX4), load(INDEX5)
    preview4, preview5 = load(PREVIEW4), load(PREVIEW5)
    report = load(EVIDENCE)
    assert len(index4["entries"]) == len(index5["entries"]) == 30
    assert len(preview4["posts"]) == len(preview5["posts"]) == 30
    assert report["candidate_count"] == report["source_anchors_matched_count"] == 30
    assert len(report["source_evidence"]) == 30
    assert report["independent_ai_collation_performed"] is True
    assert report["final_responsible_editor_approval"] is False
    for data in (index5, preview5, report):
        assert data["provider_write_authorization"] is False
        assert data["rights_review_complete"] is False
        assert data["full_bilingual_review_complete"] is False
    assert index5["approved_new_queue"] is False
    assert index5["new_release_digest"] is None
    assert preview5["release_digest"] is None
    assert report["publications_sent"] == 0
    for evidence in report["source_evidence"]:
        assert evidence["source_range_status"] == "matched_readonly"
        assert evidence["rights"] == "edition_specific_clearance_pending"


def test_only_nine_bounded_cards_change_while_source_anchors_stay_fixed() -> None:
    index4, index5 = load(INDEX4)["entries"], load(INDEX5)["entries"]
    posts4, posts5 = load(PREVIEW4)["posts"], load(PREVIEW5)["posts"]
    report = load(EVIDENCE)
    changes = {entry["sequence"]: entry for entry in report["bounded_changes"]}
    assert set(changes) == CHANGED
    assert {seq for seq, data in changes.items() if data["quoted_words_changed"]} == CHANGED_QUOTE
    for i, (before, after, old, new) in enumerate(zip(posts4, posts5, index4, index5, strict=True), 1):
        assert before["sequence"] == after["sequence"] == old["sequence"] == new["sequence"] == i
        assert (before["text"] != after["text"]) == (i in CHANGED)
        assert (quote(before["text"]) != quote(after["text"])) == (i in CHANGED_QUOTE)
        assert old["candidate_source_url"] == new["candidate_source_url"]
        assert old["candidate_source_anchor_start"] == new["candidate_source_anchor_start"]
        assert old["candidate_source_anchor_end"] == new["candidate_source_anchor_end"]
        assert new["candidate_body_sha256"] == digest(quote(after["text"]))
        assert after["candidate_full_post_sha256"] == digest(after["text"])
        assert new["editorial_approval"] is False
        assert new["eligible_for_release"] is False
        assert new["text_rights_review"] == "pending"
        if i in CHANGED:
            assert changes[i]["before_full_post_sha256"] == digest(before["text"])
            assert changes[i]["after_full_post_sha256"] == digest(after["text"])


def test_reader_facing_attribution_and_sermon_scripture_are_precise() -> None:
    posts = {post["sequence"]: post["text"] for post in load(PREVIEW5)["posts"]}
    for n, title in {
        4: "Об умерщвлении греха в верующих",
        9: "Наставление в христианской вере",
        23: "Истинный святой: хранение сердца",
        28: "Быть близко к Богу",
        29: "Философия откровения",
        30: "Разумность самоотречения",
    }.items():
        attribution = next(line for line in posts[n].splitlines() if line.startswith("©"))
        assert title in attribution
    assert "#Деяния24_15" in posts[12]
    assert "#1_Коринфянам15" not in posts[12]
    assert "в силу единения со Христом" in posts[4]
    assert "Божье владычество" in posts[3]
    assert "с искренними намерениями" in posts[30]
