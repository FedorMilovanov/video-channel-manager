from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import Iterable

from pydantic import Field

from video_channel_manager.domain.models import RemoteRef, StrictModel, VideoRecord
from video_channel_manager.exchange.audit_package import AuditPackage

_BRAND_RE = re.compile(r"@thelegendarypoet|#thelegendarypoet|#theepicpoet|#shorts", re.IGNORECASE)
_NON_WORD_RE = re.compile(r"[^a-zа-я0-9]+", re.IGNORECASE)
_SPACE_RE = re.compile(r"\s+")
_AMBIGUITY_EPSILON = 0.005


class VideoMatch(StrictModel):
    source_ref: RemoteRef
    target_ref: RemoteRef
    source_title: str
    target_title: str
    score: float = Field(ge=0.0, le=1.0)
    duration_delta_seconds: int | None = Field(default=None, ge=0)
    exact_normalized_title: bool
    exact_description: bool
    ambiguous: bool = False


class MissingVideo(StrictModel):
    ref: RemoteRef
    title: str
    duration_seconds: int | None = Field(default=None, ge=0)
    privacy_status: str | None = None
    collection_titles: list[str] = Field(default_factory=list)


class CollectionGap(StrictModel):
    source_collection_id: str
    source_title: str
    target_collection_id: str | None = None
    target_title: str | None = None
    source_member_count: int = Field(ge=0)
    matched_source_member_count: int = Field(ge=0)
    target_member_count: int = Field(ge=0)
    missing_target_video_ids: list[str] = Field(default_factory=list)

    @property
    def missing_placement_count(self) -> int:
        return len(self.missing_target_video_ids)


class CrossPlatformComparison(StrictModel):
    schema_name: str = "video-manager.cross-platform-comparison"
    schema_version: str = "1.0"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_snapshot_id: str
    target_snapshot_id: str
    source_channel: RemoteRef
    target_channel: RemoteRef
    matches: list[VideoMatch] = Field(default_factory=list)
    missing_on_target: list[MissingVideo] = Field(default_factory=list)
    extra_on_target: list[MissingVideo] = Field(default_factory=list)
    collection_gaps: list[CollectionGap] = Field(default_factory=list)

    @property
    def ambiguous_match_count(self) -> int:
        return sum(item.ambiguous for item in self.matches)

    @property
    def title_drift_count(self) -> int:
        return sum(item.source_title != item.target_title for item in self.matches)

    @property
    def description_drift_count(self) -> int:
        return sum(not item.exact_description for item in self.matches)

    @property
    def missing_collection_count(self) -> int:
        return sum(item.target_collection_id is None for item in self.collection_gaps)

    @property
    def missing_placement_count(self) -> int:
        return sum(item.missing_placement_count for item in self.collection_gaps)


def normalize_title(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").casefold().replace("ё", "е")
    normalized = _BRAND_RE.sub(" ", normalized)
    normalized = normalized.replace("version", "версия")
    normalized = _NON_WORD_RE.sub(" ", normalized)
    return _SPACE_RE.sub(" ", normalized).strip()


def _title_similarity(left: str, right: str) -> float:
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


def _duration_delta(left: VideoRecord, right: VideoRecord) -> int | None:
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


def _candidate_score(source: VideoRecord, target: VideoRecord) -> tuple[float, int | None]:
    delta = _duration_delta(source, target)
    score = _title_similarity(source.title, target.title) * 0.72 + _duration_similarity(delta) * 0.28
    if normalize_title(source.title) == normalize_title(target.title):
        score += 0.08
    return min(score, 1.0), delta


def _collection_titles_by_video(audit: AuditPackage) -> dict[str, list[str]]:
    collection_titles = {item.ref.remote_id: item.title for item in audit.collections}
    result: dict[str, list[str]] = defaultdict(list)
    for membership in audit.memberships:
        title = collection_titles.get(membership.collection_ref.remote_id)
        if title is not None:
            result[membership.video_ref.remote_id].append(title)
    return result


def _missing_video(video: VideoRecord, collection_titles: dict[str, list[str]]) -> MissingVideo:
    return MissingVideo(
        ref=video.ref,
        title=video.title,
        duration_seconds=video.duration_seconds,
        privacy_status=video.privacy_status,
        collection_titles=sorted(collection_titles.get(video.ref.remote_id, []), key=str.casefold),
    )


def _is_system_collection(collection_id: str, privacy_status: str | None, metadata: dict[str, object]) -> bool:
    raw_id = metadata.get("id")
    return privacy_status == "system" or collection_id.startswith("-") or isinstance(raw_id, int) and raw_id < 0


def _build_collection_gaps(
    source: AuditPackage,
    target: AuditPackage,
    source_to_target_video: dict[str, str],
) -> list[CollectionGap]:
    target_collections = {
        normalize_title(item.title): item
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
        target_collection = target_collections.get(normalize_title(source_collection.title))
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
                target_collection_id=target_collection.ref.remote_id if target_collection is not None else None,
                target_title=target_collection.title if target_collection is not None else None,
                source_member_count=len(source_video_ids),
                matched_source_member_count=len(expected_target_ids),
                target_member_count=len(actual_target_ids),
                missing_target_video_ids=sorted(expected_target_ids - actual_target_ids),
            )
        )
    return gaps


