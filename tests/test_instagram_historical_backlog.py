from __future__ import annotations

import json
from pathlib import Path

import pytest

from video_channel_manager.editorial.instagram_historical_backlog import (
    InstagramHistoricalBacklogError,
    build_instagram_historical_backlog,
)
from video_channel_manager.exchange.instagram_reels import InstagramReelFactoryRegistry


ROOT = Path(__file__).resolve().parents[1]
MAPPING_PATH = ROOT / "content" / "mappings" / "youtube-vk-reviewed-20260727.json"
COMMENTS_DIR = ROOT / "content" / "youtube-comments"
REGISTRY_PATH = ROOT / "content" / "instagram" / "legendary-poet-reels-factory.json"
CHANNEL_ID = "UC-78ys2S3cQ3lpqgXfo-SvQ"
DIGEST = "sha256:" + "a" * 64


def _mapping() -> dict[str, str]:
    payload = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return {str(key): str(value) for key, value in payload.items()}


def _reviewed_ids() -> set[str]:
    ids: set[str] = set()
    for path in COMMENTS_DIR.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["channel_id"] == CHANNEL_ID
        assert payload["video_id"] == path.stem
        ids.add(path.stem)
    return ids


def _registry() -> InstagramReelFactoryRegistry:
    return InstagramReelFactoryRegistry.model_validate_json(REGISTRY_PATH.read_text(encoding="utf-8"))


def _build(*, reviewed_ids: set[str] | None = None):
    return build_instagram_historical_backlog(
        _registry(),
        historical_mapping=_mapping(),
        reviewed_video_ids=_reviewed_ids() if reviewed_ids is None else reviewed_ids,
        youtube_channel_id=CHANNEL_ID,
        source_mapping_sha256=DIGEST,
        source_reviewed_corpus_sha256=DIGEST,
        source_registry_sha256=DIGEST,
    )


def test_repository_historical_floor_is_exactly_partitioned_111_9_6_96() -> None:
    result = _build()

    assert result.evidence_scope == "historical_floor_not_current_provider_state"
    assert result.provider_effect == "impossible"
    assert result.provider_writes_authorized is False
    assert result.counts.total_historical_floor_ids == 111
    assert result.counts.already_covered == 9
    assert result.counts.design_reel_jobs == 6
    assert result.counts.build_editorial_record == 96
    assert result.counts.reviewed_ids_outside_historical_floor == 0
    assert result.counts.factory_youtube_sources_outside_historical_floor == 0
    assert len(result.records) == 111
    assert tuple(record.youtube_video_id for record in result.records) == tuple(
        sorted(record.youtube_video_id for record in result.records)
    )


def test_historical_actions_preserve_exact_mapping_and_evidence_state() -> None:
    result = _build()
    by_id = {record.youtube_video_id: record for record in result.records}

    covered = by_id["mw-dYETmPIE"]
    assert covered.action == "already_covered"
    assert covered.reviewed_editorial_record == "content/youtube-comments/mw-dYETmPIE.json"
    assert len(covered.factory_reel_ids) == 6
    assert covered.exact_vk_video_id == _mapping()["mw-dYETmPIE"]

    reviewed = by_id["2GQ-T6dYH3E"]
    assert reviewed.action == "design_reel_jobs"
    assert reviewed.reviewed_editorial_record == "content/youtube-comments/2GQ-T6dYH3E.json"
    assert reviewed.factory_reel_ids == ()

    unreviewed = by_id["-3GkI8wip-w"]
    assert unreviewed.action == "build_editorial_record"
    assert unreviewed.reviewed_editorial_record is None
    assert unreviewed.factory_reel_ids == ()


def test_historical_backlog_fails_if_factory_coverage_loses_editorial_authority() -> None:
    reviewed_ids = _reviewed_ids()
    reviewed_ids.remove("mw-dYETmPIE")

    with pytest.raises(InstagramHistoricalBacklogError, match="lacks reviewed editorial authority"):
        _build(reviewed_ids=reviewed_ids)


def test_historical_backlog_rejects_cross_project_channel() -> None:
    with pytest.raises(InstagramHistoricalBacklogError, match="is not canonical"):
        build_instagram_historical_backlog(
            _registry(),
            historical_mapping=_mapping(),
            reviewed_video_ids=_reviewed_ids(),
            youtube_channel_id="UCeSJsC6go2c9pdJCuUI1BYA",
            source_mapping_sha256=DIGEST,
            source_reviewed_corpus_sha256=DIGEST,
            source_registry_sha256=DIGEST,
        )
