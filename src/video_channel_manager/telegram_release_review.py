from __future__ import annotations

import re
from datetime import datetime

from video_channel_manager.telegram_channel_profile import TelegramChannelProfile
from video_channel_manager.telegram_multichannel_release import GenericReleaseQueue
from video_channel_manager.telegram_target_binding import TelegramTargetBinding

SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _require_exact_review_contract(
    candidate: GenericReleaseQueue,
    profile: TelegramChannelProfile,
    binding: TelegramTargetBinding,
) -> None:
    if (
        candidate.project_key != profile.project_key
        or candidate.channel_username.casefold() != profile.channel_username.casefold()
        or candidate.profile_sha256 != profile.digest
        or candidate.timezone != profile.timezone
        or candidate.daily_verified_limit != profile.daily_verified_limit
    ):
        raise ValueError("release candidate differs from selected Telegram channel profile")
    if (
        binding.project_key != profile.project_key
        or binding.channel_username.casefold() != profile.channel_username.casefold()
        or binding.profile_sha256 != profile.digest
        or binding.chat_username.casefold() != profile.bare_username.casefold()
    ):
        raise ValueError("target binding differs from selected Telegram channel profile")
    if (
        candidate.target_binding_sha256 != binding.digest
        or candidate.chat_id != binding.chat_id
        or candidate.bot_id != binding.bot_id
        or (candidate.bot_username or "").casefold() != binding.bot_username.casefold()
    ):
        raise ValueError("release candidate differs from exact reviewed Telegram target binding")


def authorize_release_candidate(
    candidate: GenericReleaseQueue,
    *,
    profile: TelegramChannelProfile,
    binding: TelegramTargetBinding,
    expected_candidate_sha256: str,
    reviewed_by: str,
    reviewed_at: datetime,
) -> GenericReleaseQueue:
    """Authorize exactly one immutable generic Telegram release candidate.

    This function has no provider or state side effects. It binds human review
    metadata only after the candidate is proven against the exact current channel
    profile and immutable target binding selected for that review.
    """

    if candidate.release_authorized:
        raise ValueError("release candidate is already authorized")
    if not SHA256_RE.fullmatch(expected_candidate_sha256):
        raise ValueError("expected candidate digest must be an exact sha256 value")
    candidate_sha256 = candidate.candidate_digest()
    if candidate_sha256 != expected_candidate_sha256:
        raise ValueError("release candidate digest differs from the reviewed digest")
    reviewer = reviewed_by.strip()
    if not reviewer:
        raise ValueError("release review requires a non-empty reviewer identity")
    if reviewed_at.tzinfo is None:
        raise ValueError("release review timestamp must be timezone-aware")

    _require_exact_review_contract(candidate, profile, binding)

    return GenericReleaseQueue.model_validate(
        candidate.model_copy(
            update={
                "release_authorized": True,
                "reviewed_candidate_sha256": candidate_sha256,
                "reviewed_by": reviewer,
                "reviewed_at": reviewed_at,
            }
        ).model_dump(mode="json")
    )
