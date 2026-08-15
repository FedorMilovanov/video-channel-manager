from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from video_channel_manager.platforms.vk import milovi_issue323_finalize as finalizer
from video_channel_manager.platforms.vk.milovi_rollout_sources import (
    ROLL_OUT_IDS,
    SourceAsset,
    build_description,
    build_wall_message,
)
from video_channel_manager.platforms.vk.upload_lifecycle import UploadRecoveryRequired, UploadStage
from video_channel_manager.platforms.vk.wall_safety import VkWallSnapshot

SOURCE_ID = ROLL_OUT_IDS[8]
REMOTE_ID = "-68859909_456239233"
DUE_PRIOR_WALL_ID = "-68859909_468"


def _asset() -> SourceAsset:
    title = "Milovi source 9"
    return SourceAsset(
        source_id=SOURCE_ID,
        source_url=f"https://www.youtube.com/shorts/{SOURCE_ID}",
        title=title,
        duration_seconds=29,
        media_path=f"Z:/protected/{SOURCE_ID}.mp4",
        media_sha256="0" * 64,
        width=1080,
        height=1920,
        description=build_description(title, SOURCE_ID),
        wall_message=build_wall_message(title, SOURCE_ID),
    )


def _snapshot(second: int) -> VkWallSnapshot:
    return VkWallSnapshot(
        community_id=68859909,
        captured_at=f"2026-08-15T11:00:{second:02d}+00:00",
        complete=True,
        published_pages=1,
        postponed_pages=1,
        posts=(),
    )


class _Writer:
    def __init__(self, current: VkWallSnapshot) -> None:
        self.current = current
        self.capture_count = 0

    def capture_wall_snapshot(self, *, community_id: int, max_posts_per_surface: int = 10000) -> VkWallSnapshot:
        assert community_id == 68859909
        assert max_posts_per_surface == 10000
        self.capture_count += 1
        return self.current


def _run_recovery_case(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    exact_read_ids: tuple[str, ...],
) -> tuple[dict[str, Any], VkWallSnapshot, VkWallSnapshot, VkWallSnapshot, list[str]]:
    asset = _asset()
    current = _snapshot(1)
    effective = _snapshot(2) if exact_read_ids else current
    historical = _snapshot(3)
    writer = _Writer(current)
    upload_writer = object()
    record: dict[str, Any] = {
        "stage": UploadStage.VERIFIED.value,
        "reservation": {"remote_id": REMOTE_ID},
        "wall_safety": {"before_snapshot_sha256": historical.snapshot_sha256},
    }
    item: dict[str, Any] = {"status": "upload_in_progress", "upload_record": record}
    journal: dict[str, Any] = {
        "source_snapshot_id": "issue-323-reviewed-source-snapshot",
        "items": {SOURCE_ID: item},
    }
    calls: list[str] = []

    def fake_ensure_upload_record(raw: dict[str, Any] | None, **_kwargs: Any) -> tuple[dict[str, Any], bool]:
        assert raw is not None
        return raw, False

    def fake_supplement(
        observed_writer: Any,
        observed_current: VkWallSnapshot,
        *,
        journal: dict[str, Any],
        source_id: str,
    ) -> tuple[VkWallSnapshot, tuple[str, ...]]:
        calls.append("supplement")
        assert observed_writer is writer
        assert observed_current is current
        assert source_id == SOURCE_ID
        assert journal["items"][SOURCE_ID] is item
        return effective, exact_read_ids

    def fake_resume(
        observed_record: dict[str, Any],
        observed_current: VkWallSnapshot,
        *,
        journal: dict[str, Any] | None = None,
        successor_resolution_proven: bool = False,
        now_epoch: int | None = None,
    ) -> VkWallSnapshot:
        calls.append("resume")
        assert observed_record is item["upload_record"]
        assert observed_current is effective
        assert journal is not None
        assert journal["items"][SOURCE_ID] is item
        assert successor_resolution_proven is bool(exact_read_ids)
        assert now_epoch is None
        return historical

    def fake_execute(operation_record: dict[str, Any], **kwargs: Any) -> None:
        calls.append("execute")
        recovery_writer = kwargs["writer"]
        assert isinstance(recovery_writer, finalizer._Issue323RecoveryWriter)
        assert kwargs["wall_before_snapshot"] is historical
        assert kwargs["media_path"] is None
        assert kwargs["media_artifact"] is None
        assert operation_record is item["upload_record"]

        with pytest.raises(UploadRecoveryRequired, match="forbids a second upload reservation"):
            recovery_writer.begin_upload(
                community_id=68859909,
                title=asset.title,
                description=asset.description,
                wall_policy=object(),
            )
        with pytest.raises(UploadRecoveryRequired, match="forbids binary retransmission"):
            recovery_writer.upload_file(object(), Path(asset.media_path))

    monkeypatch.setattr(finalizer, "ensure_upload_record", fake_ensure_upload_record)
    monkeypatch.setattr(finalizer, "_has_provider_effect", lambda _record: True)
    monkeypatch.setattr(finalizer, "_supplement_due_prior_wall_readbacks", fake_supplement)
    monkeypatch.setattr(finalizer, "_resume_wall_baseline", fake_resume)
    monkeypatch.setattr(finalizer, "execute_upload_operation", fake_execute)
    monkeypatch.setattr(finalizer, "_assert_native_clip", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(finalizer, "_upload_remote_id", lambda _record: REMOTE_ID)
    monkeypatch.setattr(finalizer, "_save", lambda *_args, **_kwargs: None)

    result = finalizer._ensure_promoted_clip(
        asset,
        object(),
        item,
        journal,
        tmp_path / "journal.json",
        writer,  # type: ignore[arg-type]
        upload_writer,  # type: ignore[arg-type]
        600,
    )

    assert result == REMOTE_ID
    assert item["clip_remote_id"] == REMOTE_ID
    assert item["clip_origin"] == "resumed_token_short_video_internal_promotion"
    assert writer.capture_count == 1
    return item, current, effective, historical, calls


def test_finalizer_proves_due_successor_before_historical_recovery_without_reupload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    item, current, effective, historical, calls = _run_recovery_case(
        monkeypatch,
        tmp_path,
        exact_read_ids=(DUE_PRIOR_WALL_ID,),
    )

    assert calls == ["supplement", "resume", "execute"]
    evidence = item["upload_record"]["issue323_recovery_wall_view"]
    assert evidence["baseline_actual_snapshot_sha256"] == current.snapshot_sha256
    assert evidence["baseline_effective_snapshot_sha256"] == effective.snapshot_sha256
    assert evidence["historical_before_snapshot_sha256"] == historical.snapshot_sha256
    assert evidence["baseline_exact_read_ids"] == [DUE_PRIOR_WALL_ID]
    assert evidence["reservation_replay_authorized"] is False
    assert evidence["binary_retransmission_authorized"] is False


def test_finalizer_does_not_claim_successor_proof_without_exact_read(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    item, current, effective, historical, calls = _run_recovery_case(
        monkeypatch,
        tmp_path,
        exact_read_ids=(),
    )

    assert effective is current
    assert calls == ["supplement", "resume", "execute"]
    evidence = item["upload_record"]["issue323_recovery_wall_view"]
    assert evidence["baseline_effective_snapshot_sha256"] == current.snapshot_sha256
    assert evidence["historical_before_snapshot_sha256"] == historical.snapshot_sha256
    assert evidence["baseline_exact_read_ids"] == []
