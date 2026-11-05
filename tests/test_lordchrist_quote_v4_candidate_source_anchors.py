import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "docs/audits/2026-11-04-lordchrist-30-quote-editorial-candidate-index.json"


def test_unreleased_quote_source_anchor_corrections():
    data = json.loads(FILE.read_text(encoding="utf-8"))
    cards = {c["sequence"]: c for c in data["entries"]}
    assert len(cards) == 30
    assert cards[3]["candidate_source_anchor_end"] == "and it is God upon his throne of whom we shall speak in this discourse."
    assert cards[29]["candidate_source_anchor_start"].startswith("For, since all historical and psychological research")
    assert cards[29]["candidate_source_anchor_end"] == "the science of the revelation of God and of our knowledge concerning him."
    assert cards[30]["candidate_source_anchor_start"] == "Whoever reads the gospel with a single eye, and sincere intentions, will find,"
    assert data["approved_new_queue"] is False
    assert data["provider_write_authorization"] is False
    assert all(not c["eligible_for_release"] for c in cards.values())


def test_source_reconciliation_digests_and_preview():
    import hashlib
    evidence_path = ROOT / "docs/audits/2026-11-05-lordchrist-quote-v4-four-reconciled-drafts.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    index = json.loads(FILE.read_text(encoding="utf-8"))
    deck = json.loads((ROOT / "docs/audits/2026-11-04-lordchrist-30-card-editorial-preview-inert.json").read_text(encoding="utf-8"))
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
