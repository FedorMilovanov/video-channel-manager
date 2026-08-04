from __future__ import annotations

import pytest

from video_channel_manager.platforms.vk.upload_lifecycle import (
    UploadRecoveryRequired,
    UploadStage,
    VkUploadReadiness,
    create_upload_record,
    ensure_upload_record,
)
from video_channel_manager.platforms.vk.wall_safety import DEFAULT_UPLOAD_WALL_POLICY


def _readiness() -> VkUploadReadiness:
    return VkUploadReadiness(
        expected_title="Берёза ⚡",
        minimum_duration_seconds=115,
        allowed_types=("video",),
        require_playable=True,
    )


def _record() -> dict[str, object]:
    return create_upload_record(
        source_snapshot_id="snapshot-1",
        community_id=235216998,
        source_video_id="yt-1",
        source_title="Берёза",
        source_duration_seconds=120,
        published_title="Берёза ⚡",
        published_description="Описание",
        readiness=_readiness(),
    )


def _ensure(record: dict[str, object]) -> tuple[dict[str, object], bool]:
    return ensure_upload_record(
        record,
        source_snapshot_id="snapshot-1",
        community_id=235216998,
        source_video_id="yt-1",
        source_title="Берёза",
        source_duration_seconds=120,
        published_title="Берёза ⚡",
        published_description="Описание",
        readiness=_readiness(),
    )


def test_pre_dispatch_record_can_bind_missing_wall_policy_and_rehash_identity() -> None:
    record = _record()
    old_operation_id = record["operation_id"]
    record.pop("wall_policy")
    record["operation_id"] = "sha256:legacy-without-wall-policy"
    transitions = record["transitions"]
    assert isinstance(transitions, list)
    transitions[0]["evidence"]["operation_id"] = "sha256:legacy-without-wall-policy"

    migrated, changed = _ensure(record)

    assert changed is True
    assert migrated["wall_policy"] == DEFAULT_UPLOAD_WALL_POLICY.as_dict()
    assert migrated["operation_id"] == old_operation_id
    migrated_transitions = migrated["transitions"]
    assert isinstance(migrated_transitions, list)
    assert migrated_transitions[0]["evidence"]["operation_id"] == old_operation_id


def test_provider_dispatched_record_without_wall_policy_fails_closed() -> None:
    record = _record()
    record.pop("wall_policy")
    record["stage"] = UploadStage.PROCESSING.value
    record["reservation_dispatch_started_at"] = "2026-08-04T02:00:00+00:00"
    record["reservation"] = {
        "owner_id": -235216998,
        "video_id": 501,
        "remote_id": "-235216998_501",
        "upload_url": None,
        "upload_url_sha256": None,
        "reservation_response": None,
    }

    with pytest.raises(UploadRecoveryRequired, match="cannot be migrated automatically"):
        _ensure(record)
