from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from video_channel_manager.editorial.content import validate_content_record


ROOT = Path(__file__).resolve().parents[1]


def _canonical_payload() -> dict[str, object]:
    path = ROOT / "content" / "editorial" / "examples" / "tyutchev-night-sea.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _legacy_payload() -> dict[str, object]:
    path = ROOT / "content" / "youtube-comments" / "RQIlUvFf1KQ.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_canonical_record_requires_explicit_identity_and_suitability() -> None:
    payload = _canonical_payload()
    payload.pop("content_id")
    payload.pop("platform_suitability")

    errors = validate_content_record(payload)

    assert "canonical content requires content_id" in errors
    assert "canonical content requires explicit platform_suitability" in errors


def test_approved_record_requires_timezone_aware_review_timestamp() -> None:
    payload = _canonical_payload()
    payload["reviewed_at"] = "2026-07-25T20:22:00"

    errors = validate_content_record(payload)

    assert "approved content requires a timezone-aware reviewed_at" in errors


def test_canonical_targets_must_be_exact_and_enabled() -> None:
    payload = _canonical_payload()
    suitability = payload["platform_suitability"]
    assert isinstance(suitability, dict)
    suitability["youtube"] = ["description"]
    payload["platform_targets"] = {
        "youtube": "RQIlUvFf1KQ",
        "youtube.comment": "RQIlUvFf1KQ",
        "vk.unknown": "-235216998_1",
        "vk.post": "target with whitespace",
    }

    errors = validate_content_record(payload)

    assert "canonical platform target must use platform.surface: youtube" in errors
    assert "platform target youtube.comment is not enabled by platform_suitability" in errors
    assert "unsupported platform target surface: vk.unknown" in errors
    assert "platform target vk.post cannot contain whitespace" in errors


def test_legacy_v2_keeps_compatibility_defaults() -> None:
    payload = deepcopy(_legacy_payload())
    payload.pop("platform_suitability", None)
    payload.pop("platform_targets", None)
    payload.pop("content_id", None)

    assert validate_content_record(payload) == []


def test_repository_source_paths_reject_windows_absolute_and_parent_escape() -> None:
    payload = _canonical_payload()
    sources = payload["sources"]
    assert isinstance(sources, list)
    first = sources[0]
    second = sources[1]
    assert isinstance(first, dict)
    assert isinstance(second, dict)
    first.pop("url", None)
    first["path"] = r"C:\\private\\source.txt"
    second.pop("url", None)
    second["path"] = "docs/../secrets/source.txt"

    errors = validate_content_record(payload)

    assert errors.count("source tyutchev-night-sea-edition has an unsafe repository path") == 1
    assert errors.count("source tyutchev-night-sea-feb has an unsafe repository path") == 1
