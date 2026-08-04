from __future__ import annotations

from collections import defaultdict

from video_channel_manager.application.cross_platform.models import MatchConflict, VideoMatch
from video_channel_manager.application.cross_platform.normalize import (
    candidate_evidence,
    candidate_score,
    normalize_title,
    video_match,
)
from video_channel_manager.application.identity import canonicalize_identity_title
from video_channel_manager.exchange.audit_package import AuditPackage


def reviewed_matches(
    source: AuditPackage,
    target: AuditPackage,
    reviewed_video_mapping: dict[str, str],
) -> tuple[list[VideoMatch], set[int], set[int]]:
    source_by_id = {video.ref.remote_id: (index, video) for index, video in enumerate(source.videos)}
    target_by_id = {video.ref.remote_id: (index, video) for index, video in enumerate(target.videos)}
    unknown_source_ids = sorted(set(reviewed_video_mapping) - set(source_by_id))
    unknown_target_ids = sorted(set(reviewed_video_mapping.values()) - set(target_by_id))
    if unknown_source_ids:
        raise ValueError(f"reviewed mapping references unknown source IDs: {', '.join(unknown_source_ids)}")
    if unknown_target_ids:
        raise ValueError(f"reviewed mapping references unknown target IDs: {', '.join(unknown_target_ids)}")
    target_ids = list(reviewed_video_mapping.values())
    if len(target_ids) != len(set(target_ids)):
        raise ValueError("reviewed mapping must be one-to-one: duplicate target ID")

    matches: list[VideoMatch] = []
    used_source: set[int] = set()
    used_target: set[int] = set()
    for source_id, target_id in sorted(reviewed_video_mapping.items()):
        source_index, source_video = source_by_id[source_id]
        target_index, target_video = target_by_id[target_id]
        matches.append(video_match(source_video, target_video, method="reviewed_mapping", score=1.0))
        used_source.add(source_index)
        used_target.add(target_index)
    return matches, used_source, used_target


def exact_title_phase(
    source: AuditPackage,
    target: AuditPackage,
    *,
    available_source: set[int],
    available_target: set[int],
    max_duration_delta_seconds: int,
) -> tuple[list[VideoMatch], list[MatchConflict], set[int], set[int]]:
    source_groups: dict[str, list[int]] = defaultdict(list)
    target_groups: dict[str, list[int]] = defaultdict(list)
    for source_index in available_source:
        normalized_title = normalize_title(source.videos[source_index].title)
        if normalized_title:
            source_groups[normalized_title].append(source_index)
    for target_index in available_target:
        normalized_title = normalize_title(target.videos[target_index].title)
        if normalized_title:
            target_groups[normalized_title].append(target_index)

    matches: list[VideoMatch] = []
    conflicts: list[MatchConflict] = []
    resolved_source: set[int] = set()
    resolved_target: set[int] = set()
    for normalized_title in sorted(set(source_groups) & set(target_groups)):
        source_indices = sorted(source_groups[normalized_title], key=lambda i: source.videos[i].ref.remote_id)
        target_indices = sorted(target_groups[normalized_title], key=lambda i: target.videos[i].ref.remote_id)
        resolved_source.update(source_indices)
        resolved_target.update(target_indices)
        source_identities = [canonicalize_identity_title(source.videos[index].title) for index in source_indices]
        target_identities = [canonicalize_identity_title(target.videos[index].title) for index in target_indices]
        if len(source_indices) != 1 or len(target_indices) != 1:
            conflicts.append(
                MatchConflict(
                    reason="duplicate_exact_title",
                    normalized_title=normalized_title,
                    source_refs=[source.videos[index].ref for index in source_indices],
                    target_refs=[target.videos[index].ref for index in target_indices],
                    source_title_identities=source_identities,
                    target_title_identities=target_identities,
                )
            )
            continue

        source_video = source.videos[source_indices[0]]
        target_video = target.videos[target_indices[0]]
        score, delta = candidate_score(source_video, target_video)
        if delta is not None and delta > max_duration_delta_seconds:
            conflicts.append(
                MatchConflict(
                    reason="exact_title_duration_mismatch",
                    normalized_title=normalized_title,
                    source_refs=[source_video.ref],
                    target_refs=[target_video.ref],
                    source_title_identities=source_identities,
                    target_title_identities=target_identities,
                    candidates=[candidate_evidence(source_video, target_video, score=score, delta=delta)],
                )
            )
            continue
        matches.append(
            video_match(
                source_video,
                target_video,
                method="exact_normalized_title",
                score=score,
                delta=delta,
            )
        )
    return matches, conflicts, resolved_source, resolved_target
