from __future__ import annotations

from collections import Counter

from video_channel_manager.exchange.instagram_reels import (
    InstagramReelFactoryRegistry,
    InstagramReelJob,
    InstagramReelQueueArtifact,
    InstagramReelQueueRecord,
    ReelQueueStatus,
    ReelSourceState,
    SiteAudioReelSource,
    SiteEditorialReelSource,
    YouTubeReelSource,
)
from video_channel_manager.exchange.instagram_video import InstagramVideoRouteArtifact, InstagramVideoRouteRecord


class InstagramReelQueueError(ValueError):
    pass


def _youtube_route_map(route: InstagramVideoRouteArtifact | None) -> dict[str, InstagramVideoRouteRecord]:
    if route is None:
        return {}
    return {record.youtube_video_id: record for record in route.records}


def _source_state(
    source: YouTubeReelSource | SiteAudioReelSource | SiteEditorialReelSource,
    *,
    youtube_routes: dict[str, InstagramVideoRouteRecord],
) -> ReelSourceState:
    if isinstance(source, SiteAudioReelSource):
        return "site_audio_pinned"
    if isinstance(source, SiteEditorialReelSource):
        return "editorial_authority"

    route = youtube_routes.get(source.youtube_video_id)
    if route is None:
        return "youtube_route_missing"
    mapping: dict[str, ReelSourceState] = {
        "source_binding_required": "youtube_source_binding_required",
        "direct_remaster": "youtube_direct_remaster",
        "editorial_extract": "youtube_editorial_extract",
        "editorial_rebuild": "youtube_editorial_rebuild",
        "hold": "youtube_hold",
    }
    return mapping[route.route]


def _queue_record(
    job: InstagramReelJob,
    *,
    source_by_id: dict[str, YouTubeReelSource | SiteAudioReelSource | SiteEditorialReelSource],
    youtube_routes: dict[str, InstagramVideoRouteRecord],
) -> InstagramReelQueueRecord:
    states = {source_id: _source_state(source_by_id[source_id], youtube_routes=youtube_routes) for source_id in job.source_ids}

    blockers: list[str] = []
    if job.requires_clean_master:
        for source_id in job.source_ids:
            source = source_by_id[source_id]
            state = states[source_id]
            if isinstance(source, SiteAudioReelSource):
                blockers.append(f"materialize_pinned_site_audio:{source_id}")
            elif isinstance(source, SiteEditorialReelSource):
                blockers.append(f"clean_master_unbound:{source_id}")
            elif state == "youtube_route_missing":
                blockers.append(f"youtube_media_route_missing:{source_id}")
            elif state == "youtube_source_binding_required":
                blockers.append(f"clean_master_unbound:{source_id}")
            elif state == "youtube_editorial_rebuild":
                blockers.append(f"editorial_rebuild_required:{source_id}")
            elif state == "youtube_hold":
                blockers.append(f"media_route_hold:{source_id}")

    if job.requires_exact_text_span:
        blockers.append("exact_text_span_unbound")
    if job.requires_exact_timing:
        blockers.append("exact_timing_unselected")

    blockers = list(dict.fromkeys(blockers))
    blocker_prefixes = {item.split(":", 1)[0] for item in blockers}

    status: ReelQueueStatus
    if "media_route_hold" in blocker_prefixes:
        status = "hold"
    elif "editorial_rebuild_required" in blocker_prefixes:
        status = "editorial_rebuild_required"
    elif {"clean_master_unbound", "youtube_media_route_missing"} & blocker_prefixes:
        status = "source_binding_required"
    elif "materialize_pinned_site_audio" in blocker_prefixes:
        status = "materialization_required"
    elif "exact_text_span_unbound" in blocker_prefixes:
        status = "exact_text_binding_required"
    elif "exact_timing_unselected" in blocker_prefixes:
        status = "timing_selection_required"
    elif job.requires_clean_master:
        status = "media_edit_ready"
    else:
        status = "source_led_ready"

    return InstagramReelQueueRecord(
        reel_id=job.reel_id,
        family_id=job.family_id,
        subject=job.subject,
        source_ids=job.source_ids,
        status=status,
        blockers=tuple(blockers),
        source_states=states,
        requires_clean_master=job.requires_clean_master,
        requires_exact_text_span=job.requires_exact_text_span,
        requires_exact_timing=job.requires_exact_timing,
    )


def build_instagram_reel_queue(
    registry: InstagramReelFactoryRegistry,
    *,
    source_registry_sha256: str,
    media_route: InstagramVideoRouteArtifact | None = None,
    source_media_route_sha256: str | None = None,
) -> InstagramReelQueueArtifact:
    """Join the Reel factory with exact media routing without inventing missing evidence."""

    if media_route is None and source_media_route_sha256 is not None:
        raise InstagramReelQueueError("source_media_route_sha256 requires a media_route artifact")
    if media_route is not None:
        if source_media_route_sha256 is None:
            raise InstagramReelQueueError("media_route requires source_media_route_sha256")
        if media_route.project_key != registry.project_key:
            raise InstagramReelQueueError(
                f"media route project mismatch: {media_route.project_key} != {registry.project_key}"
            )

        expected_channels = {source.youtube_channel_id for source in registry.sources if isinstance(source, YouTubeReelSource)}
        if expected_channels and media_route.channel_id not in expected_channels:
            raise InstagramReelQueueError(
                f"media route channel mismatch: {media_route.channel_id} not in {sorted(expected_channels)}"
            )

    source_by_id = {source.source_id: source for source in registry.sources}
    youtube_routes = _youtube_route_map(media_route)
    records = tuple(
        _queue_record(job, source_by_id=source_by_id, youtube_routes=youtube_routes) for job in registry.jobs
    )
    dispositions = Counter(record.status for record in records)

    return InstagramReelQueueArtifact(
        project_key=registry.project_key,
        source_registry_sha256=source_registry_sha256,
        source_media_route_sha256=source_media_route_sha256,
        counts={
            "total": len(records),
            "source_led_ready": dispositions["source_led_ready"],
            "exact_text_binding_required": dispositions["exact_text_binding_required"],
            "source_binding_required": dispositions["source_binding_required"],
            "materialization_required": dispositions["materialization_required"],
            "timing_selection_required": dispositions["timing_selection_required"],
            "media_edit_ready": dispositions["media_edit_ready"],
            "editorial_rebuild_required": dispositions["editorial_rebuild_required"],
            "hold": dispositions["hold"],
        },
        records=records,
    )
