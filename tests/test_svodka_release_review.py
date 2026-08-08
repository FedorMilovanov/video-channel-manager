from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from video_channel_manager.svodka_queue import load_svodka_draft
from video_channel_manager.svodka_release import authorize_svodka_release, build_svodka_release_candidate
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_release import GenericReleaseQueue
from video_channel_manager.telegram_release_review import authorize_release_candidate
from video_channel_manager.telegram_target_binding import load_target_binding

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "content/telegram/channels/svodka.json"
BINDING_PATH = ROOT / "content/telegram/channels/svodka-target-binding.json"
QUEUE_PATH = ROOT / "content/telegram/svodka/draft-14-posts-2026-08.json"


def _candidate(*, with_binding: bool) -> GenericReleaseQueue:
    profile = load_channel_profile(PROFILE_PATH)
    draft = load_svodka_draft(QUEUE_PATH, profile)
    binding = load_target_binding(BINDING_PATH, profile) if with_binding else None
    return build_svodka_release_candidate(
        profile,
        draft,
        release_id="svodka-pilot-2026-08-release",
        binding=binding,
    )


def test_target_bound_candidate_freezes_exact_chat_bot_and_binding_digest() -> None:
    profile = load_channel_profile(PROFILE_PATH)
    binding = load_target_binding(BINDING_PATH, profile)
    candidate = _candidate(with_binding=True)

    assert candidate.release_authorized is False
    assert candidate.target_binding_sha256 == binding.digest
    assert candidate.chat_id == -1003527567039
    assert candidate.bot_id == 8716602202
    assert candidate.bot_username == "preaching_mp3_bot"
    assert candidate.reviewed_candidate_sha256 is None
    assert candidate.reviewed_by is None
    assert candidate.reviewed_at is None


def test_authorization_requires_exact_target_binding() -> None:
    candidate = _candidate(with_binding=False)

    with pytest.raises(ValueError, match="exact-target-bound"):
        authorize_svodka_release(
            candidate,
            reviewed_by="operator",
            reviewed_at=datetime(2026, 8, 8, tzinfo=UTC),
        )


def test_reviewed_release_preserves_payloads_and_records_exact_candidate_digest() -> None:
    candidate = _candidate(with_binding=True)
    candidate_digest = candidate.digest
    reviewed_at = datetime(2026, 8, 8, 1, 30, tzinfo=UTC)
    release = authorize_svodka_release(
        candidate,
        reviewed_by="operator",
        reviewed_at=reviewed_at,
    )

    assert release.release_authorized is True
    assert release.reviewed_candidate_sha256 == candidate_digest
    assert release.reviewed_by == "operator"
    assert release.reviewed_at == reviewed_at
    assert release.target_binding_sha256 == candidate.target_binding_sha256
    assert release.chat_id == candidate.chat_id
    assert release.bot_id == candidate.bot_id
    assert release.bot_username == candidate.bot_username
    assert [item.source_sha256 for item in release.items] == [item.source_sha256 for item in candidate.items]
    assert [item.payload.provider_payload_sha256 for item in release.items] == [
        item.payload.provider_payload_sha256 for item in candidate.items
    ]


def test_generic_review_accepts_exact_svodka_profile_binding_and_digest() -> None:
    profile = load_channel_profile(PROFILE_PATH)
    binding = load_target_binding(BINDING_PATH, profile)
    candidate = _candidate(with_binding=True)
    reviewed_at = datetime(2026, 8, 8, 10, 0, tzinfo=UTC)

    release = authorize_release_candidate(
        candidate,
        profile=profile,
        binding=binding,
        expected_candidate_sha256=candidate.candidate_digest(),
        reviewed_by="operator",
        reviewed_at=reviewed_at,
    )

    assert release.release_authorized is True
    assert release.reviewed_candidate_sha256 == candidate.candidate_digest()
    assert release.reviewed_by == "operator"
    assert release.reviewed_at == reviewed_at
    assert release.profile_sha256 == profile.digest
    assert release.target_binding_sha256 == binding.digest


def test_generic_review_rejects_current_svodka_profile_drift() -> None:
    profile = load_channel_profile(PROFILE_PATH)
    binding = load_target_binding(BINDING_PATH, profile)
    candidate = _candidate(with_binding=True)
    changed_profile = profile.model_copy(update={"channel_title": profile.channel_title + " changed"})
    assert changed_profile.digest != profile.digest

    with pytest.raises(ValueError, match="differs from selected Telegram channel profile"):
        authorize_release_candidate(
            candidate,
            profile=changed_profile,
            binding=binding,
            expected_candidate_sha256=candidate.candidate_digest(),
            reviewed_by="operator",
            reviewed_at=datetime(2026, 8, 8, 10, 0, tzinfo=UTC),
        )


