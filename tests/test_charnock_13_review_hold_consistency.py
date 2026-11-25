"""Charnock #13: the historical HOLD is closed for content, but not for sending."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "content/research/charnock-13-quotation-gap-candidate-20261117.json"
CANDIDATE_MD = ROOT / "content/research/charnock-13-quotation-gap-candidate-20261117.md"
ARTICLE = ROOT / "content/telegram/lordchrist/telegraph-v1/charnock/lordchrist-telegraph-charnock-13.json"
REVIEW = ROOT / "content/telegram/lordchrist/telegraph-v1/charnock/lordchrist-telegraph-charnock-13-проверка.md"
QUEUE = ROOT / "content/telegram/lordchrist/telegraph-v1/article-queue.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _quote(document: dict, block_id: str) -> str:
    block = next(item for item in document["blocks"] if item["block_id"] == block_id)
    pieces = block["blocks"][0]["text"]
    return "".join(piece if isinstance(piece, str) else piece["text"] for piece in pieces)


def test_current_status_is_content_corrected_and_send_held() -> None:
    text = REVIEW.read_text(encoding="utf-8")
    assert text.startswith("# Проверка Telegraph-издания 13 (2026-10-25)")
    head = text[:900]
    assert "ДЕЙСТВУЮЩИЙ СТАТУС — TELEGRAM SEND HOLD" in head
    assert "in place" in head and "21.11.2026" in head
    for block in ("q-3", "q-9", "q-11", "q-12", "q-19"):
        assert block in head
    assert "ИСТОРИЧЕСКИЙ ВЕРДИКТ" in text
    assert "SUPERSEDED" in text
    assert "Вердикт: **готово к Telegraph-публикации" not in text


def test_charnock_13_writer_hold_is_not_only_documentary() -> None:
    source = (ROOT / "src/video_channel_manager/lordchrist_charnock_reschedule.py").read_text(encoding="utf-8")
    assert 'CHARNOCK_EDITORIAL_HOLDS = frozenset({"lordchrist-telegraph-charnock-13"})' in source
    assert 'args.stage in ("prepare", "send")' in source
    assert "TELEGRAM SEND HOLD" in source


def test_all_five_canonical_quote_gaps_are_closed_or_marked() -> None:
    article = _load(ARTICLE)
    q3, q9, q11, q12, q19 = (_quote(article, f"q-{n}") for n in (3, 9, 11, 12, 19))
    assert "без прикрас. […] Немедленно пресекайте" in q3
    assert "Молча подавляйте" not in q3
    assert "Если мы колеблемся в этом начале" in q9
    assert "сладость" in q9
    assert "Чем более мы утверждаемся" in q11
    assert "Пс. 103:31" in q12 and "урок о творении" in q12
    assert "мухам" in q19 and "Пс. 10:4" in q19
    assert "так и активность наших душ" not in q19
    assert article["revision"] == "charnock-13-qc-20261121"


def test_canonical_blob_is_synchronised_with_the_queue() -> None:
    payload = ARTICLE.read_bytes()
    blob = hashlib.sha1(b"blob " + str(len(payload)).encode("ascii") + b"\0" + payload).hexdigest()
    queue = _load(QUEUE)
    matches = [item for item in queue["items"] if item["publication_id"] == "lordchrist-telegraph-charnock-13"]
    assert len(matches) == 1
    assert matches[0]["article"]["git_blob_sha"] == blob


def test_research_candidate_is_frozen_historical_evidence() -> None:
    assert hashlib.sha256(CANDIDATE.read_bytes()).hexdigest() == (
        "d647368dac7786b8f877c6c7882beafa0d95d89c61b85674b221db09d0327125"
    )
    assert hashlib.sha256(CANDIDATE_MD.read_bytes()).hexdigest() == (
        "0fc50fdde58070fab103d6254c22925b9d56b4ff1cc7f0e2533a815d239975ae"
    )
    candidate = _load(CANDIDATE)
    assert candidate["revision"] == "charnock-13-v2-editorial-candidate"
    assert "[…]" in _quote(candidate, "q-3")
    assert "[…]" in _quote(candidate, "q-19")
