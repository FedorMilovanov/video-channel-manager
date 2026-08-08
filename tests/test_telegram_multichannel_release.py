from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from video_channel_manager.svodka_queue import load_svodka_draft
from video_channel_manager.svodka_release import build_svodka_release_candidate
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_release import GenericReleaseQueue
from video_channel_manager.telegram_target_binding import load_target_binding

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka.json"
BINDING_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka-target-binding.json"
QUEUE_PATH = REPOSITORY_ROOT / "content/telegram/svodka/draft-14-posts-2026-08.json"


def _inputs():
    profile = load_channel_profile(PROFILE_PATH)
    draft = load_svodka_draft(QUEUE_PATH, profile)
    binding = load_target_binding(BINDING_PATH, profile)
    return profile, draft, binding


def test_release_candidate_is_exactly_bound_but_not_authorized() -> None:
    profile, draft, binding = _inputs()
    release = build_svodka_release_candidate(
        profile,
        draft,
        release_id="svodka-pilot-2026-08-release-test",
        binding=binding,
    )

    assert release.release_authorized is False
    assert release.target_binding_sha256 == binding.digest
    assert release.chat_id == binding.chat_id
    assert release.bot_id == binding.bot_id
    assert release.bot_username == binding.bot_username
    assert release.profile_sha256 == profile.digest
    assert len(release.items) == len(draft.posts)


def test_authorized_release_requires_complete_exact_target_identity() -> None:
    profile, draft, _ = _inputs()
    candidate = build_svodka_release_candidate(
        profile,
        draft,
        release_id="svodka-pilot-2026-08-unbound-test",
    )
    payload = candidate.model_dump(mode="json")
    payload["release_authorized"] = True
    payload["reviewed_candidate_sha256"] = candidate.digest
    payload["reviewed_by"] = "release-test"
    payload["reviewed_at"] = datetime(2026, 8, 8, 0, 0, tzinfo=UTC).isoformat()

    with pytest.raises(ValueError, match="authorized release requires exact target binding"):
        GenericReleaseQueue.model_validate(payload)


def test_release_rejects_partial_target_binding() -> None:
    profile, draft, _ = _inputs()
    candidate = build_svodka_release_candidate(
        profile,
        draft,
        release_id="svodka-pilot-2026-08-partial-target-test",
    )
    payload = candidate.model_dump(mode="json")
    payload["chat_id"] = -1003527567039

    with pytest.raises(ValueError, match="target binding must be either complete or entirely unset"):
        GenericReleaseQueue.model_validate(payload)


def test_release_rejects_equal_scheduled_timestamps() -> None:
    profile, draft, binding = _inputs()
    candidate = build_svodka_release_candidate(
        profile,
        draft,
        release_id="svodka-pilot-2026-08-duplicate-time-test",
        binding=binding,
    )
    payload = candidate.model_dump(mode="json")
    payload["items"][1]["scheduled_at"] = payload["items"][0]["scheduled_at"]

    with pytest.raises(ValueError, match="strictly ordered by scheduled_at"):
        GenericReleaseQueue.model_validate(payload)
