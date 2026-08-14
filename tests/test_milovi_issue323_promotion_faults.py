from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import video_channel_manager.platforms.vk.milovi_issue323_finalize as finalize
from video_channel_manager.platforms.vk.milovi_rollout_sources import ROLL_OUT_IDS
from video_channel_manager.platforms.vk.wall_safety import build_wall_snapshot

SOURCE_ID = ROLL_OUT_IDS[8]
CLIP_ID = 456239233
CLIP_REMOTE_ID = f"-68859909_{CLIP_ID}"
WALL_ID = 900
WALL_REMOTE_ID = f"-68859909_{WALL_ID}"
PUBLISH_DATE = 1893456000
LEGACY_DESCRIPTION = f"Cake source https://www.youtube.com/shorts/{SOURCE_ID}"
PROMOTED_DESCRIPTION = "Milovi Cake promoted description"
PROMOTED_WALL = "Milovi Cake promoted wall"


def _asset() -> Any:
    return SimpleNamespace(
        source_id=SOURCE_ID,
        title="Cake",
        description=PROMOTED_DESCRIPTION,
        wall_message=PROMOTED_WALL,
        duration_seconds=30.0,
        media_path="unused.mp4",
    )


class _PromotionWriter:
    def __init__(self, *, description: str = LEGACY_DESCRIPTION, wall_text: str = "legacy wall") -> None:
        self.description = description
        self.wall_text = wall_text
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.fail_video_after_apply = False
        self.fail_wall_after_apply = False
        self.video_reads = 0
        self.mutate_second_video_read = False
        self.wall_captures = 0
        self.mutate_second_wall_capture = False

    def read_video(self, *, owner_id: int, video_id: int) -> dict[str, Any] | None:
        assert owner_id == -68859909
        assert video_id == CLIP_ID
        self.video_reads += 1
        description = self.description
        if self.mutate_second_video_read and self.video_reads >= 2:
            description = "unrelated description"
        return {
            "owner_id": owner_id,
            "id": video_id,
            "type": "short_video",
            "title": "Cake",
            "description": description,
        }

    def _wall(self, *, wrong_clip: bool = False) -> dict[str, Any]:
        return {
            "owner_id": -68859909,
            "id": WALL_ID,
            "date": PUBLISH_DATE,
            "text": self.wall_text,
            "attachments": [
                {
                    "type": "video",
                    "video": {
                        "owner_id": -68859909,
                        "id": 999 if wrong_clip else CLIP_ID,
                        "type": "short_video",
                    },
                }
            ],
        }

    def read_post(self, *, community_id: int, post_id: int) -> dict[str, Any] | None:
        assert community_id == 68859909
        if post_id == 475:
            return {"owner_id": -68859909, "id": 475, "is_deleted": True}
        assert post_id == WALL_ID
        return self._wall()

    def capture_wall_snapshot(self, *, community_id: int, max_posts_per_surface: int = 10000):
        assert community_id == 68859909
        assert max_posts_per_surface == 10000
        self.wall_captures += 1
        wrong_clip = self.mutate_second_wall_capture and self.wall_captures >= 2
        return build_wall_snapshot(
            community_id=community_id,
            published_items=[],
            postponed_items=[self._wall(wrong_clip=wrong_clip)],
            published_pages=1,
            postponed_pages=1,
            complete=True,
            captured_at=datetime(2026, 8, 15, 0, 0, tzinfo=UTC),
        )

    def _call(self, method: str, *, params: dict[str, Any]) -> object:
        self.calls.append((method, dict(params)))
        if method == "video.edit":
            self.description = str(params["desc"])
            if self.fail_video_after_apply:
                raise RuntimeError("lost video.edit response")
            return 1
        if method == "wall.edit":
            self.wall_text = str(params["message"])
            if self.fail_wall_after_apply:
                raise RuntimeError("lost wall.edit response")
            return 1
        raise AssertionError(method)


def _journal(*, status: str = "wall_verified") -> dict[str, Any]:
    return {
        "items": {
            SOURCE_ID: {
                "status": status,
                "clip_remote_id": CLIP_REMOTE_ID,
                "wall_remote_id": WALL_REMOTE_ID,
                "publish_date": PUBLISH_DATE,
            }
        }
    }


