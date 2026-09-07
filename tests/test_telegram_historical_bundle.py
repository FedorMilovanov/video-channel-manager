from __future__ import annotations

from pathlib import Path

import pytest

from video_channel_manager.telegram_historical_bundle import (
    build_next_scaffold_from_manifest,
    materialize_historical_bundle,
    preflight_historical_bundle_manifest,
)
from video_channel_manager.telegram_historical_editorial import (
    HistoricalSourceRegistry,
    build_historical_rich_document,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path("content/telegram/lordchrist/historical-editorial/v1/cycles/2026-09-cycle-01/manifest.json")


def test_sealed_historical_bundle_materializes_against_real_repository_data() -> None:
    manifest, queue, registry, theology = materialize_historical_bundle(MANIFEST, repo_root=REPO_ROOT)

    assert manifest.state == "provider_inert"
    assert queue.live_eligible is False
    assert queue.schedule.provider_writes_authorized is False
    assert queue.schedule.backfill_policy == "none"
    assert queue.source_binding_kind == "catalog"
    assert queue.source_binding_path == manifest.source_catalog_path
    assert queue.source_binding_sha256 == manifest.source_catalog_sha256
    assert queue.source_registry_sha256 == registry.digest
    assert queue.verification.reviewed_urls == 69
    assert len(registry.sources) == 52
    assert len(queue.posts) == 9
    assert sum(len(post.claims) for post in queue.posts) == 27
    assert theology.profile_id == "lordchrist-historical-editorial-v1"


def test_sealed_historical_bundle_preflight_is_machine_readable_and_provider_inert() -> None:
    report = preflight_historical_bundle_manifest(MANIFEST, repo_root=REPO_ROOT)

    assert report.status == "PASS"
    assert report.source_count == 52
    assert report.grade_a_count >= 1
    assert report.grade_bplus_count >= 1
    assert report.independent_evidence_groups >= 2
    assert report.claim_count == 27
    assert report.direct_quote_count == 0
    assert report.controversy_post_count == 1
    assert report.martyrdom_post_count == 3
    assert report.image_plan_count == 3
    assert report.production_ready_image_count == 0
    assert report.provider_writes_authorized is False
    assert report.live_eligible is False
    assert report.backfill_policy == "none"


def test_every_sealed_post_builds_a_real_rich_article_document() -> None:
    _manifest, queue, registry, _theology = materialize_historical_bundle(MANIFEST, repo_root=REPO_ROOT)

    documents = [build_historical_rich_document(queue, post, registry) for post in queue.posts]

    assert len(documents) == 9
    assert len({document.document_id for document in documents}) == 9
    assert all(document.project_key == "lord-god-strength" for document in documents)
    assert all(document.metadata.language == "ru" for document in documents)
    assert all(document.sources for document in documents)
    assert sum(len(document.media_slots) for document in documents) == 3


def test_rich_builder_rejects_registry_identity_drift() -> None:
    _manifest, queue, registry, _theology = materialize_historical_bundle(MANIFEST, repo_root=REPO_ROOT)
    sources = list(registry.sources)
    sources[0] = sources[0].model_copy(update={"title": sources[0].title + " drift"})
    wrong_registry = HistoricalSourceRegistry(
        schema_name="video-channel-manager.telegram-historical-source-registry",
        schema_version=1,
        checked_on=registry.checked_on,
        sources=tuple(sources),
    )

    assert wrong_registry.digest != queue.source_registry_sha256
    with pytest.raises(ValueError, match="rich-document boundary"):
        build_historical_rich_document(queue, queue.posts[0], wrong_registry)


def test_next_cycle_scaffold_reuses_bound_catalog_without_authorizing_provider_writes() -> None:
    from datetime import date

    manifest, _queue, registry, _theology = materialize_historical_bundle(MANIFEST, repo_root=REPO_ROOT)
    scaffold = build_next_scaffold_from_manifest(
        MANIFEST,
        cycle_id="history-cycle-2026-10-01",
        start_on=date(2026, 10, 1),
        repo_root=REPO_ROOT,
    )

    assert scaffold.state == "draft_scaffold"
    assert scaffold.provider_writes_authorized is False
    assert scaffold.timezone == "Europe/Moscow"
    assert scaffold.local_time == "19:17"
    assert scaffold.source_binding_kind == "catalog"
    assert scaffold.source_binding_path == manifest.source_catalog_path
    assert scaffold.source_binding_sha256 == manifest.source_catalog_sha256
    assert scaffold.source_registry_sha256 == registry.digest
    assert len(scaffold.slots) == 9
    assert all(slot.scheduled_date.isoweekday() in (1, 3, 6) for slot in scaffold.slots)
