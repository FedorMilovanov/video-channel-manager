from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Any

from video_channel_manager.application.cross_platform import compare_audit_packages, normalize_title
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk.publishing import render_vk_publication
from video_channel_manager.platforms.vk.text_writer import canonical_vk_text

VK_CATALOG_PLAN_SCHEMA = "video-manager.vk-catalog-plan"
VK_CATALOG_PLAN_VERSION = 1
VK_CATALOG_POLICY_VERSION = "vk-catalog-structured-v1"


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def text_sha256(value: str) -> str:
    return canonical_sha256(canonical_vk_text(value))


def _is_system_collection(collection: Any) -> bool:
    raw_id = collection.metadata.get("id")
    return (
        collection.privacy_status == "system"
        or collection.ref.remote_id.startswith("-")
        or isinstance(raw_id, int)
        and raw_id < 0
        or bool(collection.metadata.get("is_system"))
    )


def target_video_ids_sha256(target: AuditPackage) -> str:
    return canonical_sha256(sorted(video.ref.remote_id for video in target.videos))


def catalog_state_sha256(target: AuditPackage) -> str:
    payload = {
        "videos": sorted(
            (
                video.ref.remote_id,
                canonical_vk_text(video.title),
                canonical_vk_text(video.description),
            )
            for video in target.videos
        ),
        "collections": sorted(
            (collection.ref.remote_id, canonical_vk_text(collection.title))
            for collection in target.collections
            if not _is_system_collection(collection)
        ),
        "memberships": sorted(
            (membership.collection_ref.remote_id, membership.video_ref.remote_id) for membership in target.memberships
        ),
    }
    return canonical_sha256(payload)


def _validated_reviewed_mappings(
    source: AuditPackage,
    target: AuditPackage,
    reviewed_mappings: dict[str, str],
) -> dict[str, str]:
    source_ids = {item.ref.remote_id for item in source.videos}
    target_ids = {item.ref.remote_id for item in target.videos}
    result: dict[str, str] = {}
    used_target_ids: set[str] = set()
    for raw_source_id, raw_target_id in reviewed_mappings.items():
        source_id = str(raw_source_id).strip()
        target_id = str(raw_target_id).strip()
        if source_id not in source_ids:
            raise ValueError(f"Reviewed mapping references unknown source video: {source_id}")
        if target_id not in target_ids:
            raise ValueError(f"Reviewed mapping references unknown target video: {target_id}")
        if target_id in used_target_ids:
            raise ValueError(f"Reviewed mappings reuse target video: {target_id}")
        result[source_id] = target_id
        used_target_ids.add(target_id)
    return result


def _target_collection_index(target: AuditPackage) -> dict[str, list[Any]]:
    result: dict[str, list[Any]] = defaultdict(list)
    for collection in target.collections:
        if not _is_system_collection(collection):
            result[normalize_title(collection.title)].append(collection)
    return result