def test_generic_review_rejects_current_svodka_binding_drift() -> None:
    profile = load_channel_profile(PROFILE_PATH)
    binding = load_target_binding(BINDING_PATH, profile)
    candidate = _candidate(with_binding=True)
    changed_binding = binding.model_copy(update={"chat_id": binding.chat_id - 1})
    assert changed_binding.digest != binding.digest

    with pytest.raises(ValueError, match="differs from exact reviewed Telegram target binding"):
        authorize_release_candidate(
            candidate,
            profile=profile,
            binding=changed_binding,
            expected_candidate_sha256=candidate.candidate_digest(),
            reviewed_by="operator",
            reviewed_at=datetime(2026, 8, 8, 10, 0, tzinfo=UTC),
        )


def test_generic_review_rejects_unbound_svodka_candidate() -> None:
    profile = load_channel_profile(PROFILE_PATH)
    binding = load_target_binding(BINDING_PATH, profile)
    candidate = _candidate(with_binding=False)

    with pytest.raises(ValueError, match="differs from exact reviewed Telegram target binding"):
        authorize_release_candidate(
            candidate,
            profile=profile,
            binding=binding,
            expected_candidate_sha256=candidate.candidate_digest(),
            reviewed_by="operator",
            reviewed_at=datetime(2026, 8, 8, 10, 0, tzinfo=UTC),
        )


def test_generic_review_rejects_double_svodka_authorization() -> None:
    profile = load_channel_profile(PROFILE_PATH)
    binding = load_target_binding(BINDING_PATH, profile)
    candidate = _candidate(with_binding=True)
    release = authorize_release_candidate(
        candidate,
        profile=profile,
        binding=binding,
        expected_candidate_sha256=candidate.candidate_digest(),
        reviewed_by="operator",
        reviewed_at=datetime(2026, 8, 8, 10, 0, tzinfo=UTC),
    )

    with pytest.raises(ValueError, match="already authorized"):
        authorize_release_candidate(
            release,
            profile=profile,
            binding=binding,
            expected_candidate_sha256=candidate.candidate_digest(),
            reviewed_by="operator",
            reviewed_at=datetime(2026, 8, 8, 10, 1, tzinfo=UTC),
        )


def test_unauthorized_release_cannot_claim_reviewed_candidate_digest() -> None:
    candidate = _candidate(with_binding=True)
    payload = candidate.model_dump(mode="json")
    payload["reviewed_candidate_sha256"] = "sha256:" + "0" * 64

    with pytest.raises(ValueError, match="completed review metadata"):
        GenericReleaseQueue.model_validate(payload)


def test_authorized_generic_release_requires_reviewed_candidate_provenance() -> None:
    candidate = _candidate(with_binding=True)
    payload = candidate.model_dump(mode="json")
    payload["release_authorized"] = True
    payload["reviewed_by"] = "operator"
    payload["reviewed_at"] = "2026-08-08T01:30:00+00:00"

    with pytest.raises(ValueError, match="reviewed candidate provenance"):
        GenericReleaseQueue.model_validate(payload)


def test_authorized_release_rejects_tampered_reviewed_candidate_digest() -> None:
    candidate = _candidate(with_binding=True)
    release = authorize_svodka_release(
        candidate,
        reviewed_by="operator",
        reviewed_at=datetime(2026, 8, 8, 1, 30, tzinfo=UTC),
    )
    payload = release.model_dump(mode="json")
    payload["reviewed_candidate_sha256"] = "sha256:" + "0" * 64

    with pytest.raises(ValueError, match="does not match its immutable candidate"):
        GenericReleaseQueue.model_validate(payload)


def test_authorized_release_rejects_schedule_change_after_review() -> None:
    candidate = _candidate(with_binding=True)
    release = authorize_svodka_release(
        candidate,
        reviewed_by="operator",
        reviewed_at=datetime(2026, 8, 8, 1, 30, tzinfo=UTC),
    )
    payload = release.model_dump(mode="json")
    original = release.items[0].scheduled_at
    payload["items"][0]["scheduled_at"] = (original + timedelta(minutes=1)).isoformat()

    with pytest.raises(ValueError, match="does not match its immutable candidate"):
        GenericReleaseQueue.model_validate(payload)


def test_authorized_generic_release_cannot_omit_exact_target_identity() -> None:
    candidate = _candidate(with_binding=False)
    payload = candidate.model_dump(mode="json")
    payload["release_authorized"] = True
    payload["reviewed_candidate_sha256"] = candidate.digest
    payload["reviewed_by"] = "operator"
    payload["reviewed_at"] = "2026-08-08T01:30:00+00:00"

    with pytest.raises(ValueError, match="exact target binding"):
        GenericReleaseQueue.model_validate(payload)
