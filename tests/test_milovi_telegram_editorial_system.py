from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MILOVI = ROOT / "content/telegram/milovi-cake"
MEDIA_MAP = MILOVI / "media-source-map-2026-08.json"
SEQUENCE = MILOVI / "editorial-sequence-30-posts-2026-08.json"
SCHOOL_SOURCES = MILOVI / "school-source-shortlist-2026-08.json"
ASSET_CONTRACT = MILOVI / "editorial-asset-contract-2026-08.md"
OPERATING_PLAN = MILOVI / "editorial-operating-plan-2026-08.md"
LAUNCH_PACK = MILOVI / "launch-pack-2026-08.md"


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_milovi_media_source_map_is_exact_finished_work_inventory() -> None:
    media_map = _load_json(MEDIA_MAP)
    items = media_map["items"]

    assert media_map["schema_name"] == "video-channel-manager.milovi-editorial-media-source-map"
    assert media_map["project_key"] == "milovi-cake"
    assert media_map["status"] == "provider_inert"
    assert media_map["source_repository"] == "FedorMilovanov/Milovi_Cake"
    assert media_map["source_path"] == "js/gallery/data.js"
    assert media_map["source_blob_sha"] == "e20e60c07479e8b20c1db700f1a40364b81eb669"
    assert media_map["production_bts_available"] is False
    assert isinstance(items, list)
    assert len(items) == media_map["declared_item_count"] == 46

    ids = [item["id"] for item in items]
    assert len(set(ids)) == 46

    types = Counter(item["type"] for item in items)
    assert types == {"photo": 30, "video": 16}
    assert media_map["declared_photo_count"] == 30
    assert media_map["declared_video_count"] == 16

    for item in items:
        assert item["id"]
        assert item["src"].startswith("/img/gallery/")
        assert item["title"]
        assert isinstance(item["tags"], list)
        if item["type"] == "video":
            assert item["src"].endswith(".webm")
            assert item["poster"].endswith(".webp")
        else:
            assert item["type"] == "photo"
            assert item["src"].endswith(".webp")
            assert item["full"].endswith("-hd.webp")

    v04 = next(item for item in items if item["id"] == "v04")
    assert v04["title"] == "Видео: меренговый рулет"
    assert "eclair" in v04["src"]
    assert "meringue roll" in v04["note"]


def test_milovi_editorial_sequence_is_30_slots_and_matches_no_bts_mix() -> None:
    media_map = _load_json(MEDIA_MAP)
    sequence = _load_json(SEQUENCE)
    items = media_map["items"]
    slots = sequence["slots"]
    target_mix = sequence["target_mix"]

    assert sequence["schema_name"] == "video-channel-manager.milovi-editorial-sequence"
    assert sequence["project_key"] == "milovi-cake"
    assert sequence["status"] == "provider_inert"
    assert sequence["publication_authorized"] is False
    assert sequence["production_bts_share"] == 0
    assert isinstance(slots, list)
    assert len(slots) == 30
    assert [slot["slot"] for slot in slots] == list(range(1, 31))

    actual_mix = Counter(slot["pillar"] for slot in slots)
    assert dict(actual_mix) == target_mix
    assert sum(target_mix.values()) == 30
    assert "bts" not in actual_mix
    assert "kitchen" not in actual_mix

    known_media_ids = {item["id"] for item in items}
    for slot in slots:
        assert slot["working_title"]
        assert isinstance(slot["media_ids"], list)
        assert set(slot["media_ids"]) <= known_media_ids
        if slot["pillar"] in {"finished_showcase", "finished_detail", "collection_poll", "commercial"}:
            assert slot["media_ids"]


def test_milovi_school_slots_have_exact_source_bindings() -> None:
    sequence = _load_json(SEQUENCE)
    shortlist = _load_json(SCHOOL_SOURCES)
    slots = sequence["slots"]
    articles = shortlist["articles"]

    assert shortlist["schema_name"] == "video-channel-manager.milovi-school-editorial-source-shortlist"
    assert shortlist["project_key"] == "milovi-cake"
    assert shortlist["status"] == "provider_inert"
    assert shortlist["source_repository"] == "FedorMilovanov/Milovi_School"
    assert shortlist["source_commit"] == "aa82176012b93a50ccfcfb90293d496618e50b61"
    assert shortlist["article_catalog_path"] == "src/data/articles.ts"
    assert shortlist["article_catalog_blob_sha"] == "5ef4cf1cb7db6e7bb6914607ec69d144b3d78cc5"
    assert shortlist["deep_content_path"] == "src/data/deepContents.ts"
    assert shortlist["deep_content_blob_sha"] == "d13e0dc0466ac1b73552729053043cf533dc9e39"
    assert isinstance(articles, list)
    assert len(articles) == 3

    known_school_ids = {article["id"] for article in articles}
    assert known_school_ids == {
        "paris-brest-race-dessert",
        "millefeuille-histoire",
        "creme-brulee-dispute",
    }

    school_slots = [slot for slot in slots if slot["pillar"] == "milovi_school"]
    assert len(school_slots) == 3
    assert {slot["school_article_id"] for slot in school_slots} == known_school_ids
    assert all(slot["media_ids"] == [] for slot in school_slots)

    for article in articles:
        assert article["public_url"].startswith("https://french.milovicake.ru/articles/")
        assert article["catalog_source_url"].startswith("https://")
        assert article["catalog_source_label"]
        assert "revalid" in article["telegram_claim_boundary"].lower()

    assert "Metadata binding is not enough for live copy" in shortlist["publication_rule"]


def test_milovi_no_bts_contract_controls_older_launch_copy() -> None:
    asset_contract = ASSET_CONTRACT.read_text(encoding="utf-8")
    operating_plan = OPERATING_PLAN.read_text(encoding="utf-8")
    launch_pack = LAUNCH_PACK.read_text(encoding="utf-8")

    assert "Production BTS / kitchen share: **0%**" in asset_contract
    assert "production/kitchen/BTS footage is unavailable" in operating_plan
    assert "не пытайтесь" not in operating_plan  # keep neutral repository voice

    safe_welcome = (
        "Здесь — реальные работы Milovi Cake, красивые детали и подборки, полезные подсказки перед заказом "
        "и короткие истории французской кондитерской культуры из Milovi School."
    )
    assert safe_welcome in operating_plan

    unsafe_legacy_phrase = "Здесь — реальные работы Milovi Cake, детали и процесс"
    if unsafe_legacy_phrase in launch_pack:
        assert "not publishable as written" in operating_plan
        assert "детали и процесс" in operating_plan


def test_milovi_editorial_files_remain_provider_inert() -> None:
    media_map = _load_json(MEDIA_MAP)
    sequence = _load_json(SEQUENCE)
    shortlist = _load_json(SCHOOL_SOURCES)
    operating_plan = OPERATING_PLAN.read_text(encoding="utf-8")

    assert media_map["status"] == "provider_inert"
    assert media_map["production_bts_available"] is False
    assert sequence["status"] == "provider_inert"
    assert sequence["publication_authorized"] is False
    assert sequence["production_bts_share"] == 0
    assert shortlist["status"] == "provider_inert"
    assert "provider-inert" in operating_plan
    assert "Live publication remains blocked" in operating_plan
