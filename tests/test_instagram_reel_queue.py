from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from video_channel_manager.editorial.instagram_reel_queue import (
    InstagramReelQueueError,
    build_instagram_reel_queue,
)
from video_channel_manager.exchange.instagram_reels import InstagramReelFactoryRegistry
from video_channel_manager.exchange.instagram_video import InstagramVideoRouteArtifact


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "content" / "instagram" / "legendary-poet-reels-factory.json"
REGISTRY_SHA = "sha256:" + "a" * 64
ROUTE_SHA = "sha256:" + "b" * 64
CHANNEL_ID = "UC-78ys2S3cQ3lpqgXfo-SvQ"


def _registry() -> InstagramReelFactoryRegistry:
    return InstagramReelFactoryRegistry.model_validate_json(REGISTRY_PATH.read_text(encoding="utf-8"))


def _route(video_id: str, route: str) -> InstagramVideoRouteArtifact:
    counts = Counter({route: 1})
    return InstagramVideoRouteArtifact.model_validate(
        {
            "project_key": "legendary-poet",
            "channel_id": CHANNEL_ID,
            "source_intake_sha256": "sha256:" + "c" * 64,
            "counts": {
                "total": 1,
                "source_binding_required": counts["source_binding_required"],
                "direct_remaster": counts["direct_remaster"],
                "editorial_extract": counts["editorial_extract"],
                "editorial_rebuild": counts["editorial_rebuild"],
                "hold": counts["hold"],
            },
            "records": [
                {
                    "youtube_video_id": video_id,
                    "title": "Video",
                    "route": route,
                    "reasons": ["test"],
                    "source_geometry": "vertical" if route == "direct_remaster" else "non_vertical",
                    "reviewed_editorial_record": f"content/youtube-comments/{video_id}.json",
                    "provider_writes_authorized": False,
                }
            ],
        }
    )


def _record(result, reel_id: str):
    return next(record for record in result.records if record.reel_id == reel_id)


def test_real_factory_without_media_route_has_exact_baseline_partition() -> None:
    result = build_instagram_reel_queue(_registry(), source_registry_sha256=REGISTRY_SHA)

    assert result.provider_writes_authorized is False
    assert result.counts.total == 59
    assert result.counts.source_led_ready == 40
    assert result.counts.exact_text_binding_required == 8
    assert result.counts.source_binding_required == 8
    assert result.counts.materialization_required == 3
    assert result.counts.timing_selection_required == 0
    assert result.counts.media_edit_ready == 0
    assert result.counts.editorial_rebuild_required == 0
    assert result.counts.hold == 0


def test_source_led_job_does_not_depend_on_missing_youtube_media_route() -> None:
    result = build_instagram_reel_queue(_registry(), source_registry_sha256=REGISTRY_SHA)

    record = _record(result, "BM-R01")
    assert record.status == "source_led_ready"
    assert record.source_states["youtube:mw-dYETmPIE"] == "youtube_route_missing"
    assert record.blockers == ()


def test_master_timed_youtube_job_moves_to_timing_after_direct_master_route() -> None:
    registry = _registry()
    route = _route("mFsty3NOEMs", "direct_remaster")
    result = build_instagram_reel_queue(
        registry,
        source_registry_sha256=REGISTRY_SHA,
        media_route=route,
        source_media_route_sha256=ROUTE_SHA,
    )

    record = _record(result, "GROVE-R04")
    assert record.status == "timing_selection_required"
    assert record.source_states["youtube:mFsty3NOEMs"] == "youtube_direct_remaster"
    assert record.blockers == ("exact_timing_unselected",)


def test_master_timed_job_with_text_gate_requires_text_before_timing() -> None:
    registry = _registry()
    route = _route("K-x6neQiyfs", "editorial_extract")
    result = build_instagram_reel_queue(
        registry,
        source_registry_sha256=REGISTRY_SHA,
        media_route=route,
        source_media_route_sha256=ROUTE_SHA,
    )

    record = _record(result, "OLEG-R04")
    assert record.status == "exact_text_binding_required"
    assert record.source_states["youtube:K-x6neQiyfs"] == "youtube_editorial_extract"
    assert record.blockers == ("exact_text_span_unbound", "exact_timing_unselected")


def test_media_route_hold_propagates_to_master_dependent_reel() -> None:
    result = build_instagram_reel_queue(
        _registry(),
        source_registry_sha256=REGISTRY_SHA,
        media_route=_route("RQIlUvFf1KQ", "hold"),
        source_media_route_sha256=ROUTE_SHA,
    )

    record = _record(result, "SEA-R04")
    assert record.status == "hold"
    assert "media_route_hold:youtube:RQIlUvFf1KQ" in record.blockers


def test_editorial_rebuild_route_propagates_to_master_dependent_reel() -> None:
    result = build_instagram_reel_queue(
        _registry(),
        source_registry_sha256=REGISTRY_SHA,
        media_route=_route("jkaayeq7q8g", "editorial_rebuild"),
        source_media_route_sha256=ROUTE_SHA,
    )

    record = _record(result, "FET-R04")
    assert record.status == "editorial_rebuild_required"
    assert "editorial_rebuild_required:youtube:jkaayeq7q8g" in record.blockers


def test_site_audio_master_job_requires_materialization_not_fake_media_ready() -> None:
    result = build_instagram_reel_queue(_registry(), source_registry_sha256=REGISTRY_SHA)

    record = _record(result, "TIRED-R01")
    assert record.status == "materialization_required"
    assert record.source_states["site-audio:yesenin-ya-ustalym"] == "site_audio_pinned"
    assert "materialize_pinned_site_audio:site-audio:yesenin-ya-ustalym" in record.blockers


def test_site_editorial_performance_job_requires_clean_master_binding() -> None:
    result = build_instagram_reel_queue(_registry(), source_registry_sha256=REGISTRY_SHA)

    record = _record(result, "ONEGIN-R04")
    assert record.status == "source_binding_required"
    assert record.source_states["site-editorial:pushkin-library"] == "editorial_authority"
    assert "clean_master_unbound:site-editorial:pushkin-library" in record.blockers


def test_cross_project_media_route_fails_closed() -> None:
    route = _route("mw-dYETmPIE", "direct_remaster").model_copy(update={"project_key": "lord-god-strength"})

    with pytest.raises(InstagramReelQueueError, match="project mismatch"):
        build_instagram_reel_queue(
            _registry(),
            source_registry_sha256=REGISTRY_SHA,
            media_route=route,
            source_media_route_sha256=ROUTE_SHA,
        )


def test_route_digest_without_route_is_rejected() -> None:
    with pytest.raises(InstagramReelQueueError, match="requires a media_route"):
        build_instagram_reel_queue(
            _registry(),
            source_registry_sha256=REGISTRY_SHA,
            source_media_route_sha256=ROUTE_SHA,
        )
