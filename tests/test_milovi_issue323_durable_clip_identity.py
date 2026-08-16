from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import video_channel_manager.platforms.vk.milovi_issue323_finalize as finalize
from video_channel_manager.platforms.vk.milovi_issue323_finalize import (
    MiloviFinalizerBlocked,
    _assert_native_clip,
)
from video_channel_manager.platforms.vk.milovi_rollout_sources import build_description
from video_channel_manager.platforms.vk.upload_lifecycle import UploadStage
from video_channel_manager.platforms.vk.wall_safety import build_wall_snapshot

SOURCE_ID = "d48QLgOuiTs"
TITLE = "Durable cake"
LEGACY_DESCRIPTION = build_description(TITLE, SOURCE_ID)
PROMOTED_DESCRIPTION = "promoted internal copy"
REMOTE_ID = "-68859909_456239225"


class _Writer:
    def __init__(self, item: dict[str, Any]) -> None:
        self.item = item
        self.read_calls = 0

    def read_video(self, *, owner_id: int, video_id: int) -> dict[str, Any] | None:
        assert owner_id == -68859909
        assert video_id == 456239225
        self.read_calls += 1
        return dict(self.item)


def _asset() -> Any:
    return SimpleNamespace(
        source_id=SOURCE_ID,
        title=TITLE,
        description=PROMOTED_DESCRIPTION,
        legacy_description=LEGACY_DESCRIPTION,
        duration_seconds=30.0,
        media_path="unused.mp4",
    )


def _durable_item(*, description: str = LEGACY_DESCRIPTION) -> dict[str, Any]:
    return {
        "owner_id": -68859909,
        "id": 456239225,
        "type": "short_video",
        "processing": 1,
        "converting": 0,
        "title": "",
        "description": description,
        "duration": 30,
        "can_watch": 0,
    }


def test_durable_verified_clip_ignores_transient_player_and_title_projection() -> None:
    writer = _Writer(_durable_item())

    raw = _assert_native_clip(
        writer,  # type: ignore[arg-type]
        _asset(),
        REMOTE_ID,
        description_mode="legacy_or_promoted",
        durable_verified=True,
    )

    assert raw["owner_id"] == -68859909
    assert raw["id"] == 456239225
    assert raw["type"] == "short_video"


def test_durable_verified_clip_accepts_exact_promoted_binding() -> None:
    writer = _Writer(_durable_item(description=PROMOTED_DESCRIPTION))

    raw = _assert_native_clip(
        writer,  # type: ignore[arg-type]
        _asset(),
        REMOTE_ID,
        description_mode="legacy_or_promoted",
        durable_verified=True,
    )

    assert raw["description"] == PROMOTED_DESCRIPTION


def test_durable_verified_clip_still_requires_exact_legacy_or_promoted_binding() -> None:
    writer = _Writer(
        _durable_item(description=f"manual override still containing https://www.youtube.com/shorts/{SOURCE_ID}")
    )

    with pytest.raises(MiloviFinalizerBlocked, match="neither exact reviewed legacy nor exact promoted"):
        _assert_native_clip(
            writer,  # type: ignore[arg-type]
            _asset(),
            REMOTE_ID,
            description_mode="legacy_or_promoted",
            durable_verified=True,
        )


def test_durable_verified_clip_still_requires_native_type() -> None:
    item = _durable_item()
    item["type"] = "video"
    writer = _Writer(item)

    with pytest.raises(MiloviFinalizerBlocked, match="lost native short_video type"):
        _assert_native_clip(
            writer,  # type: ignore[arg-type]
            _asset(),
            REMOTE_ID,
            description_mode="legacy_or_promoted",
            durable_verified=True,
        )


def test_ensure_promoted_clip_reuses_durable_verified_identity_during_transient_processing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """VERIFIED is a durable barrier: transient player state must not reopen upload readiness."""

    writer = _Writer(_durable_item())
    wall = build_wall_snapshot(
        community_id=68859909,
        published_items=[],
        postponed_items=[],
        published_pages=1,
        postponed_pages=1,
        complete=True,
        captured_at=datetime(2026, 8, 16, 1, 0, tzinfo=UTC),
    )

    def capture_wall_snapshot(*, community_id: int, max_posts_per_surface: int = 10000):
        assert community_id == 68859909
        assert max_posts_per_surface == 10000
        return wall

    writer.capture_wall_snapshot = capture_wall_snapshot  # type: ignore[attr-defined]
    record: dict[str, Any] = {
        "stage": UploadStage.VERIFIED.value,
        "wall_policy": finalize.DEFAULT_UPLOAD_WALL_POLICY.as_dict(),
        "wall_safety": {
            "before_snapshot_sha256": wall.snapshot_sha256,
            "before_captured_at": wall.captured_at,
            "before_published_pages": wall.published_pages,
            "before_postponed_pages": wall.postponed_pages,
            "delta": {"status": "clean"},
        },
        "reservation": {"remote_id": REMOTE_ID},
    }
    item: dict[str, Any] = {"status": "upload_in_progress", "upload_record": record}
    journal: dict[str, Any] = {
        "source_snapshot_id": "issue323-reviewed-snapshot",
        "provider_write_attempted": True,
        "items": {SOURCE_ID: item},
    }

    monkeypatch.setattr(finalize, "ensure_upload_record", lambda current, **_kwargs: (current, False))
    monkeypatch.setattr(finalize, "_save", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        finalize,
        "_supplement_due_prior_wall_readbacks",
        lambda _writer, current, **_kwargs: (current, ()),
    )
    monkeypatch.setattr(
        finalize,
        "_resume_wall_baseline",
        lambda _record, effective, **_kwargs: effective,
    )

    class NoReplayRecoveryWriter:
        def __init__(self, _delegate: Any, **_kwargs: Any) -> None:
            self.last_actual_snapshot_sha256 = None
            self.last_effective_snapshot_sha256 = None
            self.last_historical_snapshot_sha256 = None
            self.last_reversed_surface_ids: tuple[str, ...] = ()
            self.last_exact_read_ids: tuple[str, ...] = ()

        def begin_upload(self, **_kwargs: Any) -> Any:
            raise AssertionError("durable VERIFIED recovery must not reserve another VK object")

        def upload_file(self, *_args: Any, **_kwargs: Any) -> Any:
            raise AssertionError("durable VERIFIED recovery must not retransmit media")

    monkeypatch.setattr(finalize, "_Issue323RecoveryWriter", NoReplayRecoveryWriter)

    remote_id = finalize._ensure_promoted_clip(
        _asset(),
        object(),
        item,
        journal,
        tmp_path / "rollout.json",
        writer,  # type: ignore[arg-type]
        SimpleNamespace(client=object()),  # type: ignore[arg-type]
        60,
    )

    assert remote_id == REMOTE_ID
    assert item["status"] == "clip_verified"
    assert item["clip_remote_id"] == REMOTE_ID
    assert item["clip_origin"] == "resumed_token_short_video_internal_promotion"
    assert writer.read_calls == 1
