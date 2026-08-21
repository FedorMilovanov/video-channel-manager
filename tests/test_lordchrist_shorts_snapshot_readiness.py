from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from video_channel_manager.domain.enums import ChannelKind, PlatformName
from video_channel_manager.domain.models import ChannelRecord, RemoteRef, VideoRecord
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.lordchrist_shorts import KNOWN_DURATION_ONLY_SNAPSHOT_ID, YOUTUBE_CHANNEL_ID
from video_channel_manager.lordchrist_shorts_snapshot_readiness import (
    require_snapshot_ready,
    summarize_snapshot_readiness,
)

AS_OF = datetime(2026, 8, 20, 18, 0, tzinfo=UTC)


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


def _audit(
    videos: list[VideoRecord],
    *,
    channel_id: str = YOUTUBE_CHANNEL_ID,
    generated_at: datetime = datetime(2026, 8, 20, 16, 0, tzinfo=UTC),
    snapshot_id: UUID | None = None,
) -> AuditPackage:
    channel = ChannelRecord(
        ref=RemoteRef(
            platform=PlatformName.YOUTUBE,
            channel_id=channel_id,
            remote_id=channel_id,
        ),
        title="Fedor Milovanov",
        kind=ChannelKind.VIDEO_CHANNEL,
    )
    if snapshot_id is None:
        return AuditPackage(channel=channel, generated_at=generated_at, videos=videos)
    return AuditPackage(
        channel=channel,
        generated_at=generated_at,
        videos=videos,
        snapshot_id=snapshot_id,
    )


def _fully_classifiable_videos() -> list[VideoRecord]:
    return [
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


def test_snapshot_readiness_accepts_fresh_fully_classifiable_owner_snapshot() -> None:
    package = _audit(_fully_classifiable_videos())

    summary = require_snapshot_ready(package, as_of=AS_OF)
    assert summary["generated_at"] == "2026-08-20T16:00:00+00:00"
    assert summary["evaluated_at"] == "2026-08-20T18:00:00+00:00"
    assert summary["snapshot_age_seconds"] == 7200
    assert summary["fresh_enough"] is True
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

    summary = summarize_snapshot_readiness(package, as_of=AS_OF)
    assert summary["fresh_enough"] is True
    assert summary["owner_file_details_count"] == 0
    assert summary["duration_le_180_count"] == 1
    assert summary["duration_le_180_known_geometry_count"] == 0
    assert summary["duration_le_180_missing_geometry_count"] == 1
    assert summary["longform_count"] == 1
    assert summary["unresolved_non_candidate_count"] == 1
    assert summary["ready_for_exact_surface_inventory"] is False

    with pytest.raises(ValueError, match="fresh read-only video-manager youtube scan"):
        require_snapshot_ready(package, as_of=AS_OF)


def test_fully_evidenced_but_stale_snapshot_fails_closed() -> None:
    package = _audit(
        _fully_classifiable_videos(),
        generated_at=datetime(2026, 8, 17, 16, 0, tzinfo=UTC),
    )
    summary = summarize_snapshot_readiness(package, as_of=AS_OF, max_age_hours=48)
    assert summary["unresolved_non_candidate_count"] == 0
    assert summary["fresh_enough"] is False
    assert summary["ready_for_exact_surface_inventory"] is False
    with pytest.raises(ValueError, match="fresh_enough=False"):
        require_snapshot_ready(package, as_of=AS_OF, max_age_hours=48)


def test_future_dated_snapshot_fails_closed() -> None:
    package = _audit(
        _fully_classifiable_videos(),
        generated_at=datetime(2026, 8, 20, 19, 0, tzinfo=UTC),
    )
    summary = summarize_snapshot_readiness(package, as_of=AS_OF)
    assert summary["snapshot_age_seconds"] == -3600
    assert summary["fresh_enough"] is False
    assert summary["ready_for_exact_surface_inventory"] is False


def test_snapshot_readiness_rejects_non_lordchrist_channel() -> None:
    wrong_channel = "UCWrongChannel0000000000"
    package = _audit(
        [
            _video(
                "AbCdEf12345",
                duration_seconds=60,
                width=1080,
                height=1920,
                creation_time="2026-01-02T00:00:00Z",
                channel_id=wrong_channel,
            )
        ],
        channel_id=wrong_channel,
    )

    with pytest.raises(ValueError, match="AuditPackage channel mismatch"):
        summarize_snapshot_readiness(package, as_of=AS_OF)


def test_snapshot_readiness_rejects_non_positive_max_age() -> None:
    package = _audit(_fully_classifiable_videos())
    with pytest.raises(ValueError, match="max_age_hours must be positive"):
        summarize_snapshot_readiness(package, as_of=AS_OF, max_age_hours=0)


def test_known_duration_only_snapshot_id_fails_closed_even_when_otherwise_fresh() -> None:
    package = _audit(
        _fully_classifiable_videos(),
        snapshot_id=UUID(KNOWN_DURATION_ONLY_SNAPSHOT_ID),
    )
    summary = summarize_snapshot_readiness(package, as_of=AS_OF)
    assert summary["fresh_enough"] is True
    assert summary["unresolved_non_candidate_count"] == 0
    assert summary["known_duration_only_snapshot"] is True
    assert summary["ready_for_exact_surface_inventory"] is False
    with pytest.raises(ValueError, match="duration-only catalog"):
        require_snapshot_ready(package, as_of=AS_OF)
