from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from video_channel_manager.domain.models import VideoRecord


YouTubeSourceGeometry = Literal["square_or_vertical", "landscape", "unknown"]
YouTubeSurfaceStatus = Literal["short", "longform", "unknown"]

_MAX_THREE_MINUTE_SHORT_MS = 180_000


@dataclass(frozen=True, slots=True)
class YouTubeSourceFileEvidence:
    file_details_available: bool
    geometry: YouTubeSourceGeometry
    width_pixels: int | None
    height_pixels: int | None
    duration_ms: int | None
    creation_time: datetime | None


@dataclass(frozen=True, slots=True)
class YouTubeSurfaceClassification:
    status: YouTubeSurfaceStatus
    reason: str
    short_candidate: bool
    source: YouTubeSourceFileEvidence


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str):
        try:
            parsed = int(value)
        except ValueError:
            return None
        return parsed if parsed > 0 else None
    return None


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _file_details(video: VideoRecord) -> dict[str, Any]:
    value = video.metadata.get("fileDetails")
    return value if isinstance(value, dict) else {}


def _stream_dimensions(file_details: dict[str, Any]) -> set[tuple[int, int]]:
    streams = file_details.get("videoStreams")
    if not isinstance(streams, list):
        return set()

    dimensions: set[tuple[int, int]] = set()
    for stream in streams:
        if not isinstance(stream, dict):
            continue
        width = _positive_int(stream.get("widthPixels"))
        height = _positive_int(stream.get("heightPixels"))
        if width is not None and height is not None:
            dimensions.add((width, height))
    return dimensions


def extract_youtube_source_file_evidence(video: VideoRecord) -> YouTubeSourceFileEvidence:
    """Extract owner-only source-file facts already retained in VideoRecord metadata."""

    details = _file_details(video)
    dimensions = _stream_dimensions(details)

    geometry: YouTubeSourceGeometry = "unknown"
    width: int | None = None
    height: int | None = None
    if dimensions:
        orientations = {"square_or_vertical" if candidate_width <= candidate_height else "landscape" for candidate_width, candidate_height in dimensions}
        if len(orientations) == 1:
            geometry = orientations.pop()
        if len(dimensions) == 1:
            width, height = next(iter(dimensions))

    return YouTubeSourceFileEvidence(
        file_details_available=bool(details),
        geometry=geometry,
        width_pixels=width,
        height_pixels=height,
        duration_ms=_positive_int(details.get("durationMs")),
        creation_time=_parse_datetime(details.get("creationTime")),
    )


def classify_youtube_surface(video: VideoRecord) -> YouTubeSurfaceClassification:
    """Classify only what exact metadata proves; never infer Shorts from duration alone.

    A landscape source cannot satisfy YouTube's square/vertical Shorts geometry.
    A source over three minutes cannot satisfy the current three-minute Shorts cap.
    Square/vertical sources at or below three minutes remain candidates rather than
    confirmed Shorts because neither ``snippet.publishedAt`` nor file creation time
    is treated here as exact upload/surface proof.
    """

    source = extract_youtube_source_file_evidence(video)
    duration_ms = source.duration_ms
    if duration_ms is None and video.duration_seconds is not None:
        duration_ms = video.duration_seconds * 1000

    if source.geometry == "landscape":
        return YouTubeSurfaceClassification(
            status="longform",
            reason="owner_file_details_prove_landscape_source_geometry",
            short_candidate=False,
            source=source,
        )

    if duration_ms is not None and duration_ms > _MAX_THREE_MINUTE_SHORT_MS:
        return YouTubeSurfaceClassification(
            status="longform",
            reason="duration_exceeds_current_three_minute_shorts_cap",
            short_candidate=False,
            source=source,
        )

    short_candidate = source.geometry == "square_or_vertical" and duration_ms is not None and duration_ms <= _MAX_THREE_MINUTE_SHORT_MS
    if short_candidate:
        return YouTubeSurfaceClassification(
            status="unknown",
            reason="square_or_vertical_under_three_minutes_but_exact_shorts_surface_not_proved",
            short_candidate=True,
            source=source,
        )

    return YouTubeSurfaceClassification(
        status="unknown",
        reason="insufficient_exact_surface_evidence",
        short_candidate=False,
        source=source,
    )
