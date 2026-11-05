"""Fail-closed checks for untranslated quote-v4 v3 publication candidates."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs" / "audits"


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def digest(value):
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def test_v3_review_amendments_are_bound_to_the_reader_preview():
    index = load("2026-11-05-lordchrist-30-quote-editorial-candidate-index-v3.json")
    preview = load("2026-11-05-lordchrist-30-card-editorial-preview-v3-inert.json")
    evidence = load("2026-11-05-lordchrist-quote-v4-bilingual-language-revisions-v3.json")
    previous = load("2026-11-05-lordchrist-30-card-editorial-preview-v2-inert.json")
    assert len(index["entries"]) == len(preview["posts"]) == 30
    assert sorted(x["sequence"] for x in evidence["items"]) == [3, 4, 24, 27, 28]
    ix = {x["sequence"]: x for x in index["entries"]}
    post = {x["sequence"]: x for x in preview["posts"]}
    prev = {x["sequence"]: x for x in previous["posts"]}
    evidence_path = "docs/audits/2026-11-05-lordchrist-quote-v4-bilingual-language-revisions-v3.json"
    for row in evidence["items"]:
        seq = row["sequence"]
        assert ix[seq]["candidate_evidence_file"] == evidence_path
        assert post[seq]["evidence_file"] == evidence_path
        assert row["translation_sha256"] == digest(row["translation_ru"])
        assert ix[seq]["candidate_body_sha256"] == row["translation_sha256"]
        assert post[seq]["text"].split("\n\n©", 1)[0] == "«" + row["translation_ru"] + "»"
        assert row["candidate_full_post_sha256"] == digest(post[seq]["text"])
        assert row["prior_full_post_sha256"] == digest(prev[seq]["text"])
    for seq in range(1, 31):
        assert post[seq]["candidate_full_post_sha256"] == digest(post[seq]["text"])


def test_v3_keeps_both_publishing_and_review_gates_closed():
    index = load("2026-11-05-lordchrist-30-quote-editorial-candidate-index-v3.json")
    preview = load("2026-11-05-lordchrist-30-card-editorial-preview-v3-inert.json")
    evidence = load("2026-11-05-lordchrist-quote-v4-bilingual-language-revisions-v3.json")
    for doc in (index, preview, evidence):
        assert doc["provider_write_authorization"] is False
    assert index["approved_new_queue"] is False
    assert index["new_release_digest"] is None
    assert index["full_bilingual_review_complete"] is False
    assert index["rights_review_complete"] is False
    assert preview["editorial_approval"] is False
    assert evidence["editorial_approval"] is False
    assert all(x["eligible_for_release"] is False for x in index["entries"])
