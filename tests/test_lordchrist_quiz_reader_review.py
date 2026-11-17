"""Provider-inert QA for the eight Scripture-first Telegram QUIZ editorial review cards."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUIZ_DIR = ROOT / "content/telegram/lordchrist/quiz"
REVIEW = QUIZ_DIR / "QUIZ_BIBLE_THEOLOGY_READER_REVIEW_20261117.md"
DRAFT = QUIZ_DIR / "SERIES_03_PENDING_EDITORIAL_CANDIDATES_20261117.json"
CORRECT_ANNOTATION = " **← верный вариант (только для редактора)**"


def test_all_eight_reader_reviews_match_the_unapproved_exact_candidate_text() -> None:
    document = REVIEW.read_text(encoding="utf-8")
    bundle = json.loads(DRAFT.read_text(encoding="utf-8"))
    assert bundle["review_status"] == "DRAFT_HOLD"
    assert bundle["publication_authorized"] is False
    assert bundle["release_authorized"] is False
    assert "undefined" not in document.casefold()
    assert "не является независимым человеческим одобрением" in document

    sections = re.split(r"(?m)^## ([1-8])\. ", document)
    assert len(sections) == 17
    for index, candidate in enumerate(bundle["items"], start=1):
        number = sections[2 * index - 1]
        section = sections[2 * index]
        assert number == str(index)
        question = section.split("**Вопрос для читателя**\n\n", 1)[1].split("\n\n", 1)[0]
        assert question == candidate["question"], candidate["source_publication_id"]

        options_block = section.split("**Варианты ответов**\n\n", 1)[1].split("\n\n**Объяснение Telegram", 1)[0]
        lines = re.findall(r"(?m)^([1-4])\. (.+)$", options_block)
        assert [int(number) for number, _ in lines] == [1, 2, 3, 4]
        selected = []
        for number, value in lines:
            is_correct = value.endswith(CORRECT_ANNOTATION)
            plain_text = value[: -len(CORRECT_ANNOTATION)] if is_correct else value
            assert plain_text == candidate["options"][int(number) - 1]
            if is_correct:
                selected.append(int(number) - 1)
        assert selected == [candidate["correct_option_index"]]

        explanation_section = section.split("**Объяснение Telegram (", 1)[1]
        limit_text, remainder = explanation_section.split(")**", 1)
        assert limit_text == f"{len(candidate['explanation'])}/200"
        assert remainder.split("\n\n> ", 1)[1].split("\n\n", 1)[0] == candidate["explanation"]

        wrong_block = section.split("**Почему остальные варианты неверны**\n\n", 1)[1].split("\n\n**Приёмка:**", 1)[0]
        wrong = re.findall(r"(?m)^- \*\*Неверно ([1-4]):\*\* (.+)$", wrong_block)
        expected = {n for n in (1, 2, 3, 4) if n != candidate["correct_option_index"] + 1}
        assert {int(number) for number, _ in wrong} == expected
        assert len(wrong) == 3
        for number, explanation in wrong:
            assert len(explanation.strip()) >= 24, (candidate["source_publication_id"], number)
            assert explanation.lower().strip() not in {"undefined", "null", "none", "todo", "tbd"}
        assert "HOLD" in section
