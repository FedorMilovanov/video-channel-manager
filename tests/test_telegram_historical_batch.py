from __future__ import annotations

import json
from pathlib import Path

import pytest

from video_channel_manager.telegram_historical_batch import (
    load_historical_v3_batch_manifest,
    preflight_historical_v3_batch,
    validate_historical_v3_red_team,
    validate_historical_v3_topic_controls,
)
from video_channel_manager.telegram_historical_bundle import HistoricalSourceShardV1
from video_channel_manager.telegram_historical_editorial import HistoricalSource
from video_channel_manager.telegram_historical_revision import load_historical_revision_git_blob_json

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path("content/telegram/lordchrist/historical-editorial/v1/v3/batch-manifest-2026-09-08.json")


def _manifest_payload() -> dict[str, object]:
    value = json.loads((REPO_ROOT / MANIFEST).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _write_manifest(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "batch-manifest.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _first_topic_inputs() -> tuple[object, tuple[HistoricalSource, ...]]:
    manifest = load_historical_v3_batch_manifest(MANIFEST, repo_root=REPO_ROOT)
    topic = manifest.topics[0]
    verification = load_historical_revision_git_blob_json(
        REPO_ROOT,
        topic.verification,
        label="test topic verification",
    )
    sources: list[HistoricalSource] = []
    for ref in topic.source_shards:
        shard = HistoricalSourceShardV1.model_validate(
            load_historical_revision_git_blob_json(REPO_ROOT, ref, label="test source shard")
        )
        sources.extend(shard.sources)
    return verification, tuple(sources)


def test_historical_v3_batch_preflight_seals_all_remaining_topics_without_live_authority() -> None:
    report = preflight_historical_v3_batch(MANIFEST, repo_root=REPO_ROOT)

    assert report.status == "PASS"
    assert report.topic_count == 8
    assert report.source_binding_count >= 16
    assert report.unique_source_count > 0
    assert report.claim_count >= 8
    assert report.visual_slot_count == 16
    assert report.materialized_media_count == 0
    assert report.red_team_url_count == 40
    assert report.provider_writes_authorized is False
    assert report.live_eligible is False
    assert report.provider_write_performed is False


def test_historical_v3_batch_manifest_contains_exact_remaining_eight_publications() -> None:
    manifest = load_historical_v3_batch_manifest(MANIFEST, repo_root=REPO_ROOT)
    publication_ids = {topic.publication_id for topic in manifest.topics}

    assert publication_ids == {
        "lordchrist-history-bunyan-bedford-prison-v3",
        "lordchrist-history-judson-burmese-bible-v3",
        "lordchrist-history-spurgeon-cholera-1854-v3",
        "lordchrist-history-carey-enquiry-missions-v3",
        "lordchrist-history-fuller-gospel-worthy-v3",
        "lordchrist-history-tyndale-new-testament-1526-v3",
        "lordchrist-history-stam-china-december-1934-v3",
        "lordchrist-history-sattler-schleitheim-1527-v3",
    }
    assert "lordchrist-history-spurgeon-down-grade-1887-v3" not in publication_ids


def test_historical_v3_batch_preflight_rejects_bound_post_blob_drift(tmp_path: Path) -> None:
    payload = _manifest_payload()
    topics = payload["topics"]
    assert isinstance(topics, list) and isinstance(topics[0], dict)
    post = topics[0]["post"]
    assert isinstance(post, dict)
    post["git_blob_sha"] = "0" * 40
    path = _write_manifest(tmp_path, payload)

    with pytest.raises(ValueError, match="Git blob differs"):
        preflight_historical_v3_batch(path, repo_root=REPO_ROOT)


def test_historical_v3_batch_schema_rejects_duplicate_publication_identity(tmp_path: Path) -> None:
    payload = _manifest_payload()
    topics = payload["topics"]
    assert isinstance(topics, list) and len(topics) == 8
    assert isinstance(topics[0], dict) and isinstance(topics[1], dict)
    topics[1]["publication_id"] = topics[0]["publication_id"]
    path = _write_manifest(tmp_path, payload)

    with pytest.raises(ValueError, match="publication ids must be unique"):
        load_historical_v3_batch_manifest(path, repo_root=REPO_ROOT)


def test_historical_v3_batch_schema_rejects_live_or_provider_authority(tmp_path: Path) -> None:
    payload = _manifest_payload()
    payload["live_eligible"] = True
    payload["provider_writes_authorized"] = True
    path = _write_manifest(tmp_path, payload)

    with pytest.raises(ValueError):
        load_historical_v3_batch_manifest(path, repo_root=REPO_ROOT)


def test_historical_v3_red_team_rejects_fewer_than_40_reviewed_urls() -> None:
    manifest = load_historical_v3_batch_manifest(MANIFEST, repo_root=REPO_ROOT)
    value = load_historical_revision_git_blob_json(
        REPO_ROOT,
        manifest.red_team,
        label="test red-team dossier",
    )
    assert isinstance(value, dict)
    value["reviewed_urls"] = 39

    with pytest.raises(ValueError, match="at least 40"):
        validate_historical_v3_red_team(value, manifest=manifest)


def test_historical_v3_topic_controls_reject_premature_visual_materialization() -> None:
    verification, sources = _first_topic_inputs()
    assert isinstance(verification, dict)
    visual_plan = verification["visual_plan"]
    assert isinstance(visual_plan, list) and isinstance(visual_plan[0], dict)
    visual_plan[0]["production_ready"] = True

    with pytest.raises(ValueError, match="prematurely materialized"):
        validate_historical_v3_topic_controls(
            verification,
            sources=sources,
            expected_visual_slots=2,
        )


def test_historical_v3_topic_controls_reject_unbound_evidence_family() -> None:
    verification, sources = _first_topic_inputs()
    assert isinstance(verification, dict)
    groups = verification["independent_evidence_groups_used_in_reader_claims"]
    assert isinstance(groups, list)
    groups.append("invented-evidence-family")

    with pytest.raises(ValueError, match="evidence groups"):
        validate_historical_v3_topic_controls(
            verification,
            sources=sources,
            expected_visual_slots=2,
        )


def test_historical_v3_topic_controls_require_upgrade_conditions() -> None:
    verification, sources = _first_topic_inputs()
    assert isinstance(verification, dict)
    verification.pop("claim_upgrade_conditions")

    with pytest.raises(ValueError, match="claim_upgrade_conditions"):
        validate_historical_v3_topic_controls(
            verification,
            sources=sources,
            expected_visual_slots=2,
        )
