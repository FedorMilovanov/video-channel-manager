from __future__ import annotations

import inspect
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

import video_channel_manager.platforms.vk.milovi_issue323_finalize as finalizer
import video_channel_manager.platforms.vk.milovi_issue323_live_resume as resume
from video_channel_manager.platforms.vk.upload_lifecycle import UploadRecoveryRequired
from video_channel_manager.platforms.vk.wall_safety import build_wall_snapshot


class _ClipReader:
    def __init__(self, video: dict[str, Any], post: dict[str, Any] | None = None) -> None:
        self.video = video
        self.post = post

    def read_video(self, *, owner_id: int, video_id: int) -> dict[str, Any] | None:
        assert owner_id == -68859909
        assert video_id == 456239232
        return dict(self.video)

    def read_post(self, *, community_id: int, post_id: int) -> dict[str, Any] | None:
        assert community_id == 68859909
        assert post_id == 475
        return dict(self.post) if self.post is not None else None


def _protected_projection() -> dict[str, Any]:
    return {
        "owner_id": -68859909,
        "id": 456239232,
        "processing": 1,
        "title": "",
        "type": "short_video",
        "can_watch": 0,
    }


def test_preservation_only_check_does_not_require_clip_readiness() -> None:
    raw = _protected_projection()
    writer = _ClipReader(raw)
    asset = SimpleNamespace(source_id="o1WXIMupuws", description="promoted")

    observed = finalizer._assert_native_clip(
        writer,  # type: ignore[arg-type]
        asset,  # type: ignore[arg-type]
        finalizer.ANOMALY_CLIP_REMOTE_ID,
        description_mode="legacy_or_promoted",
        preservation_only=True,
    )

    assert observed == raw


def test_default_native_clip_check_remains_strict(monkeypatch: pytest.MonkeyPatch) -> None:
    writer = _ClipReader(_protected_projection())
    asset = SimpleNamespace(source_id="o1WXIMupuws", description="promoted")
    monkeypatch.setattr(finalizer, "clip_readiness", lambda _asset: object())
    monkeypatch.setattr(
        finalizer,
        "_native_clip_assessment",
        lambda *args, **kwargs: SimpleNamespace(ready=False, reasons=("not_playable",)),
    )

    with pytest.raises(finalizer.MiloviFinalizerBlocked, match="not a verified native short_video"):
        finalizer._assert_native_clip(
            writer,  # type: ignore[arg-type]
            asset,  # type: ignore[arg-type]
            finalizer.ANOMALY_CLIP_REMOTE_ID,
            description_mode="legacy_or_promoted",
        )


def test_phase2_accepts_exact_tombstone_without_delete(tmp_path: Any) -> None:
    writer = _ClipReader(
        _protected_projection(),
        {"owner_id": -68859909, "id": 475, "is_deleted": True},
    )
    state: dict[str, Any] = {"cleanup_475": {"status": "verified_absent"}}
    asset = SimpleNamespace(source_id="o1WXIMupuws", description="promoted")

    finalizer._cleanup_anomaly_475(
        writer=writer,  # type: ignore[arg-type]
        promoted_asset=asset,  # type: ignore[arg-type]
        finalizer=state,
        finalizer_path=tmp_path / "finalizer.json",
    )

    cleanup = state["cleanup_475"]
    assert cleanup["status"] == "verified_absent"
    assert cleanup["phase2_delete_authority"] is False
    assert cleanup["phase2_absence_evidence"] == "wall.getById:is_deleted_true"
    assert cleanup["protected_clip_preserved"] is True


def test_phase2_rejects_live_wall475_and_has_no_delete_path(tmp_path: Any) -> None:
    writer = _ClipReader(
        _protected_projection(),
        {"owner_id": -68859909, "id": 475, "is_deleted": False},
    )
    state: dict[str, Any] = {"cleanup_475": {"status": "verified_absent"}}
    asset = SimpleNamespace(source_id="o1WXIMupuws", description="promoted")

    with pytest.raises(finalizer.MiloviFinalizerBlocked, match="phase 2 has no delete authority"):
        finalizer._cleanup_anomaly_475(
            writer=writer,  # type: ignore[arg-type]
            promoted_asset=asset,  # type: ignore[arg-type]
            finalizer=state,
            finalizer_path=tmp_path / "finalizer.json",
        )

    assert '"wall.delete"' not in inspect.getsource(finalizer)


