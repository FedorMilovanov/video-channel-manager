from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

from video_channel_manager.editorial.article_sources import validate_article_source_bundle
from video_channel_manager.platforms.vk.catalog_policy import parse_vk_catalog_policy

_ROOT = Path(__file__).resolve().parents[1]
_SLUG = "aleksandr-blok-na-pole-kulikovom"


def _load_wall_builder() -> ModuleType:
    path = _ROOT / "scripts" / "build_vk_wall_post_plan.py"
    spec = importlib.util.spec_from_file_location("real_build_vk_wall_post_plan", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_real_blok_article_matches_its_source_ledger() -> None:
    article_path = _ROOT / "content" / "video-articles" / f"{_SLUG}.md"
    ledger_path = _ROOT / "content" / "video-articles" / f"{_SLUG}.sources.json"
    article = article_path.read_text(encoding="utf-8")
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))

    summary = validate_article_source_bundle(article, ledger)

    assert summary["claims"] >= 8
    assert summary["sources"] >= 10


def test_real_blok_wall_message_contains_every_reviewed_link_once() -> None:
    builder = _load_wall_builder()
    message_path = _ROOT / "content" / "wall-posts" / f"{_SLUG}.txt"
    sources_path = _ROOT / "content" / "wall-posts" / f"{_SLUG}.sources.json"
    message = message_path.read_text(encoding="utf-8")
    sources = builder._load_sources(sources_path)

    builder._validate_visible_links(message, sources=sources, article_url=None)


def test_real_catalog_policy_is_valid_and_skips_empty_albums() -> None:
    policy_path = _ROOT / "content" / "policies" / "vk-catalog-policy.json"
    policy = parse_vk_catalog_policy(json.loads(policy_path.read_text(encoding="utf-8")))

    assert policy.skip_collections_without_mapped_videos is True
    assert policy.title_overrides
    assert policy.sha256.startswith("sha256:")


def test_reviewed_mapping_has_unique_eleven_source_and_target_ids() -> None:
    mapping_path = _ROOT / "content" / "mappings" / "youtube-vk-reviewed-20260725.json"
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))

    assert len(mapping) == 11
    assert len(set(mapping)) == 11
    assert len(set(mapping.values())) == 11
    assert mapping["U4D40EQg10U"] == "-235216998_456239142"
