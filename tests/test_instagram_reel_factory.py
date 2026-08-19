from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from video_channel_manager.exchange.instagram_reels import (
    InstagramReelFactoryRegistry,
    SiteAudioReelSource,
    SiteEditorialReelSource,
    YouTubeReelSource,
)


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "content" / "instagram" / "legendary-poet-reels-factory.json"
PLAN_PATH = ROOT / "content" / "instagram" / "legendary-poet-reels-factory-plan.md"
MAPPING_PATH = ROOT / "content" / "mappings" / "youtube-vk-reviewed-20260727.json"
COMMENTS_DIR = ROOT / "content" / "youtube-comments"
CHANNEL_ID = "UC-78ys2S3cQ3lpqgXfo-SvQ"
SITE_COMMIT = "d371d1a79cd49359cc24b5b8c7dfd5c92114b92c"


def _registry() -> InstagramReelFactoryRegistry:
    return InstagramReelFactoryRegistry.model_validate_json(REGISTRY_PATH.read_text(encoding="utf-8"))


def _markdown_reel_ids() -> set[str]:
    text = PLAN_PATH.read_text(encoding="utf-8")
    return set(re.findall(r"^### ([A-Z]+-R\d{2})\b", text, flags=re.MULTILINE))


def test_registry_is_typed_provider_inert_and_exactly_59_jobs() -> None:
    registry = _registry()

    assert registry.project_key == "legendary-poet"
    assert registry.status == "provider-inert"
    assert registry.provider_effect == "impossible"
    assert registry.provider_writes_authorized is False
    assert registry.declared_job_count == 59
    assert len(registry.jobs) == 59
    assert len({job.reel_id for job in registry.jobs}) == 59


def test_registry_and_reviewed_markdown_plan_have_exact_same_reel_ids() -> None:
    registry = _registry()

    assert {job.reel_id for job in registry.jobs} == _markdown_reel_ids()


def test_registry_family_distribution_is_the_reviewed_factory_distribution() -> None:
    registry = _registry()
    counts = Counter(job.family_id for job in registry.jobs)

    assert counts == {
        "black-man": 6,
        "kulikovo": 5,
        "fet-whisper": 4,
        "oleg": 4,
        "golden-grove": 4,
        "night-sea": 4,
        "blok-live": 4,
        "yesenin-riddle": 3,
        "site-tired": 4,
        "site-cloud": 4,
        "site-russia": 4,
        "lermontov-road": 4,
        "onegin": 4,
        "mayakovsky": 5,
    }


def test_youtube_factory_sources_are_exact_project_ids_with_reviewed_records() -> None:
    registry = _registry()
    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))

    youtube_sources = [source for source in registry.sources if isinstance(source, YouTubeReelSource)]
    assert len(youtube_sources) == 9
    for source in youtube_sources:
        assert source.youtube_channel_id == CHANNEL_ID
        assert source.youtube_video_id in mapping
        assert source.reviewed_editorial_record == f"content/youtube-comments/{source.youtube_video_id}.json"
        assert (COMMENTS_DIR / f"{source.youtube_video_id}.json").is_file()


def test_site_sources_are_pinned_to_one_exact_current_site_commit() -> None:
    registry = _registry()

    assert registry.source_site_repository == "FedorMilovanov/TheLegendaryPoet"
    assert registry.source_site_commit_sha == SITE_COMMIT
    site_sources = [
        source
        for source in registry.sources
        if isinstance(source, (SiteAudioReelSource, SiteEditorialReelSource))
    ]
    assert len(site_sources) == 7
    assert {source.commit_sha for source in site_sources} == {SITE_COMMIT}


def test_site_audio_sources_freeze_exact_master_identity_from_site_catalog() -> None:
    registry = _registry()
    audio_sources = {
        source.source_id: source
        for source in registry.sources
        if isinstance(source, SiteAudioReelSource)
    }

    assert set(audio_sources) == {
        "site-audio:yesenin-ya-ustalym",
        "site-audio:pushkin-tucha",
        "site-audio:blok-rossiya",
    }
    assert audio_sources["site-audio:yesenin-ya-ustalym"].asset_sha256 == (
        "sha256:2f5b7c0a9b83be4685d0d83728e5896c8adde78b75b46dad361eddfb28356381"
    )
    assert audio_sources["site-audio:pushkin-tucha"].asset_sha256 == (
        "sha256:1d4f77fb01ccd31a4fe8934281fc7771157b7f9a0373529ca97ad0aafa86ff30"
    )
    assert audio_sources["site-audio:blok-rossiya"].asset_sha256 == (
        "sha256:feb6d1607278fce8621000a542e76e075cca5a6b44cf63c0a9db67603b943c9d"
    )


def test_no_reel_job_contains_fake_timing_placeholder() -> None:
    registry = _registry()

    forbidden = ("best 20", "best 30", "00:", "chorus", "strong moment")
    for job in registry.jobs:
        combined = f"{job.hook or ''} {job.brief}".lower()
        assert not any(marker in combined for marker in forbidden)
        if job.requires_exact_timing:
            assert job.requires_clean_master is True
