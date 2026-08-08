from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from video_channel_manager.svodka_queue import load_svodka_draft
from video_channel_manager.svodka_release import authorize_svodka_release, build_svodka_release_candidate
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_release import GenericReleaseQueue
from video_channel_manager.telegram_target_binding import load_target_binding

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "content/telegram/channels/svodka.json"
BINDING_PATH = ROOT / "content/telegram/channels/svodka-target-binding.json"
QUEUE_PATH = ROOT / "content/telegram/svodka/draft-14-posts-2026-08.json"


def _candidate() -> GenericReleaseQueue:
    profile = load_channel_profile(PROFILE_PATH)
    binding = load_target_binding(BINDING_PATH, profile)
    draft = load_svodka_draft(QUEUE_PATH, profile)
    return build_svodka_release_candidate(
        profile,
        draft,
        release_id="svodka-pilot-2026-08-provenance-test",
        binding=binding,
    )


def test_authorized_release_self_verifies_exact_candidate_digest() -> None:
    candidate = _candidate()
    release = authorize_svodka_release(
        candidate,
        reviewed_by="reviewer",
        reviewed_at=datetime(2026, 8, 8, 3, 0, tzinfo=UTC),
    )

    assert release.reviewed_candidate_sha256 == candidate.digest
    assert release.reviewed_candidate_sha256 == release.candidate_digest()


def test_authorized_release_rejects_forged_reviewed_candidate_digest() -> None:
    candidate = _candidate()
    payload = candidate.model_dump(mode="json")
    payload["release_authorized"] = True
    payload["reviewed_candidate_sha256"] = "sha256:" + "0" * 64
    payload["reviewed_by"] = "reviewer"
    payload["reviewed_at"] = "2026-08-08T03:00:00+00:00"

    with pytest.raises(ValueError, match="does not match its immutable candidate"):
        GenericReleaseQueue.model_validate(payload)
