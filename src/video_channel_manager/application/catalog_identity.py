from __future__ import annotations

from collections import defaultdict
from typing import Literal

from pydantic import Field

from video_channel_manager.application.identity import (
    CanonicalTextEvidence,
    canonicalize_collection_title,
)
from video_channel_manager.application.identity.digest import evidence_digest
from video_channel_manager.domain.models import (
    CollectionRecord,
    RemoteRef,
    StrictModel,
)
from video_channel_manager.exchange.audit_package import AuditPackage

CollectionDecision = Literal["mapped", "create", "conflict"]
CollectionConflictReason = Literal[
    "creation_not_approved",
    "unreviewed_existing_candidate",
    "duplicate_canonical_target_title",
    "approved_create_conflicts_with_target",
]


class CollectionIdentityDecision(StrictModel):
    source_ref: RemoteRef
    source_title_identity: CanonicalTextEvidence
    decision: CollectionDecision
    target_ref: RemoteRef | None = None
    target_title_identity: CanonicalTextEvidence | None = None
    title_drift: bool = False
    conflict_reason: CollectionConflictReason | None = None
    candidate_target_refs: list[RemoteRef] = Field(default_factory=list)
    candidate_title_identities: list[CanonicalTextEvidence] = Field(default_factory=list)
    source_member_video_ids: list[str] = Field(default_factory=list)
    mapped_target_video_ids: list[str] = Field(default_factory=list)
    unmapped_source_video_ids: list[str] = Field(default_factory=list)
    actual_target_video_ids: list[str] = Field(default_factory=list)
    missing_target_video_ids: list[str] = Field(default_factory=list)
    extra_target_video_ids: list[str] = Field(default_factory=list)


class CatalogIdentityEvidence(StrictModel):
    schema_name: str = "video-manager.catalog-identity-evidence"
    schema_version: str = "1.0"
    ruleset_version: str = "wave-8c-v1"
    project_key: str | None = None
    source_snapshot_id: str
    target_snapshot_id: str
    source_channel: RemoteRef
    target_channel: RemoteRef
    reviewed_collection_mappings: dict[str, str] = Field(default_factory=dict)
    approved_collection_creates: list[str] = Field(default_factory=list)
    decisions: list[CollectionIdentityDecision] = Field(default_factory=list)
    digest: str

    @property
    def mapped_count(self) -> int:
        return sum(item.decision == "mapped" for item in self.decisions)

    @property
    def create_count(self) -> int:
        return sum(item.decision == "create" for item in self.decisions)

    @property
    def conflict_count(self) -> int:
        return sum(item.decision == "conflict" for item in self.decisions)


def _is_system_collection(collection: CollectionRecord) -> bool:
    raw_id = collection.metadata.get("id")
    return (
        collection.privacy_status == "system"
        or collection.ref.remote_id.startswith("-")
        or isinstance(raw_id, int)
        and raw_id < 0
        or bool(collection.metadata.get("is_system"))
    )


def _catalog_identity_payload(evidence: CatalogIdentityEvidence) -> dict[str, object]:
    return evidence.model_dump(mode="json", exclude={"digest"})


def calculate_catalog_identity_digest(evidence: CatalogIdentityEvidence) -> str:
    return evidence_digest(_catalog_identity_payload(evidence))


def validate_catalog_identity_evidence(evidence: CatalogIdentityEvidence) -> None:
    if evidence.digest != calculate_catalog_identity_digest(evidence):
        raise ValueError("Catalog identity evidence digest does not match its contents")
    source_ids = [item.source_ref.remote_id for item in evidence.decisions]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("Catalog identity evidence contains duplicate source decisions")
    mapped_target_ids = [
        item.target_ref.remote_id
        for item in evidence.decisions
        if item.decision == "mapped" and item.target_ref is not None
    ]
    if len(mapped_target_ids) != len(set(mapped_target_ids)):
        raise ValueError("Catalog identity evidence reuses a mapped target collection")
    for item in evidence.decisions:
        if item.decision == "mapped" and item.target_ref is None:
            raise ValueError("Mapped collection decision requires target_ref")
        if item.decision == "create" and item.target_ref is not None:
            raise ValueError("Create collection decision cannot contain target_ref")
        if item.decision == "conflict" and item.conflict_reason is None:
            raise ValueError("Conflict collection decision requires conflict_reason")
        if item.decision != "conflict" and item.conflict_reason is not None:
            raise ValueError("Resolved collection decision cannot contain conflict_reason")


