# Historical source snapshots

> Non-executable evidence only. Do not copy or run without a new reviewed design and tests.

## 014. Select the supposed remaining 18 files

- Original: `select-remaining-18-vk-clips.ps1`
- SHA-256: `a9162f63f8f3aecc2f06d758474ef97002e30a212743fd3ed95d72d26ffa542e`

```powershell
$ErrorActionPreference = "Stop"

$Source = "C:\Users\Fedor\Downloads\Legendary-Poet-48-Shorts"
$Destination = "C:\Users\Fedor\Downloads\Legendary-Poet-18-To-Upload"

$RequiredFiles = @(
    "Родина - Михал Лермонтов @TheLegendaryPoet.mp4"
    "Страшная Сказка - Борис Пастернак @TheLegendaryPoet.mp4"
    "Творчество - VERSION 2 - Валерий Брюсов @TheLegendaryPoet.mp4"
    "Исповедь Самоубийцы - Version 2 - Сергей Есенин @TheLegendaryPoet.mp4"
    "Песнь о Вещем Олеге - А. С. Пушкин #TheLegendaryPoet.mp4"
    "Ты Меня не Любишь, не Жалеешь - Сергей Есенин @TheLegendaryPoet.mp4"
    "Берёза 🎸 Рок-Версия 🎸 Сергей Есенин @TheLegendaryPoet.mp4"
    "Черный Человек - Version 3 - Сергей Есенин (Полная Версия Стихотворения) @TheLegendaryPoet.mp4"
    "Черный Человек - Version 1 - Сергей Есенин #TheEpicPoet.mp4"
    "Скифы - Version 2 - Александр Блок #TheLegendaryPoet.mp4"
    "Я Усталым Таким Ещё не Был - Сергей Есенин @TheLegendaryPoet.mp4"
    "Жди Меня и Я Вернусь... - Константин Симонов #TheLegendaryPoet.mp4"
    "Письмо к Женщине - Сергей Есенин @TheLegendaryPoet.mp4"
    "Скифы - Version 1 - Александр Блок #TheLegendaryPoet.mp4"
    "Письмо Татьяны к Онегину — Александр Сергеевич Пушкин  @TheLegendaryPoet.mp4"
    "Черный Человек - Version 4 - Сергей Есенин @TheLegendaryPoet #Shorts.mp4"
    "Бесконечная Петля Блока ⚡ «Ночь, улица, фонарь, аптека…».mp4"
    "Брюсов： «Творчество»🌙 Тень Несозданных Созданий.mp4"
)

if (-not (Test-Path -LiteralPath $Source -PathType Container)) {
    throw "Исходная папка не найдена: $Source"
}

$SourceFiles = @(
    Get-ChildItem -LiteralPath $Source -File -Filter "*.mp4"
)

Write-Host "MP4 в исходной папке: $($SourceFiles.Count)" -ForegroundColor Cyan

if ($SourceFiles.Count -ne 48) {
    Write-Host "Внимание: сейчас в исходной папке не 48 MP4, а $($SourceFiles.Count)." -ForegroundColor Yellow
}

if (Test-Path -LiteralPath $Destination) {
    Remove-Item -LiteralPath $Destination -Recurse -Force
}

New-Item -ItemType Directory -Path $Destination -Force | Out-Null

$Copied = [System.Collections.Generic.List[string]]::new()
$Missing = [System.Collections.Generic.List[string]]::new()

foreach ($FileName in $RequiredFiles) {
    $SourcePath = Join-Path $Source $FileName

    if (Test-Path -LiteralPath $SourcePath -PathType Leaf) {
        Copy-Item -LiteralPath $SourcePath -Destination $Destination -Force
        $Copied.Add($FileName)
        Write-Host "СКОПИРОВАНО: $FileName" -ForegroundColor Green
    }
    else {
        $Missing.Add($FileName)
        Write-Host "НЕ НАЙДЕНО: $FileName" -ForegroundColor Red
    }
}

$DestinationFiles = @(
    Get-ChildItem -LiteralPath $Destination -File -Filter "*.mp4"
)

$ManifestPath = Join-Path $Destination "_СПИСОК_ДЛЯ_ЗАГРУЗКИ.txt"

@(
    "VK КЛИПЫ — ОСТАВШИЕСЯ ФАЙЛЫ"
    "Создано: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    "Исходная папка: $Source"
    "Папка загрузки: $Destination"
    "Скопировано: $($Copied.Count)"
    ""
    $Copied
) | Set-Content -LiteralPath $ManifestPath -Encoding UTF8

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Скопировано файлов: $($Copied.Count)" -ForegroundColor Cyan
Write-Host "Не найдено: $($Missing.Count)" -ForegroundColor Cyan
Write-Host "Папка: $Destination" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

if ($Missing.Count -gt 0) {
    throw "Не удалось найти $($Missing.Count) файл(а/ов). Смотрите красные строки выше."
}

if ($Copied.Count -ne 18 -or $DestinationFiles.Count -ne 18) {
    throw "Проверка количества не пройдена: ожидалось 18 файлов."
}

Write-Host ""
Write-Host "ГОТОВО: в отдельной папке ровно 18 MP4." -ForegroundColor Green
Start-Process explorer.exe $Destination
```

