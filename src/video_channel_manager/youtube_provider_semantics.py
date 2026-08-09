from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence

ProviderEffect = Literal["not_dispatched", "confirmed_absent", "may_exist", "verified"]
ReadbackVerdict = Literal["verified", "mismatch", "unobserved"]


@dataclass(frozen=True)
class BooleanReadback:
    verdict: ReadbackVerdict
    expected: bool
    actual: bool | None


def tags_equivalent(expected: Sequence[str], actual: Sequence[str]) -> bool:
    """Compare YouTube tags by value and multiplicity, never provider return order."""

    return Counter(expected) == Counter(actual)


def classify_boolean_readback(
    *,
    payload: Mapping[str, Any],
    key: str,
    expected: bool,
) -> BooleanReadback:
    """Distinguish an omitted provider field from an explicit false/mismatch value."""

    if key not in payload or payload[key] is None:
        return BooleanReadback(verdict="unobserved", expected=expected, actual=None)
    actual = payload[key]
    if not isinstance(actual, bool):
        return BooleanReadback(verdict="mismatch", expected=expected, actual=None)
    return BooleanReadback(
        verdict="verified" if actual is expected else "mismatch",
        expected=expected,
        actual=actual,
    )


def effect_after_accepted_mutation(*, provider_accepted: bool, readback_verified: bool) -> ProviderEffect:
    """An accepted write is never converted to confirmed absence by one empty readback."""

    if readback_verified:
        if not provider_accepted:
            raise ValueError("A write cannot be verified when it was never accepted/dispatched.")
        return "verified"
    if provider_accepted:
        return "may_exist"
    return "not_dispatched"


def playlist_item_video_id(item: Mapping[str, Any]) -> str | None:
    """Extract the video ID from either documented playlistItem location."""

    content_details = item.get("contentDetails")
    if isinstance(content_details, Mapping):
        value = content_details.get("videoId")
        if isinstance(value, str) and value:
            return value

    snippet = item.get("snippet")
    if not isinstance(snippet, Mapping):
        return None
    resource_id = snippet.get("resourceId")
    if not isinstance(resource_id, Mapping):
        return None
    value = resource_id.get("videoId")
    return value if isinstance(value, str) and value else None


def playlist_contains_video(items: Sequence[Mapping[str, Any]], *, video_id: str) -> bool:
    """Check an already fully enumerated playlist page-set for one exact video ID."""

    return any(playlist_item_video_id(item) == video_id for item in items)
