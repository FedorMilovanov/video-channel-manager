"""Owner-requested QUIZ editorial hold after a verified, subsequently deleted poll.

This is a provider-inert regression: never dispatch or mutate Telegram state.
The historical approved runtime/ledger remains immutable forensic evidence.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/lordchrist-quiz-series-poster.yml"
REVIEW = ROOT / "content/telegram/lordchrist/quiz/QUIZ_EDITORIAL_REAUDIT_20261114.md"
SPEC = ROOT / "content/telegram/lordchrist/quiz/lordchrist-quiz-series-02.json"
RUNTIME = ROOT / "content/telegram/lordchrist/quiz/lordchrist-quiz-series-02-runtime.json"


def test_rejected_series_cannot_run_on_schedule_or_explicit_publish() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "  schedule:" not in source
    assert "cron:" not in source
    assert "  workflow_dispatch:" in source
    assert 'if [[ "$OPERATION" == "publish" ]]; then' in source
    assert "Series 02 publication on editorial hold after owner rejection" in source
    assert source.index('if [[ "$OPERATION" == "publish" ]]; then') < source.index('case "$OPERATION" in')
    assert source.index('if [[ "$OPERATION" == "publish" ]]; then') < source.index(
        "Require exact current-main CI proof before state/provider path"
    )
    # Preserve access to provider-inert validate; hold blocks publish only.
    assert "validate-series" in source
    assert "video_channel_manager.telegram_multichannel_cli send-once" in source


def test_historical_approved_spec_and_published_identity_are_not_rewritten() -> None:
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    runtime = json.loads(RUNTIME.read_text(encoding="utf-8"))
    assert runtime["release_authorized"] is True  # historical fact, NOT ongoing permission
    assert len(spec["items"]) == len(runtime["items"]) == 10
    jephthah = spec["items"][2]
    assert jephthah["publication_id"] == "lordchrist-quiz-s02-jephthah"
    assert jephthah["scheduled_at"] == "2026-11-14T13:00:00+03:00"
    assert "обет перед битвой" in jephthah["question"]
    assert jephthah["options"][jephthah["correct_option_index"]] == "Иеффай"
    assert runtime["items"][2]["publication_id"] == "lordchrist-quiz-s02-jephthah"


def test_editorial_document_covers_all_old_questions_and_seven_provider_inert_drafts() -> None:
    source = REVIEW.read_text(encoding="utf-8")
    assert "10 вопросов Series 01" in source
    assert "10 вопросов Series 02" in source
    assert "Две отдельные пробы" in source
    assert "только editorial drafts" in source
    assert "НЕ runtime" in source
    assert "не новая очередь" in source.lower()
    assert "всесожж" in source
    assert "«земля Мориа»" in source
    assert "владельца" in source
    after_drafts = source.split("## Предложения для семи ОЖИДАЮЩИХ тем", 1)[1]
    before_rules = after_drafts.split("## Новый минимальный стандарт", 1)[0]
    assert before_rules.count("**Вопрос:**") == 7
    assert before_rules.count("**Правильный:**") == 7
    positions = [int(x) for x in re.findall(r"\\*\\*Правильный:\\*\\* ([1-4])\\.", before_rules)]
    assert len(positions) == 7
    assert len(set(positions)) == 4
    assert max(positions.count(option) for option in (1, 2, 3, 4)) <= 2
    explanations = re.findall(r"\\*\\*Пояснение quiz \\((\\d+)/200\\):\\*\\* (.+)", before_rules)
    assert len(explanations) == 7
    for declared, explanation in explanations:
        assert len(explanation) == int(declared)
        assert 100 <= len(explanation) <= 200
    # Editorial reviews are text-only and carry no runnable release/publish commands.
    assert "sendPoll(" not in source
    assert "gh workflow run" not in source