def compare_audit_packages(
    source: AuditPackage,
    target: AuditPackage,
    *,
    min_score: float = 0.65,
    max_duration_delta_seconds: int = 3,
) -> CrossPlatformComparison:
    if source.channel.ref.platform == target.channel.ref.platform:
        raise ValueError("cross-platform comparison requires different source and target platforms")
    if not 0.0 <= min_score <= 1.0:
        raise ValueError("min_score must be between 0 and 1")
    if max_duration_delta_seconds < 0:
        raise ValueError("max_duration_delta_seconds cannot be negative")

    candidates: list[tuple[float, int, int, int | None]] = []
    for source_index, source_video in enumerate(source.videos):
        for target_index, target_video in enumerate(target.videos):
            score, delta = _candidate_score(source_video, target_video)
            duration_allowed = delta is None or delta <= max_duration_delta_seconds
            if score >= min_score and duration_allowed:
                candidates.append((score, source_index, target_index, delta))

    candidates.sort(
        key=lambda item: (
            -item[0],
            source.videos[item[1]].ref.remote_id,
            target.videos[item[2]].ref.remote_id,
        )
    )
    source_best_scores: dict[int, float] = {}
    target_best_scores: dict[int, float] = {}
    for score, source_index, target_index, _ in candidates:
        source_best_scores[source_index] = max(score, source_best_scores.get(source_index, 0.0))
        target_best_scores[target_index] = max(score, target_best_scores.get(target_index, 0.0))
    source_top_counts: dict[int, int] = defaultdict(int)
    target_top_counts: dict[int, int] = defaultdict(int)
    for score, source_index, target_index, _ in candidates:
        if abs(score - source_best_scores[source_index]) <= _AMBIGUITY_EPSILON:
            source_top_counts[source_index] += 1
        if abs(score - target_best_scores[target_index]) <= _AMBIGUITY_EPSILON:
            target_top_counts[target_index] += 1

    used_source: set[int] = set()
    used_target: set[int] = set()
    matches: list[VideoMatch] = []
    for score, source_index, target_index, delta in candidates:
        if source_index in used_source or target_index in used_target:
            continue
        source_video = source.videos[source_index]
        target_video = target.videos[target_index]
        used_source.add(source_index)
        used_target.add(target_index)
        matches.append(
            VideoMatch(
                source_ref=source_video.ref,
                target_ref=target_video.ref,
                source_title=source_video.title,
                target_title=target_video.title,
                score=round(score, 6),
                duration_delta_seconds=delta,
                exact_normalized_title=normalize_title(source_video.title) == normalize_title(target_video.title),
                exact_description=source_video.description.strip() == target_video.description.strip(),
                ambiguous=source_top_counts[source_index] > 1 or target_top_counts[target_index] > 1,
            )
        )

    matches.sort(key=lambda item: item.source_title.casefold())
    source_titles = _collection_titles_by_video(source)
    target_titles = _collection_titles_by_video(target)
    missing_on_target = [
        _missing_video(video, source_titles)
        for index, video in enumerate(source.videos)
        if index not in used_source
    ]
    extra_on_target = [
        _missing_video(video, target_titles)
        for index, video in enumerate(target.videos)
        if index not in used_target
    ]
    missing_on_target.sort(key=lambda item: item.title.casefold())
    extra_on_target.sort(key=lambda item: item.title.casefold())
    source_to_target_video = {item.source_ref.remote_id: item.target_ref.remote_id for item in matches}

    return CrossPlatformComparison(
        source_snapshot_id=str(source.snapshot_id),
        target_snapshot_id=str(target.snapshot_id),
        source_channel=source.channel.ref,
        target_channel=target.channel.ref,
        matches=matches,
        missing_on_target=missing_on_target,
        extra_on_target=extra_on_target,
        collection_gaps=_build_collection_gaps(source, target, source_to_target_video),
    )


