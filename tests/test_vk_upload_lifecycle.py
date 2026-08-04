from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from video_channel_manager.platforms.vk.upload_lifecycle import (
    StoredUploadTicket,
    UploadRecoveryRequired,
    UploadRejected,
    UploadStage,
    VkUploadReadiness,
    assess_vk_upload_readiness,
    create_upload_record,
    ensure_upload_record,
    execute_upload_operation,
)
from video_channel_manager.platforms.vk.wall_safety import (
    DEFAULT_UPLOAD_WALL_POLICY,
    VkUploadWallPolicy,
)


class CrashAt(RuntimeError):
    pass


class FakeWriter:
    def __init__(self) -> None:
        self.begin_calls = 0
        self.upload_calls = 0
        self.read_calls = 0
        self.wait_calls = 0
        self.remote_item: dict[str, Any] | None = None
        self.upload_error: Exception | None = None
        self.begin_error: Exception | None = None
        self.preserve_remote_item = False
        self.observed_wall_policy: VkUploadWallPolicy | None = None

    def begin_upload(
        self,
        *,
        community_id: int,
        title: str,
        description: str,
        wall_policy: VkUploadWallPolicy,
    ) -> StoredUploadTicket:
        self.begin_calls += 1
        self.observed_wall_policy = wall_policy
        if self.begin_error is not None:
            raise self.begin_error
        return StoredUploadTicket(
            owner_id=-community_id,
            video_id=501,
            upload_url="https://upload.example/secret-ticket",
            reservation_response={
                "owner_id": -community_id,
                "video_id": 501,
                "upload_url": "https://upload.example/secret-ticket",
            },
        )

    def upload_file(self, ticket: StoredUploadTicket, path: Path) -> dict[str, Any]:
        self.upload_calls += 1
        if self.upload_error is not None:
            raise self.upload_error
        if not self.preserve_remote_item:
            self.remote_item = ready_item(ticket.owner_id, ticket.video_id)
        return {"video_id": str(ticket.video_id), "size": path.stat().st_size}

    def read_video(self, *, owner_id: int, video_id: int) -> dict[str, Any] | None:
        self.read_calls += 1
        return self.remote_item

    def wait_until_available(
        self,
        ticket: StoredUploadTicket,
        *,
        readiness: VkUploadReadiness,
        timeout_seconds: int,
        on_observation: Callable[[dict[str, Any] | None, object | None], None] | None = None,
    ) -> dict[str, Any]:
        self.wait_calls += 1
        item = self.remote_item
        if on_observation is not None:
            assessment = (
                assess_vk_upload_readiness(
                    item,
                    expected_owner_id=ticket.owner_id,
                    expected_video_id=ticket.video_id,
                    readiness=readiness,
                )
                if item is not None
                else None
            )
            on_observation(item, assessment)
        if item is None:
            raise RuntimeError(f"not visible within {timeout_seconds}")
        assessment = assess_vk_upload_readiness(
            item,
            expected_owner_id=ticket.owner_id,
            expected_video_id=ticket.video_id,
            readiness=readiness,
        )
        if not assessment.ready:
            raise RuntimeError(f"not ready within {timeout_seconds}: {assessment.reasons}")
        return item


class RetryableReservationError(RuntimeError):
    retryable = True


def ready_item(owner_id: int = -235216998, video_id: int = 501) -> dict[str, Any]:
    return {
        "owner_id": owner_id,
        "id": video_id,
        "title": "Берёза ⚡",
        "duration": 119,
        "type": "video",
        "processing": 0,
        "converting": 0,
        "can_watch": 1,
        "player": "https://vk.example/player",
    }


def readiness() -> VkUploadReadiness:
    return VkUploadReadiness(
        expected_title="Берёза ⚡",
        minimum_duration_seconds=115,
        allowed_types=("video",),
        require_playable=True,
    )


