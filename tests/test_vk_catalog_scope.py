from __future__ import annotations

from video_channel_manager.platforms.vk.catalog import calculate_vk_catalog_plan_sha256, validate_vk_catalog_plan
from video_channel_manager.platforms.vk.catalog_scope import (
    VK_CATALOG_OPERATION_SCOPE_CATALOG_ONLY,
    restrict_vk_catalog_plan_to_catalog_only,
)


def _plan() -> dict[str, object]:
    plan: dict[str, object] = {
        "schema_name": "video-manager.vk-catalog-plan",
        "schema_version": 1,
        "policy_version": "vk-catalog-structured-v1",
        "generated_at": "2026-07-27T00:00:00+00:00",
        "source_snapshot_id": "source",
        "target_snapshot_id": "target",
        "source_channel_id": "youtube",
        "target_community_id": 235216998,
        "target_video_ids_sha256": "sha256:coverage",
        "initial_catalog_state_sha256": "sha256:state",
        "reviewed_mappings": {},
        "resolved_video_mappings": {"yt-1": "-235216998_1"},
        "album_operations": [
            {
                "operation_id": "album:create:playlist-1",
                "source_collection_id": "playlist-1",
                "title": "Сергей Есенин",
                "normalized_title": "сергей есенин",
                "source_description": "",
            }
        ],
        "placement_operations": [
            {
                "operation_id": "placement:add:playlist-1:-235216998_1",
                "source_collection_id": "playlist-1",
                "album_title": "Сергей Есенин",
                "target_collection_id": None,
                "target_video_id": "-235216998_1",
                "source_video_id": "yt-1",
            }
        ],
        "text_operations": [{"operation_id": "video-text:update:-235216998_1"}],
        "review_only": [
            {
                "kind": "description_requires_editorial_review",
                "source_video_id": "yt-1",
                "target_video_id": "-235216998_1",
                "message": "visible Markdown",
            },
            {
                "kind": "ambiguous_video_match",
                "source_video_id": "yt-2",
                "suggested_target_video_id": "-235216998_2",
            },
        ],
        "summary": {
            "resolved_video_mappings": 1,
            "albums_to_create": 1,
            "placements_to_add": 1,
            "video_texts_to_update": 1,
            "review_only": 2,
            "total_operations": 3,
        },
    }
    plan["plan_sha256"] = calculate_vk_catalog_plan_sha256(plan)
    return plan


def test_catalog_only_scope_removes_text_operations_and_text_review_findings() -> None:
    original = _plan()

    scoped = restrict_vk_catalog_plan_to_catalog_only(original)

    assert scoped["operation_scope"] == VK_CATALOG_OPERATION_SCOPE_CATALOG_ONLY
    assert scoped["text_operations"] == []
    assert scoped["summary"]["video_texts_to_update"] == 0
    assert scoped["summary"]["total_operations"] == 2
    assert scoped["summary"]["review_only"] == 1
    assert scoped["review_only"][0]["kind"] == "ambiguous_video_match"
    assert original["text_operations"] != []
    validate_vk_catalog_plan(scoped)
