"""The trial Bible quiz for @lordchrist is bound to an exact reviewed release.

The committed quiz spec is the human-reviewed content; the committed runtime
release must be the review-authorized build of that exact spec against the
exact write-authorized channel profile and immutable target binding, and the
GitHub workflow may only validate, initialize state, or publish that exact
publication from current main with an exact confirmation string.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUIZ_DIR = ROOT / "content/telegram/lordchrist/quiz"
WORKFLOW = ROOT / ".github/workflows/lordchrist-quiz-poster.yml"
PUBLICATION_ID = "lordchrist-quiz-city-of-palms"


def test_trial_quiz_spec_is_factually_bound() -> None:
    from video_channel_manager.lordchrist_quiz import build_poll_description, load_quiz_spec

    spec = load_quiz_spec(QUIZ_DIR / f"{PUBLICATION_ID}.json")
    assert spec.publication_id == PUBLICATION_ID
    assert spec.options[spec.correct_option_index] == "Иерихон"
    assert "Втор. 34:3" in spec.scripture_references
    assert len(spec.explanation) <= 200
    assert len(build_poll_description(spec)) <= 1024


def test_clean_layout_v2_hides_everything_until_after_voting() -> None:
    from video_channel_manager.lordchrist_quiz import (
        build_poll_description,
        build_quiz_candidate,
        load_quiz_spec,
    )
    from video_channel_manager.telegram_channel_profile import load_channel_profile
    from video_channel_manager.telegram_target_binding import load_target_binding

    spec = load_quiz_spec(QUIZ_DIR / "lordchrist-quiz-book-without-gods-name.json")
    assert spec.layout == "v2"
    assert spec.options[spec.correct_option_index] == "Есфирь"
    # Nothing before voting: no intro block, no hashtags, no reference hints.
    assert build_poll_description(spec) is None

    profile = load_channel_profile(ROOT / "content/telegram/channels/lordchrist-rich.json")
    binding = load_target_binding(ROOT / "content/telegram/channels/lordchrist-target-binding.json", profile)
    payload = build_quiz_candidate(profile, spec, binding).items[0].payload
    assert payload.description is None
    # Scripture references arrive only with the post-vote explanation.
    assert payload.explanation is not None and "Есф. 4:14" in payload.explanation
    assert len(payload.explanation) <= 200


def test_trial_quiz_runtime_is_the_authorized_build_of_the_spec() -> None:
    from video_channel_manager.lordchrist_quiz import (
        build_quiz_candidate,
        load_quiz_spec,
        runtime_path,
        spec_source_sha256,
    )
    from video_channel_manager.telegram_channel_profile import load_channel_profile
    from video_channel_manager.telegram_multichannel_release import GenericReleaseQueue
    from video_channel_manager.telegram_target_binding import load_target_binding

    profile = load_channel_profile(ROOT / "content/telegram/channels/lordchrist-rich.json")
    binding = load_target_binding(ROOT / "content/telegram/channels/lordchrist-target-binding.json", profile)
    spec = load_quiz_spec(QUIZ_DIR / f"{PUBLICATION_ID}.json")
    release = GenericReleaseQueue.model_validate_json(runtime_path(PUBLICATION_ID).read_text(encoding="utf-8"))

    candidate = build_quiz_candidate(profile, spec, binding)
    assert release.release_authorized is True
    assert release.reviewed_candidate_sha256 == candidate.candidate_digest()
    assert release.profile_sha256 == profile.digest == binding.profile_sha256
    assert (release.chat_id, release.bot_id, release.bot_username) == (
        binding.chat_id,
        binding.bot_id,
        binding.bot_username,
    )
    assert profile.provider_writes_authorized is True

    assert len(release.items) == 1
    item = release.items[0]
    assert item.source_sha256 == spec_source_sha256(spec)
    payload = item.payload
    assert payload.poll_type == "quiz"
    assert payload.question == spec.question
    assert payload.options == spec.options
    assert payload.correct_option_ids == (spec.correct_option_index,)
    assert payload.explanation == spec.explanation


def _write_stale_ledger(state_checkout: Path, *, published: bool) -> Path:
    from video_channel_manager.lordchrist_quiz import ledger_relative_path, state_init

    target = state_checkout / ledger_relative_path(PUBLICATION_ID)
    assert state_init(PUBLICATION_ID, state_checkout) == target
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["release_digest"] = "sha256:" + "0" * 64  # bound to a superseded release
    if published:
        # A touched (no longer pending) entry must block re-initialization.
        payload["entries"][PUBLICATION_ID]["state"] = "skipped"
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def test_state_init_reinitializes_only_a_provably_untouched_stale_ledger(tmp_path: Path) -> None:
    import pytest

    from video_channel_manager.lordchrist_quiz import load_quiz_release, runtime_path, state_init
    from video_channel_manager.telegram_multichannel_state import load_ledger

    target = _write_stale_ledger(tmp_path, published=False)
    release = load_quiz_release(runtime_path(PUBLICATION_ID))
    assert state_init(PUBLICATION_ID, tmp_path) == target
    ledger = load_ledger(target, release)  # now bound to the current release
    assert ledger.release_digest == release.digest

    other = tmp_path / "published-case"
    _write_stale_ledger(other, published=True)
    with pytest.raises(ValueError, match="provably untouched"):
        state_init(PUBLICATION_ID, other)


SERIES_ID = "lordchrist-quiz-series-01"
SERIES_WORKFLOW = ROOT / ".github/workflows/lordchrist-quiz-series-poster.yml"
EXPECTED_SERIES_ANSWERS = {
    "lordchrist-quiz-s01-esther": "Есфирь",
    "lordchrist-quiz-s01-belshazzar": "Валтасар",
    "lordchrist-quiz-s01-jael": "Иаиль",
    "lordchrist-quiz-s01-moriah": "Мориа",
    "lordchrist-quiz-s01-uzzah": "Оза",
    "lordchrist-quiz-s01-stephen": "Стефан",
    "lordchrist-quiz-s01-hezekiah": "Езекия",
    "lordchrist-quiz-s01-elisha-bones": "Елисей",
    "lordchrist-quiz-s01-cain-city": "Каин",
    "lordchrist-quiz-s01-eutychus": "Евтих",
}


def test_quiz_series_spec_is_ten_clean_teaching_quizzes() -> None:
    from datetime import timedelta

    from video_channel_manager.lordchrist_quiz import build_poll_description, load_quiz_series, series_spec_path

    series = load_quiz_series(series_spec_path(SERIES_ID))
    assert len(series.items) == 10
    assert {item.publication_id: item.options[item.correct_option_index] for item in series.items} == (
        EXPECTED_SERIES_ANSWERS
    )
    first = series.items[0].scheduled_at
    assert (first.hour, first.minute) == (13, 0)  # daytime publication, Moscow
    for previous, current in zip(series.items, series.items[1:], strict=False):
        assert current.scheduled_at - previous.scheduled_at == timedelta(days=2)
    for item in series.items:
        assert item.layout == "v2"
        assert item.hashtags == ""
        assert build_poll_description(item) is None  # nothing shown before voting
        assert len(item.explanation) <= 200
        assert any(reference in item.explanation for reference in item.scripture_references)


def test_quiz_series_runtime_is_the_authorized_build() -> None:
    from video_channel_manager.lordchrist_quiz import (
        build_series_candidate,
        load_quiz_series,
        series_runtime_path,
        series_spec_path,
    )
    from video_channel_manager.telegram_channel_profile import load_channel_profile
    from video_channel_manager.telegram_multichannel_release import GenericReleaseQueue
    from video_channel_manager.telegram_target_binding import load_target_binding

    profile = load_channel_profile(ROOT / "content/telegram/channels/lordchrist-rich.json")
    binding = load_target_binding(ROOT / "content/telegram/channels/lordchrist-target-binding.json", profile)
    series = load_quiz_series(series_spec_path(SERIES_ID))
    release = GenericReleaseQueue.model_validate_json(series_runtime_path(SERIES_ID).read_text(encoding="utf-8"))

    candidate = build_series_candidate(profile, series, binding)
    assert release.release_authorized is True
    assert release.reviewed_candidate_sha256 == candidate.candidate_digest()
    assert [item.publication_id for item in release.items] == [item.publication_id for item in series.items]
    assert all(item.payload.description is None for item in release.items)
    assert all(item.payload.poll_type == "quiz" for item in release.items)


def test_quiz_series_workflow_publishes_the_due_quiz_every_two_days() -> None:
    workflow = SERIES_WORKFLOW.read_text(encoding="utf-8")
    assert 'cron: "0 10 * * *"' in workflow  # 13:00 Moscow, daily tick
    assert workflow.count("queue: max") == 1
    assert workflow.count("group: lordchrist-telegram-publisher") == 1
    assert "INITIALIZE:@lordchrist:$SERIES_ID" in workflow
    assert "PUBLISH:@lordchrist:$SERIES_ID" in workflow
    assert "validate-series" in workflow
    assert "telegram_multichannel_cli skip-expired" in workflow
    assert "telegram_publication_freshness next" in workflow
    assert "secrets.LORDCHRIST_TELEGRAM_BOT_TOKEN" in workflow


def test_quiz_workflow_is_main_only_exact_and_schedule_free() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "schedule:" not in workflow
    # GitHub rejects duplicate YAML keys at startup even though permissive
    # parsers accept them; the concurrency block must define each key once.
    assert workflow.count("queue: max") == 1
    assert workflow.count("group: lordchrist-telegram-publisher") == 1
    assert workflow.count("cancel-in-progress: false") == 1
    assert "if: github.ref == 'refs/heads/main'" in workflow
    assert "INITIALIZE:@lordchrist:$PUBLICATION_ID" in workflow
    assert "PUBLISH:@lordchrist:$PUBLICATION_ID" in workflow
    assert "video_channel_manager.lordchrist_quiz validate" in workflow
    assert "video_channel_manager.telegram_multichannel_cli send-once" in workflow
    assert "secrets.LORDCHRIST_TELEGRAM_BOT_TOKEN" in workflow
    assert (
        json.loads((QUIZ_DIR / f"{PUBLICATION_ID}-runtime.json").read_text(encoding="utf-8"))["release_authorized"]
        is True
    )