def _validated_reviewed_collection_mappings(
    source: AuditPackage,
    target: AuditPackage,
    reviewed: dict[str, str],
) -> dict[str, str]:
    source_ids = {item.ref.remote_id for item in source.collections}
    target_ids = {
        item.ref.remote_id
        for item in target.collections
        if not _is_system_collection(item)
    }
    result: dict[str, str] = {}
    used_target_ids: set[str] = set()
    for raw_source_id, raw_target_id in reviewed.items():
        source_id = str(raw_source_id).strip()
        target_id = str(raw_target_id).strip()
        if source_id not in source_ids:
            raise ValueError(
                f"Reviewed collection mapping references unknown source collection: {source_id}"
            )
        if target_id not in target_ids:
            raise ValueError(
                f"Reviewed collection mapping references unknown target collection: {target_id}"
            )
        if target_id in used_target_ids:
            raise ValueError(
                f"Reviewed collection mappings reuse target collection: {target_id}"
            )
        result[source_id] = target_id
        used_target_ids.add(target_id)
    return dict(sorted(result.items()))


def _validated_approved_creates(source: AuditPackage, approved: set[str]) -> list[str]:
    source_ids = {item.ref.remote_id for item in source.collections}
    unknown = sorted(approved - source_ids)
    if unknown:
        raise ValueError(
            "Approved collection create references unknown source collection: "
            f"{', '.join(unknown)}"
        )
    return sorted(approved)


