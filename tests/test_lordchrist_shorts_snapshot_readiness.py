from __future__ import annotations

from datetime import UTC, datetime

import pytest

from video_channel_manager.domain.enums import ChannelKind, PlatformName
from video_channel_manager.domain.models import ChannelRecord, RemoteRef, VideoRecord
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.lordchrist_shorts import YOUTUBE_CHANNEL_ID
from video_channel_manager.lordchrist_shorts_snapshot_readiness import (
    require_snapshot_ready,
    summarize_snapshot_readiness,
)


def _video(
    video_id: str,
    *,
    duration_seconds: int,
    width: int | None = None,
    height: int | None = None,
    creation_time: str | None = None,
    channel_id: str = YOUTUBE_CHANNEL_ID,
) -> VideoRecord:
    metadata: dict[str, object] = {}
    if width is not None and height is not None:
        file_details: dict[str, object] = {
            "durationMs": duration_seconds * 1000,
            "videoStreams": [
                {
                    "widthPixels": width,
                    "heightPixels": height,
                    "rotation": "none",
                }
            ],
        }
        if creation_time is not None:
            file_details["creationTime"] = creation_time
        metadata["fileDetails"] = file_details
    return VideoRecord(
        ref=RemoteRef(platform=PlatformName.YOUTUBE, channel_id=channel_id, remote_id=video_id),
        title=video_id,
        duration_seconds=duration_seconds,
        published_at=datetime(2026, 1, 10, tzinfo=UTC),
        revision=f"sha256:{video_id}",
        metadata=metadata,
    )


def _audit(videos: list[VideoRecord]) -> AuditPackage:
    channel = ChannelRecord(
        ref=RemoteRef(
            platform=PlatformName.YOUTUBE,
            channel_id=YOUTUBE_CHANNEL_ID,
            remote_id=YOUTUBE_CHANNEL_ID,
        ),
        title="Fedor Milovanov",
        kind=ChannelKind.VIDEO_CHANNEL,
    )
    return AuditPackage(
        channel=channel,
        generated_at=datetime(2026, 8, 20, 16, 0, tzinfo=UTC),
        videos=videos,
    )


def test_snapshot_readiness_accepts_fully_classifiable_owner_snapshot() -> None:
    package = _audit(
        [
            _video(
                "AbCdEf12345",
                duration_seconds=60,
                width=1080,
                height=1920,
                creation_time="2026-01-02T00:00:00Z",
            ),
            _video(
                "QwErTy67890",
                duration_seconds=45,
                width=1080,
                height=1920,
                creation_time="2024-01-02T00:00:00Z",
            ),
            _video(
                "LmNoPq13579",
                duration_seconds=50,
                width=1920,
                height=1080,
                creation_time="2026-01-02T00:00:00Z",
            ),
        ]
    )

    summary = require_snapshot_ready(package)
    assert summary["total_videos"] == 3
    assert summary["owner_file_details_count"] == 3
    assert summary["owner_creation_time_count"] == 3
    assert summary["duration_le_180_count"] == 3
    assert summary["duration_le_180_known_geometry_count"] == 3
    assert summary["duration_le_180_missing_geometry_count"] == 0
    assert summary["proven_short_count"] == 1
    assert summary["candidate_count"] == 1
    assert summary["longform_count"] == 1
    assert summary["unresolved_non_candidate_count"] == 0
    assert summary["ready_for_exact_surface_inventory"] is True
    assert summary["provider_access_performed"] is False
    assert summary["provider_write_performed"] is False


def test_historical_duration_only_snapshot_fails_closed_instead_of_reporting_zero_shorts() -> None:
    package = _audit(
        [
            _video("AbCdEf12345", duration_seconds=60),
            _video("LmNoPq13579", duration_seconds=240),
        ]
    )

    summary = summarize_snapshot_readiness(package)
    assert summary["owner_file_details_count"] == 0
    assert summary["duration_le_180_count"] == 1
    assert summary["duration_le_180_known_geometry_count"] == 0
    assert summary["duration_le_180_missing_geometry_count"] == 1
    assert summary["longform_count"] == 1
    assert summary["unresolved_non_candidate_count"] == 1
    assert summary["ready_for_exact_surface_inventory"] is False

    with pytest.raises(ValueError, match="fresh read-only video-manager youtube scan"):
        require_snapshot_ready(package)


def test_snapshot_readiness_rejects_cross_channel_records() -> None:
    package = _audit(
        [
            _video(
                "AbCdEf12345",
                duration_seconds=60,
                width=1080,
                height=1920,
                creation_time="2026-01-02T00:00:00Z",
                channel_id="UCWrongChannel0000000000",
            )
        ]
    )

    with pytest.raises(ValueError, match="cross-channel video"):
        summarize_snapshot_readiness(package)
