from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from video_channel_manager.editorial.content import (
    parse_content_record,
    validate_content_record,
)

ROOT = Path(__file__).resolve().parents[1]


def _payload() -> dict[str, object]:
    path = ROOT / "content" / "editorial" / "examples" / "tyutchev-night-sea.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_canonical_identity_rejects_scalar_coercion() -> None:
    payload = _payload()
    payload["content_id"] = 123
    payload["variation_key"] = True
    payload["reviewed_at"] = 456

    errors = validate_content_record(payload)

    assert "content_id must be a string or null" in errors
    assert "canonical content requires content_id" in errors
    assert "variation_key must be a string" in errors
    assert "reviewed_at must be a string or null" in errors
    assert "approved content requires a timezone-aware reviewed_at" in errors
    with pytest.raises(ValueError):
        parse_content_record(payload)


def test_schema_version_requires_an_integer_not_bool() -> None:
    payload = _payload()
    payload["schema_version"] = True

    errors = validate_content_record(payload)

    assert "schema_version must be an integer" in errors
    assert any(error.startswith("schema must be") for error in errors)


def test_evidence_links_and_platform_metadata_reject_non_string_scalars() -> None:
    payload = deepcopy(_payload())
    source_ids = payload["source_ids"]
    fact = payload["fact"]
    question = payload["question"]
    links = payload["links"]
    sources = payload["sources"]
    suitability = payload["platform_suitability"]
    rendering = payload["rendering_metadata"]
    targets = payload["platform_targets"]
    assert isinstance(source_ids, list)
    assert isinstance(fact, dict)
    assert isinstance(question, dict)
    assert isinstance(links, list)
    assert isinstance(sources, list)
    assert isinstance(suitability, dict)
    assert isinstance(rendering, dict)
    assert isinstance(targets, dict)
    first_link = links[0]
    first_source = sources[0]
    assert isinstance(first_link, dict)
    assert isinstance(first_source, dict)

    source_ids.append(7)
    fact_source_ids = fact["source_ids"]
    assert isinstance(fact_source_ids, list)
    fact_source_ids.append(8)
    fact["heading"] = 9
    question["lead"] = 10
    first_source["title"] = 11
    first_source["url"] = 12
    first_link["label"] = 13
    first_link["url"] = 14
    first_link["platforms"] = ["youtube", 15]
    first_link["surfaces"] = ["comment", 16]
    suitability["youtube"] = ["comment", 17]
    rendering["preferred_link_order"] = ["site", 18]
    targets["youtube.comment"] = 19

    errors = validate_content_record(payload)

    expected = {
        "source_ids must contain only strings",
        "fact.source_ids must contain only strings",
        "fact.heading must be a string",
        "question.lead must be a string or null",
        "sources[0].title must be a string",
        "sources[0].url must be a string or null",
        "links[0].label must be a string",
        "links[0].url must be a string",
        "links[0].platforms must contain only strings",
        "links[0].surfaces must contain only strings",
        "platform_suitability.youtube must contain only strings",
        "rendering_metadata.preferred_link_order must contain only strings",
        "platform target youtube.comment must be a string",
    }
    assert expected.issubset(set(errors))


def test_preferred_link_order_rejects_invalid_targets_and_link_kinds() -> None:
    payload = _payload()
    payload["rendering_metadata"] = {
        "preferred_link_order": {
            "youtube.unknown": ["site"],
            "youtube.comment": ["site", "unsupported-kind"],
        }
    }

    errors = validate_content_record(payload)

    assert "unsupported preferred_link_order target: youtube.unknown" in errors
    assert (
        "rendering_metadata.preferred_link_order.youtube.comment contains unsupported link kinds: "
        "unsupported-kind"
    ) in errors