def _wall_safety_with_delta(*, created: list[str]) -> dict[str, Any]:
    historical = build_wall_snapshot(
        community_id=68859909,
        published_items=[],
        postponed_items=[],
        published_pages=1,
        postponed_pages=1,
        complete=True,
        captured_at=datetime(2026, 8, 14, 9, 0, tzinfo=UTC),
    )
    return {
        "before_snapshot_sha256": historical.snapshot_sha256,
        "before_captured_at": historical.captured_at,
        "before_published_pages": historical.published_pages,
        "before_postponed_pages": historical.postponed_pages,
        "after_snapshot_sha256": "sha256:historical-anomaly-postflight",
        "delta": {
            "status": "changed",
            "created": created,
            "removed": [],
            "changed": [],
            "before_sha256": historical.snapshot_sha256,
            "after_sha256": "sha256:historical-anomaly-postflight",
            "reasons": [],
        },
    }


def test_eighth_recovery_accepts_only_exact_historical_wall475_delta() -> None:
    wall_safety = _wall_safety_with_delta(created=[resume.ISSUE323_RECONCILED_WALL_VIEW])
    record = {"source_video_id": resume.ISSUE323_EIGHTH_SOURCE_ID}

    resume._assert_issue323_eighth_wall_history(record, wall_safety)


@pytest.mark.parametrize(
    "created",
    [
        [],
        ["published:-68859909_999"],
        [resume.ISSUE323_RECONCILED_WALL_VIEW, "published:-68859909_999"],
    ],
)
def test_eighth_recovery_rejects_any_other_historical_wall_delta(created: list[str]) -> None:
    wall_safety = _wall_safety_with_delta(created=created)
    record = {"source_video_id": resume.ISSUE323_EIGHTH_SOURCE_ID}

    with pytest.raises(UploadRecoveryRequired, match="single authorized wall-475 side effect"):
        resume._assert_issue323_eighth_wall_history(record, wall_safety)


def test_eighth_resume_requires_current_wall_to_return_to_preupload_baseline() -> None:
    wall_safety = _wall_safety_with_delta(created=[resume.ISSUE323_RECONCILED_WALL_VIEW])
    record = {
        "source_video_id": resume.ISSUE323_EIGHTH_SOURCE_ID,
        "wall_safety": wall_safety,
    }
    current = build_wall_snapshot(
        community_id=68859909,
        published_items=[],
        postponed_items=[],
        published_pages=1,
        postponed_pages=1,
        complete=True,
        captured_at=datetime(2026, 8, 14, 12, 0, tzinfo=UTC),
    )

    normalized = resume._resume_wall_baseline(record, current)

    assert normalized.snapshot_sha256 == wall_safety["before_snapshot_sha256"]
    assert normalized.captured_at == wall_safety["before_captured_at"]


def test_eighth_resume_rejects_current_wall_with_any_extra_post() -> None:
    wall_safety = _wall_safety_with_delta(created=[resume.ISSUE323_RECONCILED_WALL_VIEW])
    record = {
        "source_video_id": resume.ISSUE323_EIGHTH_SOURCE_ID,
        "wall_safety": wall_safety,
    }
    current = build_wall_snapshot(
        community_id=68859909,
        published_items=[
            {
                "owner_id": -68859909,
                "id": 999,
                "date": 1786700000,
                "text": "unexpected",
                "attachments": [],
            }
        ],
        postponed_items=[],
        published_pages=1,
        postponed_pages=1,
        complete=True,
        captured_at=datetime(2026, 8, 14, 12, 0, tzinfo=UTC),
    )

    with pytest.raises(resume.MiloviTokenRolloutBlocked, match="pre-upload baseline"):
        resume._resume_wall_baseline(record, current)
