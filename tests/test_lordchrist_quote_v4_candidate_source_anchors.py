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
