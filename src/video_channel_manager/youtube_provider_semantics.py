from __future__ import annotations

import hashlib
import json
import re
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


def exact_caption_inventory(payload: Mapping[str, Any], video_id: str) -> dict[str, Any]:
    """Accept only a complete inventory bound to one exact video, never a partial list."""
    rows = payload.get("items")
    if (
        payload.get("nextPageToken")
        or not isinstance(rows, list)
        or not all(
            isinstance(row, dict)
            and isinstance(row.get("id"), str)
            and bool(row["id"])
            and isinstance(row.get("snippet"), dict)
            and row["snippet"].get("videoId") == video_id
            for row in rows
        )
        or len({row["id"] for row in rows}) != len(rows)
    ):
        raise ValueError("Incomplete exact caption inventory; stop without replay.")
    return {row["id"]: row["snippet"] for row in rows}


_SRT_TIME = r"(\d{2,}):([0-5]\d):([0-5]\d),(\d{3})"
_SRT_RANGE = re.compile(rf"{_SRT_TIME}[ \t]+-->[ \t]+{_SRT_TIME}")


def canonical_srt_sha256(data: bytes, *, duration_seconds: int | None = None) -> str:
    """Validate timed UTF-8 cues; ignore BOM, line endings and trailing whitespace only."""
    try:
        text = data.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    except UnicodeDecodeError as exc:
        raise ValueError("SRT must be UTF-8.") from exc
    cues = []
    previous_start = -1
    for index, block in enumerate(re.split(r"\n[ \t]*\n", text), 1):
        lines = block.splitlines()
        if len(lines) < 3 or lines[0].strip() != str(index):
            raise ValueError(f"Invalid SRT cue number or missing text at cue {index}.")
        match = _SRT_RANGE.fullmatch(lines[1].strip())
        if match is None:
            raise ValueError(f"Invalid SRT time range at cue {index}.")
        times = tuple(int(value) for value in match.groups())
        start = ((times[0] * 60 + times[1]) * 60 + times[2]) * 1000 + times[3]
        end = ((times[4] * 60 + times[5]) * 60 + times[6]) * 1000 + times[7]
        if start < previous_start or end <= start or (duration_seconds is not None and end > duration_seconds * 1000):
            raise ValueError(f"SRT cue {index} is out of order or outside the video duration.")
        body = "\n".join(line.rstrip() for line in lines[2:])
        if not body.strip():
            raise ValueError(f"Empty SRT text at cue {index}.")
        cues.append((start, end, body))
        previous_start = start
    return hashlib.sha256(json.dumps(cues, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def validate_caption_identity(language: str, name: str) -> None:
    if not re.fullmatch(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*", language) or len(name) > 150:
        raise ValueError("Invalid caption language or name.")


def manual_caption_ids(tracks: Mapping[str, Any], language: str, name: str) -> list[str]:
    """Find the exact manual language/name identity; ASR is not a manual track."""
    ids = []
    for track_id, snippet in tracks.items():
        lang = snippet.get("language")
        track_name = snippet.get("name", "")
        kind = snippet.get("trackKind")
        if not isinstance(lang, str) or not lang or not isinstance(track_name, str) or not isinstance(kind, str):
            raise ValueError("Incomplete caption language/name/kind inventory.")
        if kind != "ASR" and lang.casefold() == language.casefold() and track_name == name:
            ids.append(track_id)
    return ids
