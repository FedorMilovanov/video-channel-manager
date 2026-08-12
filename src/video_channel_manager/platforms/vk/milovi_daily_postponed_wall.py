from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from video_channel_manager.platforms.vk.milovi_immediate_wall import (
    MILOVI_COMMUNITY_ID,
    MILOVI_OWNER_ID,
    MILOVI_SOURCE_ALLOWLIST,
)
from video_channel_manager.platforms.vk.milovi_rollout_sources import (
    ROLL_OUT_IDS,
    SourceAsset,
    write_json_atomic,
)
from video_channel_manager.platforms.vk.wall import VkWallWriter
from video_channel_manager.platforms.vk.wall_safety import VkWallSurface

DAILY_SCHEDULE_SCHEMA = "video-manager.milovi-issue-323-daily-wall-schedule"
DAILY_SCHEDULE_VERSION = 1
DEFAULT_TIMEZONE = "Europe/Moscow"
DEFAULT_WALL_HOUR = 19
DEFAULT_WALL_MINUTE = 0

if frozenset(ROLL_OUT_IDS) != MILOVI_SOURCE_ALLOWLIST:
    raise RuntimeError("Issue #323 daily-wall allowlist differs from the reviewed Milovi allowlist")


class MiloviDailyWallBlocked(RuntimeError):
    pass


