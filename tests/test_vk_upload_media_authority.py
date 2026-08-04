from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from video_channel_manager.domain.enums import PlatformName
from video_channel_manager.local_media.artifact import (
    MediaArtifactEvidence,
    MediaCompatibilityProfile,
    MediaSourceIdentity,
    build_media_artifact_evidence,
    controlled_master_acquisition,
)
from video_channel_manager.local_media.quality import MediaQualityReport, sha256_file
from video_channel_manager.platforms.vk.upload_lifecycle import (
    StoredUploadTicket,
    UploadRejected,
    UploadStage,
    VkUploadReadiness,
    assess_vk_upload_readiness,
    create_upload_record,
)
from video_channel_manager.platforms.vk.upload_media import (
    execute_upload_operation,
    journal_media_evidence,
)
from video_channel_manager.platforms.vk.wall_safety import (
    VkUploadWallPolicy,
    VkWallSnapshot,
    build_wall_snapshot,
)


class FakeWriter:
    def __init__(self, media_to_mutate: Path | None = None) -> None:
        self.begin_calls = 0
        self.upload_calls = 0
        self.media_to_mutate = media_to_mutate
        self.remote_item: dict[str, Any] | None = None

    def begin_upload(
        self,
        *,
        community_id: int,
        title: str,
        description: str,
        wall_policy: VkUploadWallPolicy,
    ) -> StoredUploadTicket:
        assert (community_id, title, description) == (235216998, "Берёза ⚡", "Описание")
        assert wall_policy.wall_mutation_authorized is False
        self.begin_calls += 1
        if self.media_to_mutate is not None:
            self.media_to_mutate.write_bytes(b"changed-after-reservation")
        return StoredUploadTicket(
            owner_id=-community_id,
            video_id=501,
            upload_url="https://upload.example/ticket",
            reservation_response={
                "owner_id": -community_id,
                "video_id": 501,
                "upload_url": "https://upload.example/ticket",
            },
        )

    def upload_file(self, ticket: StoredUploadTicket, path: Path) -> dict[str, Any]:
        self.upload_calls += 1
        self.remote_item = _ready_item(ticket.owner_id, ticket.video_id)
        return {"video_id": str(ticket.video_id), "size": path.stat().st_size}

    def read_video(self, *, owner_id: int, video_id: int) -> dict[str, Any] | None:
        return self.remote_item

    def wait_until_available(
        self,
        ticket: StoredUploadTicket,
        *,
        readiness: VkUploadReadiness,
        timeout_seconds: int,
        on_observation: Callable[[dict[str, Any] | None, object | None], None] | None = None,
    ) -> dict[str, Any]:
        item = self.remote_item
        if item is None:
            raise RuntimeError(f"not visible within {timeout_seconds}")
        assessment = assess_vk_upload_readiness(
            item,
            expected_owner_id=ticket.owner_id,
            expected_video_id=ticket.video_id,
            readiness=readiness,
        )
        if on_observation is not None:
            on_observation(item, assessment)
        assert assessment.ready
        return item

    def capture_wall_snapshot(
        self,
        *,
        community_id: int,
        max_posts_per_surface: int = 10000,
    ) -> VkWallSnapshot:
        assert community_id == 235216998
        assert max_posts_per_surface == 10000
        return _clean_wall_snapshot()


def _clean_wall_snapshot() -> VkWallSnapshot:
    return build_wall_snapshot(
        community_id=235216998,
        published_items=[],
        postponed_items=[],
        published_pages=1,
        postponed_pages=1,
        complete=True,
        captured_at=datetime(2026, 8, 4, 18, 0, tzinfo=UTC),
    )


def _ready_item(owner_id: int, video_id: int) -> dict[str, Any]:
    return {
        "owner_id": owner_id,
        "id": video_id,
        "title": "Берёза ⚡",
        "duration": 120,
        "type": "video",
        "processing": 0,
        "converting": 0,
        "can_watch": 1,
        "player": "https://vk.example/player",
    }


def _readiness() -> VkUploadReadiness:
    return VkUploadReadiness(
        expected_title="Берёза ⚡",
        minimum_duration_seconds=115,
        allowed_types=("video",),
        require_playable=True,
    )


def _record() -> dict[str, Any]:
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


def _report(path: Path) -> MediaQualityReport:
    resolved = path.resolve()
    return MediaQualityReport(
        path=str(resolved),
        size_bytes=resolved.stat().st_size,
        sha256=sha256_file(resolved),
        duration_seconds=120.0,
        format_names=("mov", "mp4"),
        video_stream_count=1,
        audio_stream_count=1,
        video_codec="h264",
        audio_codec="aac",
        width=1920,
        height=1080,
        sample_rate_hz=48000,
        audio_channels=2,
    )


