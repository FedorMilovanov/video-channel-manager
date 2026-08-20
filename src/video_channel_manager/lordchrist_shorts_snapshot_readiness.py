from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

from pydantic import ValidationError

from video_channel_manager.editorial.youtube_surface_classification import classify_youtube_surface
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.lordchrist_shorts import YOUTUBE_CHANNEL_ID

_MAX_SHORT_DURATION_MS = 180_000
DEFAULT_MAX_SNAPSHOT_AGE_HOURS = 48


class SnapshotReadiness(TypedDict):
    schema_name: str
    schema_version: int
    youtube_channel_id: str
    source_snapshot_id: str
    generated_at: str
    evaluated_at: str
    snapshot_age_seconds: int
    max_snapshot_age_hours: int
    fresh_enough: bool
    total_videos: int
    owner_file_details_count: int
    owner_creation_time_count: int
    duration_le_180_count: int
    duration_le_180_known_geometry_count: int
    duration_le_180_missing_geometry_count: int
    proven_short_count: int
    candidate_count: int
    longform_count: int
    unresolved_non_candidate_count: int
    ready_for_exact_surface_inventory: bool
    provider_access_performed: bool
    provider_write_performed: bool


def _duration_ms(video_duration_seconds: int | None, source_duration_ms: int | None) -> int | None:
    if source_duration_ms is not None:
        return source_duration_ms
    if video_duration_seconds is not None:
        return video_duration_seconds * 1000
    return None


def summarize_snapshot_readiness(
    package: AuditPackage,
    *,
    as_of: datetime | None = None,
    max_age_hours: int = DEFAULT_MAX_SNAPSHOT_AGE_HOURS,
) -> SnapshotReadiness:
    if package.channel.ref.platform.value != "youtube":
        raise ValueError("LordChrist Shorts snapshot readiness requires a YouTube AuditPackage")
    if package.channel.ref.channel_id != YOUTUBE_CHANNEL_ID:
        raise ValueError(
            f"AuditPackage channel mismatch: expected {YOUTUBE_CHANNEL_ID}, got {package.channel.ref.channel_id}"
        )
    if max_age_hours <= 0:
        raise ValueError("max_age_hours must be positive")
    if package.generated_at.tzinfo is None or package.generated_at.utcoffset() is None:
        raise ValueError("AuditPackage generated_at must be timezone-aware")

    evaluated_at = as_of or datetime.now(UTC)
    if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
        raise ValueError("readiness evaluation time must be timezone-aware")
    generated_at = package.generated_at.astimezone(UTC)
    evaluated_at = evaluated_at.astimezone(UTC)
    snapshot_age_seconds = int((evaluated_at - generated_at).total_seconds())
    fresh_enough = 0 <= snapshot_age_seconds <= max_age_hours * 3600

    owner_file_details_count = 0
    owner_creation_time_count = 0
    duration_le_180_count = 0
    duration_le_180_known_geometry_count = 0
    proven_short_count = 0
    candidate_count = 0
    longform_count = 0
    unresolved_non_candidate_count = 0

    for video in package.videos:
        if video.ref.channel_id != YOUTUBE_CHANNEL_ID:
            raise ValueError(f"cross-channel video in AuditPackage: {video.ref.remote_id}")

        classification = classify_youtube_surface(video)
        source = classification.source
        if source.file_details_available:
            owner_file_details_count += 1
        if source.creation_time is not None:
            owner_creation_time_count += 1

        duration_ms = _duration_ms(video.duration_seconds, source.duration_ms)
        if duration_ms is not None and duration_ms <= _MAX_SHORT_DURATION_MS:
            duration_le_180_count += 1
            if source.geometry != "unknown":
                duration_le_180_known_geometry_count += 1

        if classification.status == "short":
            proven_short_count += 1
        elif classification.status == "longform":
            longform_count += 1
        elif classification.short_candidate:
            candidate_count += 1
        else:
            unresolved_non_candidate_count += 1

    duration_le_180_missing_geometry_count = duration_le_180_count - duration_le_180_known_geometry_count
    ready = bool(package.videos) and unresolved_non_candidate_count == 0 and fresh_enough
    return SnapshotReadiness(
        schema_name="video-channel-manager.lordchrist-shorts-snapshot-readiness",
        schema_version=1,
        youtube_channel_id=YOUTUBE_CHANNEL_ID,
        source_snapshot_id=str(package.snapshot_id),
        generated_at=generated_at.isoformat(),
        evaluated_at=evaluated_at.isoformat(),
        snapshot_age_seconds=snapshot_age_seconds,
        max_snapshot_age_hours=max_age_hours,
        fresh_enough=fresh_enough,
        total_videos=len(package.videos),
        owner_file_details_count=owner_file_details_count,
        owner_creation_time_count=owner_creation_time_count,
        duration_le_180_count=duration_le_180_count,
        duration_le_180_known_geometry_count=duration_le_180_known_geometry_count,
        duration_le_180_missing_geometry_count=duration_le_180_missing_geometry_count,
        proven_short_count=proven_short_count,
        candidate_count=candidate_count,
        longform_count=longform_count,
        unresolved_non_candidate_count=unresolved_non_candidate_count,
        ready_for_exact_surface_inventory=ready,
        provider_access_performed=False,
        provider_write_performed=False,
    )


def require_snapshot_ready(
    package: AuditPackage,
    *,
    as_of: datetime | None = None,
    max_age_hours: int = DEFAULT_MAX_SNAPSHOT_AGE_HOURS,
) -> SnapshotReadiness:
    summary = summarize_snapshot_readiness(package, as_of=as_of, max_age_hours=max_age_hours)
    if not summary["ready_for_exact_surface_inventory"]:
        raise ValueError(
            "AuditPackage is not ready for exact LordChrist Shorts surface inventory: "
            f"fresh_enough={summary['fresh_enough']}, "
            f"snapshot_age_seconds={summary['snapshot_age_seconds']}, "
            f"unresolved_non_candidate_count={summary['unresolved_non_candidate_count']}, "
            f"duration_le_180_missing_geometry_count={summary['duration_le_180_missing_geometry_count']}. "
            "Run a fresh read-only video-manager youtube scan so current owner fileDetails/videoStreams evidence is present."
        )
    return summary


def _load_audit(path: Path) -> AuditPackage:
    try:
        return AuditPackage.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid YouTube AuditPackage {path}: {exc}") from exc


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Fail-closed readiness check for a LordChrist YouTube AuditPackage before Shorts inventory."
    )
    root.add_argument("--audit", type=Path, required=True)
    root.add_argument("--max-age-hours", type=int, default=DEFAULT_MAX_SNAPSHOT_AGE_HOURS)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        package = _load_audit(args.audit)
        summary = summarize_snapshot_readiness(package, max_age_hours=args.max_age_hours)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        if not summary["ready_for_exact_surface_inventory"]:
            print(
                "ERROR: snapshot is stale or lacks enough exact owner source evidence; "
                "run a fresh read-only YouTube scan.",
            )
            return 2
        return 0
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
