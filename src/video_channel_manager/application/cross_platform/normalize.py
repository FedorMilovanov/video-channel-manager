from __future__ import annotations

from difflib import SequenceMatcher

from video_channel_manager.application.cross_platform.models import (
    MatchCandidateEvidence,
    MatchMethod,
    VideoMatch,
)
from video_channel_manager.application.identity import (
    canonicalize_description,
    canonicalize_identity_title,
)
from video_channel_manager.domain.models import VideoRecord


def normalize_title(value: str) -> str:
    """Compatibility value backed by the versioned identity-title contract."""
    return canonicalize_identity_title(value).canonical


def title_similarity(left: str, right: str) -> float:
    normalized_left = normalize_title(left)
    normalized_right = normalize_title(right)
    sequence = SequenceMatcher(None, normalized_left, normalized_right).ratio()
    left_tokens = set(normalized_left.split())
    right_tokens = set(normalized_right.split())
    union = left_tokens | right_tokens
    intersection = left_tokens & right_tokens
    jaccard = len(intersection) / len(union) if union else 1.0
    containment = len(intersection) / min(len(left_tokens), len(right_tokens)) if left_tokens and right_tokens else 1.0
    return min(1.0, sequence * 0.55 + jaccard * 0.30 + containment * 0.15)


def duration_delta(left: VideoRecord, right: VideoRecord) -> int | None:
    if left.duration_seconds is None or right.duration_seconds is None:
        return None
    return abs(left.duration_seconds - right.duration_seconds)


def _duration_similarity(delta: int | None) -> float:
    if delta is None:
        return 0.5
    if delta == 0:
        return 1.0
    if delta <= 3:
        return 0.95
    if delta <= 10:
        return 0.70
    if delta <= 20:
        return 0.40
    return 0.0


def candidate_score(source: VideoRecord, target: VideoRecord) -> tuple[float, int | None]:
    delta = duration_delta(source, target)
    score = title_similarity(source.title, target.title) * 0.72 + _duration_similarity(delta) * 0.28
    if normalize_title(source.title) == normalize_title(target.title):
        score += 0.08
    return min(score, 1.0), delta


def candidate_keys(title: str) -> set[str]:
    normalized = normalize_title(title)
    tokens = {f"token:{token}" for token in normalized.split() if len(token) >= 3}
    compact = normalized.replace(" ", "")
    trigrams = {f"gram:{compact[index : index + 3]}" for index in range(max(0, len(compact) - 2))}
    return tokens | trigrams


def candidate_evidence(
    source: VideoRecord,
    target: VideoRecord,
    *,
    score: float | None = None,
    delta: int | None = None,
) -> MatchCandidateEvidence:
    computed_score, computed_delta = candidate_score(source, target)
    source_title_identity = canonicalize_identity_title(source.title)
    target_title_identity = canonicalize_identity_title(target.title)
    return MatchCandidateEvidence(
        source_ref=source.ref,
        target_ref=target.ref,
        source_title_identity=source_title_identity,
        target_title_identity=target_title_identity,
        score=round(computed_score if score is None else score, 6),
        duration_delta_seconds=computed_delta if delta is None else delta,
        exact_normalized_title=source_title_identity.canonical == target_title_identity.canonical,
    )


def video_match(
    source: VideoRecord,
    target: VideoRecord,
    *,
    method: MatchMethod,
    score: float | None = None,
    delta: int | None = None,
) -> VideoMatch:
    computed_score, computed_delta = candidate_score(source, target)
    source_title_identity = canonicalize_identity_title(source.title)
    target_title_identity = canonicalize_identity_title(target.title)
    source_description_identity = canonicalize_description(source.description)
    target_description_identity = canonicalize_description(target.description)
    return VideoMatch(
        source_ref=source.ref,
        target_ref=target.ref,
        source_title=source.title,
        target_title=target.title,
        source_title_identity=source_title_identity,
        target_title_identity=target_title_identity,
        source_description_identity=source_description_identity,
        target_description_identity=target_description_identity,
        score=round(computed_score if score is None else score, 6),
        duration_delta_seconds=computed_delta if delta is None else delta,
        exact_normalized_title=source_title_identity.canonical == target_title_identity.canonical,
        exact_description=source_description_identity.canonical == target_description_identity.canonical,
        match_method=method,
    )
