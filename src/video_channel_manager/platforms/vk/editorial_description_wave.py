from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any

from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk.catalog import canonical_sha256
from video_channel_manager.platforms.vk.editorial_cleanup import (
    description_change_reasons,
    description_semantic_body,
)
from video_channel_manager.platforms.vk.editorial_cleanup_plan import (
    build_vk_editorial_cleanup_plan,
    calculate_vk_editorial_plan_sha256,
    validate_vk_editorial_cleanup_plan,
)


def build_vk_editorial_description_wave(
    target: AuditPackage,
    policy: dict[str, Any],
) -> dict[str, Any]:
    """Build a signed technical description-only wave.

    Titles and album names remain unchanged. Every operation must preserve the
    content-only semantic body after excluding URLs, hashtags, known footer
    material, Markdown markers, decorative rules, whitespace, and zero-width
    characters. This deliberately blocks factual or stylistic rewriting.
    """

    base_plan = build_vk_editorial_cleanup_plan(target, policy)
    excluded_ids = {
        str(remote_id).strip()
        for remote_id in list(policy.get("description_review_only_ids") or [])
        if str(remote_id).strip()
    }
    target_ids = {video.ref.remote_id for video in target.videos}
    unknown_exclusions = sorted(excluded_ids - target_ids)
    if unknown_exclusions:
        raise ValueError(f"Unknown description_review_only_ids: {unknown_exclusions}")

    operations: list[dict[str, Any]] = []
    review_only = [
        deepcopy(finding)
        for finding in base_plan["review_only"]
        if finding.get("kind") == "description_too_long"
    ]
    deferred_review = [
        deepcopy(finding)
        for finding in base_plan["review_only"]
        if finding.get("kind") in {"factual_editorial_review", "sensitive_claim_review"}
    ]
    reason_counts: Counter[str] = Counter()

    for operation in base_plan["video_text_operations"]:
        remote_id = str(operation["target_video_id"])
        if not bool(operation["description_changed"]):
            continue
        if remote_id in excluded_ids:
            review_only.append(
                {
                    "kind": "description_manual_review_excluded",
                    "target_video_id": remote_id,
                    "message": str(
                        policy.get("description_review_only_reason")
                        or "Description requires manual review before technical cleanup."
                    ),
                }
            )
            continue

        before_description = str(operation["before_description"])
        after_description = str(operation["after_description"])
        before_body = description_semantic_body(before_description, policy)
        after_body = description_semantic_body(after_description, policy)
        if before_body != after_body:
            raise ValueError(
                "Description cleanup changes semantic body for "
                f"{remote_id}; move it to description_review_only_ids"
            )

        reasons = description_change_reasons(before_description, after_description, policy)
        if not reasons:
            raise ValueError(f"Description change has no deterministic reason: {remote_id}")
        reason_counts.update(reasons)

        description_operation = deepcopy(operation)
        description_operation["after_title"] = description_operation["before_title"]
        description_operation["after_title_sha256"] = description_operation[
            "before_title_sha256"
        ]
        description_operation["title_changed"] = False
        description_operation["change_reasons"] = reasons
        description_operation["semantic_body_sha256"] = canonical_sha256(before_body)
        description_operation["semantic_body_preserved"] = True
        operations.append(description_operation)

    operations.sort(key=lambda item: item["operation_id"])
    review_only.sort(key=canonical_sha256)
    deferred_review.sort(key=canonical_sha256)

    plan: dict[str, Any] = {
        "schema_name": base_plan["schema_name"],
        "schema_version": base_plan["schema_version"],
        "operation_scope": "editorial_only",
        "component_scope": "descriptions_only",
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
        "deferred_editorial_review": deferred_review,
        "change_reason_counts": dict(sorted(reason_counts.items())),
    }
    plan["summary"] = {
        "videos_in_snapshot": len(target.videos),
        "video_text_operations": len(operations),
        "titles_to_update": 0,
        "descriptions_to_update": len(operations),
        "albums_to_rename": 0,
        "placements_to_add": 0,
        "placements_to_remove": 0,
        "videos_to_delete": 0,
        "review_only": len(review_only),
        "deferred_editorial_review": len(deferred_review),
        "total_operations": len(operations),
    }
    plan["plan_sha256"] = calculate_vk_editorial_plan_sha256(plan)
    validate_vk_editorial_cleanup_plan(plan)
    return plan


__all__ = ["build_vk_editorial_description_wave"]