def _duration_text(seconds: int | None) -> str:
    if seconds is None:
        return "—"
    return f"{seconds // 60}:{seconds % 60:02d}"


def _markdown_table(rows: Iterable[MissingVideo]) -> list[str]:
    lines = ["| Длительность | Название | ID | Коллекции |", "|---:|---|---|---|"]
    for item in rows:
        collections = "; ".join(item.collection_titles) or "—"
        lines.append(
            f"| {_duration_text(item.duration_seconds)} | {item.title.replace('|', '¦')} | "
            f"`{item.ref.remote_id}` | {collections.replace('|', '¦')} |"
        )
    return lines


def render_comparison_markdown(comparison: CrossPlatformComparison) -> str:
    public_long = [
        item
        for item in comparison.missing_on_target
        if item.privacy_status == "public" and (item.duration_seconds or 0) > 180
    ]
    public_short = [
        item
        for item in comparison.missing_on_target
        if item.privacy_status == "public" and (item.duration_seconds or 0) <= 180
    ]
    non_public = [item for item in comparison.missing_on_target if item.privacy_status != "public"]
    lines = [
        "# Сопоставление снимков каналов",
        "",
        f"Источник: `{comparison.source_channel.stable_key}`  ",
        f"Цель: `{comparison.target_channel.stable_key}`  ",
        f"Сформировано: `{comparison.generated_at.isoformat()}`  ",
        "Режим: только анализ; никаких удалённых изменений.",
        "",
        "## Итог",
        "",
        f"- Сопоставлено видео: **{len(comparison.matches)}**.",
        f"- Отсутствует на целевой платформе: **{len(comparison.missing_on_target)}**.",
        f"- Есть только на целевой платформе: **{len(comparison.extra_on_target)}**.",
        f"- Неоднозначных выбранных пар: **{comparison.ambiguous_match_count}**.",
        f"- Расхождений названий: **{comparison.title_drift_count}**.",
        f"- Расхождений описаний: **{comparison.description_drift_count}**.",
        f"- Отсутствующих целевых коллекций: **{comparison.missing_collection_count}**.",
        f"- Недостающих размещений в существующих коллекциях: **{comparison.missing_placement_count}**.",
        "",
        "## Публичные видео длиннее трёх минут, отсутствующие на цели",
        "",
        *_markdown_table(public_long),
        "",
        "## Публичные видео до трёх минут",
        "",
        "Перед переносом требуется проверить геометрию и фактический тип Short/обычного видео.",
        "",
        *_markdown_table(public_short),
        "",
        "## Непубличные видео",
        "",
        "Не включать в автоматический перенос без отдельного решения владельца.",
        "",
        *_markdown_table(non_public),
        "",
        "## Коллекции",
        "",
        "| Исходная коллекция | В источнике | Уже сопоставлено | На цели | Не хватает размещений | Статус |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for gap in comparison.collection_gaps:
        status = "существует" if gap.target_collection_id is not None else "нет целевой коллекции"
        lines.append(
            f"| {gap.source_title.replace('|', '¦')} | {gap.source_member_count} | "
            f"{gap.matched_source_member_count} | {gap.target_member_count} | "
            f"{gap.missing_placement_count} | {status} |"
        )
    lines.extend(
        [
            "",
            "## Метод",
            "",
            "Пары выбираются взаимно-однозначно по нормализованному названию и длительности. "
            "По умолчанию допускается расхождение длительности не более трёх секунд; "
            "неоднозначные группы явно помечаются и требуют ручной проверки.",
        ]
    )
    return "\n".join(lines)
