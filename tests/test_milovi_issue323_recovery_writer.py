from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

import video_channel_manager.platforms.vk.milovi_issue323_live_resume as resume
from video_channel_manager.platforms.vk.upload_lifecycle import UploadRecoveryRequired, VkUploadReadiness
from video_channel_manager.platforms.vk.wall_safety import build_wall_snapshot

PUBLISH_DATE = 1786723200


def _wall_item() -> dict[str, Any]:
    return {
        "owner_id": -68859909,
        "id": 468,
        "date": PUBLISH_DATE,
        "text": "legacy",
        "attachments": [
            {
                "type": "video",
                "video": {"owner_id": -68859909, "id": 456239225, "type": "short_video"},
            }
        ],
    }


def _historical():
    return build_wall_snapshot(
        community_id=68859909,
        published_items=[],
        postponed_items=[_wall_item()],
        published_pages=1,
        postponed_pages=1,
        complete=True,
        captured_at=datetime(2026, 8, 13, 18, 0, tzinfo=UTC),
    )


def _current():
    return build_wall_snapshot(
        community_id=68859909,
        published_items=[_wall_item()],
        postponed_items=[],
        published_pages=1,
        postponed_pages=1,
        complete=True,
        captured_at=datetime(2026, 8, 14, 18, 0, tzinfo=UTC),
    )


def _wall_safety() -> dict[str, Any]:
    before = _historical()
    return {
        "before_snapshot_sha256": before.snapshot_sha256,
        "before_captured_at": before.captured_at,
        "before_published_pages": before.published_pages,
        "before_postponed_pages": before.postponed_pages,
    }


def _journal() -> dict[str, Any]:
    return {
        "items": {
            resume.ROLL_OUT_IDS[0]: {
                "status": "wall_verified",
                "clip_remote_id": "-68859909_456239225",
                "wall_remote_id": "-68859909_468",
                "publish_date": PUBLISH_DATE,
            },
            **{source_id: {"status": "pending"} for source_id in resume.ROLL_OUT_IDS[1:]},
        }
    }


class _Delegate:
    def read_video(self, *, owner_id: int, video_id: int) -> dict[str, Any] | None:
        return {"owner_id": owner_id, "id": video_id}

    def wait_until_available(
        self,
        ticket: Any,
        *,
        readiness: VkUploadReadiness,
        timeout_seconds: int,
        on_observation: Any = None,
    ) -> dict[str, Any]:
        return {"owner_id": ticket.owner_id, "id": ticket.video_id}

    def capture_wall_snapshot(self, *, community_id: int, max_posts_per_surface: int = 10000):
        assert community_id == 68859909
        assert max_posts_per_surface == 10000
        return _current()


def test_recovery_writer_has_no_reservation_or_binary_replay_capability() -> None:
    writer = resume._Issue323RecoveryWriter(
        _Delegate(),  # type: ignore[arg-type]
        wall_safety=_wall_safety(),
        journal=_journal(),
        source_id=resume.ROLL_OUT_IDS[1],
    )

    with pytest.raises(UploadRecoveryRequired, match="second upload reservation"):
        writer.begin_upload(community_id=68859909, title="x", description="y", wall_policy=object())
    with pytest.raises(UploadRecoveryRequired, match="binary retransmission"):
        writer.upload_file(object(), Path("clip.mp4"))


def test_recovery_writer_postflight_uses_same_unique_historical_wall_view(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(resume.time, "time", lambda: PUBLISH_DATE + 3600)
    writer = resume._Issue323RecoveryWriter(
        _Delegate(),  # type: ignore[arg-type]
        wall_safety=_wall_safety(),
        journal=_journal(),
        source_id=resume.ROLL_OUT_IDS[1],
    )

    observed = writer.capture_wall_snapshot(community_id=68859909)

    assert observed.snapshot_sha256 == _historical().snapshot_sha256
    assert writer.last_actual_snapshot_sha256 == _current().snapshot_sha256
    assert writer.last_historical_snapshot_sha256 == _historical().snapshot_sha256
    assert writer.last_reversed_surface_ids == ("-68859909_468",)
