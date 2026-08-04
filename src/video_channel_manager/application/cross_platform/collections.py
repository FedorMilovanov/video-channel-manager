from __future__ import annotations

from collections import defaultdict

from video_channel_manager.application.catalog_identity import CatalogIdentityEvidence
from video_channel_manager.application.cross_platform.models import CollectionGap, MissingVideo
from video_channel_manager.application.identity import canonicalize_identity_title
from video_channel_manager.domain.models import VideoRecord
from video_channel_manager.exchange.audit_package import AuditPackage


def collection_titles_by_video(audit: AuditPackage) -> dict[str, list[str]]:
    collection_titles = {item.ref.remote_id: item.title for item in audit.collections}
    result: dict[str, list[str]] = defaultdict(list)
    for membership in audit.memberships:
        title = collection_titles.get(membership.collection_ref.remote_id)
        if title is not None:
            result[membership.video_ref.remote_id].append(title)
    return result


def missing_video(video: VideoRecord, collection_titles: dict[str, list[str]]) -> MissingVideo:
    return MissingVideo(
        ref=video.ref,
        title=video.title,
        title_identity=canonicalize_identity_title(video.title),
        duration_seconds=video.duration_seconds,
        privacy_status=video.privacy_status,
        collection_titles=sorted(collection_titles.get(video.ref.remote_id, []), key=str.casefold),
    )


def build_collection_gaps(
    source: AuditPackage,
    target: AuditPackage,
    evidence: CatalogIdentityEvidence,
) -> list[CollectionGap]:
    source_collections = {item.ref.remote_id: item for item in source.collections}
    target_collections = {item.ref.remote_id: item for item in target.collections}
    gaps: list[CollectionGap] = []
    for decision in evidence.decisions:
        source_collection = source_collections[decision.source_ref.remote_id]
        target_collection = (
            target_collections.get(decision.target_ref.remote_id)
            if decision.target_ref is not None
            else None
        )
        gaps.append(
            CollectionGap(
                source_collection_id=source_collection.ref.remote_id,
                source_title=source_collection.title,
                source_title_identity=decision.source_title_identity,
                decision=decision.decision,
                conflict_reason=decision.conflict_reason,
                target_collection_id=target_collection.ref.remote_id if target_collection is not None else None,
                target_title=target_collection.title if target_collection is not None else None,
                target_title_identity=decision.target_title_identity,
                source_member_count=len(decision.source_member_video_ids),
                matched_source_member_count=len(decision.mapped_target_video_ids),
                target_member_count=len(decision.actual_target_video_ids),
                unmapped_source_video_ids=decision.unmapped_source_video_ids,
                missing_target_video_ids=decision.missing_target_video_ids,
                extra_target_video_ids=decision.extra_target_video_ids,
            )
        )
    return gaps
