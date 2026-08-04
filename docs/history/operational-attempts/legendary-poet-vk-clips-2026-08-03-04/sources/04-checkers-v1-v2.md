# Historical source snapshots

> Non-executable evidence only. Do not copy or run without a new reviewed design and tests.

## 012. Manual VK Clips checker V1

- Original: `check_manual_vk_clips.py`
- SHA-256: `1bfcb65813846a84ec7515512cb715c6e6ac3dc38541a083b2c79b12464a8f63`

```python
from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk.store import VkTokenStore
from video_channel_manager.platforms.vk.writer import VkVideoWriter

OWNER_ID = -235216998
ACCOUNT = "legendary-poet"
FIRST_NEW_VIDEO_ID = 456239167
LAST_VIDEO_ID_TO_SCAN = 456239500
CHUNK_SIZE = 50


def normalize(text: str) -> str:
    value = (text or "").lower().replace("ё", "е")
    value = re.sub(
        r"@thelegendarypoet|#thelegendarypoet|#theepicpoet|#shorts",
        " ",
        value,
    )
    value = re.sub(r"[^a-zа-я0-9]+", " ", value)
    return " ".join(value.split())


def parse_items(response: object) -> list[dict[str, Any]]:
    if not isinstance(response, dict):
        return []
    items = response.get("items")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def remote_id(item: dict[str, Any]) -> str:
    return f"{item.get('owner_id')}_{item.get('id')}"


def load_map(repo_root: Path) -> dict[str, Any]:
    candidates = [
        repo_root
        / "legendary-poet-republish-48-clips"
        / "republish_48_map.json",
        repo_root
        / "data"
        / "reports"
        / "legendary-poet-republish-48-clips"
        / "republish_48_map.json",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return json.loads(candidate.read_text(encoding="utf-8-sig"))
    raise SystemExit(
        "Не найдена republish_48_map.json. "
        "Ожидалась папка legendary-poet-republish-48-clips в корне проекта."
    )


def scan_new_objects(writer: VkVideoWriter) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    ids = list(range(FIRST_NEW_VIDEO_ID, LAST_VIDEO_ID_TO_SCAN + 1))
    for offset in range(0, len(ids), CHUNK_SIZE):
        batch = ids[offset : offset + CHUNK_SIZE]
        videos = ",".join(f"{OWNER_ID}_{video_id}" for video_id in batch)
        response = writer._call(  # Read-only exact-ID query.
            "video.get",
            params={
                "videos": videos,
                "extended": False,
                "count": len(batch),
            },
            retry_transient=True,
        )
        for item in parse_items(response):
            if item.get("owner_id") != OWNER_ID:
                continue
            found[remote_id(item)] = item
        print(
            f"Проверены ID {batch[0]}–{batch[-1]}; "
            f"найдено объектов: {len(found)}"
        )
    return sorted(found.values(), key=lambda item: int(item.get("id") or 0))


def score_pair(expected: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    source_id = str(expected.get("source_id") or "")
    expected_title = str(expected.get("source_title") or "")
    expected_duration = int(expected.get("source_duration_seconds") or 0)

    title = str(item.get("title") or "")
    description = str(item.get("description") or "")
    item_duration = int(item.get("duration") or 0)

    expected_norm = normalize(expected_title)
    title_norm = normalize(title)
    ratio = (
        SequenceMatcher(None, expected_norm, title_norm).ratio()
        if expected_norm and title_norm
        else 0.0
    )
    duration_difference = (
        abs(expected_duration - item_duration)
        if expected_duration and item_duration
        else 999
    )
    marker = (
        source_id.lower() in title.lower()
        or source_id.lower() in description.lower()
        or title_norm == normalize(source_id)
    )

    score = 100.0 if marker else 0.0
    score += ratio * 50.0
    if title_norm == expected_norm:
        score += 40.0
    if duration_difference <= 1:
        score += 30.0
    elif duration_difference <= 3:
        score += 18.0
    elif duration_difference <= 6:
        score += 5.0
    elif not marker:
        score -= 60.0

    acceptable = marker or (duration_difference <= 3 and ratio >= 0.48)
    return {
        "score": score,
        "acceptable": acceptable,
        "marker": marker,
        "title_similarity": ratio,
        "duration_difference": duration_difference,
    }


def build_report(
    republish_map: dict[str, Any],
    objects: list[dict[str, Any]],
) -> dict[str, Any]:
    expected = [
        item for item in republish_map.get("items", []) if isinstance(item, dict)
    ]
    candidates: list[tuple[float, int, str, dict[str, Any]]] = []

    by_remote = {remote_id(item): item for item in objects}
    for expected_index, expected_item in enumerate(expected):
        for item in objects:
            details = score_pair(expected_item, item)
            if details["acceptable"]:
                candidates.append(
                    (
                        float(details["score"]),
                        expected_index,
                        remote_id(item),
                        details,
                    )
                )

    candidates.sort(key=lambda row: row[0], reverse=True)
    used_expected: set[int] = set()
    used_remote: set[str] = set()
    matches: list[dict[str, Any]] = []

    for score, expected_index, vk_remote_id, details in candidates:
        if expected_index in used_expected or vk_remote_id in used_remote:
            continue
        expected_item = expected[expected_index]
        item = by_remote[vk_remote_id]
        used_expected.add(expected_index)
        used_remote.add(vk_remote_id)
        matches.append(
            {
                "source_id": expected_item.get("source_id"),
                "expected_title": expected_item.get("source_title"),
                "expected_duration": expected_item.get(
                    "source_duration_seconds"
                ),
                "old_vk_video_id": expected_item.get("old_vk_video_id"),
                "new_vk_id": vk_remote_id,
                "new_vk_type": item.get("type"),
                "new_vk_title": item.get("title"),
                "new_vk_duration": item.get("duration"),
                "views": item.get("views"),
                "processing": item.get("processing"),
                "is_draft": item.get("is_draft"),
                "published_unix": item.get("date"),
                "match_method": (
                    "youtube_id_marker"
                    if details["marker"]
                    else "title_and_duration"
                ),
                "title_similarity": round(
                    float(details["title_similarity"]), 3
                ),
                "duration_difference": details["duration_difference"],
                "score": round(score, 2),
            }
        )

    missing = [
        item for index, item in enumerate(expected) if index not in used_expected
    ]
    extras = [
        {
            "vk_id": remote_id(item),
            "type": item.get("type"),
            "title": item.get("title"),
            "duration": item.get("duration"),
            "views": item.get("views"),
            "processing": item.get("processing"),
            "is_draft": item.get("is_draft"),
            "date": item.get("date"),
        }
        for item in objects
        if remote_id(item) not in used_remote
    ]

    type_counts: dict[str, int] = {}
    for item in objects:
        item_type = str(item.get("type") or "unknown")
        type_counts[item_type] = type_counts.get(item_type, 0) + 1

    return {
        "schema_name": "legendary-poet.manual-clips-postflight",
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "scanned_id_range": [FIRST_NEW_VIDEO_ID, LAST_VIDEO_ID_TO_SCAN],
        "objects_found": len(objects),
        "type_counts": type_counts,
        "expected_count": len(expected),
        "matched_count": len(matches),
        "matched_short_video_count": sum(
            1 for item in matches if item.get("new_vk_type") == "short_video"
        ),
        "matched_wrong_type_count": sum(
            1 for item in matches if item.get("new_vk_type") != "short_video"
        ),
        "missing_count": len(missing),
        "extra_count": len(extras),
        "matches": sorted(matches, key=lambda row: str(row["source_id"])),
        "missing": missing,
        "extras": extras,
        "raw_objects": objects,
    }


def render_text(report: dict[str, Any]) -> str:
    lines = [
        "ПРОВЕРКА РУЧНО ЗАГРУЖЕННЫХ VK КЛИПОВ",
        "=" * 62,
        f"Проверенный диапазон ID: {report['scanned_id_range'][0]}–{report['scanned_id_range'][1]}",
        f"Новых объектов найдено: {report['objects_found']}",
        f"Типы: {json.dumps(report['type_counts'], ensure_ascii=False)}",
        f"Сопоставлено с очередью: {report['matched_count']}/{report['expected_count']}",
        f"Из них настоящих short_video: {report['matched_short_video_count']}",
        f"С ошибочным типом: {report['matched_wrong_type_count']}",
        f"Не найдено из очереди: {report['missing_count']}",
        f"Лишних/неопознанных новых объектов: {report['extra_count']}",
        "",
    ]

    if report["matches"]:
        lines.extend(["СОПОСТАВЛЕННЫЕ ОБЪЕКТЫ", "-" * 62])
        for item in report["matches"]:
            lines.append(
                f"{item['new_vk_id']} | type={item['new_vk_type']} | "
                f"{item['new_vk_duration']}с | views={item['views']} | "
                f"YT={item['source_id']} | {item['new_vk_title']}"
            )
        lines.append("")

    if report["missing"]:
        lines.extend(["НЕ НАЙДЕНЫ В НОВЫХ ОБЪЕКТАХ", "-" * 62])
        for item in report["missing"]:
            lines.append(
                f"YT={item.get('source_id')} | "
                f"{item.get('source_duration_seconds')}с | "
                f"{item.get('source_title')}"
            )
        lines.append("")

    if report["extras"]:
        lines.extend(["НОВЫЕ ОБЪЕКТЫ БЕЗ УВЕРЕННОЙ ПАРЫ", "-" * 62])
        for item in report["extras"]:
            lines.append(
                f"{item['vk_id']} | type={item['type']} | "
                f"{item['duration']}с | views={item['views']} | "
                f"{item['title']}"
            )
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    repo_root = Path.cwd()
    republish_map = load_map(repo_root)

    settings = get_settings()
    token_store = VkTokenStore(settings.data_dir)
    writer = VkVideoWriter(
        token_store=token_store,
        account_alias=ACCOUNT,
        api_version=settings.vk_api_version,
    )

    print("Только чтение. VK не изменяется.")
    print(
        f"Сканирую точные ID {FIRST_NEW_VIDEO_ID}–{LAST_VIDEO_ID_TO_SCAN}..."
    )
    objects = scan_new_objects(writer)
    report = build_report(republish_map, objects)

    output_dir = (
        repo_root / "data" / "reports" / "legendary-poet-manual-clips-check"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "manual-clips-postflight.json"
    text_path = output_dir / "manual-clips-postflight.txt"

    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    text = render_text(report)
    text_path.write_text(text, encoding="utf-8")

    print("\n" + text.split("\n\n", 1)[0])
    print(f"\nTXT:  {text_path}")
    print(f"JSON: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

## 013. Manual VK Clips checker V2

- Original: `check_manual_vk_clips_v2.py`
- SHA-256: `3dba2ee07d1b6b079f0c32d36a40dcdb130a15e11210be79619194676605ee45`

```python
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk.store import VkTokenStore
from video_channel_manager.platforms.vk.writer import VkVideoWriter

