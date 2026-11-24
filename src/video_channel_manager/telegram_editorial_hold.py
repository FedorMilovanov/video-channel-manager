"""Provider and state quarantine for rejected/retired LordChrist QUIZ releases.

Historical signatures and receipts remain readable; none permits replay. A
future content review is not execution authority. The channel-level native
quiz stop also covers copied content under new IDs; it does not detect text
repurposed as a regular poll or message.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from video_channel_manager.telegram_multichannel_release import GenericReleaseQueue

RETIRED_SERIES_IDS = frozenset({"lordchrist-quiz-series-01", "lordchrist-quiz-series-02"})
RETIRED_ONE_OFF_IDS = frozenset({"lordchrist-quiz-city-of-palms", "lordchrist-quiz-book-without-gods-name"})
EDITORIAL_HOLD_SERIES_IDS = frozenset({"lordchrist-quiz-series-03"})
_ALL_SERIES = RETIRED_SERIES_IDS | EDITORIAL_HOLD_SERIES_IDS
_HISTORICAL_ITEM_PREFIXES = ("lordchrist-quiz-s01-", "lordchrist-quiz-s02-", "lordchrist-quiz-s03-")


class EditorialExecutionHold(ValueError):
    """Execution is prohibited, independent of a historical release signature."""


def require_not_historical_quiz(release: GenericReleaseQueue) -> None:
    """Block historical identities even if repackaged in a renamed release."""
    old_release = any(release.release_id == old or release.release_id.startswith(old + "-") for old in _ALL_SERIES)
    old_release |= any(
        release.release_id == old or release.release_id.startswith(old + "-") for old in RETIRED_ONE_OFF_IDS
    )
    old_item = any(
        item.publication_id in RETIRED_ONE_OFF_IDS or item.publication_id.startswith(_HISTORICAL_ITEM_PREFIXES)
        for item in release.items
    )
    if old_release or old_item:
        raise EditorialExecutionHold("Historical QUIZ identity is retired or on editorial HOLD; execution forbidden")


def require_quiz_target_not_held(*, channel_username: str, chat_id: int | None, poll_type: str) -> None:
    """Quarantine native quizzes for the exact channel without stopping other formats."""
    if poll_type == "quiz" and (channel_username.casefold() == "@lordchrist" or chat_id == -1001295216957):
        raise EditorialExecutionHold("@lordchrist QUIZ requires a separately reviewed, owner-authorized rollout")


def require_execution_not_held(release: GenericReleaseQueue) -> None:
    """Keep state initialization, advancement and send closed during the HOLD."""
    require_not_historical_quiz(release)
    for item in release.items:
        require_quiz_target_not_held(
            channel_username=release.channel_username,
            chat_id=release.chat_id,
            poll_type=getattr(item.payload, "poll_type", ""),
        )
