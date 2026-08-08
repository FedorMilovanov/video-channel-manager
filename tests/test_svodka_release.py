from __future__ import annotations

from pathlib import Path

from video_channel_manager.svodka_queue import load_svodka_draft
from video_channel_manager.svodka_release import build_svodka_release_candidate
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_transport import GenericMessagePayload, GenericPollPayload

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka.json"
QUEUE_PATH = REPOSITORY_ROOT / "content/telegram/svodka/draft-14-posts-2026-08.json"


def test_build_svodka_release_candidate_freezes_exact_provider_payloads() -> None:
    profile = load_channel_profile(PROFILE_PATH)
    draft = load_svodka_draft(QUEUE_PATH, profile)
    release = build_svodka_release_candidate(profile, draft, release_id="svodka-pilot-2026-08-candidate")

    assert release.release_authorized is False
    assert release.reviewed_by is None
    assert release.reviewed_at is None
    assert release.profile_sha256 == profile.digest
    assert len(release.items) == 14
    assert release.digest.startswith("sha256:")

    first = release.items[0]
    assert first.publication_id == "svodka-venus-day-longer-than-year"
    assert isinstance(first.payload, GenericMessagePayload)
    assert first.payload.provider_payload_sha256.startswith("sha256:")

    quiz = release.items[6]
    assert quiz.publication_id == "svodka-quiz-lightning-vs-sun"
    assert isinstance(quiz.payload, GenericPollPayload)
    assert quiz.payload.schema_version == 4
    assert quiz.payload.correct_option_ids == (0,)
    assert quiz.payload.description is not None
    assert "NOAA" in quiz.payload.description


def test_release_candidate_is_deterministic_for_same_profile_and_draft() -> None:
    profile = load_channel_profile(PROFILE_PATH)
    draft = load_svodka_draft(QUEUE_PATH, profile)
    left = build_svodka_release_candidate(profile, draft, release_id="svodka-pilot-2026-08-candidate")
    right = build_svodka_release_candidate(profile, draft, release_id="svodka-pilot-2026-08-candidate")
    assert left == right
    assert left.digest == right.digest