def _artifact(path: Path, *, profile_name: str = "vk-h264-aac-v1") -> MediaArtifactEvidence:
    return build_media_artifact_evidence(
        source=MediaSourceIdentity(
            project_key="legendary-poet",
            platform=PlatformName.YOUTUBE,
            source_channel_id="UC-78ys2S3cQ3lpqgXfo-SvQ",
            source_id="yt-1",
            source_url="https://youtu.be/yt-1",
            expected_duration_seconds=120.0,
        ),
        acquisition=controlled_master_acquisition(path),
        profile=MediaCompatibilityProfile(profile_name=profile_name),
        report=_report(path),
    )


def _execute(
    record: dict[str, Any],
    writer: FakeWriter,
    media: Path | None,
    evidence: MediaArtifactEvidence | None,
    *,
    probe_calls: list[Path] | None = None,
) -> None:
    def probe(path: Path) -> MediaQualityReport:
        if probe_calls is not None:
            probe_calls.append(path)
        return _report(path)

    execute_upload_operation(
        record,
        writer=writer,
        community_id=235216998,
        title="Берёза ⚡",
        description="Описание",
        media_path=media,
        media_artifact=evidence,
        readiness=_readiness(),
        processing_timeout=60,
        wall_before_snapshot=_clean_wall_snapshot(),
        persist=lambda: None,
        media_probe=probe,
        clock=lambda: datetime(2026, 8, 4, 18, 0, tzinfo=UTC),
    )


def test_manifest_is_required_before_provider_dispatch(tmp_path: Path) -> None:
    media = tmp_path / "yt-1.mp4"
    media.write_bytes(b"video")
    record = _record()
    writer = FakeWriter()

    with pytest.raises(UploadRejected, match="artifact evidence is required"):
        _execute(record, writer, media, None)

    assert record["stage"] == UploadStage.PLANNED.value
    assert writer.begin_calls == writer.upload_calls == 0


def test_manifest_is_journaled_bound_to_intent_and_reprobed_at_dispatch(tmp_path: Path) -> None:
    media = tmp_path / "yt-1.mp4"
    media.write_bytes(b"video")
    evidence = _artifact(media)
    record = _record()
    writer = FakeWriter()
    probe_calls: list[Path] = []

    _execute(record, writer, media, evidence, probe_calls=probe_calls)

    assert record["stage"] == UploadStage.VERIFIED.value
    assert record["media"]["schema_version"] == 2
    assert record["media"]["manifest_sha256"] == evidence.manifest_sha256
    assert record["media"]["artifact"]["probe"]["video_codec"] == "h264"
    assert record["reservation_intent"]["media_manifest_sha256"] == evidence.manifest_sha256
    assert len(probe_calls) >= 2
    assert writer.begin_calls == writer.upload_calls == 1


def test_changed_file_after_reservation_is_blocked_before_upload_dispatch(tmp_path: Path) -> None:
    media = tmp_path / "yt-1.mp4"
    media.write_bytes(b"video")
    record = _record()
    writer = FakeWriter(media_to_mutate=media)

    with pytest.raises(UploadRejected, match="changed after reservation"):
        _execute(record, writer, media, _artifact(media))

    assert writer.begin_calls == 1
    assert writer.upload_calls == 0
    assert record["stage"] == UploadStage.RESERVED.value
    assert record["reservation"]["remote_id"] == "-235216998_501"


def test_manifest_cannot_change_after_media_verified(tmp_path: Path) -> None:
    media = tmp_path / "yt-1.mp4"
    media.write_bytes(b"video")
    original = _artifact(media)
    record = _record()
    record["stage"] = UploadStage.MEDIA_VERIFIED.value
    record["media"] = journal_media_evidence(original)
    writer = FakeWriter()

    with pytest.raises(UploadRejected, match="manifest changed"):
        _execute(record, writer, media, _artifact(media, profile_name="other-compatible"))

    assert writer.begin_calls == writer.upload_calls == 0


def test_legacy_size_sha_journal_is_not_cache_authority(tmp_path: Path) -> None:
    media = tmp_path / "yt-1.mp4"
    media.write_bytes(b"video")
    record = _record()
    record["stage"] = UploadStage.MEDIA_VERIFIED.value
    record["media"] = {
        "path": str(media),
        "size_bytes": media.stat().st_size,
        "sha256": sha256_file(media),
    }
    writer = FakeWriter()

    with pytest.raises(UploadRejected, match="legacy media evidence"):
        _execute(record, writer, media, _artifact(media))

    assert writer.begin_calls == writer.upload_calls == 0
