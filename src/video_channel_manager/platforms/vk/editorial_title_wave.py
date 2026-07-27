from __future__ import annotations

from copy import deepcopy
from typing import Any

from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk.catalog import canonical_sha256
from video_channel_manager.platforms.vk.editorial_cleanup_plan import (
    build_vk_editorial_cleanup_plan,
    calculate_vk_editorial_plan_sha256,
    validate_vk_editorial_cleanup_plan,
)
from video_channel_manager.platforms.vk.text_writer import canonical_vk_text


def _title_groups(titles: dict[str, str]) -> dict[str, set[str]]:
    groups: dict[str, set[str]] = {}
    for remote_id, title in titles.items():
        groups.setdefault(canonical_vk_text(title).casefold(), set()).add(remote_id)
    return groups


def build_vk_editorial_title_wave(
    target: AuditPackage,
    policy: dict[str, Any],
) -> dict[str, Any]:
    """Build a signed title-only wave, excluding explicitly ambiguous videos.

    Description text and album titles are retained byte-for-byte after VK text
    canonicalization. Existing duplicate titles may remain for manual review,
    but this wave is forbidden from introducing any new title collision.
    """

    base_plan = build_vk_editorial_cleanup_plan(target, policy)
    excluded_ids = {
        str(remote_id).strip()
        for remote_id in list(policy.get("title_review_only_ids") or [])
        if str(remote_id).strip()
    }
    target_ids = {video.ref.remote_id for video in target.videos}
    unknown_exclusions = sorted(excluded_ids - target_ids)
    if unknown_exclusions:
        raise ValueError(f"Unknown title_review_only_ids: {unknown_exclusions}")

    operations: list[dict[str, Any]] = []
    proposed_by_id = {video.ref.remote_id: canonical_vk_text(video.title) for video in target.videos}
    base_operations = {
        operation["target_video_id"]: operation for operation in base_plan["video_text_operations"]
    }

    for remote_id, operation in base_operations.items():
        if not bool(operation["title_changed"]):
            continue
        proposed_by_id[remote_id] = str(operation["after_title"])
        if remote_id in excluded_ids:
            continue
        title_operation = deepcopy(operation)
        title_operation["after_description"] = title_operation["before_description"]
        title_operation["after_description_sha256"] = title_operation["before_description_sha256"]
        title_operation["description_changed"] = False
        operations.append(title_operation)

    before_titles = {video.ref.remote_id: canonical_vk_text(video.title) for video in target.videos}
    final_titles = dict(before_titles)
    for operation in operations:
        final_titles[operation["target_video_id"]] = str(operation["after_title"])

    before_groups = _title_groups(before_titles)
    final_groups = _title_groups(final_titles)
    introduced_collisions: list[dict[str, Any]] = []
    for key, remote_ids in final_groups.items():
        if len(remote_ids) <= 1:
            continue
        if remote_ids != before_groups.get(key, set()):
            introduced_collisions.append(
                {
                    "title": final_titles[sorted(remote_ids)[0]],
                    "target_video_ids": sorted(remote_ids),
                }
            )
    if introduced_collisions:
        raise ValueError(f"Title-only wave introduces duplicate titles: {introduced_collisions}")

    review_only = [
        deepcopy(finding)
        for finding in base_plan["review_only"]
        if finding.get("kind") == "mention_rendering_ui_test_required"
    ]
    reason = str(
        policy.get("title_review_only_reason")
        or "Ambiguous title requires manual audio/visual review."
    )
    for remote_id in sorted(excluded_ids):
        before_title = before_titles[remote_id]
        proposed_title = proposed_by_id.get(remote_id, before_title)
        review_only.append(
            {
                "kind": "title_manual_review_excluded",
                "target_video_id": remote_id,
                "before_title": before_title,
                "proposed_title": proposed_title,
                "message": reason,
            }
        )

    operations.sort(key=lambda item: item["operation_id"])
    review_only.sort(key=lambda item: canonical_sha256(item))

    plan: dict[str, Any] = {
        "schema_name": base_plan["schema_name"],
        "schema_version": base_plan["schema_version"],
        "operation_scope": "editorial_only",
        "component_scope": "titles_only",
        "generated_at": base_plan["generated_at"],
        "target_snapshot_id": base_plan["target_snapshot_id"],
        "target_community_id": base_plan["target_community_id"],
        "target_video_ids_sha256": base_plan["target_video_ids_sha256"],
        "initial_memberships_sha256": base_plan["initial_memberships_sha256"],
        "policy": policy,
        "policy_sha256": canonical_sha256(policy),
        "source_full_plan_sha256": base_plan["plan_sha256"],
        "video_text_operations": operations,
        "album_title_operations": [],
        "review_only": review_only,
    }
    plan["summary"] = {
        "videos_in_snapshot": len(target.videos),
        "video_text_operations": len(operations),
        "titles_to_update": len(operations),
        "descriptions_to_update": 0,
        "albums_to_rename": 0,
        "placements_to_add": 0,
        "placements_to_remove": 0,
        "videos_to_delete": 0,
        "review_only": len(review_only),
        "total_operations": len(operations),
    }
    plan["plan_sha256"] = calculate_vk_editorial_plan_sha256(plan)
    validate_vk_editorial_cleanup_plan(plan)
    return plan


__all__ = ["build_vk_editorial_title_wave"]
