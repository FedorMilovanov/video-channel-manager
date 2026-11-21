"""Charnock #13: historical candidate vs the approved 2026-11-21 revision."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "content/research/charnock-13-quotation-gap-candidate-20261117.json"
DRAFT = ROOT / "content/research/charnock-13-quotation-gap-candidate-20261117.md"
PROOF = ROOT / "content/research/charnock-13-primary-witness-quote-boundaries-20261118.md"
APPROVED = ROOT / "content/telegram/lordchrist/telegraph-v1/charnock/lordchrist-telegraph-charnock-13.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _quote(document: dict, block_id: str) -> str:
    block = next(item for item in document["blocks"] if item["block_id"] == block_id)
    pieces = block["blocks"][0]["text"]
    return "".join(piece if isinstance(piece, str) else piece["text"] for piece in pieces)


def test_candidate_is_the_frozen_two_block_historical_sidecar() -> None:
    assert hashlib.sha256(CANDIDATE.read_bytes()).hexdigest() == (
        "d647368dac7786b8f877c6c7882beafa0d95d89c61b85674b221db09d0327125"
    )
    assert hashlib.sha256(DRAFT.read_bytes()).hexdigest() == (
        "0fc50fdde58070fab103d6254c22925b9d56b4ff1cc7f0e2533a815d239975ae"
    )
    candidate = _load(CANDIDATE)
    assert candidate["document_id"] == "lordchrist-telegraph-charnock-13"
    assert candidate["revision"] == "charnock-13-v2-editorial-candidate"
    assert len(candidate["blocks"]) == 44
    assert "[…]" in _quote(candidate, "q-3")
    assert "[…]" in _quote(candidate, "q-19")


def test_q3_gap_is_marked_and_the_translation_calques_are_gone() -> None:
    approved, candidate = _load(APPROVED), _load(CANDIDATE)
    corrected = (
        "Немедленно пресекайте такие внушения, отвергайте их; "
        "противопоставляйте им всё устроение природы, чтобы оно сражалось против них"
    )
    for document in (approved, candidate):
        quote = _quote(document, "q-3")
        assert "без прикрас. […]" in quote
        assert corrected in quote
        assert "Молча подавляйте" not in quote
        assert "систему природы сражаться" not in quote
        assert "как звёзды сражались против Сисары" in quote
    assert corrected in DRAFT.read_text(encoding="utf-8")


def test_q19_candidate_keeps_gap_and_approved_revision_is_continuous() -> None:
    candidate, approved = _load(CANDIDATE), _load(APPROVED)
    assert "отражаться обратно к Богу. […] Что за утешение" in _quote(candidate, "q-19")
    assert "так и активность наших душ" not in _quote(candidate, "q-19")
    approved_quote = _quote(approved, "q-19")
    assert "мухам" in approved_quote and "Пс. 10:4" in approved_quote
    assert "так и активность наших душ" not in approved_quote
    assert "[…]" not in approved_quote


def test_approved_source_19_evidence_covers_the_whole_restored_interval() -> None:
    candidate = next(s for s in _load(CANDIDATE)["sources"] if s["source_id"] == "src-19-charnock")
    approved = next(s for s in _load(APPROVED)["sources"] if s["source_id"] == "src-19-charnock")
    for text in (candidate["evidence"], approved["evidence"]):
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
    assert "ПРОПУЩЕННЫЙ В РУССКОЙ ЦИТАТЕ ФРАГМЕНТ" in candidate["evidence"]
    assert "ВОССТАНОВЛЕННЫЙ 21.11.2026" in approved["evidence"]
    assert "русская цитата восстановлена непрерывно" in approved["evidence"]


def test_only_source_19_differs_between_candidate_and_approved() -> None:
    before = {s["source_id"]: s for s in _load(CANDIDATE)["sources"]}
    after = {s["source_id"]: s for s in _load(APPROVED)["sources"]}
    assert before.keys() == after.keys()
    assert {source for source in before if before[source] != after[source]} == {"src-19-charnock"}


def test_source_note_preserves_the_historical_research_verdict() -> None:
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
