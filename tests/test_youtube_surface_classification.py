from __future__ import annotations

from datetime import datetime

from video_channel_manager.domain.enums import PlatformName
from video_channel_manager.domain.models import RemoteRef, VideoRecord
from video_channel_manager.editorial.youtube_surface_classification import classify_youtube_surface


CHANNEL_ID = "UC-78ys2S3cQ3lpqgXfo-SvQ"
VIDEO_ID = "AAAAAAAAAAA"


def _video(
    *,
    width: int,
    height: int,
    rotation: str | None,
    creation_time: str,
    published_at: str | None = None,
) -> VideoRecord:
    stream = {"widthPixels": width, "heightPixels": height}
    if rotation is not None:
        stream["rotation"] = rotation
    return VideoRecord(
        ref=RemoteRef(platform=PlatformName.YOUTUBE, channel_id=CHANNEL_ID, remote_id=VIDEO_ID),
        title="Video",
        duration_seconds=60,
        published_at=(datetime.fromisoformat(published_at.replace("Z", "+00:00")) if published_at else None),
        revision="sha256:revision",
        metadata={
            "fileDetails": {
                "durationMs": "60000",
                "creationTime": creation_time,
                "videoStreams": [stream],
            }
        },
    )


def _video_without_geometry(*, published_at: str | None) -> VideoRecord:
    return VideoRecord(
        ref=RemoteRef(platform=PlatformName.YOUTUBE, channel_id=CHANNEL_ID, remote_id=VIDEO_ID),
        title="Video",
        duration_seconds=60,
        published_at=(datetime.fromisoformat(published_at.replace("Z", "+00:00")) if published_at else None),
        revision="sha256:revision",
        metadata={"fileDetails": {"durationMs": "60000", "creationTime": ""}},
    )


def test_quarter_turn_rotation_is_applied_before_surface_classification() -> None:
    result = classify_youtube_surface(
        _video(
            width=1920,
            height=1080,
            rotation="clockwise",
            creation_time="2026-08-01T00:00:00Z",
        )
    )

    assert result.source.width_pixels == 1080
    assert result.source.height_pixels == 1920
    assert result.source.geometry == "square_or_vertical"
    assert result.status == "short"


def test_upside_down_rotation_preserves_orientation() -> None:
    result = classify_youtube_surface(
        _video(
            width=1920,
            height=1080,
            rotation="upsideDown",
            creation_time="2026-08-01T00:00:00Z",
        )
    )

    assert result.source.geometry == "landscape"
    assert result.status == "longform"


def test_unknown_rotation_fails_closed_instead_of_guessing_geometry() -> None:
    result = classify_youtube_surface(
        _video(
            width=1920,
            height=1080,
            rotation="other",
            creation_time="2026-08-01T00:00:00Z",
        )
    )

    assert result.source.width_pixels is None
    assert result.source.height_pixels is None
    assert result.source.geometry == "unknown"
    assert result.status == "unknown"
    assert result.short_candidate is False


def test_post_cutoff_published_at_is_a_conservative_lower_bound_for_short_eligibility() -> None:
    result = classify_youtube_surface(
        _video(
            width=1080,
            height=1920,
            rotation=None,
            creation_time="",
            published_at="2026-08-20T10:00:00Z",
        )
    )

    assert result.status == "short"
    assert result.short_candidate is False
    assert result.reason == "owner_publication_time_proves_post_universal_three_minute_shorts_cutoff"


def test_duration_eligible_missing_geometry_is_kept_as_candidate() -> None:
    result = classify_youtube_surface(
        _video_without_geometry(published_at="2026-08-20T10:00:00Z")
    )

    assert result.source.geometry == "unknown"
    assert result.status == "unknown"
    assert result.short_candidate is True
    assert result.reason == "duration_eligible_but_owner_source_geometry_missing"
