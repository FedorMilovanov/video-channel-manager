from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Set

from video_channel_manager.editorial._project_profiles import PROJECT_CHANNEL_IDS
from video_channel_manager.exchange.instagram_historical_backlog import (
    InstagramHistoricalBacklogArtifact,
    InstagramHistoricalBacklogCounts,
    InstagramHistoricalBacklogRecord,
)
from video_channel_manager.exchange.instagram_reels import InstagramReelFactoryRegistry, YouTubeReelSource


class InstagramHistoricalBacklogError(ValueError):
    pass


def _factory_reels_by_youtube_id(registry: InstagramReelFactoryRegistry) -> dict[str, tuple[str, ...]]:
    youtube_source_ids = {
        source.source_id: source.youtube_video_id
        for source in registry.sources
        if isinstance(source, YouTubeReelSource)
    }
    reel_ids: dict[str, list[str]] = defaultdict(list)
    for job in registry.jobs:
        for source_id in job.source_ids:
            youtube_video_id = youtube_source_ids.get(source_id)
            if youtube_video_id is not None:
                reel_ids[youtube_video_id].append(job.reel_id)
    return {video_id: tuple(sorted(ids)) for video_id, ids in reel_ids.items()}


def build_instagram_historical_backlog(
    registry: InstagramReelFactoryRegistry,
    *,
    historical_mapping: Mapping[str, str],
    reviewed_video_ids: Set[str],
    youtube_channel_id: str,
    source_mapping_sha256: str,
    source_reviewed_corpus_sha256: str,
    source_registry_sha256: str,
) -> InstagramHistoricalBacklogArtifact:
    """Partition an exact historical identity floor without claiming current provider state."""

    expected_channels = PROJECT_CHANNEL_IDS.get(registry.project_key, frozenset())
    if youtube_channel_id not in expected_channels:
        raise InstagramHistoricalBacklogError(
            f"channel {youtube_channel_id!r} is not canonical for project {registry.project_key!r}"
        )

    factory_sources = [source for source in registry.sources if isinstance(source, YouTubeReelSource)]
    wrong_channels = sorted(
        source.youtube_video_id for source in factory_sources if source.youtube_channel_id != youtube_channel_id
    )
    if wrong_channels:
        raise InstagramHistoricalBacklogError(
            f"factory contains YouTube sources from a different channel: {wrong_channels}"
        )

    normalized_mapping: dict[str, str] = {}
    for raw_video_id, raw_vk_id in historical_mapping.items():
        video_id = raw_video_id.strip()
        vk_id = raw_vk_id.strip()
        if not video_id or not vk_id:
            raise InstagramHistoricalBacklogError("historical mapping contains an empty identity")
        if video_id in normalized_mapping:
            raise InstagramHistoricalBacklogError(f"duplicate historical YouTube ID: {video_id}")
        normalized_mapping[video_id] = vk_id

    historical_ids = set(normalized_mapping)
    reviewed_ids = {video_id.strip() for video_id in reviewed_video_ids if video_id.strip()}
    factory_reels = _factory_reels_by_youtube_id(registry)
    factory_ids = set(factory_reels)

    reviewed_outside = tuple(sorted(reviewed_ids - historical_ids))
    factory_outside = tuple(sorted(factory_ids - historical_ids))

    records: list[InstagramHistoricalBacklogRecord] = []
    for video_id in sorted(historical_ids):
        reviewed = video_id in reviewed_ids
        reel_ids = factory_reels.get(video_id, ())
        if reel_ids:
            if not reviewed:
                raise InstagramHistoricalBacklogError(
                    f"historical factory source lacks reviewed editorial authority: {video_id}"
                )
            action = "already_covered"
        elif reviewed:
            action = "design_reel_jobs"
        else:
            action = "build_editorial_record"

        records.append(
            InstagramHistoricalBacklogRecord(
                youtube_video_id=video_id,
                exact_vk_video_id=normalized_mapping[video_id],
                reviewed_editorial_record=(f"content/youtube-comments/{video_id}.json" if reviewed else None),
                factory_reel_ids=reel_ids,
                action=action,
            )
        )

    already_covered = sum(record.action == "already_covered" for record in records)
    design_reel_jobs = sum(record.action == "design_reel_jobs" for record in records)
    build_editorial_record = sum(record.action == "build_editorial_record" for record in records)

    return InstagramHistoricalBacklogArtifact(
        project_key=registry.project_key,
        youtube_channel_id=youtube_channel_id,
        source_mapping_sha256=source_mapping_sha256,
        source_reviewed_corpus_sha256=source_reviewed_corpus_sha256,
        source_registry_sha256=source_registry_sha256,
        reviewed_ids_outside_historical_floor=reviewed_outside,
        factory_youtube_sources_outside_historical_floor=factory_outside,
        counts=InstagramHistoricalBacklogCounts(
            total_historical_floor_ids=len(records),
            already_covered=already_covered,
            design_reel_jobs=design_reel_jobs,
            build_editorial_record=build_editorial_record,
            reviewed_ids_outside_historical_floor=len(reviewed_outside),
            factory_youtube_sources_outside_historical_floor=len(factory_outside),
        ),
        records=tuple(records),
    )