def new_record() -> dict[str, Any]:
    return create_upload_record(
        source_snapshot_id="snapshot-1",
        community_id=235216998,
        source_video_id="yt-1",
        source_title="Берёза",
        source_duration_seconds=120,
        published_title="Берёза ⚡",
        published_description="Описание",
        readiness=readiness(),
    )


def run(
    record: dict[str, Any],
    writer: FakeWriter,
    media: Path | None,
    *,
    crash_boundary: str | None = None,
) -> int:
    persists = 0

    def persist() -> None:
        nonlocal persists
        persists += 1

    def fault(boundary: str) -> None:
        if boundary == crash_boundary:
            raise CrashAt(boundary)

    execute_upload_operation(
        record,
        writer=writer,
        community_id=235216998,
        title="Берёза ⚡",
        description="Описание",
        media_path=media,
        readiness=readiness(),
        processing_timeout=60,
        persist=persist,
        fault_hook=fault,
    )
    return persists


def test_readiness_requires_identity_title_duration_type_and_playability() -> None:
    item = ready_item()
    assert assess_vk_upload_readiness(
        item,
        expected_owner_id=-235216998,
        expected_video_id=501,
        readiness=readiness(),
    ).ready

    broken = dict(item)
    broken.update(
        {
            "id": 999,
            "title": "Другое",
            "duration": 0,
            "type": "short_video",
            "can_watch": 0,
            "player": "",
        }
    )
    assessment = assess_vk_upload_readiness(
        broken,
        expected_owner_id=-235216998,
        expected_video_id=501,
        readiness=readiness(),
    )
    assert assessment.ready is False
    assert set(assessment.reasons) == {
        "identity_mismatch",
        "title_mismatch",
        "duration_below_minimum",
        "unexpected_type",
        "not_playable",
    }


def test_new_upload_record_binds_versioned_wall_policy_into_operation_identity() -> None:
    record = new_record()
    policy = record["wall_policy"]

    assert policy == DEFAULT_UPLOAD_WALL_POLICY.as_dict()
    assert policy["policy_sha256"].startswith("sha256:")
    assert record["transitions"][0]["evidence"]["operation_id"] == record["operation_id"]

    changed_policy_record = create_upload_record(
        source_snapshot_id="snapshot-1",
        community_id=235216998,
        source_video_id="yt-1",
        source_title="Берёза",
        source_duration_seconds=120,
        published_title="Берёза ⚡",
        published_description="Описание",
        readiness=readiness(),
        wall_policy=VkUploadWallPolicy(),
    )
    assert changed_policy_record["operation_id"] == record["operation_id"]


def test_existing_schema_record_without_wall_policy_migrates_to_safe_default() -> None:
    record = new_record()
    record.pop("wall_policy")

    migrated, changed = ensure_upload_record(
        record,
        source_snapshot_id="snapshot-1",
        community_id=235216998,
        source_video_id="yt-1",
        source_title="Берёза",
        source_duration_seconds=120,
        published_title="Берёза ⚡",
        published_description="Описание",
        readiness=readiness(),
    )

    assert changed is True
    assert migrated["wall_policy"] == DEFAULT_UPLOAD_WALL_POLICY.as_dict()


def test_tampered_wall_policy_blocks_before_media_or_provider_dispatch(tmp_path: Path) -> None:
    media = tmp_path / "yt-1.mp4"
    media.write_bytes(b"video")
    record = new_record()
    tampered = deepcopy(record["wall_policy"])
    tampered["wall_mutation_authorized"] = True
    record["wall_policy"] = tampered
    writer = FakeWriter()

    with pytest.raises(UploadRejected, match="wall policy is invalid"):
        run(record, writer, media)

    assert record["stage"] == UploadStage.PLANNED.value
    assert record["media"] is None
    assert writer.begin_calls == 0
    assert writer.upload_calls == 0