def _aware(value: datetime, *, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value


def _parse_clip_remote_id(remote_id: str) -> int:
    owner_text, separator, video_text = remote_id.partition("_")
    if not separator:
        raise MiloviDailyWallBlocked(f"Invalid VK Clip remote ID: {remote_id}")
    try:
        owner_id = int(owner_text)
        video_id = int(video_text)
    except ValueError as exc:
        raise MiloviDailyWallBlocked(f"Invalid VK Clip remote ID: {remote_id}") from exc
    if owner_id != MILOVI_OWNER_ID or video_id <= 0:
        raise MiloviDailyWallBlocked(f"VK Clip {remote_id} does not belong to exact Milovi owner {MILOVI_OWNER_ID}")
    return video_id


def plan_daily_publish_slots(
    *,
    existing_postponed_publish_dates: Sequence[int],
    now: datetime | None = None,
    source_ids: Sequence[str] = ROLL_OUT_IDS,
    timezone_name: str = DEFAULT_TIMEZONE,
    wall_hour: int = DEFAULT_WALL_HOUR,
    wall_minute: int = DEFAULT_WALL_MINUTE,
    minimum_future_seconds: int = 300,
) -> dict[str, datetime]:
    """Assign one Issue #323 wall slot per free calendar day.

    Any calendar day that already contains a postponed VK post is skipped. This
    is deliberately stricter than merely avoiding the same clock time: the
    rollout must not create a second scheduled wall appearance on that day.
    """

    if tuple(source_ids) != tuple(ROLL_OUT_IDS):
        raise MiloviDailyWallBlocked("Daily schedule source allowlist/order differs from Issue #323")
    if not 0 <= wall_hour <= 23 or not 0 <= wall_minute <= 59:
        raise ValueError("wall_hour/wall_minute are outside the clock range")
    if minimum_future_seconds < 0:
        raise ValueError("minimum_future_seconds cannot be negative")

    timezone = ZoneInfo(timezone_name)
    current = _aware(now or datetime.now(UTC), field="now").astimezone(timezone)
    occupied_days = {
        datetime.fromtimestamp(int(value), tz=UTC).astimezone(timezone).date()
        for value in existing_postponed_publish_dates
        if int(value) > 0
    }

    candidate_day = current.date()
    candidate = datetime.combine(candidate_day, time(wall_hour, wall_minute), tzinfo=timezone)
    if candidate <= current + timedelta(seconds=minimum_future_seconds):
        candidate_day += timedelta(days=1)

    result: dict[str, datetime] = {}
    for source_id in source_ids:
        while candidate_day in occupied_days:
            candidate_day += timedelta(days=1)
        publish_at = datetime.combine(candidate_day, time(wall_hour, wall_minute), tzinfo=timezone)
        result[source_id] = publish_at
        occupied_days.add(candidate_day)
        candidate_day += timedelta(days=1)
    return result


def _schedule_payload(slots: Mapping[str, datetime]) -> dict[str, Any]:
    return {
        "schema_name": DAILY_SCHEDULE_SCHEMA,
        "schema_version": DAILY_SCHEDULE_VERSION,
        "project_key": "milovi-cake",
        "community_id": MILOVI_COMMUNITY_ID,
        "owner_id": MILOVI_OWNER_ID,
        "timezone": DEFAULT_TIMEZONE,
        "wall_time": f"{DEFAULT_WALL_HOUR:02d}:{DEFAULT_WALL_MINUTE:02d}",
        "cadence": "one_post_per_calendar_day",
        "source_ids": list(ROLL_OUT_IDS),
        "slots": {source_id: slots[source_id].isoformat() for source_id in ROLL_OUT_IDS},
        "created_at": datetime.now(UTC).isoformat(),
    }


def _validate_schedule_payload(payload: Mapping[str, Any]) -> dict[str, datetime]:
    if payload.get("schema_name") != DAILY_SCHEDULE_SCHEMA or payload.get("schema_version") != DAILY_SCHEDULE_VERSION:
        raise MiloviDailyWallBlocked("Unexpected Milovi daily wall schedule schema")
    if payload.get("project_key") != "milovi-cake":
        raise MiloviDailyWallBlocked("Milovi daily wall schedule project identity differs")
    if payload.get("community_id") != MILOVI_COMMUNITY_ID or payload.get("owner_id") != MILOVI_OWNER_ID:
        raise MiloviDailyWallBlocked("Milovi daily wall schedule VK identity differs")
    if payload.get("timezone") != DEFAULT_TIMEZONE:
        raise MiloviDailyWallBlocked("Milovi daily wall schedule timezone differs")
    if payload.get("wall_time") != f"{DEFAULT_WALL_HOUR:02d}:{DEFAULT_WALL_MINUTE:02d}":
        raise MiloviDailyWallBlocked("Milovi daily wall schedule clock time differs")
    if tuple(payload.get("source_ids") or ()) != tuple(ROLL_OUT_IDS):
        raise MiloviDailyWallBlocked("Milovi daily wall schedule allowlist/order differs")

    raw_slots = payload.get("slots")
    if not isinstance(raw_slots, Mapping) or set(raw_slots) != set(ROLL_OUT_IDS):
        raise MiloviDailyWallBlocked("Milovi daily wall schedule slots differ from exact allowlist")
    slots: dict[str, datetime] = {}
    for source_id in ROLL_OUT_IDS:
        raw = raw_slots[source_id]
        if not isinstance(raw, str):
            raise MiloviDailyWallBlocked(f"Milovi daily wall slot is invalid for {source_id}")
        try:
            value = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise MiloviDailyWallBlocked(f"Milovi daily wall slot is invalid for {source_id}") from exc
        slots[source_id] = _aware(value, field=f"slot[{source_id}]")

    local_days = [value.astimezone(ZoneInfo(DEFAULT_TIMEZONE)).date() for value in slots.values()]
    if len(set(local_days)) != len(local_days):
        raise MiloviDailyWallBlocked("Milovi daily wall schedule contains more than one rollout post on a day")
    return slots


def load_or_create_daily_schedule(
    path: Path,
    *,
    writer: VkWallWriter,
    now: datetime | None = None,
) -> dict[str, datetime]:
    """Freeze the exact 12-day schedule before the first wall mutation."""

    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise MiloviDailyWallBlocked("Milovi daily wall schedule JSON is unreadable") from exc
        if not isinstance(payload, Mapping):
            raise MiloviDailyWallBlocked("Milovi daily wall schedule is not a JSON object")
        return _validate_schedule_payload(payload)

    snapshot = writer.capture_wall_snapshot(community_id=MILOVI_COMMUNITY_ID, max_posts_per_surface=10000)
    if not snapshot.complete:
        raise MiloviDailyWallBlocked("Complete published/postponed wall readback is unavailable for scheduling")
    existing_publish_dates = [
        int(post.publish_date)
        for post in snapshot.posts
        if post.surface is VkWallSurface.POSTPONED and post.publish_date is not None and int(post.publish_date) > 0
    ]
    slots = plan_daily_publish_slots(existing_postponed_publish_dates=existing_publish_dates, now=now)
    write_json_atomic(path, _schedule_payload(slots))
    return slots


def _daily_guid(source_id: str, publish_at: datetime) -> str:
    seed = f"milovi-323:{source_id}:{int(_aware(publish_at, field='publish_at').timestamp())}"
    return "vcm-milovi-323-daily-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20]


def ensure_postponed_wall_post(
    *,
    writer: VkWallWriter,
    asset: SourceAsset,
    clip_remote_id: str,
    publish_at: datetime,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Idempotently ensure one exact postponed post for one verified Clip."""

    if asset.source_id not in MILOVI_SOURCE_ALLOWLIST:
        raise MiloviDailyWallBlocked(f"Source is outside Issue #323 allowlist: {asset.source_id}")
    video_id = _parse_clip_remote_id(clip_remote_id)
    expected_publish_date = int(_aware(publish_at, field="publish_at").timestamp())
    attachment = f"video{MILOVI_OWNER_ID}_{video_id}"

    snapshot = writer.capture_wall_snapshot(community_id=MILOVI_COMMUNITY_ID, max_posts_per_surface=10000)
    if not snapshot.complete:
        raise MiloviDailyWallBlocked("Complete wall readback is unavailable before postponed publication")
    matches = [post for post in snapshot.posts if attachment in post.attachments]
    if len(matches) > 1:
        raise MiloviDailyWallBlocked(
            f"Clip {clip_remote_id} already appears in multiple wall posts: "
            f"{[f'{post.surface.value}:{post.remote_id}' for post in matches]}"
        )
    if matches:
        match = matches[0]
        if match.surface is not VkWallSurface.POSTPONED:
            raise MiloviDailyWallBlocked(
                f"Clip {clip_remote_id} already appears on published wall as {match.remote_id}; refusing duplicate"
            )
        if match.publish_date != expected_publish_date:
            raise MiloviDailyWallBlocked(
                f"Clip {clip_remote_id} is postponed for {match.publish_date}, expected {expected_publish_date}"
            )
        return {
            "source_id": asset.source_id,
            "clip_remote_id": clip_remote_id,
            "wall_remote_id": match.remote_id,
            "publish_date": expected_publish_date,
            "publish_at": publish_at.isoformat(),
            "origin": "adopted_existing_postponed",
        }

    result = writer.post_video(
        community_id=MILOVI_COMMUNITY_ID,
        video_owner_id=MILOVI_OWNER_ID,
        video_id=video_id,
        message=asset.wall_message,
        guid=_daily_guid(asset.source_id, publish_at),
        publish_at=publish_at,
        now=now,
        minimum_future_seconds=300,
        max_posts_per_surface=10000,
    )
    return {
        "source_id": asset.source_id,
        "clip_remote_id": clip_remote_id,
        "wall_remote_id": result.remote_id,
        "publish_date": result.publish_date,
        "publish_at": publish_at.isoformat(),
        "origin": "new_postponed",
    }


__all__ = [
    "DAILY_SCHEDULE_SCHEMA",
    "DAILY_SCHEDULE_VERSION",
    "DEFAULT_TIMEZONE",
    "DEFAULT_WALL_HOUR",
    "DEFAULT_WALL_MINUTE",
    "MiloviDailyWallBlocked",
    "ensure_postponed_wall_post",
    "load_or_create_daily_schedule",
    "plan_daily_publish_slots",
]
