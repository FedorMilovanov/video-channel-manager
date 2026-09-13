from datetime import datetime, timedelta, timezone
from pathlib import Path

from video_channel_manager.instagram.daily_queue import (
    PUBLISHED_SOURCE_IDS,
    RIGHTS_REVIEW,
    build_legendary_poet_daily_queue,
    queue_sha256,
)

SNAPSHOT = (
    Path(__file__).resolve().parents[1]
    / "content"
    / "instagram"
    / "legendary-poet-youtube-shorts-snapshot-20260912.json"
)


def _queue():
    return build_legendary_poet_daily_queue(
        SNAPSHOT,
        account_id="17841435926122104",
        start_at=datetime(2026, 9, 14, 19, 0, tzinfo=timezone(timedelta(hours=3))),
    )


def test_full_short_inventory_partitions_without_duplicates() -> None:
    queue = _queue()
    assert queue.item_count == 62
    assert queue.published_count == 2
    assert queue.rights_review_count == 6
    assert queue.ready_count == 54
    assert {item.source_id for item in queue.items if item.status == "published"} == PUBLISHED_SOURCE_IDS
    assert {item.source_id for item in queue.items if item.status == "rights_review"} == set(RIGHTS_REVIEW)
    assert len({item.source_id for item in queue.items}) == 62
    assert len({item.publication_key for item in queue.items}) == 62


def test_ready_schedule_is_daily_and_seo_bounded() -> None:
    queue = _queue()
    ready = sorted(
        (item for item in queue.items if item.status == "ready"),
        key=lambda item: item.scheduled_at,
    )
    assert ready[0].scheduled_at.isoformat() == "2026-09-14T19:00:00+03:00"
    assert ready[-1].scheduled_at - ready[0].scheduled_at == timedelta(days=53)
    assert all(len(item.hashtags) <= 5 for item in ready)
    assert all(len(item.caption) <= 2200 for item in ready)
    assert all("#TheLegendaryPoet" in item.hashtags for item in ready)
    assert all(item.width < item.height for item in ready)
    assert all(item.duration_seconds <= 180 for item in ready)


def test_priority_queue_starts_with_proven_short_and_diversifies_authors() -> None:
    queue = _queue()
    ready = sorted(
        (item for item in queue.items if item.status == "ready"),
        key=lambda item: item.scheduled_at,
    )
    assert ready[0].source_id == "7IP9_wxDTAc"
    for left, right in zip(ready, ready[1:], strict=False):
        if left.author is not None and right.author is not None:
            assert left.author != right.author


def test_queue_digest_is_stable_sha256() -> None:
    digest = queue_sha256(_queue())
    assert digest.startswith("sha256:")
    assert len(digest) == 71
