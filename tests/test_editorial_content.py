from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from video_channel_manager.editorial.content import (
    CANONICAL_SCHEMA_NAME,
    parse_content_record,
    validate_content_collection,
    validate_content_record,
)


def _example_payload() -> dict[str, object]:
    path = Path(__file__).resolve().parents[1] / "content" / "editorial" / "examples" / "tyutchev-night-sea.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_canonical_content_record_is_valid_and_sourced() -> None:
    payload = _example_payload()
    assert validate_content_record(payload, expected_channel_id="UC-78ys2S3cQ3lpqgXfo-SvQ") == []
    record = parse_content_record(payload)
    assert record.schema_name == CANONICAL_SCHEMA_NAME
    assert record.supports("youtube", "comment")
    assert record.supports("vk", "video_description")
    assert record.fact.source_ids == ("tyutchev-night-sea-edition", "tyutchev-night-sea-feb")


def test_existing_youtube_v2_record_migrates_without_reauthoring() -> None:
    path = Path(__file__).resolve().parents[1] / "content" / "youtube-comments" / "RQIlUvFf1KQ.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    record = parse_content_record(payload)
    assert record.origin_schema_name == "video-manager.youtube-comment-content"
    assert record.content_id == "RQIlUvFf1KQ"
    assert record.supports("vk", "post")


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
    assert any("absent from sources/project link map" in error for error in errors)


def test_collection_rejects_duplicate_variation_keys() -> None:
    record = parse_content_record(_example_payload())
    errors = validate_content_collection([record, record])
    assert f"duplicate variation_key: {record.variation_key}" in errors
    assert f"duplicate content_id: {record.content_id}" in errors