def test_happy_path_persists_policy_at_intent_and_reservation_boundaries(tmp_path: Path) -> None:
    media = tmp_path / "yt-1.mp4"
    media.write_bytes(b"video")
    record = new_record()
    writer = FakeWriter()

    persists = run(record, writer, media)

    assert record["stage"] == UploadStage.VERIFIED.value
    assert writer.observed_wall_policy == DEFAULT_UPLOAD_WALL_POLICY
    policy_sha256 = record["wall_policy"]["policy_sha256"]
    assert record["reservation_intent"]["wall_policy_sha256"] == policy_sha256
    assert record["reservation"]["wall_policy_sha256"] == policy_sha256
    assert writer.begin_calls == 1
    assert writer.upload_calls == 1
    assert writer.wait_calls == 1
    assert persists >= 8
    transitions = [item["to"] for item in record["transitions"]]
    assert transitions == [
        UploadStage.PLANNED.value,
        UploadStage.MEDIA_VERIFIED.value,
        UploadStage.RESERVATION_INTENT_COMMITTED.value,
        UploadStage.RESERVED.value,
        UploadStage.UPLOAD_STARTED.value,
        UploadStage.UPLOAD_RESPONSE_RECEIVED.value,
        UploadStage.PROCESSING.value,
        UploadStage.VERIFIED.value,
    ]
    assert record["reservation_dispatch_started_at"]

    run(record, writer, None)
    assert writer.begin_calls == 1
    assert writer.upload_calls == 1
    assert writer.wait_calls == 1


@pytest.mark.parametrize(
    ("boundary", "expected_stage", "expected_begin", "expected_upload"),
    [
        ("before_reservation_intent_commit", UploadStage.MEDIA_VERIFIED, 0, 0),
        ("after_reservation_intent_commit", UploadStage.RESERVATION_INTENT_COMMITTED, 0, 0),
        (
            "after_reservation_dispatch_started_commit",
            UploadStage.RESERVATION_INTENT_COMMITTED,
            0,
            0,
        ),
        (
            "after_provider_reservation_before_ticket_commit",
            UploadStage.RESERVATION_INTENT_COMMITTED,
            1,
            0,
        ),
        ("after_ticket_commit", UploadStage.RESERVED, 1, 0),
        ("after_upload_started_commit", UploadStage.UPLOAD_STARTED, 1, 0),
        ("after_upload_response_commit", UploadStage.UPLOAD_RESPONSE_RECEIVED, 1, 1),
        ("after_remote_ready_before_verified_commit", UploadStage.PROCESSING, 1, 1),
        ("after_verified_commit", UploadStage.VERIFIED, 1, 1),
    ],
)
def test_crash_boundaries_never_allow_second_reservation(
    tmp_path: Path,
    boundary: str,
    expected_stage: UploadStage,
    expected_begin: int,
    expected_upload: int,
) -> None:
    media = tmp_path / "yt-1.mp4"
    media.write_bytes(b"video")
    record = new_record()
    writer = FakeWriter()

    with pytest.raises(CrashAt, match=boundary):
        run(record, writer, media, crash_boundary=boundary)

    assert record["stage"] == expected_stage.value
    assert writer.begin_calls == expected_begin
    assert writer.upload_calls == expected_upload

    if expected_stage == UploadStage.MEDIA_VERIFIED:
        run(record, writer, media)
        assert writer.begin_calls == 1
        return
    if expected_stage == UploadStage.RESERVATION_INTENT_COMMITTED:
        if boundary == "after_reservation_intent_commit":
            run(record, writer, media)
            assert writer.begin_calls == 1
            assert writer.upload_calls == 1
            return
        with pytest.raises(UploadRecoveryRequired, match="no exact VK ID"):
            run(record, writer, media)
        assert writer.begin_calls == expected_begin
        return
    if expected_stage == UploadStage.RESERVED:
        run(record, writer, media)
        assert writer.begin_calls == 1
        assert writer.upload_calls == 1
        return
    if expected_stage == UploadStage.UPLOAD_STARTED:
        with pytest.raises(UploadRecoveryRequired, match="not visible"):
            run(record, writer, None)
        assert writer.begin_calls == 1
        assert writer.upload_calls == 0
        return
    if expected_stage in {UploadStage.UPLOAD_RESPONSE_RECEIVED, UploadStage.PROCESSING}:
        run(record, writer, None)
        assert writer.begin_calls == 1
        assert writer.upload_calls == 1
        return
    run(record, writer, None)
    assert writer.begin_calls == 1
    assert writer.upload_calls == 1


