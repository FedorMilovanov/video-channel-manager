from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import video_channel_manager.platforms.vk.milovi_issue323_finalize as finalizer
from video_channel_manager.platforms.vk.milovi_rollout_sources import build_wall_message
from video_channel_manager.platforms.vk.wall_safety import VkWallSurface, build_wall_snapshot

PUBLISH_DATE = 1786723200
CLIP_REMOTE_ID = "-68859909_456239225"
WALL_REMOTE_ID = "-68859909_468"
SOURCE_ID = "d48QLgOuiTs"
TITLE = "Cake"
LEGACY_WALL = build_wall_message(TITLE, SOURCE_ID)
PROMOTED_WALL = "new internal promotion"


def _wall_item(*, text: str = LEGACY_WALL, post_id: int = 468, publish_date: int = PUBLISH_DATE) -> dict[str, Any]:
    return {
        "owner_id": -68859909,
        "id": post_id,
        "date": publish_date,
        "text": text,
        "attachments": [
            {
                "type": "video",
                "video": {
                    "owner_id": -68859909,
                    "id": 456239225,
                    "type": "short_video",
                },
            }
        ],
    }


class _WallWriter:
    def __init__(
        self,
        *,
        published: list[dict[str, Any]] | None = None,
        postponed: list[dict[str, Any]] | None = None,
    ) -> None:
        self.published = published or []
        self.postponed = postponed or []
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def read_post(self, *, community_id: int, post_id: int) -> dict[str, Any] | None:
        assert community_id == 68859909
        if post_id == 475:
            return {"owner_id": -68859909, "id": 475, "is_deleted": True}
        for items in (self.published, self.postponed):
            for item in items:
                if item["id"] == post_id:
                    return dict(item)
        return None

    def _read_wall_surface(
        self,
        *,
        community_id: int,
        surface: VkWallSurface,
        max_posts: int,
    ) -> tuple[list[dict[str, Any]], int, bool]:
        assert community_id == 68859909
        assert max_posts == 10000
        items = self.published if surface is VkWallSurface.PUBLISHED else self.postponed
        return [dict(item) for item in items], 1, True

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
            captured_at=datetime(2026, 8, 14, 17, 30, tzinfo=UTC),
        )

    def _call(self, method: str, *, params: dict[str, Any]) -> object:
        assert method == "wall.edit"
        self.calls.append((method, dict(params)))
        post_id = int(params["post_id"])
        for items in (self.published, self.postponed):
            for item in items:
                if item["id"] == post_id:
                    item["text"] = str(params["message"])
                    return 1
        raise AssertionError(f"post not found: {post_id}")


def _edit_asset() -> Any:
    return SimpleNamespace(source_id=SOURCE_ID, title=TITLE, wall_message=PROMOTED_WALL)


def test_published_scheduled_post_edit_preserves_surface_without_publish_date(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    writer = _WallWriter(published=[_wall_item()])
    monkeypatch.setattr(finalizer, "_prove_target", lambda _client: None)
    operation: dict[str, Any] = {"status": "pending"}
    state = {"wall_message_edits": {SOURCE_ID: operation}}

    finalizer._edit_wall_message(
        writer=writer,  # type: ignore[arg-type]
        client=object(),  # type: ignore[arg-type]
        asset=_edit_asset(),  # type: ignore[arg-type]
        journal=_journal(),
        wall_remote_id=WALL_REMOTE_ID,
        clip_remote_id=CLIP_REMOTE_ID,
        publish_date=PUBLISH_DATE,
        operation=operation,
        finalizer=state,
        finalizer_path=tmp_path / "finalizer.json",
    )

    assert writer.calls == [
        (
            "wall.edit",
            {
                "owner_id": -68859909,
                "post_id": 468,
                "message": PROMOTED_WALL,
                "attachments": "video-68859909_456239225",
            },
        )
    ]
    assert operation["status"] == "verified"
    assert operation["surface"] == "published"


def test_postponed_edit_keeps_exact_publish_date(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    writer = _WallWriter(postponed=[_wall_item()])
    monkeypatch.setattr(finalizer, "_prove_target", lambda _client: None)
    operation: dict[str, Any] = {"status": "pending"}

    finalizer._edit_wall_message(
        writer=writer,  # type: ignore[arg-type]
        client=object(),  # type: ignore[arg-type]
        asset=_edit_asset(),  # type: ignore[arg-type]
        journal=_journal(),
        wall_remote_id=WALL_REMOTE_ID,
        clip_remote_id=CLIP_REMOTE_ID,
        publish_date=PUBLISH_DATE,
        operation=operation,
        finalizer={"operation": operation},
        finalizer_path=tmp_path / "finalizer.json",
    )

    assert writer.calls[0][1]["publish_date"] == PUBLISH_DATE
    assert operation["surface"] == "postponed"


def _journal() -> dict[str, Any]:
    return {
        "items": {
            SOURCE_ID: {
                "status": "wall_verified",
                "clip_remote_id": CLIP_REMOTE_ID,
                "wall_remote_id": WALL_REMOTE_ID,
                "publish_date": PUBLISH_DATE,
            }
        }
    }


def _asset() -> Any:
    return SimpleNamespace(
        source_id=SOURCE_ID,
        title=TITLE,
        description="promoted clip description",
        wall_message=PROMOTED_WALL,
    )


def test_final_postflight_accepts_due_post_after_normal_postponed_to_published_transition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    writer = _WallWriter(published=[_wall_item(text=PROMOTED_WALL)])
    monkeypatch.setattr(finalizer, "_assert_native_clip", lambda *args, **kwargs: {})
    monkeypatch.setattr(finalizer.time, "time", lambda: PUBLISH_DATE + 3600)

    evidence = finalizer._final_postflight(writer, [_asset()], _journal())  # type: ignore[arg-type]

    assert evidence[0]["wall_remote_id"] == WALL_REMOTE_ID
    assert evidence[0]["wall_surface"] == "published"


def test_final_postflight_rejects_future_post_that_published_early(monkeypatch: pytest.MonkeyPatch) -> None:
    writer = _WallWriter(published=[_wall_item(text=PROMOTED_WALL)])
    monkeypatch.setattr(finalizer, "_assert_native_clip", lambda *args, **kwargs: {})
    monkeypatch.setattr(finalizer.time, "time", lambda: PUBLISH_DATE - 3600)

    with pytest.raises(finalizer.MiloviFinalizerBlocked, match="published before its scheduled slot"):
        finalizer._final_postflight(writer, [_asset()], _journal())  # type: ignore[arg-type]
