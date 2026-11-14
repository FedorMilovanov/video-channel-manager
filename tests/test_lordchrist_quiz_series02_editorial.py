"""Series 02: meaningful Bible-quiz content, isolated from historical Series 01.

These tests are provider-inert. Passing validation does NOT authorize delivery.
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path


from video_channel_manager.lordchrist_quiz import (
    build_poll_description,
    build_series_candidate,
    load_quiz_series,
    series_runtime_path,
    series_spec_path,
    validate_series,
)
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_release import GenericReleaseQueue
from video_channel_manager.telegram_target_binding import load_target_binding

ROOT = Path(__file__).resolve().parents[1]
SERIES_ID = "lordchrist-quiz-series-02"
SERIES_WORKFLOW = ROOT / ".github/workflows/lordchrist-quiz-series-poster.yml"
IDENTITY_CONTEXT = {
    "lordchrist-quiz-s02-hagar",
    "lordchrist-quiz-s02-ahab",
    "lordchrist-quiz-s02-jephthah",
    "lordchrist-quiz-s02-sardis",
}
EXEGETICAL = {
    "lordchrist-quiz-s02-melchizedek",
    "lordchrist-quiz-s02-bronze-serpent",
    "lordchrist-quiz-s02-isaac-resurrection",
    "lordchrist-quiz-s02-david-sabbath",
    "lordchrist-quiz-s02-faith-and-works",
    "lordchrist-quiz-s02-adam-christ",
}
EXPECTED_ANSWERS = {
    "lordchrist-quiz-s02-hagar": "Агарь",
    "lordchrist-quiz-s02-ahab": "Ахав",
    "lordchrist-quiz-s02-jephthah": "Иеффай",
    "lordchrist-quiz-s02-sardis": "Сардийской",
    "lordchrist-quiz-s02-melchizedek": "Авраам дал ему десятину и принял благословение",
    "lordchrist-quiz-s02-bronze-serpent": "Медный змей",
    "lordchrist-quiz-s02-isaac-resurrection": "Он верил, что Бог может воскресить Исаака",
    "lordchrist-quiz-s02-david-sabbath": "Давид и спутники ели хлебы предложения",
    "lordchrist-quiz-s02-faith-and-works": "Признание истины без дел ещё не живая вера",
    "lordchrist-quiz-s02-adam-christ": "Непослушание одного ведёт к осуждению, послушание Другого — к оправданию",
}


def test_series02_textual_review_shape_and_distinct_answers() -> None:
    series = load_quiz_series(series_spec_path(SERIES_ID))
    assert len(series.items) == 10
    assert set(EXPECTED_ANSWERS) == IDENTITY_CONTEXT | EXEGETICAL
    assert len(IDENTITY_CONTEXT) == 4
    assert len(EXEGETICAL) == 6
    assert {item.publication_id: item.options[item.correct_option_index] for item in series.items} == EXPECTED_ANSWERS
    assert series.items[0].scheduled_at.isoformat() == "2026-11-10T13:00:00+03:00"
    assert series.items[-1].scheduled_at.isoformat() == "2026-11-28T13:00:00+03:00"

    for item in series.items:
        assert len(item.options) == 4
        assert len(set(o.casefold() for o in item.options)) == 4
        assert len(item.question) >= 45
        assert 100 <= len(item.explanation) <= 200
        assert item.layout == "v2"
        assert item.hashtags == ""
        assert build_poll_description(item) is None
        assert any(ref in item.explanation for ref in item.scripture_references)
        assert all("\n" not in option for option in item.options)

    assert all(
        b.scheduled_at - a.scheduled_at == timedelta(days=2)
        for a, b in zip(series.items, series.items[1:], strict=False)
    )


def test_series02_runtime_matches_user_approved_exact_candidate() -> None:
    profile = load_channel_profile(ROOT / "content/telegram/channels/lordchrist-rich.json")
    binding = load_target_binding(ROOT / "content/telegram/channels/lordchrist-target-binding.json", profile)
    series = load_quiz_series(series_spec_path(SERIES_ID))
    candidate = build_series_candidate(profile, series, binding)
    committed = GenericReleaseQueue.model_validate_json(series_runtime_path(SERIES_ID).read_text(encoding="utf-8"))
    assert committed.project_key == "lord-god-strength"
    assert committed.channel_username == "@lordchrist"
    assert committed.release_authorized is True
    assert committed.reviewed_candidate_sha256 == candidate.candidate_digest()
    assert committed.reviewed_candidate_sha256 == (
        "sha256:e8bb34452127f7ef7baa9343b9b338428931717ec329446a4d90d9ef0a777a15"
    )
    assert committed.reviewed_by == "Fedor Milovanov (user editorial approval, 2026-11-03)"
    assert committed.reviewed_at is not None
    assert len(committed.items) == 10
    assert all(
        (actual.publication_id, actual.source_sha256, actual.payload.model_dump(mode="json"))
        == (expected.publication_id, expected.source_sha256, expected.payload.model_dump(mode="json"))
        for actual, expected in zip(committed.items, candidate.items, strict=True)
    )
    assert all(item.payload.description is None for item in committed.items)
    assert all(item.payload.poll_type == "quiz" for item in committed.items)
    assert all(item.payload.explanation is not None for item in committed.items)
    assert validate_series(SERIES_ID, require_release_authorized=True)["release_authorized"] is True
    assert validate_series(SERIES_ID, require_execution_authorized=True)["release_authorized"] is True


def test_workflow_targets_only_new_series_without_implicit_authorization() -> None:
    workflow = SERIES_WORKFLOW.read_text(encoding="utf-8")
    assert "SERIES_ID: lordchrist-quiz-series-02" in workflow
    assert "SERIES_ID: lordchrist-quiz-series-01" not in workflow
    assert "  schedule:" not in workflow
    assert "publication on editorial hold" in workflow
    assert workflow.index("publication on editorial hold") < workflow.index('case "$OPERATION" in')
    assert "if: github.ref == 'refs/heads/main'" in workflow
    assert "INITIALIZE:@lordchrist:$SERIES_ID" in workflow
    assert "PUBLISH:@lordchrist:$SERIES_ID" in workflow
    assert "telegram_publication_freshness next" in workflow
    assert 'mkdir -p "$(dirname "$FRESHNESS_PATH")"' in workflow


def test_immutable_prior_series_is_not_repurposed_as_series02() -> None:
    old = json.loads(series_runtime_path("lordchrist-quiz-series-01").read_text(encoding="utf-8"))
    new = json.loads(series_runtime_path(SERIES_ID).read_text(encoding="utf-8"))
    assert old["release_id"] == "lordchrist-quiz-series-01-v1"
    assert old["release_authorized"] is True  # Historical approval is never inherited.
    assert new["release_id"] == "lordchrist-quiz-series-02-v1"
    assert new["release_authorized"] is True
    assert new["reviewed_candidate_sha256"] != old["reviewed_candidate_sha256"]
    assert not {item["publication_id"] for item in old["items"]} & {item["publication_id"] for item in new["items"]}