def test_ambiguous_reservation_failure_is_never_retried(tmp_path: Path) -> None:
    media = tmp_path / "yt-1.mp4"
    media.write_bytes(b"video")
    record = new_record()
    writer = FakeWriter()
    writer.begin_error = RetryableReservationError("response lost")

    with pytest.raises(UploadRecoveryRequired, match="second reservation is forbidden"):
        run(record, writer, media)

    assert record["stage"] == UploadStage.UNKNOWN_REQUIRES_RECONCILIATION.value
    assert writer.begin_calls == 1
    with pytest.raises(UploadRecoveryRequired):
        run(record, writer, media)
    assert writer.begin_calls == 1


def test_upload_transport_failure_is_unknown_and_never_retransmitted(tmp_path: Path) -> None:
    media = tmp_path / "yt-1.mp4"
    media.write_bytes(b"video")
    record = new_record()
    writer = FakeWriter()
    writer.upload_error = RuntimeError("connection reset after send")

    with pytest.raises(UploadRecoveryRequired, match="retransmission is forbidden"):
        run(record, writer, media)

    assert record["stage"] == UploadStage.UNKNOWN_REQUIRES_RECONCILIATION.value
    assert writer.begin_calls == 1
    assert writer.upload_calls == 1
    with pytest.raises(UploadRecoveryRequired, match="not visible"):
        run(record, writer, None)
    assert writer.begin_calls == 1
    assert writer.upload_calls == 1


def test_ambiguous_upload_can_be_reconciled_by_exact_remote_id(tmp_path: Path) -> None:
    media = tmp_path / "yt-1.mp4"
    media.write_bytes(b"video")
    record = new_record()
    writer = FakeWriter()
    writer.upload_error = RuntimeError("response lost")

    with pytest.raises(UploadRecoveryRequired):
        run(record, writer, media)

    writer.upload_error = None
    writer.remote_item = ready_item()
    run(record, writer, None)

    assert record["stage"] == UploadStage.VERIFIED.value
    assert writer.begin_calls == 1
    assert writer.upload_calls == 1


def test_visible_zero_duration_object_is_not_verified(tmp_path: Path) -> None:
    media = tmp_path / "yt-1.mp4"
    media.write_bytes(b"video")
    record = new_record()
    writer = FakeWriter()
    writer.preserve_remote_item = True
    writer.remote_item = {
        **ready_item(),
        "duration": 0,
        "processing": 0,
        "converting": 0,
    }

    with pytest.raises(RuntimeError, match="not ready within"):
        run(record, writer, media)

    assert record["stage"] == UploadStage.PROCESSING.value
    assert record["verification"] is None


def test_legacy_verified_record_requires_exact_reconciliation() -> None:
    legacy = {
        "remote_id": "-235216998_501",
        "status": "uploaded_and_verified",
        "published_title": "Берёза ⚡",
    }
    record, changed = ensure_upload_record(
        legacy,
        source_snapshot_id="snapshot-1",
        community_id=235216998,
        source_video_id="yt-1",
        source_title="Берёза",
        source_duration_seconds=120,
        published_title="Берёза ⚡",
        published_description="Описание",
        readiness=readiness(),
    )

    assert changed is True
    assert record["stage"] == UploadStage.PROCESSING.value
    assert record["verification"] is None
    assert record["reservation"]["remote_id"] == "-235216998_501"
    assert record["wall_policy"] == DEFAULT_UPLOAD_WALL_POLICY.as_dict()
