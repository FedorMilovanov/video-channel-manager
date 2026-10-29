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


def test_quiz_workflow_is_main_only_exact_and_schedule_free() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "schedule:" not in workflow
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
