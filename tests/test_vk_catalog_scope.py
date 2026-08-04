from __future__ import annotations

from video_channel_manager.application.catalog_identity import (
    CatalogIdentityEvidence,
    CollectionIdentityDecision,
    calculate_catalog_identity_digest,
)
from video_channel_manager.application.identity import canonicalize_collection_title
from video_channel_manager.domain.enums import PlatformName
from video_channel_manager.domain.models import RemoteRef
from video_channel_manager.platforms.vk.catalog import calculate_vk_catalog_plan_sha256, validate_vk_catalog_plan
from video_channel_manager.platforms.vk.catalog_scope import (
    VK_CATALOG_OPERATION_SCOPE_CATALOG_ONLY,
    restrict_vk_catalog_plan_to_catalog_only,
)

_SOURCE_CHANNEL_ID = "UC-78ys2S3cQ3lpqgXfo-SvQ"
_TARGET_COMMUNITY_ID = 235216998
_TARGET_VIDEO_ID = "-235216998_1"


def _ref(platform: PlatformName, channel_id: str, remote_id: str) -> RemoteRef:
    return RemoteRef(platform=platform, channel_id=channel_id, remote_id=remote_id)


def _catalog_identity() -> CatalogIdentityEvidence:
    provisional = CatalogIdentityEvidence(
        project_key="legendary-poet",
        source_snapshot_id="source",
        target_snapshot_id="target",
        source_channel=_ref(PlatformName.YOUTUBE, _SOURCE_CHANNEL_ID, _SOURCE_CHANNEL_ID),
        target_channel=_ref(
            PlatformName.VK,
            str(_TARGET_COMMUNITY_ID),
            str(_TARGET_COMMUNITY_ID),
        ),
        approved_collection_creates=["playlist-1"],
        decisions=[
            CollectionIdentityDecision(
                source_ref=_ref(
                    PlatformName.YOUTUBE,
                    _SOURCE_CHANNEL_ID,
                    "playlist-1",
                ),
                source_title_identity=canonicalize_collection_title("Сергей Есенин"),
                decision="create",
                source_member_video_ids=["yt-1"],
                mapped_target_video_ids=[_TARGET_VIDEO_ID],
                missing_target_video_ids=[_TARGET_VIDEO_ID],
            )
        ],
        digest="0" * 64,
    )
    return provisional.model_copy(update={"digest": calculate_catalog_identity_digest(provisional)})


def _plan() -> dict[str, object]:
    identity = _catalog_identity()
    plan: dict[str, object] = {
        "schema_name": "video-manager.vk-catalog-plan",
        "schema_version": 1,
        "policy_version": "vk-catalog-structured-v1",
        "generated_at": "2026-07-27T00:00:00+00:00",
        "source_snapshot_id": "source",
        "target_snapshot_id": "target",
        "source_channel_id": _SOURCE_CHANNEL_ID,
        "target_community_id": _TARGET_COMMUNITY_ID,
        "target_video_ids_sha256": "sha256:coverage",
        "initial_catalog_state_sha256": "sha256:state",
        "reviewed_mappings": {},
        "resolved_video_mappings": {"yt-1": _TARGET_VIDEO_ID},
        "reviewed_collection_mappings": {},
        "approved_collection_creates": ["playlist-1"],
        "catalog_identity": identity.model_dump(mode="json"),
        "catalog_identity_sha256": identity.digest,
        "album_operations": [
            {
                "operation_id": "album:create:playlist-1",
                "source_collection_id": "playlist-1",
                "title": "Сергей Есенин",
                "source_description": "",
                "catalog_identity_digest": identity.digest,
            }
        ],
        "placement_operations": [
            {
                "operation_id": f"placement:add:playlist-1:{_TARGET_VIDEO_ID}",
                "source_collection_id": "playlist-1",
                "album_title": "Сергей Есенин",
                "target_collection_id": None,
                "target_video_id": _TARGET_VIDEO_ID,
                "source_video_id": "yt-1",
                "catalog_identity_digest": identity.digest,
            }
        ],
        "text_operations": [{"operation_id": f"video-text:update:{_TARGET_VIDEO_ID}"}],
        "review_only": [
            {
                "kind": "description_requires_editorial_review",
                "source_video_id": "yt-1",
                "target_video_id": _TARGET_VIDEO_ID,
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
            "resolved_collection_mappings": 0,
            "albums_to_create": 1,
            "collection_conflicts": 0,
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
