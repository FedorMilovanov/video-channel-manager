"""Editorial-only v4 regression checks. These never authorize publication."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs" / "audits"
V3_INDEX = "2026-11-05-lordchrist-30-quote-editorial-candidate-index-v3.json"
V4_INDEX = "2026-11-05-lordchrist-30-quote-editorial-candidate-index-v4.json"
V3_PREVIEW = "2026-11-05-lordchrist-30-card-editorial-preview-v3-inert.json"
V4_PREVIEW = "2026-11-05-lordchrist-30-card-editorial-preview-v4-inert.json"
EVIDENCE = "2026-11-05-lordchrist-quote-v4-language-polish-v4.json"


def read(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def digest(text):
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def quote(text):
    body = text.split("\n\n©", 1)[0]
    assert body.startswith("«") and body.endswith("»")
    return body[1:-1]


def canonical(text):
    excluded = set("«»„“”")
    return "".join(c for c in text.casefold() if not c.isspace() and c not in excluded)


def test_polish_has_no_provider_release_or_source_drift():
    earlier = read(V3_INDEX)
    current = read(V4_INDEX)
    posts = read(V4_PREVIEW)
    assert len(earlier["entries"]) == len(current["entries"]) == 30
    assert len(posts["posts"]) == 30
    for data in (current, posts):
        assert data["provider_write_authorization"] is False
        assert data["rights_review_complete"] is False
        assert data["full_bilingual_review_complete"] is False
    assert current["approved_new_queue"] is False
    assert current["new_release_digest"] is None

    old_by_number = {x["sequence"]: x for x in earlier["entries"]}
    now_by_number = {x["sequence"]: x for x in current["entries"]}
    old_posts = {x["sequence"]: x for x in read(V3_PREVIEW)["posts"]}
    new_posts = {x["sequence"]: x for x in posts["posts"]}

    for n in range(1, 31):
        old = old_by_number[n]
        new = now_by_number[n]
        assert new["eligible_for_release"] is False
        assert new["editorial_approval"] is False
        assert new["text_rights_review"] == "pending"
        assert new["candidate_source_url"] == old["candidate_source_url"]
        assert new["candidate_source_anchor_start"] == old["candidate_source_anchor_start"]
        assert new["candidate_source_anchor_end"] == old["candidate_source_anchor_end"]
        assert new_posts[n]["candidate_full_post_sha256"] == digest(new_posts[n]["text"])
        if n not in (3, 20, 23):
            assert new["candidate_body_sha256"] == old["candidate_body_sha256"]
            assert canonical(quote(new_posts[n]["text"])) == canonical(
                quote(old_posts[n]["text"])
            )


def test_six_polished_cards_and_three_quote_digests():
    report = read(EVIDENCE)
    current = read(V4_INDEX)
    posts = read(V4_PREVIEW)
    revisions = {x["sequence"]: x for x in report["revisions"]}
    index = {x["sequence"]: x for x in current["entries"]}
    messages = {x["sequence"]: x["text"] for x in posts["posts"]}
    assert sorted(revisions) == [3, 8, 20, 21, 23, 24]
    assert report["editorial_approval"] is False
    assert report["provider_write_authorization"] is False
    for n, rev in revisions.items():
        assert rev["after_post_sha256"] == digest(messages[n])
        assert rev["before_post_sha256"] != rev["after_post_sha256"]
        if rev["quote_changed"]:
            assert n in (3, 20, 23)
            assert index[n]["candidate_body_sha256"] == digest(quote(messages[n]))
            assert index[n]["candidate_evidence_file"] == "docs/audits/" + EVIDENCE
            assert rev["after_quote_sha256"] == digest(quote(messages[n]))
        else:
            assert n in (8, 21, 24)
            assert rev["before_quote_sha256"] == rev["after_quote_sha256"]

    assert "sic oculus, sic ille manus, sic ora ferebat" in messages[23]
    assert "Контекст: речь о личном наставлении" in messages[8]
    assert "Редакционное примечание" not in messages[21]
    assert "Примечание редакции:" in messages[21]
    assert "а) Святость — привычка" in messages[20]