## 015. Final manual VK Clips checker

- Original: `check_manual_vk_clips_final.py`
- SHA-256: `70426d648302a74b5171e58cbaf1fb02b753473ce67a4064b337b220cd19bf85`

```python
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk.store import VkTokenStore
from video_channel_manager.platforms.vk.writer import VkVideoWriter

ACCOUNT = "legendary-poet"
OWNER_ID = -235216998
FIRST_NEW_VIDEO_ID = 456239167
LAST_NEW_VIDEO_ID = 456239320
BATCH_SIZE = 50

EXPECTED = [
    {"source_id":"g9bW6upeQCg","duration":62,"title":"Calm Night - Спокойная Ночь (English Version)"},
    {"source_id":"TDbW__q3hYk","duration":62,"title":"Веселая Невесёлая Песня - Цой в Новом Звучании - Кавер"},
    {"source_id":"r1YIF5scHgU","duration":62,"title":"Послушайте! - Лирическая Рок-Версия - Владимир Маяковский"},
    {"source_id":"_jqID4P7BiA","duration":88,"title":"Я научилась просто, мудро жить - Анна Ахматова"},
    {"source_id":"0C1-2tk9aQg","duration":44,"title":"Сергей Есенин - Хулиган - Рок-Версия"},
    {"source_id":"h6VxRWTm0eY","duration":58,"title":"Never Have I Been So Much Tired - Sergey Esenin"},
    {"source_id":"55IPY5t7AOo","duration":56,"title":"Парус - Dj Версия 2 - Михаил Лермонтов"},
    {"source_id":"gavdyL0QWJU","duration":58,"title":"Нет, Дед Мороз! - Расскажи, Снегурочка"},
    {"source_id":"T6WIgGaZm74","duration":61,"title":"Что Это Такое - Кто Здесь - Сергей Есенин"},
    {"source_id":"E4gJWCKD50s","duration":59,"title":"И Скучно и Грустно - Михаил Лермонтов"},
    {"source_id":"I1OsM65y-Lo","duration":57,"title":"Парус - Dj Версия - Михаил Лермонтов"},
    {"source_id":"ux2T7UVjUpM","duration":58,"title":"Шёпот, робкое дыханье - Афанасий Фет"},
    {"source_id":"V_64WsowBZc","duration":59,"title":"В Этой Жизни Помереть Не Трудно - Маяковский"},
    {"source_id":"9nD37a7hKQ8","duration":57,"title":"Шабаш - Алиса Cover"},
    {"source_id":"mFj0U1Sj_Ik","duration":62,"title":"Внимая Ужасам Войны - Николай Некрасов"},
    {"source_id":"11u1wlWFT2Y","duration":59,"title":"Сукин Сын - Сергей Есенин"},
    {"source_id":"pE5Im38_jN0","duration":58,"title":"Парус - Драматическая Версия - Михаил Лермонтов"},
    {"source_id":"fwSlg4TDfms","duration":58,"title":"Поёт Зима, Аукает - Nordic Folk Version - Сергей Есенин"},
    {"source_id":"IvAnQnO2CtQ","duration":60,"title":"У Лукоморья Дуб Зелёный - Кинематографическая Версия"},
    {"source_id":"bStyYN4dvEs","duration":59,"title":"Выхожу один я на дорогу - Михаил Лермонтов"},
    {"source_id":"MBdv5JvWuhw","duration":59,"title":"Узник - Мы Вольные Птицы - Александр Пушкин"},
    {"source_id":"kGav2FpMaZc","duration":45,"title":"Лиличка! - Маяковский"},
    {"source_id":"cMuGYGlaof8","duration":58,"title":"DJ Маяковский - Ноктюрн - А Вы Могли Бы"},
    {"source_id":"lt3jbgLjklA","duration":56,"title":"Песнь о Вещем Олеге - Version 2"},
    {"source_id":"Sdv8puPeJYw","duration":55,"title":"Кто Здесь - Version 3"},
    {"source_id":"6caLdFvuvds","duration":57,"title":"Черный Человек - Version 2"},
    {"source_id":"-3GkI8wip-w","duration":59,"title":"Пророк - А. С. Пушкин"},
    {"source_id":"KUDVfsn_atc","duration":60,"title":"Родина - Касаясь Трех Великих Океанов - Константин Симонов"},
    {"source_id":"M5hNecL_MsQ","duration":153,"title":"Пушкин Танцует Последнюю Бурю"},
    {"source_id":"NFLJP84QQo4","duration":173,"title":"Маяковский в Стиле Регги - А Вы Могли Бы"},
    {"source_id":"F5kgP197YUE","duration":63,"title":"Скифы - Version 1 - Александр Блок"},
    {"source_id":"ItewE1lCUJ8","duration":65,"title":"Письмо к Женщине - Сергей Есенин"},
    {"source_id":"LjNpRbJ57Sc","duration":65,"title":"Жди Меня и Я Вернусь - Константин Симонов"},
    {"source_id":"Wsbkvfzq5x0","duration":65,"title":"Я Усталым Таким Ещё не Был - Сергей Есенин"},
    {"source_id":"156l_su1P48","duration":72,"title":"Скифы - Version 2 - Александр Блок"},
    {"source_id":"8S_JgM5u6QE","duration":74,"title":"Черный Человек - Version 1 - Сергей Есенин"},
    {"source_id":"l-nzhGTw0V0","duration":74,"title":"Черный Человек - Version 3 - Сергей Есенин"},
    {"source_id":"BXZeRiEOHmQ","duration":81,"title":"Берёза - Рок-Версия - Сергей Есенин"},
    {"source_id":"vCYylNPkP6c","duration":83,"title":"Ты Меня не Любишь, не Жалеешь - Сергей Есенин"},
    {"source_id":"7IP9_wxDTAc","duration":85,"title":"Песнь о Вещем Олеге - Version 1 - А. С. Пушкин"},
    {"source_id":"_JhTcxchSn8","duration":88,"title":"Исповедь Самоубийцы - Version 2 - Сергей Есенин"},
    {"source_id":"wFHa8VOom3U","duration":93,"title":"Творчество - Version 2 - Валерий Брюсов"},
    {"source_id":"JefLdqrWmUM","duration":96,"title":"Страшная Сказка - Борис Пастернак"},
    {"source_id":"x-TPtQ9E2mc","duration":104,"title":"Родина - Михаил Лермонтов"},
    {"source_id":"V9XRuxOHl5E","duration":114,"title":"Письмо Татьяны к Онегину - Александр Пушкин"},
    {"source_id":"Ac7Fz_9HS3I","duration":142,"title":"Черный Человек - Version 4 - Сергей Есенин"},
    {"source_id":"EOaXd3EKNxA","duration":146,"title":"Ночь, улица, фонарь, аптека - Александр Блок"},
    {"source_id":"c__ZdqdiSJ0","duration":152,"title":"Творчество - Валерий Брюсов"},
]


def normalize(text: str) -> str:
    value = (text or "").lower().replace("ё", "е")
    value = re.sub(r"@thelegendarypoet|@theepicpoet", " ", value)
    value = re.sub(r"#thelegendarypoet|#theepicpoet|#shorts", " ", value)
    value = value.replace("⚡", " ").replace("🎶", " ").replace("🌙", " ").replace("🔥", " ").replace("👤", " ")
    value = value.replace("“", '"').replace("”", '"').replace("«", '"').replace("»", '"')
    value = value.replace("：", ":").replace("？", "?").replace("—", "-").replace("–", "-")
    value = re.sub(r"[^a-zа-я0-9]+", " ", value)
    return " ".join(value.split())


def get_blob(item: dict[str, Any]) -> str:
    return "\n".join(
        str(item.get(k) or "")
        for k in ("title", "description", "direct_url", "share_url")
    )


def item_remote_id(item: dict[str, Any]) -> str:
    return f"{item.get('owner_id')}_{item.get('id')}"


def parse_items(response: Any) -> list[dict[str, Any]]:
    if not isinstance(response, dict):
        return []
    items = response.get("items")
    if isinstance(items, list):
        return [x for x in items if isinstance(x, dict)]
    return []


def scan_new_clips(writer: VkVideoWriter) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for start in range(FIRST_NEW_VIDEO_ID, LAST_NEW_VIDEO_ID + 1, BATCH_SIZE):
        batch_ids = list(range(start, min(LAST_NEW_VIDEO_ID, start + BATCH_SIZE - 1) + 1))
        videos = ",".join(f"{OWNER_ID}_{video_id}" for video_id in batch_ids)
        response = writer._call(
            "video.get",
            params={"videos": videos, "extended": False, "count": len(batch_ids)},
            retry_transient=True,
        )
        for item in parse_items(response):
            if (
                item.get("owner_id") == OWNER_ID
                and item.get("type") == "short_video"
                and int(item.get("duration") or 0) > 0
                and isinstance(item.get("id"), int)
            ):
                found[item_remote_id(item)] = item
    return sorted(found.values(), key=lambda x: int(x.get("id") or 0))


def score_expected_vs_clip(expected: dict[str, Any], clip: dict[str, Any]) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    blob = get_blob(clip)
    norm_blob = normalize(blob)
    source_id = expected["source_id"].lower()
    if source_id in blob.lower():
        score += 1000
        reasons.append("youtube_id")

    exp_norm = normalize(expected["title"])
    exp_tokens = [t for t in exp_norm.split() if len(t) >= 4]
    if exp_norm and exp_norm in norm_blob:
        score += 500
        reasons.append("full_title")
    else:
        token_hits = sum(1 for t in exp_tokens if t in norm_blob)
        if token_hits:
            score += token_hits * 25
            reasons.append(f"title_tokens:{token_hits}")

    dur_diff = abs(int(expected["duration"]) - int(clip.get("duration") or 0))
    if dur_diff == 0:
        score += 120
        reasons.append("dur0")
    elif dur_diff == 1:
        score += 80
        reasons.append("dur1")
    elif dur_diff == 2:
        score += 40
        reasons.append("dur2")
    else:
        score -= dur_diff * 3

    title_text = str(clip.get("title") or "") + " " + str(clip.get("description") or "")
    title_low = title_text.lower()

    for marker in ("version 1", "version 2", "version 3", "version 4"):
        if marker in expected["title"].lower():
            if marker in title_low:
                score += 180
                reasons.append(marker)
            else:
                score -= 120

    if "черный человек" in exp_norm and "черны" in norm_blob:
        score += 50
        reasons.append("black_man")
    if "скифы" in exp_norm and "скиф" in norm_blob:
        score += 50
        reasons.append("scythians")
    if "творчество" in exp_norm and "творчеств" in norm_blob:
        score += 50
        reasons.append("creation")
    if "родина" in exp_norm and "родин" in norm_blob:
        score += 35
        reasons.append("motherland")
    if "песнь о вещем олеге" in exp_norm and "олег" in norm_blob:
        score += 50
        reasons.append("oleg")
    if "письмо" in exp_norm and "письм" in norm_blob:
        score += 25
        reasons.append("letter")
    if "береза" in exp_norm and "берез" in norm_blob:
        score += 50
        reasons.append("birch")

    return score, reasons


def greedy_match(expected_items: list[dict[str, Any]], clips: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    candidates = []
    for exp in expected_items:
        for clip in clips:
            score, reasons = score_expected_vs_clip(exp, clip)
            if score > 120:
                candidates.append((score, exp["source_id"], item_remote_id(clip), exp, clip, reasons))
    candidates.sort(key=lambda row: (-row[0], row[1], row[2]))

    matched_exp: set[str] = set()
    matched_clip: set[str] = set()
    matches: list[dict[str, Any]] = []

    for score, source_id, clip_id, exp, clip, reasons in candidates:
        if source_id in matched_exp or clip_id in matched_clip:
            continue
        matched_exp.add(source_id)
        matched_clip.add(clip_id)
        matches.append({
            "source_id": exp["source_id"],
            "source_title": exp["title"],
            "source_duration": exp["duration"],
            "new_vk_clip_id": clip_id,
            "new_vk_duration": clip.get("duration"),
            "vk_title": clip.get("title"),
            "vk_description": clip.get("description"),
            "vk_url": clip.get("direct_url") or clip.get("share_url"),
            "views": clip.get("views"),
            "score": score,
            "reasons": reasons,
        })

    missing = [exp for exp in expected_items if exp["source_id"] not in matched_exp]
    extra = [clip for clip in clips if item_remote_id(clip) not in matched_clip]
    return matches, missing, extra


def main() -> int:
    settings = get_settings()
    store = VkTokenStore(settings.data_dir)
    writer = VkVideoWriter(
        token_store=store,
        account_alias=ACCOUNT,
        api_version=settings.vk_api_version,
    )

    print("Сканирую новые VK-клипы...")
    clips = scan_new_clips(writer)
    print(f"Найдено реальных short_video: {len(clips)}")

    matches, missing, extra = greedy_match(EXPECTED, clips)

    report_dir = Path("data/reports/legendary-poet-manual-clips-final-check")
    report_dir.mkdir(parents=True, exist_ok=True)

    json_path = report_dir / "final-check.json"
    txt_path = report_dir / "final-check.txt"
    csv_path = report_dir / "final-check.csv"

    payload = {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "scan_range": [FIRST_NEW_VIDEO_ID, LAST_NEW_VIDEO_ID],
        "new_short_video_count": len(clips),
        "matched_count": len(matches),
        "missing_count": len(missing),
        "extra_count": len(extra),
        "matches": matches,
        "missing": missing,
        "extra": [
            {
                "vk_clip_id": item_remote_id(clip),
                "duration": clip.get("duration"),
                "title": clip.get("title"),
                "description": clip.get("description"),
                "url": clip.get("direct_url") or clip.get("share_url"),
                "views": clip.get("views"),
            }
            for clip in extra
        ],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["vk_clip_id","youtube_id","source_title","source_duration","vk_duration","vk_url","score","reasons"])
        for row in sorted(matches, key=lambda x: int(x["new_vk_clip_id"].split("_")[-1])):
            w.writerow([
                row["new_vk_clip_id"], row["source_id"], row["source_title"], row["source_duration"],
                row["new_vk_duration"], row["vk_url"], row["score"], ",".join(row["reasons"])
            ])

    lines = []
    lines.append("ФИНАЛЬНАЯ ПРОВЕРКА VK КЛИПОВ")
    lines.append("=" * 72)
    lines.append(f"Новых short_video в диапазоне {FIRST_NEW_VIDEO_ID}-{LAST_NEW_VIDEO_ID}: {len(clips)}")
    lines.append(f"Сопоставлено с целевой очередью 48: {len(matches)}/48")
    lines.append(f"Не найдено из 48: {len(missing)}")
    lines.append(f"Новые short_video без пары: {len(extra)}")
    lines.append("")

    lines.append("НОМЕРНАЯ ПРОВЕРКА")
    lines.append("-" * 72)
    clip_ids = [int(item["new_vk_clip_id"].split("_")[-1]) for item in matches]
    if clip_ids:
        lines.append(f"Минимальный новый ID: {min(clip_ids)}")
        lines.append(f"Максимальный новый ID: {max(clip_ids)}")
        sorted_ids = sorted(clip_ids)
        gaps = []
        for prev, cur in zip(sorted_ids, sorted_ids[1:]):
            if cur != prev + 1:
                gaps.append((prev, cur))
        lines.append(f"Количество разрывов в последовательности ID: {len(gaps)}")
        if gaps:
            for prev, cur in gaps:
                lines.append(f"  gap: {prev} -> {cur}")
    lines.append("")

    lines.append("СОПОСТАВЛЕННЫЕ КЛИПЫ")
    lines.append("-" * 72)
    for row in sorted(matches, key=lambda x: int(x["new_vk_clip_id"].split("_")[-1])):
        lines.append(
            f"{row['new_vk_clip_id']} | YT={row['source_id']} | "
            f"{row['source_duration']}→{row['new_vk_duration']}с | "
            f"score={row['score']} | {row['source_title']}"
        )

    lines.append("")
    lines.append("НЕ ЗАГРУЖЕНО / НЕ ОПОЗНАНО")
    lines.append("-" * 72)
    if missing:
        for row in missing:
            lines.append(f"YT={row['source_id']} | {row['duration']}с | {row['title']}")
    else:
        lines.append("Нет. Все 48 найдены.")

    lines.append("")
    lines.append("НОВЫЕ КЛИПЫ БЕЗ ПАРЫ")
    lines.append("-" * 72)
    if extra:
        for clip in extra:
            lines.append(
                f"{item_remote_id(clip)} | {clip.get('duration')}с | "
                f"title={clip.get('title')!r} | desc={str(clip.get('description') or '')[:120]!r}"
            )
    else:
        lines.append("Нет.")

    txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n".join(lines))
    print()
    print(f"TXT:  {txt_path}")
    print(f"CSV:  {csv_path}")
    print(f"JSON: {json_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```
