from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from video_channel_manager.domain.models import VideoRecord


YouTubeSourceGeometry = Literal["square_or_vertical", "landscape", "unknown"]
YouTubeSurfaceStatus = Literal["short", "longform", "unknown"]

_MAX_THREE_MINUTE_SHORT_MS = 180_000
# Conservative universal boundary: standard channels crossed the three-minute
# Shorts boundary earlier, while Official Artist Channels use 2025-12-08.
# Using the later date avoids needing to guess the channel's artist status.
_UNIVERSAL_THREE_MINUTE_SHORTS_CUTOFF = datetime(2025, 12, 8, tzinfo=UTC)


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


def _display_dimensions(file_details: dict[str, Any]) -> tuple[set[tuple[int, int]], bool]:
    streams = file_details.get("videoStreams")
    if not isinstance(streams, list):
        return set(), False

    dimensions: set[tuple[int, int]] = set()
    ambiguous_rotation = False
    for stream in streams:
        if not isinstance(stream, dict):
            continue
        width = _positive_int(stream.get("widthPixels"))
        height = _positive_int(stream.get("heightPixels"))
        if width is None or height is None:
            continue

        rotation = stream.get("rotation")
        if rotation in (None, "none", "upsideDown"):
            dimensions.add((width, height))
        elif rotation in ("clockwise", "counterClockwise"):
            dimensions.add((height, width))
        else:
            ambiguous_rotation = True
    return dimensions, ambiguous_rotation


def _geometry_for_dimensions(width: int, height: int) -> YouTubeSourceGeometry:
    return "square_or_vertical" if width <= height else "landscape"


def extract_youtube_source_file_evidence(video: VideoRecord) -> YouTubeSourceFileEvidence:
    """Extract owner-only source-file facts already retained in VideoRecord metadata."""

    details = _file_details(video)
    dimensions, ambiguous_rotation = _display_dimensions(details)

    geometry: YouTubeSourceGeometry = "unknown"
    width: int | None = None
    height: int | None = None
    if dimensions and not ambiguous_rotation:
        orientations = {
            _geometry_for_dimensions(candidate_width, candidate_height)
            for candidate_width, candidate_height in dimensions
        }
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
    """Classify only what exact owner metadata proves.

    YouTube's current policy categorizes square/vertical uploads up to three minutes
    as Shorts after the applicable rollout date. Standard channels crossed that
    boundary earlier; Official Artist Channels use the later 2025-12-08 boundary.
    A recorded source-file creation time after that boundary proves the upload cannot
    predate it. Likewise, YouTube's public ``publishedAt`` timestamp is a safe lower
    bound for upload time: a video cannot be published before it is uploaded. That is
    enough to prove post-cutoff eligibility without pretending ``publishedAt`` is the
    exact upload time.

    Missing geometry never becomes a confirmed Short. Duration-eligible records with
    unknown geometry remain candidates so the exact owner-media acceptance step can
    resolve them from the actual bytes later.
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

    duration_eligible = duration_ms is not None and duration_ms <= _MAX_THREE_MINUTE_SHORT_MS
    if not duration_eligible:
        return YouTubeSurfaceClassification(
            status="unknown",
            reason="insufficient_exact_surface_evidence",
            short_candidate=False,
            source=source,
        )

    post_cutoff_proven = False
    proof_reason = ""
    if source.creation_time is not None and source.creation_time >= _UNIVERSAL_THREE_MINUTE_SHORTS_CUTOFF:
        post_cutoff_proven = True
        proof_reason = "owner_file_creation_time_proves_post_universal_three_minute_shorts_cutoff"
    elif video.published_at is not None and video.published_at >= _UNIVERSAL_THREE_MINUTE_SHORTS_CUTOFF:
        post_cutoff_proven = True
        proof_reason = "owner_publication_time_proves_post_universal_three_minute_shorts_cutoff"

    if source.geometry == "square_or_vertical" and post_cutoff_proven:
        return YouTubeSurfaceClassification(
            status="short",
            reason=proof_reason,
            short_candidate=False,
            source=source,
        )

    if source.geometry == "unknown":
        return YouTubeSurfaceClassification(
            status="unknown",
            reason="duration_eligible_but_owner_source_geometry_missing",
            short_candidate=True,
            source=source,
        )

    return YouTubeSurfaceClassification(
        status="unknown",
        reason="short_geometry_and_duration_proved_but_post_cutoff_upload_not_yet_proved",
        short_candidate=True,
        source=source,
    )
