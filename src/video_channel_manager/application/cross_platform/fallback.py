from __future__ import annotations

from collections import defaultdict

from video_channel_manager.application.cross_platform.models import (
    MatchCandidateEvidence,
    MatchConflict,
    VideoMatch,
)
from video_channel_manager.application.cross_platform.normalize import (
    candidate_evidence,
    candidate_keys,
    candidate_score,
    duration_delta,
    video_match,
)
from video_channel_manager.application.identity import canonicalize_identity_title
from video_channel_manager.exchange.audit_package import AuditPackage


def fallback_candidates(
    source: AuditPackage,
    target: AuditPackage,
    *,
    available_source: set[int],
    available_target: set[int],
    min_score: float,
    max_duration_delta_seconds: int,
) -> dict[tuple[int, int], MatchCandidateEvidence]:
    target_key_index: dict[str, set[int]] = defaultdict(set)
    for target_index in available_target:
        for key in candidate_keys(target.videos[target_index].title):
            target_key_index[key].add(target_index)

    candidates: dict[tuple[int, int], MatchCandidateEvidence] = {}
    for source_index in sorted(available_source, key=lambda i: source.videos[i].ref.remote_id):
        source_video = source.videos[source_index]
        target_indices: set[int] = set()
        for key in candidate_keys(source_video.title):
            target_indices.update(target_key_index.get(key, set()))
        for target_index in sorted(target_indices, key=lambda i: target.videos[i].ref.remote_id):
            target_video = target.videos[target_index]
            delta = duration_delta(source_video, target_video)
            if delta is not None and delta > max_duration_delta_seconds:
                continue
            score, delta = candidate_score(source_video, target_video)
            if score < min_score:
                continue
            candidates[(source_index, target_index)] = candidate_evidence(
                source_video,
                target_video,
                score=score,
                delta=delta,
            )
    return candidates


def fallback_components(
    source: AuditPackage,
    target: AuditPackage,
    candidates: dict[tuple[int, int], MatchCandidateEvidence],
) -> tuple[list[VideoMatch], list[MatchConflict], set[int], set[int]]:
    source_neighbors: dict[int, set[int]] = defaultdict(set)
    target_neighbors: dict[int, set[int]] = defaultdict(set)
    for source_index, target_index in candidates:
        source_neighbors[source_index].add(target_index)
        target_neighbors[target_index].add(source_index)

    matches: list[VideoMatch] = []
    conflicts: list[MatchConflict] = []
    resolved_source: set[int] = set()
    resolved_target: set[int] = set()
    remaining_source = set(source_neighbors)
    while remaining_source:
        start = min(remaining_source, key=lambda i: source.videos[i].ref.remote_id)
        component_source: set[int] = set()
        component_target: set[int] = set()
        source_stack = [start]
        while source_stack:
            source_index = source_stack.pop()
            if source_index in component_source:
                continue
            component_source.add(source_index)
            for target_index in source_neighbors[source_index]:
                if target_index not in component_target:
                    component_target.add(target_index)
                    source_stack.extend(target_neighbors[target_index] - component_source)

        remaining_source -= component_source
        resolved_source.update(component_source)
        resolved_target.update(component_target)
        evidence = sorted(
            (
                item
                for (source_index, target_index), item in candidates.items()
                if source_index in component_source and target_index in component_target
            ),
            key=lambda item: (-item.score, item.source_ref.remote_id, item.target_ref.remote_id),
        )
        if len(component_source) == 1 and len(component_target) == 1:
            source_index = next(iter(component_source))
            target_index = next(iter(component_target))
            item = candidates[(source_index, target_index)]
            matches.append(
                video_match(
                    source.videos[source_index],
                    target.videos[target_index],
                    method="fuzzy_unique",
                    score=item.score,
                    delta=item.duration_delta_seconds,
                )
            )
            continue
        source_indices = sorted(component_source, key=lambda i: source.videos[i].ref.remote_id)
        target_indices = sorted(component_target, key=lambda i: target.videos[i].ref.remote_id)
        conflicts.append(
            MatchConflict(
                reason="non_unique_fallback",
                source_refs=[source.videos[index].ref for index in source_indices],
                target_refs=[target.videos[index].ref for index in target_indices],
                source_title_identities=[
                    canonicalize_identity_title(source.videos[index].title) for index in source_indices
                ],
                target_title_identities=[
                    canonicalize_identity_title(target.videos[index].title) for index in target_indices
                ],
                candidates=evidence,
            )
        )
    return matches, conflicts, resolved_source, resolved_target
