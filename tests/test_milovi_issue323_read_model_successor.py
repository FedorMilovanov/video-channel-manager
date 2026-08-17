from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from video_channel_manager.platforms.vk import milovi_issue323_read_model as read_model
from video_channel_manager.platforms.vk.milovi_rollout_sources import ROLL_OUT_IDS
from video_channel_manager.platforms.vk.wall_safety import build_wall_snapshot

PUBLISH_DATE = 1786723200
SOURCE_ID = ROLL_OUT_IDS[0]
OLD_WALL_ID = "-68859909_468"
SUCCESSOR_WALL_ID = "-68859909_900"
CLIP_ID = "-68859909_456239225"


def _wall(post_id: int, *, text: str = "reviewed", clip_id: int = 456239225) -> dict[str, Any]:
    return {
        "owner_id": -68859909,
        "id": post_id,
        "date": PUBLISH_DATE,
        "text": text,
        "attachments": [
            {
                "type": "video",
                "video": {
                    "owner_id": -68859909,
                    "id": clip_id,
                    "type": "short_video",
                },
            }
        ],
    }


def _journal() -> dict[str, Any]:
    return {
        "items": {
            SOURCE_ID: {
                "status": "wall_verified",
                "clip_remote_id": CLIP_ID,
                "wall_remote_id": OLD_WALL_ID,
                "publish_date": PUBLISH_DATE,
            }
        }
    }


class _Reader:
    def __init__(
        self,
        *,
        published: list[dict[str, Any]],
        postponed: list[dict[str, Any]] | None = None,
        old_exact: dict[str, Any] | None = None,
    ) -> None:
        self.published = published
        self.postponed = postponed or []
        self.old_exact = old_exact
        self.read_post_calls: list[int] = []

    def capture_wall_snapshot(self, *, community_id: int, max_posts_per_surface: int):
        assert community_id == 68859909
        assert max_posts_per_surface == 10000
        return build_wall_snapshot(
            community_id=community_id,
            published_items=self.published,
            postponed_items=self.postponed,
            published_pages=1,
            postponed_pages=1,
            complete=True,
            captured_at=datetime(2026, 8, 14, 19, 0, tzinfo=UTC),
        )

    def read_post(self, *, community_id: int, post_id: int) -> dict[str, Any] | None:
        assert community_id == 68859909
        self.read_post_calls.append(post_id)
        if post_id == 468:
            return dict(self.old_exact) if self.old_exact is not None else None
        for post in [*self.published, *self.postponed]:
            if post.get("id") == post_id:
                return dict(post)
        return None


def test_due_tombstoned_wall_resolves_unique_published_successor() -> None:
    successor = _wall(900)
    tombstone = {"owner_id": -68859909, "id": 468, "date": PUBLISH_DATE, "is_deleted": True}
    reader = _Reader(published=[successor], old_exact=tombstone)
    snapshot = reader.capture_wall_snapshot(community_id=68859909, max_posts_per_surface=10000)

    actual_id, surface, exact, mode = read_model._resolve_wall_incarnation(
        writer=reader,  # type: ignore[arg-type]
        snapshot=snapshot,
        journal=_journal(),
        wall_remote_id=OLD_WALL_ID,
        clip_remote_id=CLIP_ID,
        publish_date=PUBLISH_DATE,
        now_epoch=PUBLISH_DATE + 3600,
    )

    assert actual_id == SUCCESSOR_WALL_ID
    assert surface.value == "published"
    assert exact["id"] == 900
    assert mode == "published_successor"
    assert reader.read_post_calls == [468, 900]


def test_future_missing_journaled_id_blocks_before_exact_read() -> None:
    reader = _Reader(published=[])
    snapshot = reader.capture_wall_snapshot(community_id=68859909, max_posts_per_surface=10000)

    with pytest.raises(read_model.MiloviIssue323ReadModelBlocked, match="before its frozen slot"):
        read_model._resolve_wall_incarnation(
            writer=reader,  # type: ignore[arg-type]
            snapshot=snapshot,
            journal=_journal(),
            wall_remote_id=OLD_WALL_ID,
            clip_remote_id=CLIP_ID,
            publish_date=PUBLISH_DATE,
            now_epoch=PUBLISH_DATE - 3600,
        )

    assert reader.read_post_calls == []


def test_ambiguous_published_successor_blocks() -> None:
    tombstone = {"owner_id": -68859909, "id": 468, "date": PUBLISH_DATE, "is_deleted": True}
    reader = _Reader(published=[_wall(900), _wall(901)], old_exact=tombstone)
    snapshot = reader.capture_wall_snapshot(community_id=68859909, max_posts_per_surface=10000)

    with pytest.raises(read_model.MiloviIssue323ReadModelBlocked, match="successor is ambiguous"):
        read_model._resolve_wall_incarnation(
            writer=reader,  # type: ignore[arg-type]
            snapshot=snapshot,
            journal=_journal(),
            wall_remote_id=OLD_WALL_ID,
            clip_remote_id=CLIP_ID,
            publish_date=PUBLISH_DATE,
            now_epoch=PUBLISH_DATE + 3600,
        )


def test_future_live_postponed_incarnation_keeps_journaled_id() -> None:
    raw = _wall(468)
    reader = _Reader(published=[], postponed=[raw], old_exact=raw)
    snapshot = reader.capture_wall_snapshot(community_id=68859909, max_posts_per_surface=10000)

    actual_id, surface, exact, mode = read_model._resolve_wall_incarnation(
        writer=reader,  # type: ignore[arg-type]
        snapshot=snapshot,
        journal=_journal(),
        wall_remote_id=OLD_WALL_ID,
        clip_remote_id=CLIP_ID,
        publish_date=PUBLISH_DATE,
        now_epoch=PUBLISH_DATE - 3600,
    )

    assert actual_id == OLD_WALL_ID
    assert surface.value == "postponed"
    assert exact["id"] == 468
    assert mode == "journaled_id"
