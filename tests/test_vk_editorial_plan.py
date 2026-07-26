from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from video_channel_manager.editorial.content import parse_content_record
from video_channel_manager.platforms.vk.catalog import (
    VK_CATALOG_PLAN_SCHEMA,
    VK_CATALOG_PLAN_VERSION,
    calculate_vk_catalog_plan_sha256,
    text_sha256,
    validate_vk_catalog_plan,
)
from video_channel_manager.platforms.vk.editorial_plan import apply_editorial_records_to_vk_catalog_plan


def _record():
    path = Path(__file__).resolve().parents[1] / "content" / "editorial" / "examples" / "tyutchev-night-sea.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return parse_content_record(payload)


def _catalog_plan() -> dict[str, object]:
    before_title = "Старое название"
    after_title = "Новое название"
    before_description = "Старое описание"
    after_description = "Временное описание"
    plan: dict[str, object] = {
        "schema_name": VK_CATALOG_PLAN_SCHEMA,
        "schema_version": VK_CATALOG_PLAN_VERSION,
        "policy_version": "vk-catalog-structured-v1",
        "generated_at": "2026-07-25T20:30:00+00:00",
        "source_snapshot_id": "source-snapshot",
        "target_snapshot_id": "target-snapshot",
        "source_channel_id": "UC-78ys2S3cQ3lpqgXfo-SvQ",
        "target_community_id": 123,
        "target_video_ids_sha256": "sha256:inventory",
        "initial_catalog_state_sha256": "sha256:state",
        "reviewed_mappings": {"RQIlUvFf1KQ": "123_456"},
        "resolved_video_mappings": {"RQIlUvFf1KQ": "123_456"},
        "album_operations": [],
        "placement_operations": [],
        "text_operations": [
            {
                "operation_id": "video-text:update:123_456",
                "source_video_id": "RQIlUvFf1KQ",
                "target_video_id": "123_456",
                "before_title": before_title,
                "after_title": after_title,
                "before_description": before_description,
                "after_description": after_description,
                "before_title_sha256": text_sha256(before_title),
                "after_title_sha256": text_sha256(after_title),
                "before_description_sha256": text_sha256(before_description),
                "after_description_sha256": text_sha256(after_description),
                "publication_policy_version": "legacy",
            }
        ],
        "review_only": [],
        "summary": {
            "resolved_video_mappings": 1,
            "albums_to_create": 0,
            "placements_to_add": 0,
            "video_texts_to_update": 1,
            "review_only": 0,
            "total_operations": 1,
        },
    }
    plan["plan_sha256"] = calculate_vk_catalog_plan_sha256(plan)
    return plan


def test_vk_catalog_plan_reuses_guards_and_gets_canonical_description() -> None:
    original = _catalog_plan()
    adapted = apply_editorial_records_to_vk_catalog_plan(original, [_record()], require_all_text_operations=True)
    validate_vk_catalog_plan(adapted)
    original_op = original["text_operations"][0]  # type: ignore[index]
    adapted_op = adapted["text_operations"][0]  # type: ignore[index]
    assert adapted_op["before_description"] == original_op["before_description"]
    assert adapted_op["before_description_sha256"] == original_op["before_description_sha256"]
    assert "*" not in adapted_op["after_description"]
    assert "Сообщество проекта в VK: https://vk.com/thelegendarypoet" in adapted_op["after_description"]
    assert adapted_op["editorial_variation_key"] == "tyutchev-night-sea-two-editions-nice-v3"
    assert adapted_op["editorial_reviewed_at"] == "2026-07-25T20:22:00+00:00"
    assert adapted["plan_sha256"] != original["plan_sha256"]


def test_vk_catalog_plan_rejects_draft_unreviewed_or_malformed_review() -> None:
    record = _record()
    draft = replace(record, status="draft", reviewed_at=None)
    with pytest.raises(ValueError, match="timezone-aware review"):
        apply_editorial_records_to_vk_catalog_plan(_catalog_plan(), [draft])

    unreviewed = replace(record, reviewed_at=None)
    with pytest.raises(ValueError, match="timezone-aware review"):
        apply_editorial_records_to_vk_catalog_plan(_catalog_plan(), [unreviewed])

    malformed = replace(record, reviewed_at="yesterday")
    with pytest.raises(ValueError, match="timezone-aware review"):
        apply_editorial_records_to_vk_catalog_plan(_catalog_plan(), [malformed])

    naive = replace(record, reviewed_at="2026-07-25T20:22:00")
    with pytest.raises(ValueError, match="timezone-aware review"):
        apply_editorial_records_to_vk_catalog_plan(_catalog_plan(), [naive])
