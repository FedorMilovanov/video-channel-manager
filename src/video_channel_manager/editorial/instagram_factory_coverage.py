from __future__ import annotations

from collections import Counter, defaultdict

from video_channel_manager.exchange.instagram_factory_coverage import (
    InstagramFactoryCoverageArtifact,
    InstagramFactoryCoverageRecord,
)
from video_channel_manager.exchange.instagram_reels import (
    InstagramReelFactoryRegistry,
    YouTubeReelSource,
)
from video_channel_manager.exchange.instagram_video import InstagramVideoIntakeArtifact


class InstagramFactoryCoverageError(ValueError):
    pass


def build_instagram_factory_coverage(
    intake: InstagramVideoIntakeArtifact,
    registry: InstagramReelFactoryRegistry,
    *,
    source_intake_sha256: str,
    source_registry_sha256: str,
) -> InstagramFactoryCoverageArtifact:
    """Prove that every current YouTube video has one explicit Reel-factory coverage state."""

    if intake.project_key != registry.project_key:
        raise InstagramFactoryCoverageError(
            f"project mismatch: intake={intake.project_key} registry={registry.project_key}"
        )

    youtube_sources = [source for source in registry.sources if isinstance(source, YouTubeReelSource)]
    source_channels = {source.youtube_channel_id for source in youtube_sources}
    if source_channels and source_channels != {intake.channel_id}:
        raise InstagramFactoryCoverageError(
            f"factory YouTube channel mismatch: intake={intake.channel_id} registry={sorted(source_channels)}"
        )

    reel_ids_by_video: dict[str, list[str]] = defaultdict(list)
    source_to_video = {source.source_id: source.youtube_video_id for source in youtube_sources}
    for job in registry.jobs:
        for source_id in job.source_ids:
            video_id = source_to_video.get(source_id)
            if video_id is not None:
                reel_ids_by_video[video_id].append(job.reel_id)

    intake_ids = {record.youtube_video_id for record in intake.records}
    factory_video_ids = set(source_to_video.values())
    missing_factory_sources = tuple(sorted(factory_video_ids - intake_ids))

    records: list[InstagramFactoryCoverageRecord] = []
    for source_record in intake.records:
        reel_ids = tuple(sorted(set(reel_ids_by_video.get(source_record.youtube_video_id, []))))
        if reel_ids:
            coverage_status = "covered_by_factory"
        elif source_record.reviewed_editorial_record is not None:
            coverage_status = "reviewed_unexpanded"
        else:
            coverage_status = "editorial_review_required"

        records.append(
            InstagramFactoryCoverageRecord(
                youtube_video_id=source_record.youtube_video_id,
                title=source_record.title,
                youtube_format_status=source_record.youtube_format_status,
                youtube_short_candidate=source_record.youtube_short_candidate,
                reviewed_editorial_record=source_record.reviewed_editorial_record,
                coverage_status=coverage_status,
                reel_ids=reel_ids,
            )
        )

    dispositions = Counter(record.coverage_status for record in records)
    return InstagramFactoryCoverageArtifact(
        project_key=intake.project_key,
        channel_id=intake.channel_id,
        source_intake_sha256=source_intake_sha256,
        source_registry_sha256=source_registry_sha256,
        factory_sources_missing_from_current_snapshot=missing_factory_sources,
        counts={
            "total_current_videos": len(records),
            "covered_by_factory": dispositions["covered_by_factory"],
            "reviewed_unexpanded": dispositions["reviewed_unexpanded"],
            "editorial_review_required": dispositions["editorial_review_required"],
            "factory_reel_jobs": len(registry.jobs),
            "factory_youtube_sources": len(factory_video_ids),
            "current_factory_sources": len(factory_video_ids & intake_ids),
            "factory_sources_missing_from_current_snapshot": len(missing_factory_sources),
        },
        records=tuple(records),
    )
