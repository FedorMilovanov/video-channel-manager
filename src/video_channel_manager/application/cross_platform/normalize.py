from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

from video_channel_manager.application.cross_platform.models import (
    MatchCandidateEvidence,
    MatchMethod,
    VideoMatch,
)
from video_channel_manager.domain.models import VideoRecord

_BRAND_RE = re.compile(r"@thelegendarypoet|#thelegendarypoet|#theepicpoet|#shorts", re.IGNORECASE)
_NON_WORD_RE = re.compile(r"[^a-zа-я0-9]+", re.IGNORECASE)
_SPACE_RE = re.compile(r"\s+")


def normalize_title(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").casefold().replace("ё", "е")
    normalized = _BRAND_RE.sub(" ", normalized)
    normalized = normalized.replace("version", "версия")
    normalized = _NON_WORD_RE.sub(" ", normalized)
    return _SPACE_RE.sub(" ", normalized).strip()


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
    return MatchCandidateEvidence(
        source_ref=source.ref,
        target_ref=target.ref,
        score=round(computed_score if score is None else score, 6),
        duration_delta_seconds=computed_delta if delta is None else delta,
        exact_normalized_title=normalize_title(source.title) == normalize_title(target.title),
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
    return VideoMatch(
        source_ref=source.ref,
        target_ref=target.ref,
        source_title=source.title,
        target_title=target.title,
        score=round(computed_score if score is None else score, 6),
        duration_delta_seconds=computed_delta if delta is None else delta,
        exact_normalized_title=normalize_title(source.title) == normalize_title(target.title),
        exact_description=source.description.strip() == target.description.strip(),
        match_method=method,
    )
