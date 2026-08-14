from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

import video_channel_manager.platforms.vk.milovi_issue323_finalize as finalize
from video_channel_manager.platforms.vk.milovi_rollout_sources import ROLL_OUT_IDS, SourceAsset
from video_channel_manager.platforms.vk.wall_safety import build_wall_snapshot

PUBLISH_DATE = 1786723200
SOURCE_ID = ROLL_OUT_IDS[0]
OLD_WALL_ID = "-68859909_468"
SUCCESSOR_WALL_ID = "-68859909_900"
CLIP_ID = "-68859909_456239225"


def _legacy_asset() -> SourceAsset:
    title = "Авторский торт Milovi Cake"
    source_url = f"https://www.youtube.com/shorts/{SOURCE_ID}"
    return SourceAsset(
        source_id=SOURCE_ID,
        source_url=source_url,
        title=title,
        duration_seconds=27,
        media_path=str(Path("clip.mp4")),
        media_sha256="a" * 64,
        width=1080,
        height=1920,
        description=f"{title}\n\nИсточник YouTube Shorts: {source_url}",
        wall_message=f"{title}\n\nИсточник: {source_url}",
    )


def _promoted_asset() -> SourceAsset:
    return finalize._promote_asset(_legacy_asset())


def _wall(post_id: int, *, text: str, clip_id: int = 456239225) -> dict[str, Any]:
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


class _Writer:
    def __init__(
        self,
        *,
        published: list[dict[str, Any]],
        postponed: list[dict[str, Any]] | None = None,
        old_exact: dict[str, Any] | None = None,
        asset: SourceAsset | None = None,
    ) -> None:
        self.published = published
        self.postponed = postponed or []
        self.old_exact = old_exact
        self.asset = asset or _promoted_asset()
        self.calls: list[tuple[str, dict[str, Any]]] = []
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
        if post_id == 475:
            return {"owner_id": -68859909, "id": 475, "is_deleted": True}
        if post_id == 468:
            return dict(self.old_exact) if self.old_exact is not None else None
        for post in [*self.published, *self.postponed]:
            if post.get("id") == post_id:
                return dict(post)
        return None

    def read_video(self, *, owner_id: int, video_id: int) -> dict[str, Any] | None:
        assert owner_id == -68859909
        assert video_id == 456239225
        return {
            "owner_id": owner_id,
            "id": video_id,
            "type": "short_video",
            "description": self.asset.description,
        }

    def _call(self, method: str, *, params: dict[str, Any]) -> object:
        self.calls.append((method, dict(params)))
        if method == "wall.edit":
            for post in [*self.published, *self.postponed]:
                if post.get("id") == params["post_id"]:
                    post["text"] = params["message"]
                    return 1
        raise AssertionError(f"Unexpected mutation: {method}: {params}")


def test_due_published_successor_is_edited_by_current_id_without_reschedule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    asset = _promoted_asset()
    successor = _wall(900, text="legacy wall copy")
    tombstone = {"owner_id": -68859909, "id": 468, "date": PUBLISH_DATE, "is_deleted": True}
    writer = _Writer(published=[successor], old_exact=tombstone, asset=asset)
    operation: dict[str, Any] = {"status": "pending"}
    finalizer = {"wall_message_edits": {SOURCE_ID: operation}}
    monkeypatch.setattr(finalize, "_prove_target", lambda _client: None)
    monkeypatch.setattr(finalize.time, "time", lambda: PUBLISH_DATE + 3600)

    finalize._edit_wall_message(
        writer=writer,  # type: ignore[arg-type]
        client=object(),  # type: ignore[arg-type]
        asset=asset,
        journal=_journal(),
        wall_remote_id=OLD_WALL_ID,
        clip_remote_id=CLIP_ID,
        publish_date=PUBLISH_DATE,
        operation=operation,
        finalizer=finalizer,
        finalizer_path=tmp_path / "finalizer.json",
    )

    assert len(writer.calls) == 1
    method, params = writer.calls[0]
    assert method == "wall.edit"
    assert params["post_id"] == 900
    assert "publish_date" not in params
    assert successor["text"] == asset.wall_message
    assert operation["status"] == "verified"
    assert operation["journal_remote_id"] == OLD_WALL_ID
    assert operation["remote_id"] == SUCCESSOR_WALL_ID
    assert operation["surface"] == "published"
    assert operation["resolution_mode"] == "published_successor"
    assert operation["dispatch_started"] is True
    assert operation["before_message_sha256"] == finalize._sha256_text("legacy wall copy")
    assert operation["target_message_sha256"] == finalize._sha256_text(asset.wall_message.strip())


