from __future__ import annotations

from pathlib import Path

import pytest

from video_channel_manager.editorial.instagram_factory_coverage import (
    InstagramFactoryCoverageError,
    build_instagram_factory_coverage,
)
from video_channel_manager.exchange.instagram_reels import InstagramReelFactoryRegistry
from video_channel_manager.exchange.instagram_video import InstagramVideoIntakeArtifact


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "content" / "instagram" / "legendary-poet-reels-factory.json"
CHANNEL_ID = "UC-78ys2S3cQ3lpqgXfo-SvQ"
INTAKE_SHA = "sha256:" + "a" * 64
REGISTRY_SHA = "sha256:" + "b" * 64


def _registry() -> InstagramReelFactoryRegistry:
    return InstagramReelFactoryRegistry.model_validate_json(REGISTRY_PATH.read_text(encoding="utf-8"))


def _record(video_id: str, *, reviewed: bool) -> dict[str, object]:
    return {
        "youtube_video_id": video_id,
        "title": video_id,
        "duration_seconds": 120,
        "published_at": None,
        "privacy_status": "public",
        "tags": [],
        "thumbnail_url": None,
        "revision": f"sha256:{video_id}",
        "present_in_frozen_mapping": True,
        "exact_vk_video_id": None,
        "reviewed_editorial_record": f"content/youtube-comments/{video_id}.json" if reviewed else None,
        "youtube_format_status": "unknown",
        "youtube_format_reason": "insufficient_exact_surface_evidence",
        "youtube_short_candidate": False,
        "youtube_file_details_available": False,
        "youtube_source_geometry": "unknown",
        "youtube_source_width_pixels": None,
        "youtube_source_height_pixels": None,
        "youtube_source_duration_ms": None,
        "youtube_source_creation_time": None,
        "clean_master_status": "unbound",
        "instagram_route": "source_binding_required",
        "provider_writes_authorized": False,
    }


def _intake() -> InstagramVideoIntakeArtifact:
    records = [
        _record("mw-dYETmPIE", reviewed=True),
        _record("2GQ-T6dYH3E", reviewed=True),
        _record("AAAAAAAAAAA", reviewed=False),
    ]
    return InstagramVideoIntakeArtifact.model_validate(
        {
            "project_key": "legendary-poet",
            "channel_id": CHANNEL_ID,
            "source_snapshot_id": "00000000-0000-0000-0000-000000000001",
            "source_generated_at": "2026-08-20T00:00:00+00:00",
            "source_evidence": {"audit_package_sha256": "sha256:" + "c" * 64},
            "counts": {
                "current_videos": 3,
                "frozen_mapping_ids": 3,
                "reviewed_editorial_ids": 2,
                "current_also_in_frozen_mapping": 3,
                "new_current_vs_frozen_mapping": 0,
                "historical_mapped_missing_from_current_snapshot": 0,
                "confirmed_short": 0,
                "confirmed_longform": 0,
                "format_unknown": 3,
                "short_candidates": 0,
                "file_details_available": 0,
                "source_geometry_known": 0,
            },
            "reconciliation": {
                "new_current_ids": [],
                "historical_mapped_missing_from_current_snapshot": [],
                "reviewed_missing_from_current_snapshot": [],
            },
            "classification_policy": {
                "shorts": "fail closed",
                "longform": "fail closed",
                "owner_file_details_used": True,
                "published_at_is_not_upload_time": True,
                "file_creation_time_is_not_upload_time": True,
                "unknown_is_not_excluded": True,
                "social_delivery_encoding_is_not_source_master": True,
            },
            "records": records,
        }
    )


def test_factory_coverage_partitions_every_current_video_exactly_once() -> None:
    result = build_instagram_factory_coverage(
        _intake(),
        _registry(),
        source_intake_sha256=INTAKE_SHA,
        source_registry_sha256=REGISTRY_SHA,
    )

    assert result.provider_effect == "impossible"
    assert result.provider_writes_authorized is False
    assert result.counts.total_current_videos == 3
    assert result.counts.covered_by_factory == 1
    assert result.counts.reviewed_unexpanded == 1
    assert result.counts.editorial_review_required == 1
    assert result.counts.factory_reel_jobs == 59
    assert result.counts.factory_youtube_sources == 9
    assert result.counts.current_factory_sources == 1
    assert result.counts.factory_sources_missing_from_current_snapshot == 8

    by_id = {record.youtube_video_id: record for record in result.records}
    assert by_id["mw-dYETmPIE"].coverage_status == "covered_by_factory"
    assert set(by_id["mw-dYETmPIE"].reel_ids) == {
        "BM-R01",
        "BM-R02",
        "BM-R03",
        "BM-R04",
        "BM-R05",
        "BM-R06",
    }
    assert by_id["2GQ-T6dYH3E"].coverage_status == "reviewed_unexpanded"
    assert by_id["2GQ-T6dYH3E"].reel_ids == ()
    assert by_id["AAAAAAAAAAA"].coverage_status == "editorial_review_required"


def test_factory_sources_missing_from_snapshot_are_explicit_not_silently_dropped() -> None:
    result = build_instagram_factory_coverage(
        _intake(),
        _registry(),
        source_intake_sha256=INTAKE_SHA,
        source_registry_sha256=REGISTRY_SHA,
    )

    assert "mw-dYETmPIE" not in result.factory_sources_missing_from_current_snapshot
    assert len(result.factory_sources_missing_from_current_snapshot) == 8
    assert tuple(sorted(result.factory_sources_missing_from_current_snapshot)) == (
        result.factory_sources_missing_from_current_snapshot
    )


def test_cross_project_registry_join_fails_closed() -> None:
    registry = _registry().model_copy(update={"project_key": "lord-god-strength"})

    with pytest.raises(InstagramFactoryCoverageError, match="project mismatch"):
        build_instagram_factory_coverage(
            _intake(),
            registry,
            source_intake_sha256=INTAKE_SHA,
            source_registry_sha256=REGISTRY_SHA,
        )