def test_recovered_child_accepts_exact_legacy_binding_then_promotion_reaches_strict_final_postflight(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    writer = _PromotionWriter()
    asset = _asset()
    journal = _journal(status="clip_verified")

    def fake_ensure_wall(_asset, _clip_id, _slot, item, _journal, _journal_path, _writer, _client) -> None:
        item.update(status="wall_verified", wall_remote_id=WALL_REMOTE_ID, publish_date=PUBLISH_DATE)

    monkeypatch.setattr(finalize, "_ensure_wall", fake_ensure_wall)
    monkeypatch.setattr(finalize, "_prove_target", lambda _client: None)
    finalize._complete_child(
        SOURCE_ID,
        legacy_assets={SOURCE_ID: asset},
        promoted_assets={SOURCE_ID: asset},
        artifacts={SOURCE_ID: object()},
        journal=journal,
        journal_path=tmp_path / "rollout.json",
        slots={SOURCE_ID: object()},
        writer=writer,  # type: ignore[arg-type]
        upload_writer=object(),  # type: ignore[arg-type]
        client=object(),  # type: ignore[arg-type]
        verify_timeout_seconds=60,
    )
    assert journal["items"][SOURCE_ID]["status"] == "wall_verified"
    with pytest.raises(finalize.MiloviFinalizerBlocked, match="public description differs"):
        finalize._final_postflight(writer, [asset], journal, now_epoch=1700000000)  # type: ignore[arg-type]

    clip_operation: dict[str, Any] = {"status": "pending"}
    wall_operation: dict[str, Any] = {"status": "pending"}
    state = {
        "clip_description_edits": {SOURCE_ID: clip_operation},
        "wall_message_edits": {SOURCE_ID: wall_operation},
    }
    finalize._edit_clip_description(
        writer=writer,  # type: ignore[arg-type]
        client=object(),  # type: ignore[arg-type]
        asset=asset,
        remote_id=CLIP_REMOTE_ID,
        operation=clip_operation,
        finalizer=state,
        finalizer_path=tmp_path / "finalizer.json",
    )
    finalize._edit_wall_message(
        writer=writer,  # type: ignore[arg-type]
        client=object(),  # type: ignore[arg-type]
        asset=asset,
        journal=journal,
        wall_remote_id=WALL_REMOTE_ID,
        clip_remote_id=CLIP_REMOTE_ID,
        publish_date=PUBLISH_DATE,
        operation=wall_operation,
        finalizer=state,
        finalizer_path=tmp_path / "finalizer.json",
    )
    evidence = finalize._final_postflight(writer, [asset], journal, now_epoch=1700000000)  # type: ignore[arg-type]
    assert evidence[0]["clip_remote_id"] == CLIP_REMOTE_ID
    assert clip_operation["status"] == "verified"
    assert wall_operation["status"] == "verified"
    assert [call[0] for call in writer.calls] == ["video.edit", "wall.edit"]


def test_recovered_child_rejects_unrelated_description_before_wall_mutation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    writer = _PromotionWriter(description="unrelated description")
    asset = _asset()
    journal = _journal(status="clip_verified")
    wall_calls: list[str] = []
    monkeypatch.setattr(finalize, "_ensure_wall", lambda *_args, **_kwargs: wall_calls.append("wall"))
    with pytest.raises(finalize.MiloviFinalizerBlocked, match="cannot be bound to source"):
        finalize._complete_child(
            SOURCE_ID,
            legacy_assets={SOURCE_ID: asset},
            promoted_assets={SOURCE_ID: asset},
            artifacts={SOURCE_ID: object()},
            journal=journal,
            journal_path=tmp_path / "rollout.json",
            slots={SOURCE_ID: object()},
            writer=writer,  # type: ignore[arg-type]
            upload_writer=object(),  # type: ignore[arg-type]
            client=object(),  # type: ignore[arg-type]
            verify_timeout_seconds=60,
        )
    assert wall_calls == []


def test_clip_promotion_rechecks_source_binding_before_dispatch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    writer = _PromotionWriter()
    writer.mutate_second_video_read = True
    monkeypatch.setattr(finalize, "_prove_target", lambda _client: None)
    operation: dict[str, Any] = {"status": "pending"}
    state = {"clip_description_edits": {SOURCE_ID: operation}}
    with pytest.raises(finalize.MiloviFinalizerBlocked, match="cannot be bound to source"):
        finalize._edit_clip_description(
            writer=writer,  # type: ignore[arg-type]
            client=object(),  # type: ignore[arg-type]
            asset=_asset(),
            remote_id=CLIP_REMOTE_ID,
            operation=operation,
            finalizer=state,
            finalizer_path=tmp_path / "finalizer.json",
        )
    assert writer.calls == []
    assert operation["dispatch_started"] is False


def test_clip_promotion_lost_response_reconciles_exact_target_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    writer = _PromotionWriter()
    writer.fail_video_after_apply = True
    monkeypatch.setattr(finalize, "_prove_target", lambda _client: None)
    operation: dict[str, Any] = {"status": "pending"}
    state = {"clip_description_edits": {SOURCE_ID: operation}}
    finalize._edit_clip_description(
        writer=writer,  # type: ignore[arg-type]
        client=object(),  # type: ignore[arg-type]
        asset=_asset(),
        remote_id=CLIP_REMOTE_ID,
        operation=operation,
        finalizer=state,
        finalizer_path=tmp_path / "finalizer.json",
    )
    assert [call[0] for call in writer.calls] == ["video.edit"]
    assert operation["dispatch_started"] is True
    assert operation["response_lost_reconciled"] is True
    assert operation["status"] == "verified"


def test_clip_promotion_dispatch_started_legacy_copy_blocks_blind_replay(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    writer = _PromotionWriter()
    monkeypatch.setattr(finalize, "_prove_target", lambda _client: None)
    operation: dict[str, Any] = {"status": "edit_dispatch_started", "dispatch_started": True}
    state = {"clip_description_edits": {SOURCE_ID: operation}}
    with pytest.raises(finalize.MiloviFinalizerBlocked, match="blind retry is forbidden"):
        finalize._edit_clip_description(
            writer=writer,  # type: ignore[arg-type]
            client=object(),  # type: ignore[arg-type]
            asset=_asset(),
            remote_id=CLIP_REMOTE_ID,
            operation=operation,
            finalizer=state,
            finalizer_path=tmp_path / "finalizer.json",
        )
    assert writer.calls == []


def test_wall_promotion_rechecks_logical_binding_before_dispatch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    writer = _PromotionWriter()
    writer.mutate_second_wall_capture = True
    monkeypatch.setattr(finalize, "_prove_target", lambda _client: None)
    operation: dict[str, Any] = {"status": "pending"}
    state = {"wall_message_edits": {SOURCE_ID: operation}}
    with pytest.raises(finalize.MiloviFinalizerBlocked, match="Logical wall mapping|attachment|successor"):
        finalize._edit_wall_message(
            writer=writer,  # type: ignore[arg-type]
            client=object(),  # type: ignore[arg-type]
            asset=_asset(),
            journal=_journal(),
            wall_remote_id=WALL_REMOTE_ID,
            clip_remote_id=CLIP_REMOTE_ID,
            publish_date=PUBLISH_DATE,
            operation=operation,
            finalizer=state,
            finalizer_path=tmp_path / "finalizer.json",
        )
    assert writer.calls == []
    assert operation["dispatch_started"] is False


def test_wall_promotion_lost_response_reconciles_exact_target_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    writer = _PromotionWriter()
    writer.fail_wall_after_apply = True
    monkeypatch.setattr(finalize, "_prove_target", lambda _client: None)
    operation: dict[str, Any] = {"status": "pending"}
    state = {"wall_message_edits": {SOURCE_ID: operation}}
    finalize._edit_wall_message(
        writer=writer,  # type: ignore[arg-type]
        client=object(),  # type: ignore[arg-type]
        asset=_asset(),
        journal=_journal(),
        wall_remote_id=WALL_REMOTE_ID,
        clip_remote_id=CLIP_REMOTE_ID,
        publish_date=PUBLISH_DATE,
        operation=operation,
        finalizer=state,
        finalizer_path=tmp_path / "finalizer.json",
    )
    assert [call[0] for call in writer.calls] == ["wall.edit"]
    assert operation["dispatch_started"] is True
    assert operation["response_lost_reconciled"] is True
    assert operation["status"] == "verified"


def test_wall_promotion_dispatch_started_old_copy_blocks_blind_replay(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    writer = _PromotionWriter()
    monkeypatch.setattr(finalize, "_prove_target", lambda _client: None)
    operation: dict[str, Any] = {"status": "edit_dispatch_started", "dispatch_started": True}
    state = {"wall_message_edits": {SOURCE_ID: operation}}
    with pytest.raises(finalize.MiloviFinalizerBlocked, match="blind retry is forbidden"):
        finalize._edit_wall_message(
            writer=writer,  # type: ignore[arg-type]
            client=object(),  # type: ignore[arg-type]
            asset=_asset(),
            journal=_journal(),
            wall_remote_id=WALL_REMOTE_ID,
            clip_remote_id=CLIP_REMOTE_ID,
            publish_date=PUBLISH_DATE,
            operation=operation,
            finalizer=state,
            finalizer_path=tmp_path / "finalizer.json",
        )
    assert writer.calls == []
