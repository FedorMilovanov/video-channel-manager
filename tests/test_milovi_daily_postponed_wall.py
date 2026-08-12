from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from video_channel_manager.platforms.vk.milovi_daily_postponed_wall import (
    DAILY_SCHEDULE_SCHEMA,
    DEFAULT_TIMEZONE,
    MiloviDailyWallBlocked,
    ensure_postponed_wall_post,
    load_or_create_daily_schedule,
    plan_daily_publish_slots,
)
from video_channel_manager.platforms.vk.milovi_rollout_sources import ROLL_OUT_IDS, SourceAsset
from video_channel_manager.platforms.vk.wall_safety import VkWallSurface

MOSCOW = ZoneInfo(DEFAULT_TIMEZONE)


def _asset(source_id: str = ROLL_OUT_IDS[0]) -> SourceAsset:
    return SourceAsset(
        source_id=source_id,
        source_url=f"https://www.youtube.com/shorts/{source_id}",
        title="Milovi Cake test",
        duration_seconds=30,
        media_path="C:/tmp/test.mp4",
        media_sha256="a" * 64,
        width=1080,
        height=1920,
        description=f"Источник YouTube Shorts: https://www.youtube.com/shorts/{source_id}",
        wall_message=f"Milovi Cake test\nИсточник: https://www.youtube.com/shorts/{source_id}",
    )


class FakeWriter:
    def __init__(self, posts: list[SimpleNamespace] | None = None) -> None:
        self.posts = list(posts or [])
        self.post_calls: list[dict[str, object]] = []

    def capture_wall_snapshot(self, *, community_id: int, max_posts_per_surface: int) -> SimpleNamespace:
        assert community_id == 68859909
        assert max_posts_per_surface == 10000
        return SimpleNamespace(complete=True, posts=list(self.posts))

    def post_video(self, **kwargs: object) -> SimpleNamespace:
        self.post_calls.append(dict(kwargs))
        publish_at = kwargs["publish_at"]
        assert isinstance(publish_at, datetime)
        return SimpleNamespace(
            remote_id="-68859909_9001",
            publish_date=int(publish_at.timestamp()),
        )


def _post(*, remote_id: str, surface: VkWallSurface, publish_at: datetime, attachment: str) -> SimpleNamespace:
    return SimpleNamespace(
        remote_id=remote_id,
        surface=surface,
        publish_date=int(publish_at.timestamp()),
        attachments=(attachment,),
    )


def test_plan_daily_publish_slots_assigns_exactly_one_rollout_post_per_day() -> None:
    now = datetime(2026, 8, 13, 2, 30, tzinfo=MOSCOW)

    slots = plan_daily_publish_slots(existing_postponed_publish_dates=[], now=now)

    assert tuple(slots) == tuple(ROLL_OUT_IDS)
    values = list(slots.values())
    assert len(values) == 12
    assert len({value.date() for value in values}) == 12
    assert all((value.hour, value.minute) == (19, 0) for value in values)
    assert values[0] == datetime(2026, 8, 13, 19, 0, tzinfo=MOSCOW)
    assert values[-1] == datetime(2026, 8, 24, 19, 0, tzinfo=MOSCOW)


def test_plan_daily_publish_slots_skips_any_day_with_existing_postponed_post() -> None:
    now = datetime(2026, 8, 13, 2, 30, tzinfo=MOSCOW)
    occupied = datetime(2026, 8, 14, 11, 15, tzinfo=MOSCOW)

    slots = plan_daily_publish_slots(
        existing_postponed_publish_dates=[int(occupied.timestamp())],
        now=now,
    )

    dates = [value.date().isoformat() for value in slots.values()]
    assert dates[:3] == ["2026-08-13", "2026-08-15", "2026-08-16"]
    assert "2026-08-14" not in dates