def build_catalog_identity_evidence(
    source: AuditPackage,
    target: AuditPackage,
    *,
    project_key: str | None,
    video_mapping: dict[str, str],
    reviewed_collection_mappings: dict[str, str] | None = None,
    approved_collection_creates: set[str] | None = None,
) -> CatalogIdentityEvidence:
    reviewed = _validated_reviewed_collection_mappings(
        source,
        target,
        reviewed_collection_mappings or {},
    )
    approved_creates = _validated_approved_creates(
        source,
        approved_collection_creates or set(),
    )
    overlap = sorted(set(reviewed) & set(approved_creates))
    if overlap:
        raise ValueError(
            "Source collections cannot be both mapped and approved for create: "
            f"{', '.join(overlap)}"
        )

    source_videos = {item.ref.remote_id for item in source.videos}
    target_videos = {item.ref.remote_id for item in target.videos}
    if set(video_mapping) - source_videos:
        raise ValueError(
            "Catalog identity video mapping references an unknown source video"
        )
    if set(video_mapping.values()) - target_videos:
        raise ValueError(
            "Catalog identity video mapping references an unknown target video"
        )
    if len(video_mapping.values()) != len(set(video_mapping.values())):
        raise ValueError("Catalog identity video mapping must be one-to-one")

    source_collections = {
        item.ref.remote_id: item for item in source.collections
    }
    target_collections = {
        item.ref.remote_id: item
        for item in target.collections
        if not _is_system_collection(item)
    }
    target_by_title: dict[str, list[CollectionRecord]] = defaultdict(list)
    for collection in target_collections.values():
        canonical_title = canonicalize_collection_title(collection.title).canonical
        target_by_title[canonical_title].append(collection)

    source_members: dict[str, set[str]] = defaultdict(set)
    target_members: dict[str, set[str]] = defaultdict(set)
    for membership in source.memberships:
        source_members[membership.collection_ref.remote_id].add(
            membership.video_ref.remote_id
        )
    for membership in target.memberships:
        target_members[membership.collection_ref.remote_id].add(
            membership.video_ref.remote_id
        )

    decisions: list[CollectionIdentityDecision] = []
    for source_id in sorted(source_collections):
        source_collection = source_collections[source_id]
        source_identity = canonicalize_collection_title(source_collection.title)
        source_member_ids = sorted(source_members.get(source_id, set()))
        mapped_target_ids = sorted(
            video_mapping[item]
            for item in source_member_ids
            if item in video_mapping
        )
        unmapped_source_ids = sorted(
            item for item in source_member_ids if item not in video_mapping
        )

        target_id = reviewed.get(source_id)
        if target_id is not None:
            target_collection = target_collections[target_id]
            target_identity = canonicalize_collection_title(target_collection.title)
            actual_target_ids = sorted(target_members.get(target_id, set()))
            expected_set = set(mapped_target_ids)
            actual_set = set(actual_target_ids)
            decisions.append(
                CollectionIdentityDecision(
                    source_ref=source_collection.ref,
                    source_title_identity=source_identity,
                    decision="mapped",
                    target_ref=target_collection.ref,
                    target_title_identity=target_identity,
                    title_drift=(
                        source_identity.canonical != target_identity.canonical
                    ),
                    source_member_video_ids=source_member_ids,
                    mapped_target_video_ids=mapped_target_ids,
                    unmapped_source_video_ids=unmapped_source_ids,
                    actual_target_video_ids=actual_target_ids,
                    missing_target_video_ids=sorted(expected_set - actual_set),
                    extra_target_video_ids=sorted(actual_set - expected_set),
                )
            )
            continue

        candidates = sorted(
            target_by_title.get(source_identity.canonical, []),
            key=lambda item: item.ref.remote_id,
        )
        candidate_refs = [item.ref for item in candidates]
        candidate_identities = [
            canonicalize_collection_title(item.title) for item in candidates
        ]
        if len(candidates) > 1:
            reason: CollectionConflictReason = (
                "duplicate_canonical_target_title"
            )
        elif len(candidates) == 1 and source_id in approved_creates:
            reason = "approved_create_conflicts_with_target"
        elif len(candidates) == 1:
            reason = "unreviewed_existing_candidate"
        elif source_id not in approved_creates:
            reason = "creation_not_approved"
        else:
            decisions.append(
                CollectionIdentityDecision(
                    source_ref=source_collection.ref,
                    source_title_identity=source_identity,
                    decision="create",
                    source_member_video_ids=source_member_ids,
                    mapped_target_video_ids=mapped_target_ids,
                    unmapped_source_video_ids=unmapped_source_ids,
                    missing_target_video_ids=mapped_target_ids,
                )
            )
            continue
        decisions.append(
            CollectionIdentityDecision(
                source_ref=source_collection.ref,
                source_title_identity=source_identity,
                decision="conflict",
                conflict_reason=reason,
                candidate_target_refs=candidate_refs,
                candidate_title_identities=candidate_identities,
                source_member_video_ids=source_member_ids,
                mapped_target_video_ids=mapped_target_ids,
                unmapped_source_video_ids=unmapped_source_ids,
            )
        )

    provisional = CatalogIdentityEvidence(
        project_key=project_key,
        source_snapshot_id=str(source.snapshot_id),
        target_snapshot_id=str(target.snapshot_id),
        source_channel=source.channel.ref,
        target_channel=target.channel.ref,
        reviewed_collection_mappings=reviewed,
        approved_collection_creates=approved_creates,
        decisions=decisions,
        digest="0" * 64,
    )
    evidence = provisional.model_copy(
        update={"digest": calculate_catalog_identity_digest(provisional)}
    )
    validate_catalog_identity_evidence(evidence)
    return evidence


__all__ = [
    "CatalogIdentityEvidence",
    "CollectionIdentityDecision",
    "build_catalog_identity_evidence",
    "calculate_catalog_identity_digest",
    "validate_catalog_identity_evidence",
]
