from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from video_channel_manager.application.cross_platform import compare_audit_packages, normalize_title
from video_channel_manager.domain.models import CollectionMembership, CollectionRecord
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk.text_writer import canonical_vk_text

VK_CATALOG_POLICY_SCHEMA = "video-manager.vk-catalog-policy"
VK_CATALOG_POLICY_VERSION = 1


@dataclass(frozen=True, slots=True)
class VkCatalogPolicy:
    title_overrides: dict[str, str]
    excluded_titles: frozenset[str]
    skip_collections_without_mapped_videos: bool = True

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_name": VK_CATALOG_POLICY_SCHEMA,
            "schema_version": VK_CATALOG_POLICY_VERSION,
            "title_overrides": dict(sorted(self.title_overrides.items())),
            "excluded_titles": sorted(self.excluded_titles),
            "skip_collections_without_mapped_videos": self.skip_collections_without_mapped_videos,
        }

    @property
    def sha256(self) -> str:
        encoded = json.dumps(
            self.to_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def parse_vk_catalog_policy(payload: object | None) -> VkCatalogPolicy:
    if payload is None:
        return VkCatalogPolicy(title_overrides={}, excluded_titles=frozenset())
    if not isinstance(payload, dict):
        raise ValueError("VK catalog policy must be a JSON object")
    allowed = {
        "schema_name",
        "schema_version",
        "title_overrides",
        "excluded_titles",
        "skip_collections_without_mapped_videos",
    }
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(f"Unknown VK catalog policy fields: {unknown}")
    if payload.get("schema_name") != VK_CATALOG_POLICY_SCHEMA:
        raise ValueError("Unexpected VK catalog policy schema")
    if payload.get("schema_version") != VK_CATALOG_POLICY_VERSION:
        raise ValueError("Unsupported VK catalog policy version")

    raw_overrides = payload.get("title_overrides", {})
    if not isinstance(raw_overrides, dict):
        raise ValueError("title_overrides must be an object")
    title_overrides: dict[str, str] = {}
    target_titles: dict[str, str] = {}
    for raw_source_title, raw_target_title in raw_overrides.items():
        if not isinstance(raw_source_title, str) or not isinstance(raw_target_title, str):
            raise ValueError("title_overrides keys and values must be strings")
        source_title = normalize_title(raw_source_title)
        target_title = canonical_vk_text(raw_target_title)
        if not source_title or not target_title:
            raise ValueError("title_overrides cannot contain blank titles")
        target_normalized = normalize_title(target_title)
        existing_source = target_titles.get(target_normalized)
        if existing_source is not None and existing_source != source_title:
            raise ValueError(f"Two source titles map to the same VK album title: {existing_source!r}, {source_title!r}")
        title_overrides[source_title] = target_title
        target_titles[target_normalized] = source_title

    raw_excluded = payload.get("excluded_titles", [])
    if not isinstance(raw_excluded, list) or not all(isinstance(item, str) for item in raw_excluded):
        raise ValueError("excluded_titles must be an array of strings")
    excluded_titles = frozenset(normalize_title(item) for item in raw_excluded if normalize_title(item))
    overlapping = sorted(set(title_overrides) & excluded_titles)
    if overlapping:
        raise ValueError(f"A source title cannot be both overridden and excluded: {overlapping}")

    skip_empty = payload.get("skip_collections_without_mapped_videos", True)
    if not isinstance(skip_empty, bool):
        raise ValueError("skip_collections_without_mapped_videos must be boolean")
    return VkCatalogPolicy(
        title_overrides=title_overrides,
        excluded_titles=excluded_titles,
        skip_collections_without_mapped_videos=skip_empty,
    )


def _candidate_mapped_source_ids(
    source: AuditPackage,
    target: AuditPackage,
    reviewed_mappings: dict[str, str],
) -> set[str]:
    mapped_source_ids = set(reviewed_mappings)
    used_target_ids = set(reviewed_mappings.values())
    comparison = compare_audit_packages(source, target)
    for match in comparison.matches:
        source_id = match.source_ref.remote_id
        target_id = match.target_ref.remote_id
        if source_id in mapped_source_ids or match.ambiguous or target_id in used_target_ids:
            continue
        mapped_source_ids.add(source_id)
        used_target_ids.add(target_id)
    return mapped_source_ids


def apply_vk_catalog_policy(
    source: AuditPackage,
    target: AuditPackage,
    *,
    reviewed_mappings: dict[str, str],
    policy: VkCatalogPolicy,
) -> tuple[AuditPackage, list[dict[str, Any]]]:
    mapped_source_ids = _candidate_mapped_source_ids(source, target, reviewed_mappings)
    mapped_memberships = [
        membership for membership in source.memberships if membership.video_ref.remote_id in mapped_source_ids
    ]
    mapped_collection_ids = {membership.collection_ref.remote_id for membership in mapped_memberships}
    retained_collections: list[CollectionRecord] = []
    retained_collection_ids: set[str] = set()
    policy_review: list[dict[str, Any]] = []
    normalized_final_titles: dict[str, str] = {}

    for collection in source.collections:
        collection_id = collection.ref.remote_id
        source_title_normalized = normalize_title(collection.title)
        if source_title_normalized in policy.excluded_titles:
            policy_review.append(
                {
                    "kind": "collection_excluded_by_policy",
                    "source_collection_id": collection_id,
                    "source_title": collection.title,
                }
            )
            continue
        if policy.skip_collections_without_mapped_videos and collection_id not in mapped_collection_ids:
            policy_review.append(
                {
                    "kind": "collection_skipped_without_mapped_videos",
                    "source_collection_id": collection_id,
                    "source_title": collection.title,
                }
            )
            continue

        target_title = policy.title_overrides.get(source_title_normalized, canonical_vk_text(collection.title))
        normalized_target_title = normalize_title(target_title)
        existing_collection_id = normalized_final_titles.get(normalized_target_title)
        if existing_collection_id is not None:
            raise ValueError(
                "VK catalog policy produces duplicate normalized album titles: "
                f"{existing_collection_id!r} and {collection_id!r} → {target_title!r}"
            )
        normalized_final_titles[normalized_target_title] = collection_id
        retained_collection_ids.add(collection_id)
        retained_collections.append(collection.model_copy(update={"title": target_title}))
        if target_title != canonical_vk_text(collection.title):
            policy_review.append(
                {
                    "kind": "collection_title_overridden",
                    "source_collection_id": collection_id,
                    "source_title": collection.title,
                    "target_title": target_title,
                }
            )

    retained_memberships: list[CollectionMembership] = [
        membership
        for membership in mapped_memberships
        if membership.collection_ref.remote_id in retained_collection_ids
    ]
    curated = source.model_copy(
        update={
            "collections": retained_collections,
            "memberships": retained_memberships,
        }
    )
    return curated, policy_review


__all__ = [
    "VK_CATALOG_POLICY_SCHEMA",
    "VK_CATALOG_POLICY_VERSION",
    "VkCatalogPolicy",
    "apply_vk_catalog_policy",
    "parse_vk_catalog_policy",
]
