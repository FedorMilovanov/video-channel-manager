import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "docs/audits/2026-11-05-lordchrist-30-quote-editorial-candidate-index-v2.json"


def test_unreleased_quote_source_anchor_corrections():
    data = json.loads(FILE.read_text(encoding="utf-8"))
    cards = {c["sequence"]: c for c in data["entries"]}
    assert len(cards) == 30
    assert (
        cards[3]["candidate_source_anchor_end"]
        == "and it is God upon his throne of whom we shall speak in this discourse."
    )
    assert cards[29]["candidate_source_anchor_start"].startswith("For, since all historical and psychological research")
    assert (
        cards[29]["candidate_source_anchor_end"]
        == "the science of the revelation of God and of our knowledge concerning him."
    )
    assert (
        cards[30]["candidate_source_anchor_start"]
        == "Whoever reads the gospel with a single eye, and sincere intentions, will find,"
    )
    assert cards[23]["candidate_source_anchor_end"] == "that I might weep abundantly over them all!"
    assert data["approved_new_queue"] is False
    assert data["provider_write_authorization"] is False
    assert all(not c["eligible_for_release"] for c in cards.values())


def test_source_reconciliation_digests_and_preview():
    import hashlib

    evidence_path = ROOT / "docs/audits/2026-11-05-lordchrist-quote-v4-four-reconciled-drafts.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    index = json.loads(FILE.read_text(encoding="utf-8"))
    deck = json.loads(
        (ROOT / "docs/audits/2026-11-05-lordchrist-30-card-editorial-preview-v2-inert.json").read_text(encoding="utf-8")
    )
    ix = {x["sequence"]: x for x in index["entries"]}
    posts = {x["sequence"]: x for x in deck["posts"]}
    assert len(evidence["items"]) == 4
    assert evidence["provider_write_authorization"] is False
    for entry in evidence["items"]:
        num, body = entry["sequence"], entry["translation_ru"]
        digest = "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()
        assert entry["translation_sha256"] == digest
        assert ix[num]["candidate_body_sha256"] == digest
        assert posts[num]["text"].split("\n\n©", 1)[0] == "«" + body + "»"
    assert "единственный наш клик" not in posts[2]["text"]


def test_all_twenty_redrafts_match_the_inert_reader_preview():
    import re

    base = ROOT / "docs/audits"
    files = [
        "2026-11-04-lordchrist-contiguous-quote-redrafts.json",
        "2026-11-04-lordchrist-remaining-10-contiguous-redrafts.json",
    ]
    draft_items = []
    for filename in files:
        draft_items.extend(json.loads((base / filename).read_text(encoding="utf-8"))["drafts"])
    corrected = json.loads(
        (base / "2026-11-05-lordchrist-quote-v4-four-reconciled-drafts.json").read_text(encoding="utf-8")
    )
    by_number = {entry["sequence"]: entry["translation_ru"] for entry in draft_items}
    assert len(by_number) == 20
    by_number.update({entry["sequence"]: entry["translation_ru"] for entry in corrected["items"]})
    preview = json.loads(
        (base / "2026-11-05-lordchrist-30-card-editorial-preview-v2-inert.json").read_text(encoding="utf-8")
    )
    previews = {entry["sequence"]: entry["text"] for entry in preview["posts"]}

    def canonical(text):
        return re.sub(r"[\s«»„“”]", "", text).casefold()

    for number, accepted_text in by_number.items():
        quote = previews[number].split("\n\n©", 1)[0]
        assert canonical(quote) == canonical(accepted_text), number


def test_ten_retained_candidates_match_evidence_hashes():
    import hashlib

    base = ROOT / "docs/audits"
    name = "2026-11-05-lordchrist-quote-v4-ten-retained-candidates.json"
    evidence = json.loads((base / name).read_text(encoding="utf-8"))
    index = json.loads(FILE.read_text(encoding="utf-8"))
    deck = json.loads(
        (base / "2026-11-05-lordchrist-30-card-editorial-preview-v2-inert.json").read_text(encoding="utf-8")
    )
    idx = {x["sequence"]: x for x in index["entries"]}
    posts = {x["sequence"]: x for x in deck["posts"]}
    assert sorted(x["sequence"] for x in evidence["items"]) == [
        2,
        3,
        4,
        9,
        20,
        23,
        24,
        28,
        29,
        30,
    ]
    assert evidence["provider_write_authorization"] is False
    for x in evidence["items"]:
        n, text = x["sequence"], x["translation_ru"]
        digest = "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
        assert x["translation_sha256"] == digest
        assert idx[n]["candidate_body_sha256"] == digest
        assert posts[n]["text"].split("\n\n©", 1)[0] == "«" + text + "»"
        assert idx[n]["eligible_for_release"] is False


def test_all_candidate_digests_are_source_bound():
    import hashlib

    data = json.loads(FILE.read_text(encoding="utf-8"))
    base = ROOT / "docs/audits"
    sources = {}
    for name in (
        "2026-11-04-lordchrist-contiguous-quote-redrafts.json",
        "2026-11-04-lordchrist-remaining-10-contiguous-redrafts.json",
    ):
        files = json.loads((base / name).read_text(encoding="utf-8"))
        sources.update({x["sequence"]: x["translation_ru"] for x in files["drafts"]})
    for name in (
        "2026-11-05-lordchrist-quote-v4-four-reconciled-drafts.json",
        "2026-11-05-lordchrist-quote-v4-ten-retained-candidates.json",
    ):
        files = json.loads((base / name).read_text(encoding="utf-8"))
        sources.update({x["sequence"]: x["translation_ru"] for x in files["items"]})
    assert len(sources) == len(data["entries"]) == 30
    for entry in data["entries"]:
        digest = hashlib.sha256(sources[entry["sequence"]].encode()).hexdigest()
        assert entry["candidate_body_sha256"] == "sha256:" + digest
    assert data["provider_write_authorization"] is False