def test_load_or_create_daily_schedule_freezes_slots_across_restarts(tmp_path: Path) -> None:
    writer = FakeWriter()
    schedule_path = tmp_path / "schedule.json"
    now = datetime(2026, 8, 13, 2, 30, tzinfo=MOSCOW)

    first = load_or_create_daily_schedule(schedule_path, writer=writer, now=now)
    second = load_or_create_daily_schedule(
        schedule_path,
        writer=FakeWriter(
            [
                _post(
                    remote_id="-68859909_9010",
                    surface=VkWallSurface.POSTPONED,
                    publish_at=datetime(2026, 8, 14, 10, 0, tzinfo=MOSCOW),
                    attachment="video-68859909_777",
                )
            ]
        ),
        now=datetime(2026, 8, 14, 3, 0, tzinfo=MOSCOW),
    )

    assert first == second
    text = schedule_path.read_text(encoding="utf-8")
    assert DAILY_SCHEDULE_SCHEMA in text


def test_ensure_postponed_wall_post_adopts_exact_existing_schedule_without_write() -> None:
    asset = _asset()
    publish_at = datetime(2026, 8, 13, 19, 0, tzinfo=MOSCOW)
    writer = FakeWriter(
        [
            _post(
                remote_id="-68859909_9020",
                surface=VkWallSurface.POSTPONED,
                publish_at=publish_at,
                attachment="video-68859909_456240001",
            )
        ]
    )

    result = ensure_postponed_wall_post(
        writer=writer,  # type: ignore[arg-type]
        asset=asset,
        clip_remote_id="-68859909_456240001",
        publish_at=publish_at,
        now=datetime(2026, 8, 13, 2, 30, tzinfo=MOSCOW),
    )

    assert result["origin"] == "adopted_existing_postponed"
    assert result["wall_remote_id"] == "-68859909_9020"
    assert writer.post_calls == []


def test_ensure_postponed_wall_post_rejects_existing_published_attachment() -> None:
    asset = _asset()
    publish_at = datetime(2026, 8, 13, 19, 0, tzinfo=MOSCOW)
    writer = FakeWriter(
        [
            _post(
                remote_id="-68859909_9030",
                surface=VkWallSurface.PUBLISHED,
                publish_at=datetime(2026, 8, 12, 19, 0, tzinfo=MOSCOW),
                attachment="video-68859909_456240002",
            )
        ]
    )

    with pytest.raises(MiloviDailyWallBlocked, match="published wall"):
        ensure_postponed_wall_post(
            writer=writer,  # type: ignore[arg-type]
            asset=asset,
            clip_remote_id="-68859909_456240002",
            publish_at=publish_at,
            now=datetime(2026, 8, 13, 2, 30, tzinfo=MOSCOW),
        )

    assert writer.post_calls == []


def test_ensure_postponed_wall_post_dispatches_exact_token_wall_write() -> None:
    asset = _asset()
    publish_at = datetime(2026, 8, 13, 19, 0, tzinfo=MOSCOW)
    writer = FakeWriter()

    result = ensure_postponed_wall_post(
        writer=writer,  # type: ignore[arg-type]
        asset=asset,
        clip_remote_id="-68859909_456240003",
        publish_at=publish_at,
        now=datetime(2026, 8, 13, 2, 30, tzinfo=MOSCOW),
    )

    assert result["origin"] == "new_postponed"
    assert result["publish_date"] == int(publish_at.timestamp())
    assert len(writer.post_calls) == 1
    call = writer.post_calls[0]
    assert call["community_id"] == 68859909
    assert call["video_owner_id"] == -68859909
    assert call["video_id"] == 456240003
    assert call["message"] == asset.wall_message
    assert call["publish_at"] == publish_at
    assert str(call["guid"]).startswith("vcm-milovi-323-daily-")


def test_plan_requires_exact_issue_323_allowlist_order() -> None:
    now = datetime(2026, 8, 13, 2, 30, tzinfo=UTC)

    with pytest.raises(MiloviDailyWallBlocked, match="allowlist/order"):
        plan_daily_publish_slots(
            existing_postponed_publish_dates=[],
            now=now,
            source_ids=tuple(reversed(ROLL_OUT_IDS)),
        )
