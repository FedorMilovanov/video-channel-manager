"""Prevent a superseded Charnock #13 review from acting as a release grant."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "content/telegram/lordchrist/telegraph-v1/charnock/lordchrist-telegraph-charnock-13-проверка.md"


def test_charnock_13_current_verdict_is_hold_and_old_ready_verdict_retired() -> None:
    text = REVIEW.read_text(encoding="utf-8")
    assert text.startswith("# Проверка Telegraph-издания 13 (2026-10-25)")
    assert "ДЕЙСТВУЮЩИЙ СТАТУС — EDITORIAL/PUBLICATION_HOLD" in text[:750]
    assert "ИСТОРИЧЕСКИЙ ВЕРДИКТ" in text
    assert "SUPERSEDED" in text
    assert "q-3" in text and "q-19" in text
    assert "Вердикт: **готово к Telegraph-публикации" not in text


def test_charnock_13_writer_hold_is_not_only_documentary() -> None:
    source = (ROOT / "src/video_channel_manager/lordchrist_charnock_reschedule.py").read_text(encoding="utf-8")
    assert 'CHARNOCK_EDITORIAL_HOLDS = frozenset({"lordchrist-telegraph-charnock-13"})' in source
    assert 'args.stage in ("prepare", "send")' in source
