from __future__ import annotations

from typing import Iterable

from video_channel_manager.application.cross_platform.models import (
    CrossPlatformComparison,
    MatchConflict,
    MissingVideo,
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


def _conflict_table(conflicts: Iterable[MatchConflict]) -> list[str]:
    lines = ["| Причина | Source IDs | Target IDs | Кандидатов |", "|---|---|---|---:|"]
    for conflict in conflicts:
        source_ids = ", ".join(f"`{item.remote_id}`" for item in conflict.source_refs)
        target_ids = ", ".join(f"`{item.remote_id}`" for item in conflict.target_refs)
        lines.append(f"| {conflict.reason} | {source_ids} | {target_ids} | {len(conflict.candidates)} |")
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
    non_public = [
        item for item in comparison.missing_on_target if item.privacy_status != "public"
    ]
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
        f"- Конфликтных video-групп: **{comparison.conflict_count}**.",
        f"- Source-объектов в video-конфликтах: **{comparison.unresolved_source_count}**.",
        f"- Target-объектов в video-конфликтах: **{comparison.unresolved_target_count}**.",
        f"- Отсутствует на целевой платформе: **{len(comparison.missing_on_target)}**.",
        f"- Есть только на целевой платформе: **{len(comparison.extra_on_target)}**.",
        f"- Расхождений названий: **{comparison.title_drift_count}**.",
        f"- Расхождений описаний: **{comparison.description_drift_count}**.",
        f"- Collection-конфликтов: **{comparison.collection_conflict_count}**.",
        f"- Одобренных коллекций к созданию: **{comparison.missing_collection_count}**.",
        f"- Недостающих semantic placements: **{comparison.missing_placement_count}**.",
        "",
        "## Конфликты сопоставления видео",
        "",
        "Конфликтные объекты не считаются отсутствующими и не попадают в mapping или план загрузки.",
        "",
        *_conflict_table(comparison.conflicts),
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
        "| Исходная коллекция | Решение | Target | Source | Mapped | Target members | Missing | Extra |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for gap in comparison.collection_gaps:
        decision = (
            gap.decision
            if gap.conflict_reason is None
            else f"conflict: {gap.conflict_reason}"
        )
        target_id = (
            f"`{gap.target_collection_id}`"
            if gap.target_collection_id is not None
            else "—"
        )
        lines.append(
            f"| {gap.source_title.replace('|', '¦')} | {decision} | {target_id} | "
            f"{gap.source_member_count} | {gap.matched_source_member_count} | {gap.target_member_count} | "
            f"{gap.missing_placement_count} | {len(gap.extra_target_video_ids)} |"
        )
    lines.extend(
        [
            "",
            "## Метод",
            "",
            "Video matching использует reviewed mappings, unique exact canonical titles и только затем bounded fuzzy fallback. "
            "Collection identity использует exact reviewed IDs либо отдельное explicit create approval. Title-кандидаты "
            "никогда не выбираются автоматически: один существующий кандидат, дубликаты и неразрешённое создание "
            "становятся конфликтами. Membership сравнивается как множество exact target video IDs; позиции провайдера "
            "не являются identity.",
        ]
    )
    return "\n".join(lines)