def _build_mapping(
    source: AuditPackage,
    target: AuditPackage,
    reviewed_mappings: dict[str, str],
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    comparison = compare_audit_packages(source, target)
    mapping = _validated_reviewed_mappings(source, target, reviewed_mappings)
    used_target_ids = set(mapping.values())
    review_only: list[dict[str, Any]] = []

    for match in comparison.matches:
        source_id = match.source_ref.remote_id
        target_id = match.target_ref.remote_id
        if source_id in mapping:
            continue
        if match.ambiguous:
            review_only.append(
                {
                    "kind": "ambiguous_video_match",
                    "source_video_id": source_id,
                    "suggested_target_video_id": target_id,
                    "source_title": match.source_title,
                    "target_title": match.target_title,
                    "score": match.score,
                }
            )
            continue
        if target_id in used_target_ids:
            review_only.append(
                {
                    "kind": "target_video_reused",
                    "source_video_id": source_id,
                    "target_video_id": target_id,
                }
            )
            continue
        mapping[source_id] = target_id
        used_target_ids.add(target_id)

    mapped_source_ids = set(mapping)
    for missing in comparison.missing_on_target:
        if missing.ref.remote_id not in mapped_source_ids:
            review_only.append(
                {
                    "kind": "source_video_not_mapped",
                    "source_video_id": missing.ref.remote_id,
                    "source_title": missing.title,
                }
            )
    return mapping, review_only


def build_vk_catalog_plan(
    source: AuditPackage,
    target: AuditPackage,
    *,
    reviewed_mappings: dict[str, str] | None = None,
) -> dict[str, Any]:
    if source.channel.ref.platform.value != "youtube":
        raise ValueError("VK catalog source must be a YouTube AuditPackage")
    if target.channel.ref.platform.value != "vk":
        raise ValueError("VK catalog target must be a VK AuditPackage")

    mapping, review_only = _build_mapping(source, target, reviewed_mappings or {})
    source_videos = {item.ref.remote_id: item for item in source.videos}
    target_videos = {item.ref.remote_id: item for item in target.videos}
    source_collections = {item.ref.remote_id: item for item in source.collections}
    target_collections = _target_collection_index(target)
    target_memberships = {
        (membership.collection_ref.remote_id, membership.video_ref.remote_id) for membership in target.memberships
    }

    album_operations: list[dict[str, Any]] = []
    collection_targets: dict[str, str | None] = {}
    for source_collection in sorted(source.collections, key=lambda item: item.title.casefold()):
        normalized = normalize_title(source_collection.title)
        candidates = target_collections.get(normalized, [])
        if len(candidates) > 1:
            review_only.append(
                {
                    "kind": "duplicate_target_album_title",
                    "source_collection_id": source_collection.ref.remote_id,
                    "title": source_collection.title,
                    "target_collection_ids": sorted(item.ref.remote_id for item in candidates),
                }
            )
            continue
        if candidates:
            collection_targets[source_collection.ref.remote_id] = candidates[0].ref.remote_id
            continue
        collection_targets[source_collection.ref.remote_id] = None
        album_operations.append(
            {
                "operation_id": f"album:create:{source_collection.ref.remote_id}",
                "source_collection_id": source_collection.ref.remote_id,
                "title": canonical_vk_text(source_collection.title),
                "normalized_title": normalized,
                "source_description": canonical_vk_text(source_collection.description),
            }
        )

    placement_operations: list[dict[str, Any]] = []
    seen_placements: set[tuple[str, str]] = set()
    for membership in source.memberships:
        source_video_id = membership.video_ref.remote_id
        target_video_id = mapping.get(source_video_id)
        if target_video_id is None:
            continue
        source_collection_id = membership.collection_ref.remote_id
        membership_collection = source_collections.get(source_collection_id)
        if membership_collection is None or source_collection_id not in collection_targets:
            continue
        target_collection_id = collection_targets[source_collection_id]
        if target_collection_id is not None and (target_collection_id, target_video_id) in target_memberships:
            continue
        key = (source_collection_id, target_video_id)
        if key in seen_placements:
            continue
        seen_placements.add(key)
        placement_operations.append(
            {
                "operation_id": f"placement:add:{source_collection_id}:{target_video_id}",
                "source_collection_id": source_collection_id,
                "album_title": canonical_vk_text(membership_collection.title),
                "target_collection_id": target_collection_id,
                "target_video_id": target_video_id,
                "source_video_id": source_video_id,
            }
        )

    text_operations: list[dict[str, Any]] = []
    for source_video_id, target_video_id in sorted(mapping.items()):
        source_video = source_videos[source_video_id]
        target_video = target_videos[target_video_id]
        try:
            publication = render_vk_publication(source_video.title, source_video.description)
        except ValueError as exc:
            review_only.append(
                {
                    "kind": "description_requires_editorial_review",
                    "source_video_id": source_video_id,
                    "target_video_id": target_video_id,
                    "message": str(exc),
                }
            )
            continue
        before_title = canonical_vk_text(target_video.title)
        before_description = canonical_vk_text(target_video.description)
        after_title = canonical_vk_text(publication.title)
        after_description = canonical_vk_text(publication.description)
        if before_title == after_title and before_description == after_description:
            continue
        text_operations.append(
            {
                "operation_id": f"video-text:update:{target_video_id}",
                "source_video_id": source_video_id,
                "target_video_id": target_video_id,
                "before_title": before_title,
                "after_title": after_title,
                "before_description": before_description,
                "after_description": after_description,
                "before_title_sha256": text_sha256(before_title),
                "after_title_sha256": text_sha256(after_title),
                "before_description_sha256": text_sha256(before_description),
                "after_description_sha256": text_sha256(after_description),
                "publication_policy_version": publication.policy_version,
            }
        )

    plan: dict[str, Any] = {
        "schema_name": VK_CATALOG_PLAN_SCHEMA,
        "schema_version": VK_CATALOG_PLAN_VERSION,
        "policy_version": VK_CATALOG_POLICY_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "source_snapshot_id": str(source.snapshot_id),
        "target_snapshot_id": str(target.snapshot_id),
        "source_channel_id": source.channel.ref.channel_id,
        "target_community_id": int(target.channel.ref.channel_id),
        "target_video_ids_sha256": target_video_ids_sha256(target),
        "initial_catalog_state_sha256": catalog_state_sha256(target),
        "reviewed_mappings": dict(sorted((reviewed_mappings or {}).items())),
        "resolved_video_mappings": dict(sorted(mapping.items())),
        "album_operations": album_operations,
        "placement_operations": sorted(placement_operations, key=lambda item: item["operation_id"]),
        "text_operations": text_operations,
        "review_only": sorted(review_only, key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True)),
    }
    plan["summary"] = {
        "resolved_video_mappings": len(mapping),
        "albums_to_create": len(album_operations),
        "placements_to_add": len(placement_operations),
        "video_texts_to_update": len(text_operations),
        "review_only": len(review_only),
        "total_operations": len(album_operations) + len(placement_operations) + len(text_operations),
    }
    plan["plan_sha256"] = calculate_vk_catalog_plan_sha256(plan)
    validate_vk_catalog_plan(plan)
    return plan


