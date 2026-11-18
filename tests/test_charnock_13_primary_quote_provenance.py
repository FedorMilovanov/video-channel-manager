"""Research-only Charnock #13 quote proof: no silent canonical publication change."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "content/research/charnock-13-quotation-gap-candidate-20261117.json"
DRAFT = ROOT / "content/research/charnock-13-quotation-gap-candidate-20261117.md"
PROOF = ROOT / "content/research/charnock-13-primary-witness-quote-boundaries-20261118.md"
APPROVED = (
    ROOT / "content/telegram/lordchrist/telegraph-v1/charnock/lordchrist-telegraph-charnock-13.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _quote(document: dict, block_id: str) -> str:
    block = next(item for item in document["blocks"] if item["block_id"] == block_id)
    pieces = block["blocks"][0]["text"]
    return "".join(piece if isinstance(piece, str) else piece["text"] for piece in pieces)


def test_candidate_keeps_all_other_approved_blocks_unchanged() -> None:
    before, after = _load(APPROVED), _load(CANDIDATE)
    assert before["document_id"] == after["document_id"] == "lordchrist-telegraph-charnock-13"
    assert before["revision"] == "charnock-13-v1"
    assert after["revision"] == "charnock-13-v2-editorial-candidate"
    assert len(before["blocks"]) == len(after["blocks"]) == 44
    assert [x["block_id"] for x in before["blocks"]] == [x["block_id"] for x in after["blocks"]]
    changed = {
        old["block_id"]
        for old, new in zip(before["blocks"], after["blocks"], strict=True)
        if old != new
    }
    assert changed == {"q-3", "q-19"}
    for key in ("document_id", "project_key", "schema_name", "schema_version", "media", "media_slots"):
        assert before[key] == after[key]


def test_q3_correction_is_in_both_drafts_and_visible_as_a_gap() -> None:
    candidate, original = _load(CANDIDATE), _load(APPROVED)
    quote = _quote(candidate, "q-3")
    md = DRAFT.read_text(encoding="utf-8")
    assert "[…]" in quote
    corrected = (
        "Немедленно пресекайте такие внушения, отвергайте их; "
        "противопоставляйте им всё устроение природы, чтобы оно сражалось против них"
    )
    assert corrected in quote
    assert corrected in md
    assert "Молча подавляйте" not in quote
    assert "Молча подавляйте" not in md
    assert "систему природы сражаться" not in quote
    assert "Молча подавляйте" in _quote(original, "q-3")
    assert "как звёзды сражались против Сисары" in quote


def test_q19_gap_and_full_source_provenance_are_not_erased() -> None:
    candidate = _load(CANDIDATE)
    original = _load(APPROVED)
    quote = _quote(candidate, "q-19")
    assert "[…]" in quote
    assert "Что за утешение может быть" in quote
    assert "Забытый Бог для нас" in quote
    assert "так и активность наших душ" not in quote
    assert "[…]" not in _quote(original, "q-19")
    proof = next(s for s in candidate["sources"] if s["source_id"] == "src-19-charnock")
    text = proof["evidence"]
    for anchor in (
        "Our minds are a beam from God",
        "like flies",
        "dunghills than flowers",
        "God is not in all his thoughts",
        "Psalm 10:4",
        "What comfort can be had in the being of God",
        "A God forgotten is as good as no God to us",
    ):
        assert anchor in text
    assert "[ПРОПУЩЕННЫЙ В РУССКОЙ ЦИТАТЕ ФРАГМЕНТ:" in text
    assert "What comfort can be had" not in next(
        s for s in original["sources"] if s["source_id"] == "src-19-charnock"
    )["evidence"]


def test_only_research_evidence_source_19_was_extended() -> None:
    before, after = _load(APPROVED), _load(CANDIDATE)
    b = {s["source_id"]: s for s in before["sources"]}
    a = {s["source_id"]: s for s in after["sources"]}
    assert b.keys() == a.keys()
    changed = {source for source in b if b[source] != a[source]}
    assert changed == {"src-19-charnock"}


def test_source_note_preserves_independent_review_and_publication_hold() -> None:
    proof = PROOF.read_text(encoding="utf-8")
    for term in (
        "RESEARCH_ONLY",
        "NO_PEER_APPROVAL",
        "q-3",
        "q-19",
        "silence them quickly",
        "like flies",
        "Psalm 10:4",
        "Пс. 9:25",
        "Isa. 34:12",
        "Ис. 43:12",
        "INDEPENDENT_PHILOLOGICAL_REVIEW_PENDING",
        "EDITORIAL/PUBLICATION_HOLD",
    ):
        assert term in proof
    assert "https://www.gutenberg.org/ebooks/53527" in proof
    assert "https://library.pristinegrace.com/article/discourse-i-on-the-existence-of-god" in proof
