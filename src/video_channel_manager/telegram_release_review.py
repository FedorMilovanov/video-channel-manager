from __future__ import annotations

import re
from datetime import datetime

from video_channel_manager.telegram_multichannel_release import GenericReleaseQueue

SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def authorize_release_candidate(
    candidate: GenericReleaseQueue,
    *,
    expected_candidate_sha256: str,
    reviewed_by: str,
    reviewed_at: datetime,
) -> GenericReleaseQueue:
    """Authorize exactly one immutable generic Telegram release candidate.

    This function has no provider or state side effects. It only binds human review
    metadata to the exact candidate digest already represented by ``candidate``.
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
    if any(
        value is None
        for value in (
            candidate.target_binding_sha256,
            candidate.chat_id,
            candidate.bot_id,
            candidate.bot_username,
        )
    ):
        raise ValueError("release candidate must have complete exact target binding before authorization")

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