OWNER_ID = -235216998
ACCOUNT = "legendary-poet"
FIRST_NEW_VIDEO_ID = 456239167
LAST_NEW_VIDEO_ID = 456239250
CHUNK_SIZE = 50
FRAME_WIDTH = 48
FRAME_HEIGHT = 48
FRAME_TIMES = (2.0, 10.0)


def normalize(text: str) -> str:
    value = (text or "").lower().replace("ё", "е")
    value = re.sub(
        r"@thelegendarypoet|#thelegendarypoet|#theepicpoet|#shorts",
        " ",
        value,
    )
    value = re.sub(r"[^a-zа-я0-9_-]+", " ", value)
    return " ".join(value.split())


def remote_id(item: dict[str, Any]) -> str:
    return f"{item.get('owner_id')}_{item.get('id')}"


def parse_items(response: object) -> list[dict[str, Any]]:
    if not isinstance(response, dict):
        return []
    items = response.get("items")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def is_real_clip(item: dict[str, Any]) -> bool:
    return (
        item.get("owner_id") == OWNER_ID
        and isinstance(item.get("id"), int)
        and item.get("type") == "short_video"
        and isinstance(item.get("duration"), int)
        and int(item.get("duration") or 0) > 0
    )


def load_map(repo_root: Path) -> dict[str, Any]:
    candidates = [
        repo_root
        / "legendary-poet-republish-48-clips"
        / "republish_48_map.json",
        repo_root
        / "data"
        / "reports"
        / "legendary-poet-republish-48-clips"
        / "republish_48_map.json",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return json.loads(candidate.read_text(encoding="utf-8-sig"))
    raise SystemExit(
        "Не найдена republish_48_map.json. "
        "Папка legendary-poet-republish-48-clips должна находиться "
        "в корне video-channel-manager."
    )


def scan_new_clips(writer: VkVideoWriter) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    ids = list(range(FIRST_NEW_VIDEO_ID, LAST_NEW_VIDEO_ID + 1))

    for offset in range(0, len(ids), CHUNK_SIZE):
        batch = ids[offset : offset + CHUNK_SIZE]
        videos = ",".join(f"{OWNER_ID}_{video_id}" for video_id in batch)
        response = writer._call(
            "video.get",
            params={
                "videos": videos,
                "extended": False,
                "count": len(batch),
            },
            retry_transient=True,
        )
        for item in parse_items(response):
            if is_real_clip(item):
                found[remote_id(item)] = item

    return sorted(
        found.values(),
        key=lambda item: int(item.get("id") or 0),
    )


def best_remote_media_url(item: dict[str, Any]) -> str | None:
    files = item.get("files")
    if isinstance(files, dict):
        for key in (
            "mp4_240",
            "mp4_360",
            "mp4_144",
            "mp4_480",
            "mp4_720",
            "mp4_1080",
            "hls",
            "hls_fmp4",
        ):
            value = files.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value

    player = item.get("player")
    if isinstance(player, str) and player.startswith(("http://", "https://")):
        return player

    return None


def run_ffmpeg_frame(
    ffmpeg: str,
    source: str,
    second: float,
) -> bytes | None:
    command = [
        ffmpeg,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{second:.3f}",
        "-i",
        source,
        "-frames:v",
        "1",
        "-vf",
        f"scale={FRAME_WIDTH}:{FRAME_HEIGHT}:force_original_aspect_ratio=disable,"
        "format=gray",
        "-f",
        "rawvideo",
        "pipe:1",
    ]
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    expected_size = FRAME_WIDTH * FRAME_HEIGHT
    if result.returncode != 0 or len(result.stdout) != expected_size:
        return None

    return result.stdout


def average_hash(frame: bytes) -> int:
    mean = sum(frame) / len(frame)
    result = 0
    for value in frame:
        result = (result << 1) | int(value >= mean)
    return result


def hamming(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def fingerprint_source(
    ffmpeg: str,
    source: str,
    duration: int,
) -> tuple[int, ...] | None:
    hashes: list[int] = []
    for requested_second in FRAME_TIMES:
        second = min(requested_second, max(0.5, duration - 1.0))
        frame = run_ffmpeg_frame(ffmpeg, source, second)
        if frame is None:
            continue
        hashes.append(average_hash(frame))
    return tuple(hashes) or None


def fingerprint_distance(
    left: tuple[int, ...],
    right: tuple[int, ...],
) -> float:
    count = min(len(left), len(right))
    if count <= 0:
        return float("inf")
    return sum(hamming(left[i], right[i]) for i in range(count)) / count


def marker_match(
    expected: dict[str, Any],
    clip: dict[str, Any],
) -> bool:
    source_id = str(expected.get("source_id") or "").lower()
    haystack = "\n".join(
        str(clip.get(key) or "")
        for key in ("title", "description")
    ).lower()
    return bool(source_id and source_id in haystack)


def duration_close(
    expected: dict[str, Any],
    clip: dict[str, Any],
    tolerance: int = 2,
) -> bool:
    expected_duration = int(expected.get("source_duration_seconds") or 0)
    actual_duration = int(clip.get("duration") or 0)
    return (
        expected_duration > 0
        and actual_duration > 0
        and abs(expected_duration - actual_duration) <= tolerance
    )


def build_exact_map(
    repo_root: Path,
    republish_map: dict[str, Any],
    clips: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    expected = [
        item
        for item in republish_map.get("items", [])
        if isinstance(item, dict)
    ]
    cache_dir = (
        repo_root
        / "data"
        / "cache"
        / "legendary-poet-republish-48-clips"
    )

    used_sources: set[str] = set()
    used_clips: set[str] = set()
    matches: list[dict[str, Any]] = []

    # Stage 1: exact YouTube-ID marker in title/description.
    for clip in clips:
        possible = [
            item
            for item in expected
            if str(item.get("source_id") or "") not in used_sources
            and marker_match(item, clip)
        ]
        if len(possible) != 1:
            continue
        item = possible[0]
        source_id = str(item["source_id"])
        rid = remote_id(clip)
        used_sources.add(source_id)
        used_clips.add(rid)
        matches.append(
            {
                "source_id": source_id,
                "source_title": item.get("source_title"),
                "source_duration": item.get("source_duration_seconds"),
                "old_vk_video_id": item.get("old_vk_video_id"),
                "new_vk_clip_id": rid,
                "new_vk_duration": clip.get("duration"),
                "views": clip.get("views"),
                "method": "youtube_id_marker",
                "visual_distance": None,
            }
        )

    remaining_clips = [
        clip for clip in clips if remote_id(clip) not in used_clips
    ]
    remaining_expected = [
        item
        for item in expected
        if str(item.get("source_id") or "") not in used_sources
    ]

    if not remaining_clips:
        missing = remaining_expected
        return matches, missing, []

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print(
            "FFmpeg не найден: визуальное сопоставление недоступно. "
            "Будут использованы только точные маркеры и уникальные длительности."
        )

    local_fingerprints: dict[str, tuple[int, ...]] = {}
    if ffmpeg:
        print("\nСоздаю отпечатки локальных MP4...")
        for index, item in enumerate(remaining_expected, start=1):
            source_id = str(item.get("source_id") or "")
            path = cache_dir / f"{source_id}.mp4"
            if not path.is_file():
                continue
            duration = int(item.get("source_duration_seconds") or 0)
            fp = fingerprint_source(ffmpeg, str(path), duration)
            if fp is not None:
                local_fingerprints[source_id] = fp
            print(
                f"  local {index}/{len(remaining_expected)} "
                f"{source_id}: {'OK' if fp else 'нет кадра'}"
            )

    remote_fingerprints: dict[str, tuple[int, ...]] = {}
    if ffmpeg:
        print("\nСоздаю отпечатки 30 новых VK-клипов...")
        for index, clip in enumerate(remaining_clips, start=1):
            rid = remote_id(clip)
            url = best_remote_media_url(clip)
            fp = None
            if url:
                fp = fingerprint_source(
                    ffmpeg,
                    url,
                    int(clip.get("duration") or 0),
                )
            if fp is not None:
                remote_fingerprints[rid] = fp
            print(
                f"  remote {index}/{len(remaining_clips)} "
                f"{rid}: {'OK' if fp else 'нет кадра'}"
            )

    # Stage 2: build all plausible duration/visual candidates.
    candidates: list[dict[str, Any]] = []
    for clip in remaining_clips:
        rid = remote_id(clip)
        clip_fp = remote_fingerprints.get(rid)
        for item in remaining_expected:
            source_id = str(item.get("source_id") or "")
            if not duration_close(item, clip, tolerance=2):
                continue

            local_fp = local_fingerprints.get(source_id)
            visual_distance = None
            if clip_fp is not None and local_fp is not None:
                visual_distance = fingerprint_distance(local_fp, clip_fp)

            duration_difference = abs(
                int(item.get("source_duration_seconds") or 0)
                - int(clip.get("duration") or 0)
            )

            candidates.append(
                {
                    "source": item,
                    "clip": clip,
                    "source_id": source_id,
                    "clip_id": rid,
                    "duration_difference": duration_difference,
                    "visual_distance": visual_distance,
                    "sort_key": (
                        visual_distance
                        if visual_distance is not None
                        else 100000.0,
                        duration_difference,
                    ),
                }
            )

    # Prefer the globally clearest visual pairs.
    candidates.sort(key=lambda row: row["sort_key"])

    for candidate in candidates:
        source_id = candidate["source_id"]
        rid = candidate["clip_id"]
        if source_id in used_sources or rid in used_clips:
            continue

        visual_distance = candidate["visual_distance"]

        # A 48x48 average hash has 2304 bits. Matching transcodes are usually
        # dramatically closer than unrelated videos. Keep a conservative gate.
        if visual_distance is not None and visual_distance > 620:
            continue

        # Without a visual fingerprint, accept only a duration that is unique
        # among the still-unmatched expected sources.
        if visual_distance is None:
            actual_duration = int(candidate["clip"].get("duration") or 0)
            possible = [
                item
                for item in remaining_expected
                if str(item.get("source_id") or "") not in used_sources
                and abs(
                    int(item.get("source_duration_seconds") or 0)
                    - actual_duration
                )
                <= 1
            ]
            if len(possible) != 1:
                continue
            if str(possible[0].get("source_id") or "") != source_id:
                continue

        item = candidate["source"]
        clip = candidate["clip"]
        used_sources.add(source_id)
        used_clips.add(rid)
        matches.append(
            {
                "source_id": source_id,
                "source_title": item.get("source_title"),
                "source_duration": item.get("source_duration_seconds"),
                "old_vk_video_id": item.get("old_vk_video_id"),
                "new_vk_clip_id": rid,
                "new_vk_duration": clip.get("duration"),
                "views": clip.get("views"),
                "method": (
                    "visual_fingerprint"
                    if visual_distance is not None
                    else "unique_duration"
                ),
                "visual_distance": (
                    round(float(visual_distance), 2)
                    if visual_distance is not None
                    else None
                ),
            }
        )

    missing = [
        item
        for item in expected
        if str(item.get("source_id") or "") not in used_sources
    ]
    unresolved_clips = [
        clip for clip in clips if remote_id(clip) not in used_clips
    ]

    return matches, missing, unresolved_clips


def render_text(
    clips: list[dict[str, Any]],
    matches: list[dict[str, Any]],
    missing: list[dict[str, Any]],
    unresolved_clips: list[dict[str, Any]],
) -> str:
    lines = [
        "ТОЧНАЯ ПРОВЕРКА РУЧНО ЗАГРУЖЕННЫХ VK КЛИПОВ — V2",
        "=" * 72,
        f"Реальных новых short_video: {len(clips)}",
        f"Сопоставлено с очередью 48: {len(matches)}/48",
        f"Ещё не сопоставлено/не загружено: {len(missing)}",
        f"Новых клипов без уверенной пары: {len(unresolved_clips)}",
        "",
        "СОПОСТАВЛЕННЫЕ КЛИПЫ",
        "-" * 72,
    ]

    for row in sorted(
        matches,
        key=lambda item: int(
            str(item["new_vk_clip_id"]).split("_")[-1]
        ),
    ):
        lines.append(
            f"{row['new_vk_clip_id']} | "
            f"YT={row['source_id']} | "
            f"{row['source_duration']}→{row['new_vk_duration']}с | "
            f"method={row['method']} | "
            f"{row['source_title']}"
        )

    lines.extend(
        [
            "",
            "ОСТАЛИСЬ ИЗ ОЧЕРЕДИ 48",
            "-" * 72,
        ]
    )
    for item in missing:
        lines.append(
            f"YT={item.get('source_id')} | "
            f"{item.get('source_duration_seconds')}с | "
            f"{item.get('source_title')}"
        )

    if unresolved_clips:
        lines.extend(
            [
                "",
                "НОВЫЕ КЛИПЫ БЕЗ УВЕРЕННОЙ ПАРЫ",
                "-" * 72,
            ]
        )
        for clip in unresolved_clips:
            lines.append(
                f"{remote_id(clip)} | "
                f"{clip.get('duration')}с | "
                f"views={clip.get('views')} | "
                f"description={clip.get('description')!r}"
            )

    return "\n".join(lines) + "\n"


def main() -> int:
    repo_root = Path.cwd()
    republish_map = load_map(repo_root)

    settings = get_settings()
    store = VkTokenStore(settings.data_dir)
    writer = VkVideoWriter(
        token_store=store,
        account_alias=ACCOUNT,
        api_version=settings.vk_api_version,
    )

    print("Читаю новые объекты VK...")
    clips = scan_new_clips(writer)
    print(f"Найдено реальных short_video: {len(clips)}")

    matches, missing, unresolved = build_exact_map(
        repo_root,
        republish_map,
        clips,
    )

    report_dir = (
        repo_root
        / "data"
        / "reports"
        / "legendary-poet-manual-clips-check-v2"
    )
    report_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "schema_name": "legendary-poet.manual-clips-postflight-v2",
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "real_short_video_count": len(clips),
        "matched_count": len(matches),
        "missing_count": len(missing),
        "unresolved_clip_count": len(unresolved),
        "matches": matches,
        "missing": missing,
        "unresolved_clips": [
            {
                "vk_id": remote_id(item),
                "duration": item.get("duration"),
                "views": item.get("views"),
                "description": item.get("description"),
                "date": item.get("date"),
            }
            for item in unresolved
        ],
    }

    json_path = report_dir / "manual-clips-postflight-v2.json"
    text_path = report_dir / "manual-clips-postflight-v2.txt"

    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    text = render_text(clips, matches, missing, unresolved)
    text_path.write_text(text, encoding="utf-8")

    print()
    print(text)
    print(f"TXT:  {text_path}")
    print(f"JSON: {json_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```
