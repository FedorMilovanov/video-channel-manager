"""Series 03 owner-directed editorial relaunch, with legacy writers retired.

Provider-free tests only: immutable release/current-main CI and durable state
must succeed independently before a scheduled send can occur.
"""

from __future__ import annotations

from datetime import datetime, timedelta
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
SERIES = "lordchrist-quiz-series-03"
WORKFLOW_DIR = ROOT / ".github" / "workflows"
ACTIVE = WORKFLOW_DIR / "lordchrist-quiz-series-03-poster.yml"
ARCHIVE = ROOT / ".github" / "retired-workflows"
EXPECTED_SLUGS = (
    "atonement-goat",
    "sardis-vigil",
    "melchizedek-greater",
    "ark-right-order",
    "bronze-serpent",
    "isaac-return",
    "david-bread",
    "one-sacrifice",
    "faith-and-works",
    "adam-christ",
)


def test_series03_is_independent_ten_item_semantic_release() -> None:
    source = load_quiz_series(series_spec_path(SERIES))
    assert source.series_id == SERIES
    assert len(source.items) == 10
    assert [x.publication_id for x in source.items] == [f"lordchrist-quiz-s03-{slug}" for slug in EXPECTED_SLUGS]
    assert source.items[0].scheduled_at.isoformat() == "2026-11-15T13:00:00+03:00"
    assert source.items[-1].scheduled_at.isoformat() == "2026-12-03T13:00:00+03:00"
    assert all(
        next_item.scheduled_at - current.scheduled_at == timedelta(days=2)
        for current, next_item in zip(source.items, source.items[1:], strict=False)
    )
    answers = []
    for item in source.items:
        assert item.layout == "v2"
        assert build_poll_description(item) is None
        assert len(item.options) == 4
        assert len({x.casefold() for x in item.options}) == 4
        assert 45 <= len(item.question) <= 300
        assert 100 <= len(item.explanation) <= 200
        assert any(ref in item.explanation for ref in item.scripture_references)
        assert all(0 < len(x) <= 100 for x in item.options)
        assert "s01-" not in item.publication_id and "s02-" not in item.publication_id
        answers.append(item.correct_option_index)
    assert all(answers.count(position) <= 3 for position in range(4))
    assert "Иеффай" not in " ".join(item.question for item in source.items)
    assert "всесожж" not in source.items[0].question  # no answer in question


def test_series03_runtime_exact_sha_profile_and_bot_target_binding() -> None:
    profile = load_channel_profile(ROOT / "content/telegram/channels/lordchrist-rich.json")
    binding = load_target_binding(ROOT / "content/telegram/channels/lordchrist-target-binding.json", profile)
    source = load_quiz_series(series_spec_path(SERIES))
    actual = GenericReleaseQueue.model_validate_json(series_runtime_path(SERIES).read_text(encoding="utf-8"))
    expected = build_series_candidate(profile, source, binding)

    assert actual.release_id == "lordchrist-quiz-series-03-v1"
    assert actual.release_authorized is True
    assert "Owner-directed" in str(actual.reviewed_by)  # delegated, not fabricated personal review
    assert actual.reviewed_candidate_sha256 == expected.candidate_digest()
    assert actual.profile_sha256 == profile.digest
    assert actual.target_binding_sha256 == binding.digest
    assert actual.project_key == "lord-god-strength"
    assert (actual.channel_username, actual.chat_id, actual.bot_id, actual.bot_username) == (
        "@lordchrist",
        binding.chat_id,
        binding.bot_id,
        binding.bot_username,
    )
    assert len(actual.items) == len(expected.items) == 10
    assert all(
        x.model_dump(mode="json") == y.model_dump(mode="json")
        for x, y in zip(actual.items, expected.items, strict=True)
    )
    assert validate_series(SERIES, require_execution_authorized=True)["release_authorized"] is True


def test_old_quiz_workflows_are_absent_from_all_executable_paths() -> None:
    assert not (WORKFLOW_DIR / "lordchrist-quiz-poster.yml").exists()
    assert not (WORKFLOW_DIR / "lordchrist-quiz-series-poster.yml").exists()
    assert (ARCHIVE / "lordchrist-quiz-poster.yml").exists()
    assert (ARCHIVE / "lordchrist-quiz-series-02-poster.yml").exists()
    executable = [p for p in WORKFLOW_DIR.glob("*.yml") if "quiz" in p.name.lower()]
    assert executable == [ACTIVE]

    workflow = ACTIVE.read_text(encoding="utf-8")
    assert "SERIES_ID: lordchrist-quiz-series-03" in workflow
    assert "lordchrist-quiz-series-02" not in workflow
    assert "lordchrist-quiz-series-01" not in workflow
    assert 'cron: "0 10 * * *"' in workflow
    assert 'cron: "17 4,6,8,10,12,14 * * *"' in workflow
    assert "group: lordchrist-telegram-publisher" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "Send exactly once through the canonical generic Telegram runtime" in workflow
    assert "--verified-manual-canary-release" in workflow
    assert "telegram_multichannel_cli skip-expired" in workflow
    assert "series-state-check" in workflow
    assert "prepare" in workflow and "send-once" in workflow and "apply-outcome" in workflow
    assert "publication on editorial hold after owner rejection" not in workflow


def test_series03_is_not_historical_release_or_deleted_poll() -> None:
    new = load_quiz_series(series_spec_path(SERIES))
    old_one = load_quiz_series(series_spec_path("lordchrist-quiz-series-01"))
    old_two = load_quiz_series(series_spec_path("lordchrist-quiz-series-02"))
    new_ids = {x.publication_id for x in new.items}
    old_ids = {x.publication_id for x in (*old_one.items, *old_two.items)}
    assert not new_ids & old_ids
    assert "lordchrist-quiz-s02-jephthah" in old_ids
    assert "lordchrist-quiz-s02-jephthah" not in new_ids
    assert all(x.scheduled_at > datetime.fromisoformat("2026-11-14T16:05:00+03:00") for x in new.items)
