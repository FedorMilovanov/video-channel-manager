from __future__ import annotations

from video_channel_manager.application.cross_platform.collections import (
    build_collection_gaps,
    collection_titles_by_video,
    missing_video,
)
from video_channel_manager.application.cross_platform.exact import exact_title_phase, reviewed_matches
from video_channel_manager.application.cross_platform.fallback import fallback_candidates, fallback_components
from video_channel_manager.application.cross_platform.models import CrossPlatformComparison, MatchConflict
from video_channel_manager.exchange.audit_package import AuditPackage


def compare_audit_packages(
    source: AuditPackage,
    target: AuditPackage,
    *,
    min_score: float = 0.65,
    max_duration_delta_seconds: int = 3,
    reviewed_video_mapping: dict[str, str] | None = None,
) -> CrossPlatformComparison:
    if source.channel.ref.platform == target.channel.ref.platform:
        raise ValueError("cross-platform comparison requires different source and target platforms")
    if not 0.0 <= min_score <= 1.0:
        raise ValueError("min_score must be between 0 and 1")
    if max_duration_delta_seconds < 0:
        raise ValueError("max_duration_delta_seconds cannot be negative")

    matches, used_source, used_target = reviewed_matches(source, target, reviewed_video_mapping or {})
    conflicts: list[MatchConflict] = []
    available_source = set(range(len(source.videos))) - used_source
    available_target = set(range(len(target.videos))) - used_target

    exact_matches, exact_conflicts, exact_source, exact_target = exact_title_phase(
        source,
        target,
        available_source=available_source,
        available_target=available_target,
        max_duration_delta_seconds=max_duration_delta_seconds,
    )
    matches.extend(exact_matches)
    conflicts.extend(exact_conflicts)
    used_source.update(exact_source)
    used_target.update(exact_target)

    available_source = set(range(len(source.videos))) - used_source
    available_target = set(range(len(target.videos))) - used_target
    candidates = fallback_candidates(
        source,
        target,
        available_source=available_source,
        available_target=available_target,
        min_score=min_score,
        max_duration_delta_seconds=max_duration_delta_seconds,
    )
    fallback_matches, fallback_conflicts, fallback_source, fallback_target = fallback_components(
        source,
        target,
        candidates,
    )
    matches.extend(fallback_matches)
    conflicts.extend(fallback_conflicts)
    used_source.update(fallback_source)
    used_target.update(fallback_target)

    matches.sort(key=lambda item: (item.source_title.casefold(), item.source_ref.remote_id))
    conflicts.sort(
        key=lambda item: (
            item.reason,
            item.normalized_title or "",
            item.source_refs[0].remote_id,
            item.target_refs[0].remote_id,
        )
    )
    source_titles = collection_titles_by_video(source)
    target_titles = collection_titles_by_video(target)
    missing_on_target = [
        missing_video(video, source_titles)
        for index, video in enumerate(source.videos)
        if index not in used_source
    ]
    extra_on_target = [
        missing_video(video, target_titles)
        for index, video in enumerate(target.videos)
        if index not in used_target
    ]
    missing_on_target.sort(key=lambda item: (item.title.casefold(), item.ref.remote_id))
    extra_on_target.sort(key=lambda item: (item.title.casefold(), item.ref.remote_id))
    source_to_target_video = {item.source_ref.remote_id: item.target_ref.remote_id for item in matches}

    return CrossPlatformComparison(
        source_snapshot_id=str(source.snapshot_id),
        target_snapshot_id=str(target.snapshot_id),
        source_channel=source.channel.ref,
        target_channel=target.channel.ref,
        matches=matches,
        conflicts=conflicts,
        missing_on_target=missing_on_target,
        extra_on_target=extra_on_target,
        collection_gaps=build_collection_gaps(source, target, source_to_target_video),
    )
