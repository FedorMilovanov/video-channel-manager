from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import Any

from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk.catalog import canonical_sha256, text_sha256
from video_channel_manager.platforms.vk.editorial_cleanup_plan import (
    VK_EDITORIAL_CLEANUP_SCHEMA,
    VK_EDITORIAL_CLEANUP_VERSION,
    calculate_vk_editorial_plan_sha256,
    membership_state_sha256,
    target_video_ids_sha256,
    validate_vk_editorial_cleanup_plan,
)
from video_channel_manager.platforms.vk.editorial_stance import (
    validate_the_legendary_poet_editorial_stance,
)
from video_channel_manager.platforms.vk.text_writer import canonical_vk_text

VK_DESCRIPTION_GUARD_HASH_ALGORITHM = "video-manager.text-sha256-v1"


def _indexed_items(items: list[dict[str, Any]], *, id_field: str, label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        item_id = str(item.get(id_field) or "").strip()
        if not item_id:
            raise ValueError(f"{label} has no {id_field}")
        if item_id in result:
            raise ValueError(f"Duplicate {label} ID: {item_id}")
        result[item_id] = item
    return result


def build_vk_reviewed_correction_wave(
    target: AuditPackage,
    decisions: dict[str, Any],
    *,
    source_review_bundle_sha256: str,
) -> dict[str, Any]:
    """Build an exact description-only correction plan from reviewed decisions."""

    if target.channel.ref.platform.value != "vk":
        raise ValueError("VK correction target must be a VK AuditPackage")
    community_id = int(target.channel.ref.channel_id)
    if int(decisions.get("target_community_id", 0)) != community_id:
        raise ValueError("Correction decisions target a different VK community")
    if str(decisions.get("description_guard_hash_algorithm") or "") != VK_DESCRIPTION_GUARD_HASH_ALGORITHM:
        raise ValueError(
            f"Correction decisions must declare canonical description guards with {VK_DESCRIPTION_GUARD_HASH_ALGORITHM}"
        )
    expected_review_sha = str(decisions.get("source_review_bundle_sha256") or "")
    if source_review_bundle_sha256 != expected_review_sha:
        raise ValueError("Review bundle SHA-256 differs from the reviewed correction decisions")

    replacements = _indexed_items(
        [item for item in decisions.get("shared_replacements", []) if isinstance(item, dict)],
        id_field="replacement_id",
        label="replacement",
    )
    sources = _indexed_items(
        [item for item in decisions.get("sources", []) if isinstance(item, dict)],
        id_field="source_id",
        label="source",
    )
    editorial_profile = validate_the_legendary_poet_editorial_stance(decisions, sources)
    decision_items = [item for item in decisions.get("decisions", []) if isinstance(item, dict)]
    if not decision_items:
        raise ValueError("Correction decision set is empty")

    videos = {video.ref.remote_id: video for video in target.videos}
    seen_targets: set[str] = set()
    operations: list[dict[str, Any]] = []
    for decision in decision_items:
        decision_id = str(decision.get("decision_id") or "").strip()
        remote_id = str(decision.get("target_video_id") or "").strip()
        if not decision_id or not remote_id:
            raise ValueError("Correction decision has no ID or target video ID")
        if remote_id in seen_targets:
            raise ValueError(f"Duplicate correction target: {remote_id}")
        seen_targets.add(remote_id)
        video = videos.get(remote_id)
        if video is None:
            raise ValueError(f"Correction target is absent from snapshot: {remote_id}")

        before_title = canonical_vk_text(video.title)
        before_description = canonical_vk_text(video.description)
        if before_title != str(decision.get("expected_title") or ""):
            raise ValueError(f"Title guard mismatch for {remote_id}")
        expected_description_sha = str(decision.get("expected_description_sha256") or "")
        actual_description_sha = text_sha256(before_description)
        if actual_description_sha != expected_description_sha:
            raw_description_sha = f"sha256:{hashlib.sha256(before_description.encode('utf-8')).hexdigest()}"
            raise ValueError(
                f"Description guard mismatch for {remote_id}: expected {expected_description_sha}, "
                f"actual {actual_description_sha}, raw_text_sha256 {raw_description_sha}, "
                f"algorithm {VK_DESCRIPTION_GUARD_HASH_ALGORITHM}"
            )

        after_description = before_description
        applied_replacements: list[dict[str, Any]] = []
        for replacement_id in decision.get("replacement_ids", []):
            replacement = replacements.get(str(replacement_id))
            if replacement is None:
                raise ValueError(f"Unknown replacement {replacement_id} in {decision_id}")
            old = str(replacement.get("old") or "")
            new = str(replacement.get("new") or "")
            expected_count = int(replacement.get("expected_count", 1))
            actual_count = after_description.count(old)
            if actual_count != expected_count:
                raise ValueError(
                    f"Replacement {replacement_id} expected {expected_count} matches in {remote_id}, found {actual_count}"
                )
            after_description = after_description.replace(old, new)
            applied_replacements.append(deepcopy(replacement))

        if after_description == before_description:
            raise ValueError(f"Correction decision makes no change: {remote_id}")
        if len(after_description) > 5000:
            raise ValueError(f"Corrected description exceeds 5000 characters: {remote_id}")

        source_ids = [str(value) for value in decision.get("source_ids", [])]
        if not source_ids:
            raise ValueError(f"Correction decision has no source evidence: {decision_id}")
        decision_sources: list[dict[str, Any]] = []
        for source_id in source_ids:
            source = sources.get(source_id)
            if source is None:
                raise ValueError(f"Unknown source {source_id} in {decision_id}")
            decision_sources.append(deepcopy(source))

        operations.append(
            {
                "operation_id": f"video-text:reviewed-correction:{remote_id}",
                "target_video_id": remote_id,
                "duration_seconds": video.duration_seconds,
                "before_title": before_title,
                "after_title": before_title,
                "before_description": before_description,
                "after_description": after_description,
                "before_title_sha256": text_sha256(before_title),
                "after_title_sha256": text_sha256(before_title),
                "before_description_sha256": text_sha256(before_description),
                "after_description_sha256": text_sha256(after_description),
                "title_changed": False,
                "description_changed": True,
                "reviewed_correction": True,
                "decision_id": decision_id,
                "applied_replacements": applied_replacements,
                "source_evidence": decision_sources,
            }
        )

    operations.sort(key=lambda item: item["operation_id"])
    decisions_sha256 = canonical_sha256(decisions)
    plan: dict[str, Any] = {
        "schema_name": VK_EDITORIAL_CLEANUP_SCHEMA,
        "schema_version": VK_EDITORIAL_CLEANUP_VERSION,
        "operation_scope": "editorial_only",
        "component_scope": "descriptions_only",
        "correction_scope": "reviewed_factual_and_sensitive",
        "generated_at": target.generated_at.isoformat(),
        "target_snapshot_id": str(target.snapshot_id),
        "target_community_id": community_id,
        "target_video_ids_sha256": target_video_ids_sha256(target),
        "initial_memberships_sha256": membership_state_sha256(target),
        "policy": decisions,
        "policy_sha256": decisions_sha256,
        "decision_set_id": str(decisions.get("decision_set_id") or ""),
        "decisions_sha256": decisions_sha256,
        "editorial_profile": deepcopy(editorial_profile),
        "stance_source_ids": [str(value) for value in decisions.get("stance_source_ids") or []],
        "source_plan_sha256": str(decisions.get("source_plan_sha256") or ""),
        "source_review_bundle_sha256": source_review_bundle_sha256,
        "video_text_operations": operations,
        "album_title_operations": [],
        "review_only": [],
        "deferred_editorial_review": [],
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
        "review_only": 0,
        "deferred_editorial_review": 0,
        "total_operations": len(operations),
    }
    plan["plan_sha256"] = calculate_vk_editorial_plan_sha256(plan)
    validate_vk_editorial_cleanup_plan(plan)
    return plan


__all__ = [
    "VK_DESCRIPTION_GUARD_HASH_ALGORITHM",
    "build_vk_reviewed_correction_wave",
]