def calculate_vk_catalog_plan_sha256(plan: dict[str, Any]) -> str:
    return canonical_sha256({key: value for key, value in plan.items() if key != "plan_sha256"})


def validate_vk_catalog_plan(plan: dict[str, Any]) -> None:
    if plan.get("schema_name") != VK_CATALOG_PLAN_SCHEMA:
        raise ValueError("Unexpected VK catalog plan schema")
    if plan.get("schema_version") != VK_CATALOG_PLAN_VERSION:
        raise ValueError("Unsupported VK catalog plan version")
    community_id = plan.get("target_community_id")
    if not isinstance(community_id, int) or community_id <= 0:
        raise ValueError("target_community_id must be a positive integer")
    for field in ("target_video_ids_sha256", "initial_catalog_state_sha256", "plan_sha256"):
        value = plan.get(field)
        if not isinstance(value, str) or not value.startswith("sha256:"):
            raise ValueError(f"{field} must contain a SHA-256 digest")
    expected = calculate_vk_catalog_plan_sha256(plan)
    if plan["plan_sha256"] != expected:
        raise ValueError("VK catalog plan self-digest does not match its contents")

    operation_ids: list[str] = []
    for section in ("album_operations", "placement_operations", "text_operations"):
        operations = plan.get(section)
        if not isinstance(operations, list):
            raise ValueError(f"{section} must be a list")
        for operation in operations:
            if not isinstance(operation, dict) or not isinstance(operation.get("operation_id"), str):
                raise ValueError(f"Invalid operation in {section}")
            operation_ids.append(operation["operation_id"])
    duplicates = [item for item, count in Counter(operation_ids).items() if count > 1]
    if duplicates:
        raise ValueError(f"Duplicate operation IDs: {duplicates}")

    for operation in plan["text_operations"]:
        for side in ("before", "after"):
            for field in ("title", "description"):
                value = str(operation[f"{side}_{field}"])
                if operation[f"{side}_{field}_sha256"] != text_sha256(value):
                    raise ValueError(f"Text hash mismatch in {operation['operation_id']}: {side}_{field}")


__all__ = [
    "VK_CATALOG_PLAN_SCHEMA",
    "VK_CATALOG_PLAN_VERSION",
    "VK_CATALOG_POLICY_VERSION",
    "build_vk_catalog_plan",
    "calculate_vk_catalog_plan_sha256",
    "catalog_state_sha256",
    "target_video_ids_sha256",
    "text_sha256",
    "validate_vk_catalog_plan",
]
