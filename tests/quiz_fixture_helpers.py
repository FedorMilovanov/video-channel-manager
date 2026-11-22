"""Synthetic QUIZ releases for state-machine tests; never target a real channel.

The source questions are historical fixtures only. All identities, receipts and
review labels below are fabricated and grant no editorial or provider authority.
"""

from __future__ import annotations

from datetime import UTC, datetime

from video_channel_manager import lordchrist_quiz as quiz
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_release_review import authorize_release_candidate
from video_channel_manager.telegram_target_binding import load_target_binding

FIXTURE_ONE = "lordchrist-quiz-fixture-city-of-palms"


def fake_profile_binding():
    original = load_channel_profile(quiz.PROFILE_PATH)
    original_binding = load_target_binding(quiz.BINDING_PATH, original)
    profile = original.model_copy(
        update={
            "project_key": "quiz-test-fixture",
            "channel_username": "@quizfixture",
            "channel_title": "QUIZ fixture, never a provider target",
            "state_branch": "state/quiz-fixture",
            "concurrency_group": "quiz-fixture-publisher",
        }
    )
    binding = original_binding.model_copy(
        update={
            "project_key": profile.project_key,
            "channel_username": profile.channel_username,
            "profile_sha256": profile.digest,
            "chat_id": -1001234567890,
            "chat_username": "quizfixture",
            "bot_id": 42,
            "bot_username": "quiz_fixture_bot",
        }
    )
    return profile, binding


def _authorize(candidate, profile, binding):
    return authorize_release_candidate(
        candidate,
        profile=profile,
        binding=binding,
        expected_candidate_sha256=candidate.candidate_digest(),
        reviewed_by="synthetic test fixture; not a real approval",
        reviewed_at=datetime(2026, 11, 14, tzinfo=UTC),
    )


def fake_one(profile, binding):
    source = quiz.load_quiz_spec(quiz.spec_path("lordchrist-quiz-city-of-palms"))
    spec = source.model_copy(update={"publication_id": FIXTURE_ONE})
    return spec, _authorize(quiz.build_quiz_candidate(profile, spec, binding), profile, binding)


def fake_series(profile, binding, *, source_id="lordchrist-quiz-series-02"):
    source = quiz.load_quiz_series(quiz.series_spec_path(source_id))
    number = source_id[-2:]
    series = source.model_copy(
        update={
            "series_id": "lordchrist-quiz-series-99",
            "items": tuple(
                item.model_copy(update={"publication_id": item.publication_id.replace(f"-s{number}-", "-fixture-")})
                for item in source.items
            ),
        }
    )
    candidate = quiz.build_series_candidate(profile, series, binding).model_copy(
        update={"release_id": "fixture-quiz-series-release"}
    )
    return series, _authorize(candidate, profile, binding)
