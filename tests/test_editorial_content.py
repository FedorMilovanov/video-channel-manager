from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from video_channel_manager.editorial.content import (
    CANONICAL_SCHEMA_NAME,
    LEGENDARY_POET,
    LORD_GOD_STRENGTH,
    parse_content_record,
    validate_content_collection,
    validate_content_record,
)


def _example_payload() -> dict[str, object]:
    path = Path(__file__).resolve().parents[1] / "content" / "editorial" / "examples" / "tyutchev-night-sea.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _legacy_payload() -> dict[str, object]:
    path = Path(__file__).resolve().parents[1] / "content" / "youtube-comments" / "RQIlUvFf1KQ.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _lord_god_payload() -> dict[str, object]:
    payload = deepcopy(_example_payload())
    payload["project_key"] = LORD_GOD_STRENGTH
    payload["channel_id"] = "UCeSJsC6go2c9pdJCuUI1BYA"
    payload["content_id"] = "lord-god-strength-example"
    payload["variation_key"] = "lord-god-strength-example-v1"
    links = payload["links"]
    assert isinstance(links, list)
    site = links[0]
    vk = links[2]
    assert isinstance(site, dict)
    assert isinstance(vk, dict)
    site["label"] = "📌 *Господь Бог — Сила Моя:*"
    site["url"] = "https://gospod-bog.ru/"
    vk["url"] = "https://vk.ru/the_lord_god_is_my_strength"
    payload["links"] = [site, vk, links[3]]
    return payload


def test_canonical_content_record_is_valid_and_sourced() -> None:
    payload = _example_payload()
    assert validate_content_record(payload, expected_channel_id="UC-78ys2S3cQ3lpqgXfo-SvQ") == []
    record = parse_content_record(payload)
    assert record.schema_name == CANONICAL_SCHEMA_NAME
    assert record.project_key == LEGENDARY_POET
    assert record.supports("youtube", "comment")
    assert record.supports("vk", "video_description")
    assert record.fact.source_ids == ("tyutchev-night-sea-edition", "tyutchev-night-sea-feb")


def test_existing_youtube_v2_record_migrates_without_reauthoring() -> None:
    record = parse_content_record(_legacy_payload())
    assert record.origin_schema_name == "video-manager.youtube-comment-content"
    assert record.project_key == LEGENDARY_POET
    assert record.content_id == "RQIlUvFf1KQ"
    assert record.supports("vk", "post")


def test_unknown_legacy_channel_cannot_default_to_poet() -> None:
    payload = deepcopy(_legacy_payload())
    payload["channel_id"] = "UC_UNKNOWN_LEGACY_CHANNEL"
    payload.pop("project_key", None)

    errors = validate_content_record(payload)

    assert "content requires one registered project identity" in errors
    with pytest.raises(ValueError, match="registered project identity"):
        parse_content_record(payload)


def test_expected_project_context_is_enforced_before_parsing() -> None:
    payload = _example_payload()

    errors = validate_content_record(payload, expected_project_key=LORD_GOD_STRENGTH)

    assert any("does not match requested project" in error for error in errors)
    with pytest.raises(ValueError, match="does not match requested project"):
        parse_content_record(payload, expected_project_key=LORD_GOD_STRENGTH)


def test_lord_god_strength_profile_accepts_only_its_registered_links() -> None:
    payload = _lord_god_payload()
    assert validate_content_record(payload, expected_channel_id="UCeSJsC6go2c9pdJCuUI1BYA") == []
    record = parse_content_record(payload)
    assert record.project_key == LORD_GOD_STRENGTH


def test_lord_god_strength_profile_rejects_poet_project_link() -> None:
    payload = _lord_god_payload()
    links = payload["links"]
    assert isinstance(links, list)
    first = links[0]
    assert isinstance(first, dict)
    first["url"] = "https://thelegendarypoet.ru/"
    errors = validate_content_record(payload)
    assert any("belongs to another project profile" in error for error in errors)


def test_explicit_project_key_must_match_registered_channel() -> None:
    payload = deepcopy(_example_payload())
    payload["project_key"] = LORD_GOD_STRENGTH
    errors = validate_content_record(payload)
    assert any("does not match channel_id project" in error for error in errors)


def test_unknown_canonical_channel_requires_explicit_project_key() -> None:
    payload = deepcopy(_example_payload())
    payload["channel_id"] = "UC_UNKNOWN_PROJECT_CHANNEL"
    payload.pop("project_key", None)
    errors = validate_content_record(payload)
    assert "content requires one registered project identity" in errors


def test_common_validator_rejects_hallucination_language_and_unmapped_links() -> None:
    payload = deepcopy(_example_payload())
    fact = payload["fact"]
    links = payload["links"]
    assert isinstance(fact, dict)
    assert isinstance(links, list)
    fact["text"] = str(fact["text"]) + " Поэт предсказал будущее России."
    first = links[0]
    assert isinstance(first, dict)
    first["url"] = "https://invented.example/path"
    errors = validate_content_record(payload)
    assert "generic or unsupported phrase is forbidden: поэт предсказал" in errors
    assert any("not approved for project" in error for error in errors)


def test_collection_rejects_duplicate_variation_keys() -> None:
    record = parse_content_record(_example_payload())
    errors = validate_content_collection([record, record])
    assert f"duplicate variation_key: {record.variation_key}" in errors
    assert f"duplicate content_id: {record.content_id}" in errors
