from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from video_channel_manager.platforms.vk.milovi_token_clip_rollout import (
    MiloviTokenRolloutBlocked,
    _ensure_wall,
    _read_wall_attachment,
)
from video_channel_manager.platforms.vk.wall_safety import build_wall_snapshot

CLIP_ID = 456239999
CLIP_REMOTE_ID = f"-68859909_{CLIP_ID}"
WALL_ID = 1200
WALL_REMOTE_ID = f"-68859909_{WALL_ID}"


def _post(*, publish_date: int, extra_non_video: bool = False, second_video: bool = False) -> dict[str, Any]:
    attachments: list[dict[str, Any]] = [
        {
            "type": "video",
            "video": {"owner_id": -68859909, "id": CLIP_ID, "type": "short_video"},
        }
    ]
    if extra_non_video:
        attachments.append({"type": "link", "link": {"url": "https://milovicake.ru/"}})
    if second_video:
        attachments.append(
            {
                "type": "video",
                "video": {"owner_id": -68859909, "id": CLIP_ID + 1, "type": "short_video"},
            }
        )
    return {
        "owner_id": -68859909,
        "id": WALL_ID,
        "date": publish_date,
        "text": "legacy wall",
        "attachments": attachments,
    }


class _Writer:
    def __init__(
        self,
        *,
        publish_date: int,
        published: bool,
        extra_non_video: bool = False,
        second_video: bool = False,
    ) -> None:
        post = _post(
            publish_date=publish_date,
            extra_non_video=extra_non_video,
            second_video=second_video,
        )
        self.snapshot = build_wall_snapshot(
            community_id=68859909,
            published_items=[post] if published else [],
            postponed_items=[] if published else [post],
            published_pages=1,
            postponed_pages=1,
            complete=True,
            captured_at=datetime(2026, 8, 15, 0, 0, tzinfo=UTC),
        )
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def capture_wall_snapshot(self, *, community_id: int, max_posts_per_surface: int = 10000):
        assert community_id == 68859909
        assert max_posts_per_surface == 10000
        return self.snapshot

    def _call(self, method: str, *, params: dict[str, Any]) -> object:
        self.calls.append((method, dict(params)))
        raise AssertionError("read-only wall recovery must not mutate provider state")


def test_unresolved_wall_accepts_published_incarnation_after_frozen_slot() -> None:
    publish_date = 1_700_000_000
    writer = _Writer(publish_date=publish_date, published=True)
    publish_at = datetime.fromtimestamp(publish_date, tz=UTC)

    assert (
        _read_wall_attachment(
            writer,  # type: ignore[arg-type]
            CLIP_REMOTE_ID,
            publish_at,
            now_epoch=publish_date + 3600,
        )
        == WALL_REMOTE_ID
    )
    assert writer.calls == []


def test_unresolved_wall_rejects_publication_before_frozen_slot() -> None:
    publish_date = 1_893_456_000
    writer = _Writer(publish_date=publish_date, published=True)
    publish_at = datetime.fromtimestamp(publish_date, tz=UTC)

    with pytest.raises(MiloviTokenRolloutBlocked, match="published before its frozen slot"):
        _read_wall_attachment(
            writer,  # type: ignore[arg-type]
            CLIP_REMOTE_ID,
            publish_at,
            now_epoch=publish_date - 3600,
        )


def test_unresolved_wall_tolerates_non_video_projection_but_requires_one_exact_video() -> None:
    publish_date = 1_700_000_000
    publish_at = datetime.fromtimestamp(publish_date, tz=UTC)
    projected = _Writer(publish_date=publish_date, published=True, extra_non_video=True)

    assert (
        _read_wall_attachment(
            projected,  # type: ignore[arg-type]
            CLIP_REMOTE_ID,
            publish_at,
            now_epoch=publish_date + 1,
        )
        == WALL_REMOTE_ID
    )

    ambiguous = _Writer(publish_date=publish_date, published=True, second_video=True)
    with pytest.raises(MiloviTokenRolloutBlocked, match="exactly one exact video attachment"):
        _read_wall_attachment(
            ambiguous,  # type: ignore[arg-type]
            CLIP_REMOTE_ID,
            publish_at,
            now_epoch=publish_date + 1,
        )


def test_wall_may_exist_restart_adopts_due_published_effect_without_replay(tmp_path: Path) -> None:
    publish_date = 1_700_000_000
    publish_at = datetime.fromtimestamp(publish_date, tz=UTC)
    writer = _Writer(publish_date=publish_date, published=True)
    source_id = "1_SuzeQD_1g"
    asset = SimpleNamespace(source_id=source_id)
    item: dict[str, Any] = {"status": "wall_may_exist", "clip_remote_id": CLIP_REMOTE_ID}
    journal: dict[str, Any] = {"items": {source_id: item}}
    journal_path = tmp_path / "journal.json"

    remote_id = _ensure_wall(
        asset,  # type: ignore[arg-type]
        CLIP_REMOTE_ID,
        publish_at,
        item,
        journal,
        journal_path,
        writer,  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
    )

    assert remote_id == WALL_REMOTE_ID
    assert writer.calls == []
    assert item["status"] == "wall_verified"
    assert item["wall_remote_id"] == WALL_REMOTE_ID
    assert item["publish_date"] == publish_date
    persisted = json.loads(journal_path.read_text(encoding="utf-8"))
    assert persisted["items"][source_id]["wall_remote_id"] == WALL_REMOTE_ID
