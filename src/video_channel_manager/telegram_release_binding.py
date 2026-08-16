from __future__ import annotations

import re

from video_channel_manager.telegram_channel_profile import TelegramChannelProfile
from video_channel_manager.telegram_multichannel_release import GenericReleaseQueue
from video_channel_manager.telegram_target_binding import TelegramTargetBinding

SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _require_profile_contract(candidate: GenericReleaseQueue, profile: TelegramChannelProfile) -> None:
    if (
        candidate.project_key != profile.project_key
        or candidate.channel_username.casefold() != profile.channel_username.casefold()
        or candidate.profile_sha256 != profile.digest
        or candidate.timezone != profile.timezone
        or candidate.daily_verified_limit != profile.daily_verified_limit
    ):
        raise ValueError("release candidate differs from selected Telegram channel profile")


def _require_binding_contract(binding: TelegramTargetBinding, profile: TelegramChannelProfile) -> None:
    if (
        binding.project_key != profile.project_key
        or binding.channel_username.casefold() != profile.channel_username.casefold()
        or binding.profile_sha256 != profile.digest
        or binding.chat_username.casefold() != profile.bare_username.casefold()
    ):
        raise ValueError("target binding differs from selected Telegram channel profile")
    if binding.provider_write_performed:
        raise ValueError("target binding must come from provider-read-only discovery")


def bind_release_candidate(
    candidate: GenericReleaseQueue,
    *,
    profile: TelegramChannelProfile,
    binding: TelegramTargetBinding,
    expected_unbound_candidate_sha256: str,
) -> GenericReleaseQueue:
    """Bind an unauthorized release candidate to one immutable Telegram target.

    This transform is provider-free and state-free. It cannot authorize a release:
    human review remains a separate step after the exact target-bound candidate
    digest is known.
    """

    if candidate.release_authorized:
        raise ValueError("release candidate is already authorized")
    if not SHA256_RE.fullmatch(expected_unbound_candidate_sha256):
        raise ValueError("expected unbound candidate digest must be an exact sha256 value")

    candidate_sha256 = candidate.candidate_digest()
    if candidate_sha256 != expected_unbound_candidate_sha256:
        raise ValueError("release candidate digest differs from the expected unbound digest")

    target_values = (
        candidate.target_binding_sha256,
        candidate.chat_id,
        candidate.bot_id,
        candidate.bot_username,
    )
    if any(value is not None for value in target_values):
        raise ValueError("release candidate is already target-bound")

    _require_profile_contract(candidate, profile)
    _require_binding_contract(binding, profile)

    bound = GenericReleaseQueue.model_validate(
        candidate.model_copy(
            update={
                "target_binding_sha256": binding.digest,
                "chat_id": binding.chat_id,
                "bot_id": binding.bot_id,
                "bot_username": binding.bot_username,
            }
        ).model_dump(mode="json")
    )
    if bound.release_authorized:
        raise AssertionError("target binding unexpectedly authorized the release")
    if bound.reviewed_candidate_sha256 is not None or bound.reviewed_by is not None or bound.reviewed_at is not None:
        raise AssertionError("target binding unexpectedly added review metadata")
    if bound.items != candidate.items:
        raise AssertionError("target binding unexpectedly changed release items")
    return bound
