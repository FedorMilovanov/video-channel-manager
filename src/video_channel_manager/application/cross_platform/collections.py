from __future__ import annotations

from collections import defaultdict

from video_channel_manager.application.cross_platform.models import CollectionGap, MissingVideo
from video_channel_manager.application.identity import (
    canonicalize_collection_title,
    canonicalize_identity_title,
)
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


def _is_system_collection(collection_id: str, privacy_status: str | None, metadata: dict[str, object]) -> bool:
    raw_id = metadata.get("id")
    return privacy_status == "system" or collection_id.startswith("-") or isinstance(raw_id, int) and raw_id < 0


def build_collection_gaps(
    source: AuditPackage,
    target: AuditPackage,
    source_to_target_video: dict[str, str],
) -> list[CollectionGap]:
    # Wave 8C will replace this title-only lookup with reviewed collection IDs.
    target_collections = {
        canonicalize_collection_title(item.title).canonical: item
        for item in target.collections
        if not _is_system_collection(item.ref.remote_id, item.privacy_status, item.metadata)
    }
    source_members: dict[str, set[str]] = defaultdict(set)
    target_members: dict[str, set[str]] = defaultdict(set)
    for membership in source.memberships:
        source_members[membership.collection_ref.remote_id].add(membership.video_ref.remote_id)
    for membership in target.memberships:
        target_members[membership.collection_ref.remote_id].add(membership.video_ref.remote_id)

    gaps: list[CollectionGap] = []
    for source_collection in sorted(source.collections, key=lambda item: item.title.casefold()):
        source_title_identity = canonicalize_collection_title(source_collection.title)
        target_collection = target_collections.get(source_title_identity.canonical)
        target_title_identity = (
            canonicalize_collection_title(target_collection.title) if target_collection is not None else None
        )
        source_video_ids = source_members.get(source_collection.ref.remote_id, set())
        expected_target_ids = {
            source_to_target_video[source_video_id]
            for source_video_id in source_video_ids
            if source_video_id in source_to_target_video
        }
        actual_target_ids = (
            target_members.get(target_collection.ref.remote_id, set()) if target_collection is not None else set()
        )
        gaps.append(
            CollectionGap(
                source_collection_id=source_collection.ref.remote_id,
                source_title=source_collection.title,
                source_title_identity=source_title_identity,
                target_collection_id=target_collection.ref.remote_id if target_collection is not None else None,
                target_title=target_collection.title if target_collection is not None else None,
                target_title_identity=target_title_identity,
                source_member_count=len(source_video_ids),
                matched_source_member_count=len(expected_target_ids),
                target_member_count=len(actual_target_ids),
                missing_target_video_ids=sorted(expected_target_ids - actual_target_ids),
            )
        )
    return gaps