def test_future_missing_journaled_id_blocks_before_exact_read_or_mutation() -> None:
    writer = _Writer(published=[])
    snapshot = writer.capture_wall_snapshot(community_id=68859909, max_posts_per_surface=10000)

    with pytest.raises(finalize.MiloviFinalizerBlocked, match="before its frozen slot"):
        finalize._resolve_wall_incarnation(
            writer=writer,  # type: ignore[arg-type]
            snapshot=snapshot,
            journal=_journal(),
            wall_remote_id=OLD_WALL_ID,
            clip_remote_id=CLIP_ID,
            publish_date=PUBLISH_DATE,
            now_epoch=PUBLISH_DATE - 3600,
        )

    assert writer.read_post_calls == []
    assert writer.calls == []


def test_ambiguous_published_successor_blocks_before_mutation() -> None:
    tombstone = {"owner_id": -68859909, "id": 468, "date": PUBLISH_DATE, "is_deleted": True}
    writer = _Writer(
        published=[_wall(900, text="a"), _wall(901, text="b")],
        old_exact=tombstone,
    )
    snapshot = writer.capture_wall_snapshot(community_id=68859909, max_posts_per_surface=10000)

    with pytest.raises(finalize.MiloviFinalizerBlocked, match="successor is ambiguous"):
        finalize._resolve_wall_incarnation(
            writer=writer,  # type: ignore[arg-type]
            snapshot=snapshot,
            journal=_journal(),
            wall_remote_id=OLD_WALL_ID,
            clip_remote_id=CLIP_ID,
            publish_date=PUBLISH_DATE,
            now_epoch=PUBLISH_DATE + 3600,
        )

    assert writer.calls == []


def test_future_live_postponed_incarnation_keeps_journaled_id() -> None:
    raw = _wall(468, text="legacy wall copy")
    writer = _Writer(published=[], postponed=[raw], old_exact=raw)
    snapshot = writer.capture_wall_snapshot(community_id=68859909, max_posts_per_surface=10000)

    actual_id, surface, exact, mode = finalize._resolve_wall_incarnation(
        writer=writer,  # type: ignore[arg-type]
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


def test_final_postflight_accepts_unique_successor_and_preserves_historical_id() -> None:
    asset = _promoted_asset()
    successor = _wall(900, text=asset.wall_message)
    tombstone = {"owner_id": -68859909, "id": 468, "date": PUBLISH_DATE, "is_deleted": True}
    writer = _Writer(published=[successor], old_exact=tombstone, asset=asset)

    evidence = finalize._final_postflight(
        writer,  # type: ignore[arg-type]
        [asset],
        _journal(),
        now_epoch=PUBLISH_DATE + 3600,
    )

    assert evidence == [
        {
            "source_id": SOURCE_ID,
            "clip_remote_id": CLIP_ID,
            "wall_remote_id": OLD_WALL_ID,
            "current_wall_remote_id": SUCCESSOR_WALL_ID,
            "wall_resolution_mode": "published_successor",
            "publish_date": PUBLISH_DATE,
            "wall_surface": "published",
            "clip_description_sha256": finalize._sha256_text(asset.description),
            "wall_message_sha256": finalize._sha256_text(asset.wall_message),
        }
    ]
