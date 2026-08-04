from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Any

from video_channel_manager.application.catalog_identity import (
    CatalogIdentityEvidence,
    build_catalog_identity_evidence,
    validate_catalog_identity_evidence,
)
from video_channel_manager.application.cross_platform import compare_audit_packages
from video_channel_manager.editorial._project_profiles import PROJECT_KEYS, resolve_project_key
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk.publishing import render_vk_publication
from video_channel_manager.platforms.vk.text_writer import canonical_vk_text

VK_CATALOG_PLAN_SCHEMA = "video-manager.vk-catalog-plan"
VK_CATALOG_PLAN_VERSION = 3
VK_CATALOG_POLICY_VERSION = "vk-catalog-exact-collection-v3"


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


def _build_mapping(
    source: AuditPackage,
    target: AuditPackage,
    reviewed_mappings: dict[str, str],
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    comparison = compare_audit_packages(source, target, reviewed_video_mapping=reviewed_mappings)
    mapping = _validated_reviewed_mappings(source, target, reviewed_mappings)
    used_target_ids = set(mapping.values())
    review_only: list[dict[str, Any]] = []

    for match in comparison.matches:
        source_id = match.source_ref.remote_id
        target_id = match.target_ref.remote_id
        if source_id in mapping:
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
    for conflict in comparison.conflicts:
        review_only.append(
            {
                "kind": "video_identity_conflict",
                "reason": conflict.reason,
                "source_video_ids": sorted(item.remote_id for item in conflict.source_refs),
                "target_video_ids": sorted(item.remote_id for item in conflict.target_refs),
            }
        )
    for missing in comparison.missing_on_target:
        if missing.ref.remote_id not in mapped_source_ids:
            review_only.append(
                {
                    "kind": "source_video_not_mapped",
                    "source_video_id": missing.ref.remote_id,
                    "source_title": missing.title,
                }
            )
    return dict(sorted(mapping.items())), review_only


def _resolved_catalog_project(source: AuditPackage, target: AuditPackage) -> str:
    project_key = resolve_project_key(
        {
            "channel_id": source.channel.ref.channel_id,
            "community_id": target.channel.ref.channel_id,
        }
    )
    if project_key is None:
        raise ValueError(
            "VK catalog project identity is unknown or conflicting; "
            "source channel and target community must resolve to one registered project"
        )
    return project_key


def _collection_review_items(evidence: CatalogIdentityEvidence) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for decision in evidence.decisions:
        source_id = decision.source_ref.remote_id
        if decision.decision == "conflict":
            items.append(
                {
                    "kind": "collection_identity_conflict",
                    "reason": decision.conflict_reason,
                    "source_collection_id": source_id,
                    "source_title": decision.source_title_identity.original,
                    "candidate_target_collection_ids": sorted(
                        item.remote_id for item in decision.candidate_target_refs
                    ),
                }
            )
        elif decision.decision == "mapped" and decision.title_drift:
            items.append(
                {
                    "kind": "reviewed_collection_title_drift",
                    "source_collection_id": source_id,
                    "target_collection_id": decision.target_ref.remote_id if decision.target_ref is not None else None,
                    "source_title": decision.source_title_identity.original,
                    "target_title": (
                        decision.target_title_identity.original if decision.target_title_identity is not None else None
                    ),
                }
            )
        if decision.unmapped_source_video_ids:
            items.append(
                {
                    "kind": "collection_contains_unmapped_source_videos",
                    "source_collection_id": source_id,
                    "source_video_ids": decision.unmapped_source_video_ids,
                }
            )
    return items


def build_vk_catalog_plan(
    source: AuditPackage,
    target: AuditPackage,
    *,
    reviewed_mappings: dict[str, str] | None = None,
    reviewed_collection_mappings: dict[str, str] | None = None,
    approved_collection_creates: set[str] | None = None,
) -> dict[str, Any]:
    if source.channel.ref.platform.value != "youtube":
        raise ValueError("VK catalog source must be a YouTube AuditPackage")
    if target.channel.ref.platform.value != "vk":
        raise ValueError("VK catalog target must be a VK AuditPackage")

    project_key = _resolved_catalog_project(source, target)
    mapping, review_only = _build_mapping(source, target, reviewed_mappings or {})
    source_videos = {item.ref.remote_id: item for item in source.videos}
    target_videos = {item.ref.remote_id: item for item in target.videos}
    source_collections = {item.ref.remote_id: item for item in source.collections}
    catalog_identity = build_catalog_identity_evidence(
        source,
        target,
        project_key=project_key,
        video_mapping=mapping,
        reviewed_collection_mappings=reviewed_collection_mappings,
        approved_collection_creates=approved_collection_creates,
    )
    review_only.extend(_collection_review_items(catalog_identity))

    album_operations: list[dict[str, Any]] = []
    collection_targets: dict[str, str | None] = {}
    resolved_collection_ids: set[str] = set()
    for decision in catalog_identity.decisions:
        source_id = decision.source_ref.remote_id
        if decision.decision == "conflict":
            continue
        resolved_collection_ids.add(source_id)
        if decision.decision == "mapped":
            if decision.target_ref is None:
                raise ValueError("Mapped catalog identity decision has no target collection")
            collection_targets[source_id] = decision.target_ref.remote_id
            continue
        collection_targets[source_id] = None
        source_collection = source_collections[source_id]
        album_operations.append(
            {
                "operation_id": f"album:create:{source_id}",
                "source_collection_id": source_id,
                "title": canonical_vk_text(source_collection.title),
                "source_description": canonical_vk_text(source_collection.description),
                "catalog_identity_digest": catalog_identity.digest,
            }
        )

    placement_operations: list[dict[str, Any]] = []
    seen_placements: set[tuple[str, str]] = set()
    decision_by_source = {item.source_ref.remote_id: item for item in catalog_identity.decisions}
    for membership in source.memberships:
        source_collection_id = membership.collection_ref.remote_id
        if source_collection_id not in resolved_collection_ids:
            continue
        source_video_id = membership.video_ref.remote_id
        target_video_id = mapping.get(source_video_id)
        if target_video_id is None:
            continue
        decision = decision_by_source[source_collection_id]
        if target_video_id not in decision.missing_target_video_ids:
            continue
        key = (source_collection_id, target_video_id)
        if key in seen_placements:
            continue
        seen_placements.add(key)
        placement_operations.append(
            {
                "operation_id": f"placement:add:{source_collection_id}:{target_video_id}",
                "source_collection_id": source_collection_id,
                "album_title": canonical_vk_text(source_collections[source_collection_id].title),
                "target_collection_id": collection_targets[source_collection_id],
                "target_video_id": target_video_id,
                "source_video_id": source_video_id,
                "catalog_identity_digest": catalog_identity.digest,
            }
        )

    text_operations: list[dict[str, Any]] = []
    for source_video_id, target_video_id in sorted(mapping.items()):
        source_video = source_videos[source_video_id]
        target_video = target_videos[target_video_id]
        try:
            publication = render_vk_publication(
                source_video.title,
                source_video.description,
                project_key=project_key,
            )
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
                "project_key": publication.project_key,
            }
        )

    plan: dict[str, Any] = {
        "schema_name": VK_CATALOG_PLAN_SCHEMA,
        "schema_version": VK_CATALOG_PLAN_VERSION,
        "policy_version": VK_CATALOG_POLICY_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "project_key": project_key,
        "source_snapshot_id": str(source.snapshot_id),
        "target_snapshot_id": str(target.snapshot_id),
        "source_channel_id": source.channel.ref.channel_id,
        "target_community_id": int(target.channel.ref.channel_id),
        "target_video_ids_sha256": target_video_ids_sha256(target),
        "initial_catalog_state_sha256": catalog_state_sha256(target),
        "reviewed_mappings": dict(sorted((reviewed_mappings or {}).items())),
        "resolved_video_mappings": mapping,
        "reviewed_collection_mappings": dict(sorted((reviewed_collection_mappings or {}).items())),
        "approved_collection_creates": sorted(approved_collection_creates or set()),
        "catalog_identity": catalog_identity.model_dump(mode="json"),
        "catalog_identity_sha256": catalog_identity.digest,
        "album_operations": sorted(album_operations, key=lambda item: item["operation_id"]),
        "placement_operations": sorted(placement_operations, key=lambda item: item["operation_id"]),
        "text_operations": text_operations,
        "review_only": sorted(review_only, key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True)),
    }
    plan["summary"] = {
        "resolved_video_mappings": len(mapping),
        "resolved_collection_mappings": catalog_identity.mapped_count,
        "albums_to_create": len(album_operations),
        "collection_conflicts": catalog_identity.conflict_count,
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


def _validate_catalog_operations(plan: dict[str, Any], evidence: CatalogIdentityEvidence) -> None:
    decision_by_source = {item.source_ref.remote_id: item for item in evidence.decisions}
    create_ids = {item.source_ref.remote_id for item in evidence.decisions if item.decision == "create"}
    actual_create_ids = {str(item["source_collection_id"]) for item in plan["album_operations"]}
    if actual_create_ids != create_ids:
        raise ValueError("Album operations do not exactly match approved catalog create decisions")

    placements: dict[str, set[str]] = defaultdict(set)
    for operation in plan["placement_operations"]:
        source_id = str(operation["source_collection_id"])
        decision = decision_by_source.get(source_id)
        if decision is None or decision.decision == "conflict":
            raise ValueError("Placement operation references unresolved collection identity")
        expected_target_id = decision.target_ref.remote_id if decision.target_ref is not None else None
        if operation.get("target_collection_id") != expected_target_id:
            raise ValueError("Placement operation target collection does not match catalog identity")
        if operation.get("catalog_identity_digest") != evidence.digest:
            raise ValueError("Placement operation catalog identity digest mismatch")
        placements[source_id].add(str(operation["target_video_id"]))
    for decision in evidence.decisions:
        expected = set(decision.missing_target_video_ids) if decision.decision != "conflict" else set()
        if placements.get(decision.source_ref.remote_id, set()) != expected:
            raise ValueError("Placement operations do not match semantic membership delta")

    for operation in plan["album_operations"]:
        if operation.get("catalog_identity_digest") != evidence.digest:
            raise ValueError("Album operation catalog identity digest mismatch")


def validate_vk_catalog_plan(plan: dict[str, Any]) -> None:
    if plan.get("schema_name") != VK_CATALOG_PLAN_SCHEMA:
        raise ValueError("Unexpected VK catalog plan schema")
    if plan.get("schema_version") != VK_CATALOG_PLAN_VERSION:
        raise ValueError("Unsupported VK catalog plan version")
    community_id = plan.get("target_community_id")
    if not isinstance(community_id, int) or isinstance(community_id, bool) or community_id <= 0:
        raise ValueError("target_community_id must be a positive integer")
    project_key = plan.get("project_key")
    if project_key not in PROJECT_KEYS:
        raise ValueError("project_key must identify a registered project")
    resolved_project = resolve_project_key(
        {
            "project_key": project_key,
            "channel_id": plan.get("source_channel_id"),
            "community_id": community_id,
        }
    )
    if resolved_project != project_key:
        raise ValueError("VK catalog plan project identity does not match its exact provider targets")
    for field in (
        "target_video_ids_sha256",
        "initial_catalog_state_sha256",
        "catalog_identity_sha256",
        "plan_sha256",
    ):
        value = plan.get(field)
        if not isinstance(value, str) or not value.startswith("sha256:"):
            raise ValueError(f"{field} must contain a SHA-256 digest")
    expected = calculate_vk_catalog_plan_sha256(plan)
    if plan["plan_sha256"] != expected:
        raise ValueError("VK catalog plan self-digest does not match its contents")

    evidence = CatalogIdentityEvidence.model_validate(plan.get("catalog_identity"))
    validate_catalog_identity_evidence(evidence)
    if evidence.digest != plan["catalog_identity_sha256"]:
        raise ValueError("VK catalog plan catalog identity digest mismatch")
    if evidence.project_key != project_key:
        raise ValueError("Catalog identity project mismatch")
    if evidence.source_snapshot_id != plan.get("source_snapshot_id"):
        raise ValueError("Catalog identity source snapshot mismatch")
    if evidence.target_snapshot_id != plan.get("target_snapshot_id"):
        raise ValueError("Catalog identity target snapshot mismatch")
    if evidence.reviewed_collection_mappings != plan.get("reviewed_collection_mappings"):
        raise ValueError("Reviewed collection mappings do not match catalog identity evidence")
    if evidence.approved_collection_creates != plan.get("approved_collection_creates"):
        raise ValueError("Approved collection creates do not match catalog identity evidence")

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

    _validate_catalog_operations(plan, evidence)
    for operation in plan["text_operations"]:
        if operation.get("project_key") != project_key:
            raise ValueError(f"Text operation project mismatch: {operation.get('operation_id')}")
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
