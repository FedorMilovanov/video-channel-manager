from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

import video_channel_manager.platforms.vk.milovi_issue323_upload_wall_reconcile as reconcile
from video_channel_manager.platforms.vk.milovi_rollout_sources import ROLL_OUT_IDS
from video_channel_manager.platforms.vk.upload_lifecycle import UploadRecoveryRequired, UploadStage
from video_channel_manager.platforms.vk.wall_safety import build_wall_snapshot

SOURCE9 = ROLL_OUT_IDS[8]
SOURCE9_CLIP_ID = 456239233
AUTO_POST_ID = 478
AUTO_POST_DATE = 1786735800


def _current_without_auto():
    return build_wall_snapshot(
        community_id=68859909,
        published_items=[],
        postponed_items=[],
        published_pages=1,
        postponed_pages=1,
        complete=True,
        captured_at=datetime.fromtimestamp(AUTO_POST_DATE + 30, UTC),
    )


def _record() -> dict[str, Any]:
    before_captured_at = datetime.fromtimestamp(AUTO_POST_DATE - 30, UTC).isoformat()
    after_captured_at = datetime.fromtimestamp(AUTO_POST_DATE + 30, UTC).isoformat()
    return {
        "source_video_id": SOURCE9,
        "stage": UploadStage.UNKNOWN_REQUIRES_RECONCILIATION.value,
        "reservation": {
            "owner_id": -68859909,
            "video_id": SOURCE9_CLIP_ID,
            "remote_id": f"-68859909_{SOURCE9_CLIP_ID}",
            "upload_url": "journal-only",
        },
        "wall_safety": {
            "before_snapshot_sha256": "sha256:before",
            "before_captured_at": before_captured_at,
            "after_snapshot_sha256": "sha256:after",
            "after_captured_at": after_captured_at,
            "delta": {
                "status": "changed",
                "created": [f"published:-68859909_{AUTO_POST_ID}"],
                "removed": [],
                "changed": [],
                "before_sha256": "sha256:before",
                "after_sha256": "sha256:after",
                "reasons": [],
            },
        },
    }


def _auto_post(*, video_id: int = SOURCE9_CLIP_ID) -> dict[str, Any]:
    return {
        "owner_id": -68859909,
        "id": AUTO_POST_ID,
        "date": AUTO_POST_DATE,
        "text": "",
        "attachments": [
            {
                "type": "video",
                "video": {
                    "owner_id": -68859909,
                    "id": video_id,
                    "type": "short_video",
                },
            }
        ],
    }


class _ExactOnlyWriter:
    def __init__(self, *, video_id: int = SOURCE9_CLIP_ID) -> None:
        self.video_id = video_id
        self.deleted = False
        self.delete_calls: list[tuple[str, dict[str, Any]]] = []

    def read_post(self, *, community_id: int, post_id: int) -> dict[str, Any] | None:
        assert community_id == 68859909
        assert post_id == AUTO_POST_ID
        if self.deleted:
            return {
                "owner_id": -68859909,
                "id": AUTO_POST_ID,
                "date": AUTO_POST_DATE,
                "is_deleted": True,
            }
        return _auto_post(video_id=self.video_id)

    def capture_wall_snapshot(self, *, community_id: int, max_posts_per_surface: int = 10000):
        assert community_id == 68859909
        assert max_posts_per_surface == 10000
        return _current_without_auto()

    def _call(self, method: str, *, params: dict[str, Any]):
        assert method == "wall.delete"
        assert params == {"owner_id": -68859909, "post_id": AUTO_POST_ID}
        self.delete_calls.append((method, dict(params)))
        self.deleted = True
        return 1


def _journal() -> dict[str, Any]:
    return {"items": {source_id: {"status": "pending"} for source_id in ROLL_OUT_IDS}}


def _install_baseline_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    baseline = SimpleNamespace(snapshot_sha256="sha256:before")
    monkeypatch.setattr(
        reconcile,
        "_prove_historical_baseline",
        lambda **_kwargs: (baseline, ()),
    )
    monkeypatch.setattr(reconcile, "_prove_target", lambda _client: None)


def test_exact_live_created_post_is_reconciled_even_when_aggregate_omits_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_baseline_stub(monkeypatch)
    writer = _ExactOnlyWriter()
    record = _record()
    persisted: list[str] = []

    current, baseline = reconcile.reconcile_issue323_upload_wall_effect(
        record=record,
        current_wall=_current_without_auto(),
        journal=_journal(),
        writer=writer,  # type: ignore[arg-type]
        client=object(),
        source_id=SOURCE9,
        persist=lambda: persisted.append(str(record["issue323_upload_wall_reconcile"]["status"])),
    )

    assert writer.delete_calls == [("wall.delete", {"owner_id": -68859909, "post_id": AUTO_POST_ID})]
    assert writer.deleted is True
    assert current.snapshot_sha256 == _current_without_auto().snapshot_sha256
    assert baseline.snapshot_sha256 == "sha256:before"
    assert record["issue323_upload_wall_reconcile"]["status"] == "verified_absent"
    assert "delete_dispatch_started" in persisted
    assert persisted[-1] == "verified_absent"


def test_exact_live_aggregate_omission_with_wrong_clip_still_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_baseline_stub(monkeypatch)
    writer = _ExactOnlyWriter(video_id=999)
    record = _record()

    with pytest.raises(UploadRecoveryRequired, match="changed Clip binding"):
        reconcile.reconcile_issue323_upload_wall_effect(
            record=record,
            current_wall=_current_without_auto(),
            journal=_journal(),
            writer=writer,  # type: ignore[arg-type]
            client=object(),
            source_id=SOURCE9,
            persist=lambda: None,
        )

    assert writer.delete_calls == []
    assert writer.deleted is False
