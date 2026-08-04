# Historical source snapshots

> Non-executable evidence only. Do not copy or run without a new reviewed design and tests.

## 016. Expanded postflight tool

- Original: `legendary_poet_postflight.py`
- SHA-256: `db9ea3a60ccecd0bef346ee6831dfcc09b6d7d461d2b9bcdfa006d86e48bc7a5`

```python
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable


FRAME_FRACTIONS = (0.25, 0.70)
FRAME_SIZE = 64
VISUAL_PASS_SIMILARITY = 0.77
DURATION_TOLERANCE_SECONDS = 2.5


@dataclass(slots=True)
class LocalMedia:
    source_id: str
    canonical_title: str
    filename_hint: str
    path: Path
    size_bytes: int
    sha256: str
    duration: float
    width: int
    height: int
    has_video: bool
    has_audio: bool
    frames: list[bytes]
    frame_files: list[Path]


@dataclass(slots=True)
class RemoteClip:
    remote_id: str
    owner_id: int
    video_id: int
    type: str
    duration: float
    title: str
    description: str
    views: int | None
    processing: bool
    converting: bool
    playable: bool
    direct_media_url: str | None
    frames: list[bytes]
    frame_files: list[Path]
    raw: dict[str, Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only full/quick postflight for Legendary Poet manual VK Clip uploads."
    )
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=("quick", "full"), default="quick")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--max-wall-posts", type=int, default=10000)
    return parser.parse_args()


def normalize_text(value: str) -> str:
    text = (value or "").casefold().replace("ё", "е")
    replacements = {
        "：": ":",
        "？": "?",
        "！": "!",
        "＂": '"',
        "“": '"',
        "”": '"',
        "«": '"',
        "»": '"',
        "—": "-",
        "–": "-",
        "−": "-",
        "…": "...",
        "𝖭": "n",
        "𝖮": "o",
        "𝖪": "k",
        "𝖳": "t",
        "𝖴": "u",
        "𝖱": "r",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"[\u200b-\u200f\u202a-\u202e\u2060\u2066-\u2069\ufeff]", "", text)
    text = re.sub(r"@thelegendarypoet|@theepicpoet", " ", text)
    text = re.sub(r"#thelegendarypoet|#theepicpoet|#shorts", " ", text)
    text = re.sub(r"[^a-zа-я0-9]+", " ", text)
    return " ".join(text.split())


def tokens(value: str) -> set[str]:
    return {item for item in normalize_text(value).split() if len(item) >= 3}


def text_similarity(left: str, right: str) -> float:
    a = normalize_text(left)
    b = normalize_text(right)
    if not a or not b:
        return 0.0
    seq = SequenceMatcher(None, a, b).ratio()
    ta, tb = tokens(a), tokens(b)
    jaccard = len(ta & tb) / len(ta | tb) if ta or tb else 0.0
    containment = 1.0 if a in b or b in a else 0.0
    return max(seq * 0.65 + jaccard * 0.35, containment * 0.95)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_checked(command: list[str], *, timeout: int = 300) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(command, check=False, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Command timed out: {command[0]}") from exc
    except OSError as exc:
        raise RuntimeError(f"Cannot run {command[0]}: {exc}") from exc


def probe_media(ffprobe: str, source: str) -> dict[str, Any]:
    result = run_checked(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=index,codec_type,width,height,duration",
            "-of",
            "json",
            source,
        ],
        timeout=180,
    )
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"ffprobe failed for {source}: {message[:500]}")
    payload = json.loads(result.stdout.decode("utf-8"))
    streams = payload.get("streams") if isinstance(payload, dict) else None
    fmt = payload.get("format") if isinstance(payload, dict) else None
    if not isinstance(streams, list) or not isinstance(fmt, dict):
        raise RuntimeError(f"ffprobe returned an invalid payload for {source}")
    duration = float(fmt.get("duration") or 0.0)
    video_streams = [item for item in streams if isinstance(item, dict) and item.get("codec_type") == "video"]
    audio_streams = [item for item in streams if isinstance(item, dict) and item.get("codec_type") == "audio"]
    width = max((int(item.get("width") or 0) for item in video_streams), default=0)
    height = max((int(item.get("height") or 0) for item in video_streams), default=0)
    return {
        "duration": duration,
        "has_video": bool(video_streams),
        "has_audio": bool(audio_streams),
        "width": width,
        "height": height,
    }


def extract_gray_frame(ffmpeg: str, source: str, second: float) -> bytes | None:
    result = run_checked(
        [
            ffmpeg,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{max(0.0, second):.3f}",
            "-i",
            source,
            "-frames:v",
            "1",
            "-vf",
            f"scale={FRAME_SIZE}:{FRAME_SIZE}:force_original_aspect_ratio=disable,format=gray",
            "-f",
            "rawvideo",
            "pipe:1",
        ],
        timeout=180,
    )
    expected = FRAME_SIZE * FRAME_SIZE
    return result.stdout if result.returncode == 0 and len(result.stdout) == expected else None


def extract_png_frame(ffmpeg: str, source: str, second: float, output: Path) -> bool:
    output.parent.mkdir(parents=True, exist_ok=True)
    result = run_checked(
        [
            ffmpeg,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{max(0.0, second):.3f}",
            "-i",
            source,
            "-frames:v",
            "1",
            "-vf",
            "scale=360:-2",
            str(output),
        ],
        timeout=180,
    )
    return result.returncode == 0 and output.is_file() and output.stat().st_size > 0


def average_hash(frame: bytes) -> int:
    mean = sum(frame) / len(frame)
    value = 0
    for pixel in frame:
        value = (value << 1) | int(pixel >= mean)
    return value


def frame_similarity(left: list[bytes], right: list[bytes]) -> float | None:
    count = min(len(left), len(right))
    if count <= 0:
        return None
    scores: list[float] = []
    bit_count = FRAME_SIZE * FRAME_SIZE
    for index in range(count):
        distance = (average_hash(left[index]) ^ average_hash(right[index])).bit_count()
        scores.append(1.0 - distance / bit_count)
    return sum(scores) / len(scores)


def safe_seconds(duration: float) -> list[float]:
    if duration <= 0:
        return []
    return [min(max(duration * fraction, 0.5), max(duration - 0.5, 0.5)) for fraction in FRAME_FRACTIONS]


def load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if payload.get("schema_name") != "legendary-poet.manual-native-clips-postflight":
        raise RuntimeError("Unsupported manifest schema")
    items = payload.get("items")
    if not isinstance(items, list) or len(items) != 48:
        raise RuntimeError("Manifest must contain exactly 48 items")
    source_ids = [str(item.get("source_id") or "") for item in items if isinstance(item, dict)]
    if len(source_ids) != 48 or len(set(source_ids)) != 48:
        raise RuntimeError("Manifest source IDs are incomplete or duplicated")
    return payload


def locate_local_files(source_dir: Path, items: list[dict[str, Any]]) -> tuple[list[LocalMedia], list[str]]:
    actual_files = sorted(source_dir.glob("*.mp4"), key=lambda path: path.name.casefold())
    if not actual_files:
        raise RuntimeError(f"No MP4 files found in {source_dir}")
    unmatched = set(actual_files)
    rows: list[LocalMedia] = []
    problems: list[str] = []

    for item in items:
        hint = str(item["filename_hint"])
        exact = source_dir / hint
        if exact in unmatched and exact.is_file():
            selected = exact
        else:
            scored = sorted(
                ((text_similarity(hint, candidate.name), candidate) for candidate in unmatched),
                reverse=True,
                key=lambda pair: pair[0],
            )
            if not scored or scored[0][0] < 0.70:
                problems.append(f"Local source not confidently found: {hint}")
                continue
            selected = scored[0][1]
        unmatched.discard(selected)
        rows.append(
            LocalMedia(
                source_id=str(item["source_id"]),
                canonical_title=str(item["canonical_title"]),
                filename_hint=hint,
                path=selected,
                size_bytes=selected.stat().st_size,
                sha256="",
                duration=0.0,
                width=0,
                height=0,
                has_video=False,
                has_audio=False,
                frames=[],
                frame_files=[],
            )
        )

    if unmatched:
        problems.append("Unexpected local MP4 files: " + "; ".join(path.name for path in sorted(unmatched)))
    return rows, problems


def prepare_local_media(
    rows: list[LocalMedia],
    *,
    ffprobe: str,
    ffmpeg: str,
    mode: str,
    frames_dir: Path,
) -> list[str]:
    problems: list[str] = []
    for index, row in enumerate(rows, start=1):
        print(f"LOCAL {index:02d}/{len(rows)}: {row.path.name}")
        row.sha256 = sha256_file(row.path)
        try:
            info = probe_media(ffprobe, str(row.path))
        except Exception as exc:
            problems.append(str(exc))
            continue
        row.duration = float(info["duration"])
        row.width = int(info["width"])
        row.height = int(info["height"])
        row.has_video = bool(info["has_video"])
        row.has_audio = bool(info["has_audio"])
        if not row.has_video or not row.has_audio or row.duration <= 0 or row.size_bytes <= 0:
            problems.append(f"Invalid local media streams/duration: {row.path.name}")
        if mode == "full":
            for frame_index, second in enumerate(safe_seconds(row.duration), start=1):
                raw = extract_gray_frame(ffmpeg, str(row.path), second)
                if raw is not None:
                    row.frames.append(raw)
                png = frames_dir / "local" / f"{row.source_id}-{frame_index}.png"
                if extract_png_frame(ffmpeg, str(row.path), second, png):
                    row.frame_files.append(png)
            if len(row.frames) != len(FRAME_FRACTIONS):
                problems.append(f"Could not extract all local comparison frames: {row.path.name}")
    duplicate_hashes: dict[str, list[str]] = {}
    for row in rows:
        if row.sha256:
            duplicate_hashes.setdefault(row.sha256, []).append(row.path.name)
    for digest, names in duplicate_hashes.items():
        if len(names) > 1:
            problems.append(f"Duplicate local media SHA-256 {digest}: {names}")
    return problems


def import_repo_modules(repository_root: Path):
    src = repository_root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    from video_channel_manager.config import get_settings
    from video_channel_manager.platforms.vk.store import VkTokenStore
    from video_channel_manager.platforms.vk.wall import VkWallWriter

    return get_settings, VkTokenStore, VkWallWriter


def parse_vk_items(response: object) -> list[dict[str, Any]]:
    if not isinstance(response, dict):
        return []
    items = response.get("items")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def fetch_exact_videos(writer: Any, owner_id: int, video_ids: Iterable[int]) -> dict[int, dict[str, Any]]:
    ids = list(dict.fromkeys(int(item) for item in video_ids))
    found: dict[int, dict[str, Any]] = {}
    for start in range(0, len(ids), 50):
        batch = ids[start : start + 50]
        response = writer._call(
            "video.get",
            params={
                "videos": ",".join(f"{owner_id}_{video_id}" for video_id in batch),
                "extended": False,
                "count": len(batch),
            },
            retry_transient=True,
        )
        for item in parse_vk_items(response):
            video_id = item.get("id")
            if item.get("owner_id") == owner_id and type(video_id) is int and video_id in batch:
                found[video_id] = item
    return found


def best_media_url(item: dict[str, Any]) -> str | None:
    files = item.get("files")
    if isinstance(files, dict):
        for key in ("mp4_360", "mp4_240", "mp4_480", "mp4_720", "mp4_1080", "mp4_144"):
            value = files.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value
    return None


def remote_from_item(owner_id: int, video_id: int, item: dict[str, Any]) -> RemoteClip:
    files = item.get("files")
    playable = bool(best_media_url(item)) or isinstance(item.get("player"), str)
    return RemoteClip(
        remote_id=f"{owner_id}_{video_id}",
        owner_id=owner_id,
        video_id=video_id,
        type=str(item.get("type") or ""),
        duration=float(item.get("duration") or 0.0),
        title=str(item.get("title") or ""),
        description=str(item.get("description") or ""),
        views=int(item["views"]) if type(item.get("views")) is int else None,
        processing=bool(item.get("processing")),
        converting=bool(item.get("converting")),
        playable=playable,
        direct_media_url=best_media_url(item),
        frames=[],
        frame_files=[],
        raw=item,
    )


def prepare_remote_frames(
    clips: list[RemoteClip],
    *,
    ffmpeg: str,
    mode: str,
    frames_dir: Path,
) -> list[str]:
    problems: list[str] = []
    if mode != "full":
        return problems
    for index, clip in enumerate(clips, start=1):
        print(f"REMOTE {index:02d}/{len(clips)}: {clip.remote_id}")
        if not clip.direct_media_url:
            problems.append(f"No direct media URL for visual check: {clip.remote_id}")
            continue
        for frame_index, second in enumerate(safe_seconds(clip.duration), start=1):
            raw = extract_gray_frame(ffmpeg, clip.direct_media_url, second)
            if raw is not None:
                clip.frames.append(raw)
            png = frames_dir / "remote" / f"{clip.video_id}-{frame_index}.png"
            if extract_png_frame(ffmpeg, clip.direct_media_url, second, png):
                clip.frame_files.append(png)
        if len(clip.frames) != len(FRAME_FRACTIONS):
            problems.append(f"Could not extract all remote comparison frames: {clip.remote_id}")
    return problems


def duration_similarity(left: float, right: float) -> float:
    difference = abs(left - right)
    return max(0.0, 1.0 - difference / 12.0)


def clip_text(clip: RemoteClip) -> str:
    return "\n".join(part for part in (clip.title, clip.description) if part)


def pair_score(local: LocalMedia, remote: RemoteClip, *, mode: str) -> tuple[float, dict[str, float | None]]:
    text_score = max(
        text_similarity(local.path.stem, clip_text(remote)),
        text_similarity(local.canonical_title, clip_text(remote)),
    )
    duration_score = duration_similarity(local.duration, remote.duration)
    visual_score = frame_similarity(local.frames, remote.frames) if mode == "full" else None
    marker = 1.0 if local.source_id.casefold() in clip_text(remote).casefold() else 0.0
    if visual_score is None:
        score = text_score * 0.72 + duration_score * 0.23 + marker * 0.05
    else:
        score = text_score * 0.42 + duration_score * 0.18 + visual_score * 0.35 + marker * 0.05
    return score, {
        "text_similarity": text_score,
        "duration_similarity": duration_score,
        "visual_similarity": visual_score,
        "source_marker": marker,
    }


def hungarian_maximize(scores: list[list[float]]) -> list[int]:
    n = len(scores)
    if n == 0 or any(len(row) != n for row in scores):
        raise RuntimeError("Hungarian matcher requires a non-empty square matrix")
    max_value = max(max(row) for row in scores)
    cost = [[max_value - value for value in row] for row in scores]
    u = [0.0] * (n + 1)
    v = [0.0] * (n + 1)
    p = [0] * (n + 1)
    way = [0] * (n + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [math.inf] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = math.inf
            j1 = 0
            for j in range(1, n + 1):
                if used[j]:
                    continue
                cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                if cur < minv[j]:
                    minv[j] = cur
                    way[j] = j0
                if minv[j] < delta:
                    delta = minv[j]
                    j1 = j
            for j in range(n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    assignment = [-1] * n
    for j in range(1, n + 1):
        if p[j] != 0:
            assignment[p[j] - 1] = j - 1
    return assignment


def match_local_to_remote(
    local_rows: list[LocalMedia], remote_rows: list[RemoteClip], *, mode: str
) -> tuple[list[dict[str, Any]], list[str]]:
    if len(local_rows) != len(remote_rows):
        return [], [f"Cannot build exact mapping: local={len(local_rows)} remote={len(remote_rows)}"]
    scores: list[list[float]] = []
    details: list[list[dict[str, float | None]]] = []
    for local in local_rows:
        score_row: list[float] = []
        detail_row: list[dict[str, float | None]] = []
        for remote in remote_rows:
            score, detail = pair_score(local, remote, mode=mode)
            score_row.append(score)
            detail_row.append(detail)
        scores.append(score_row)
        details.append(detail_row)
    assignment = hungarian_maximize(scores)
    matches: list[dict[str, Any]] = []
    problems: list[str] = []
    for local_index, remote_index in enumerate(assignment):
        local = local_rows[local_index]
        remote = remote_rows[remote_index]
        detail = details[local_index][remote_index]
        duration_difference = abs(local.duration - remote.duration)
        visual = detail["visual_similarity"]
        text_ok = float(detail["text_similarity"] or 0.0) >= 0.55
        duration_ok = duration_difference <= DURATION_TOLERANCE_SECONDS
        visual_ok = mode != "full" or (visual is not None and float(visual) >= VISUAL_PASS_SIMILARITY)
        confident = text_ok and duration_ok and visual_ok
        if not confident:
            problems.append(
                f"Low-confidence mapping {local.source_id} -> {remote.remote_id}: "
                f"text={detail['text_similarity']:.3f} duration_diff={duration_difference:.2f} "
                f"visual={visual if visual is not None else 'n/a'}"
            )
        matches.append(
            {
                "source_id": local.source_id,
                "canonical_title": local.canonical_title,
                "local_filename": local.path.name,
                "local_sha256": local.sha256,
                "local_duration": round(local.duration, 3),
                "local_width": local.width,
                "local_height": local.height,
                "local_has_video": local.has_video,
                "local_has_audio": local.has_audio,
                "vk_clip_id": remote.remote_id,
                "vk_video_id": remote.video_id,
                "vk_type": remote.type,
                "vk_duration": remote.duration,
                "vk_views": remote.views,
                "vk_description": remote.description,
                "processing": remote.processing,
                "converting": remote.converting,
                "playable": remote.playable,
                "score": round(scores[local_index][remote_index], 6),
                "text_similarity": round(float(detail["text_similarity"] or 0.0), 6),
                "duration_difference": round(duration_difference, 3),
                "visual_similarity": round(float(visual), 6) if visual is not None else None,
                "confident": confident,
                "local_frame_files": [str(path) for path in local.frame_files],
                "remote_frame_files": [str(path) for path in remote.frame_files],
            }
        )
    return matches, problems


def snapshot_wall(writer: Any, *, community_id: int, max_posts: int) -> dict[str, Any]:
    snapshot = writer.capture_wall_snapshot(
        community_id=community_id,
        max_posts_per_surface=max_posts,
    )
    return snapshot.as_dict()


def wall_references(snapshot: dict[str, Any], owner_id: int, video_ids: set[int]) -> list[dict[str, Any]]:
    expected = {f"video{owner_id}_{video_id}" for video_id in video_ids}
    matches: list[dict[str, Any]] = []
    for post in snapshot.get("posts") or []:
        if not isinstance(post, dict):
            continue
        attachments = set(str(item) for item in post.get("attachments") or [])
        found = sorted(expected & attachments)
        if found:
            matches.append(
                {
                    "owner_id": post.get("owner_id"),
                    "post_id": post.get("post_id"),
                    "surface": post.get("surface"),
                    "publish_date": post.get("publish_date"),
                    "attachments": found,
                }
            )
    return matches


def album_ids(writer: Any, *, community_id: int, owner_id: int, video_id: int) -> list[int]:
    response = writer._call(
        "video.getAlbumsByVideo",
        params={"target_id": -community_id, "owner_id": owner_id, "video_id": video_id},
        retry_transient=True,
    )
    if isinstance(response, dict):
        items = response.get("items")
    else:
        items = response
    if not isinstance(items, list):
        return []
    result: list[int] = []
    for item in items:
        album_id = item.get("id") if isinstance(item, dict) else item
        if type(album_id) is int and album_id > 0:
            result.append(album_id)
    return sorted(set(result))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def relative_to_output(path_text: str, output_dir: Path) -> str:
    try:
        return str(Path(path_text).relative_to(output_dir)).replace("\\", "/")
    except ValueError:
        return Path(path_text).as_uri()


def build_visual_html(matches: list[dict[str, Any]], output_dir: Path) -> str:
    rows: list[str] = []
    for item in sorted(matches, key=lambda row: int(row["vk_video_id"])):
        local_images = "".join(
            f'<img src="{html.escape(relative_to_output(path, output_dir))}" loading="lazy">'
            for path in item.get("local_frame_files") or []
        )
        remote_images = "".join(
            f'<img src="{html.escape(relative_to_output(path, output_dir))}" loading="lazy">'
            for path in item.get("remote_frame_files") or []
        )
        rows.append(
            "<tr>"
            f"<td><strong>{html.escape(item['source_id'])}</strong><br>{html.escape(item['canonical_title'])}" 
            f"<br><code>{html.escape(item['vk_clip_id'])}</code></td>"
            f"<td>{local_images or 'нет кадров'}</td>"
            f"<td>{remote_images or 'нет кадров'}</td>"
            f"<td>text={item['text_similarity']}<br>Δ={item['duration_difference']}с"
            f"<br>visual={item['visual_similarity']}<br>confident={item['confident']}</td>"
            "</tr>"
        )
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><title>Legendary Poet — visual postflight</title>
<style>
body{{font-family:system-ui,Arial,sans-serif;margin:20px;background:#111;color:#eee}}
table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #444;padding:8px;vertical-align:top}}
img{{width:180px;height:auto;margin:3px;border:1px solid #666}}code{{color:#9fd}}
</style></head><body>
<h1>Legendary Poet — визуальная сверка 48 клипов</h1>
<p>Слева локальные кадры, справа кадры текущего VK-транскода.</p>
<table><thead><tr><th>Источник / VK ID</th><th>Локальный MP4</th><th>VK Clip</th><th>Метрики</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></body></html>"""


def main() -> int:
    args = parse_args()
    repository_root = args.repository_root.resolve()
    source_dir = args.source_dir.resolve()
    manifest_path = args.manifest.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = output_dir / "frames"

    if not repository_root.is_dir() or not (repository_root / "src").is_dir():
        raise SystemExit(f"Invalid repository root: {repository_root}")
    if not source_dir.is_dir():
        raise SystemExit(f"Source directory not found: {source_dir}")
    for executable in (args.ffmpeg, args.ffprobe):
        if not shutil.which(executable) and not Path(executable).is_file():
            raise SystemExit(f"Required executable not found: {executable}")

    manifest = load_manifest(manifest_path)
    manifest_sha256 = sha256_file(manifest_path)
    items = [item for item in manifest["items"] if isinstance(item, dict)]
    owner_id = int(manifest["vk_owner_id"])
    community_id = int(manifest["vk_community_id"])
    account_alias = str(manifest["vk_account_alias"])
    new_ids = list(range(int(manifest["new_clip_first_id"]), int(manifest["new_clip_last_id"]) + 1))
    correct_ids = [int(item) for item in manifest["already_correct_clip_ids"]]
    expected_clip_ids = set(correct_ids + new_ids)
    scan_ids = list(range(int(manifest["scan_first_id"]), int(manifest["scan_last_id"]) + 1))
    old_ids = [int(item["old_vk_id"]) for item in items]

    local_rows, local_location_problems = locate_local_files(source_dir, items)
    print(f"Local MP4 found: {len(local_rows)}/48")
    local_problems = list(local_location_problems)
    local_problems.extend(
        prepare_local_media(
            local_rows,
            ffprobe=args.ffprobe,
            ffmpeg=args.ffmpeg,
            mode=args.mode,
            frames_dir=frames_dir,
        )
    )

    get_settings, VkTokenStore, VkWallWriter = import_repo_modules(repository_root)
    settings = get_settings()
    token_store = VkTokenStore(settings.data_dir)
    writer = VkWallWriter(
        token_store=token_store,
        account_alias=account_alias,
        api_version=settings.vk_api_version,
    )

    try:
        print("Reading exact VK clip IDs...")
        expected_remote = fetch_exact_videos(writer, owner_id, expected_clip_ids)
        scan_remote = fetch_exact_videos(writer, owner_id, scan_ids)
        old_remote = fetch_exact_videos(writer, owner_id, old_ids)

        new_clips = [
            remote_from_item(owner_id, video_id, expected_remote[video_id])
            for video_id in new_ids
            if video_id in expected_remote
        ]
        correct_clips = [
            remote_from_item(owner_id, video_id, expected_remote[video_id])
            for video_id in correct_ids
            if video_id in expected_remote
        ]

        remote_problems: list[str] = []
        missing_new = sorted(set(new_ids) - set(expected_remote))
        missing_correct = sorted(set(correct_ids) - set(expected_remote))
        if missing_new:
            remote_problems.append(f"Missing new VK IDs: {missing_new}")
        if missing_correct:
            remote_problems.append(f"Missing previously correct VK IDs: {missing_correct}")

        for clip in new_clips + correct_clips:
            if clip.type != "short_video":
                remote_problems.append(f"Wrong final type {clip.remote_id}: {clip.type!r}")
            if clip.duration <= 0:
                remote_problems.append(f"Zero/invalid remote duration: {clip.remote_id}")
            if clip.processing or clip.converting:
                remote_problems.append(f"Remote processing is not finished: {clip.remote_id}")
            if not clip.playable:
                remote_problems.append(f"No playability evidence: {clip.remote_id}")
            if not clip.description.strip():
                remote_problems.append(f"Blank VK clip description: {clip.remote_id}")

        extra_short_videos = sorted(
            video_id
            for video_id, item in scan_remote.items()
            if str(item.get("type") or "") == "short_video" and video_id not in expected_clip_ids
        )
        if extra_short_videos:
            remote_problems.append(
                "Extra short_video objects in reviewed ID window: " + ", ".join(map(str, extra_short_videos))
            )

        remote_problems.extend(
            prepare_remote_frames(
                new_clips,
                ffmpeg=args.ffmpeg,
                mode=args.mode,
                frames_dir=frames_dir,
            )
        )

        matches, match_problems = match_local_to_remote(local_rows, new_clips, mode=args.mode)

        albums_by_video: dict[int, list[int]] = {}
        if args.mode == "full":
            print("Reading current album memberships for the 48 new clips...")
            for index, clip in enumerate(new_clips, start=1):
                print(f"ALBUM {index:02d}/{len(new_clips)}: {clip.remote_id}")
                albums_by_video[clip.video_id] = album_ids(
                    writer,
                    community_id=community_id,
                    owner_id=owner_id,
                    video_id=clip.video_id,
                )
        for match in matches:
            match["album_ids"] = albums_by_video.get(int(match["vk_video_id"]), [])

        print("Capturing complete published + postponed wall snapshot...")
        wall_snapshot = snapshot_wall(
            writer,
            community_id=community_id,
            max_posts=args.max_wall_posts,
        )
        wall_matches = wall_references(wall_snapshot, owner_id, set(new_ids))
        wall_problems: list[str] = []
        if not wall_snapshot.get("complete"):
            wall_problems.append("Published/postponed wall snapshot is incomplete")
        if wall_matches:
            wall_problems.append(
                f"Found {len(wall_matches)} published/postponed wall posts referencing the new clips"
            )

        old_rows: list[dict[str, Any]] = []
        for item in items:
            source_id = str(item["source_id"])
            old_id = int(item["old_vk_id"])
            remote = old_remote.get(old_id)
            mapped = next((row for row in matches if row["source_id"] == source_id), None)
            old_rows.append(
                {
                    "source_id": source_id,
                    "canonical_title": item["canonical_title"],
                    "old_vk_id": f"{owner_id}_{old_id}",
                    "old_exists": remote is not None,
                    "old_type": str(remote.get("type") or "") if remote else "",
                    "old_views": remote.get("views") if remote else None,
                    "old_duration": remote.get("duration") if remote else None,
                    "new_vk_clip_id": mapped.get("vk_clip_id") if mapped else None,
                    "new_views": mapped.get("vk_views") if mapped else None,
                    "action": "review_only_no_delete",
                }
            )

        problems = local_problems + remote_problems + match_problems + wall_problems
        exact_48_types = len(new_clips) == 48 and all(clip.type == "short_video" for clip in new_clips)
        exact_8_types = len(correct_clips) == 8 and all(clip.type == "short_video" for clip in correct_clips)
        mapping_complete = len(matches) == 48 and all(bool(row["confident"]) for row in matches)
        local_complete = len(local_rows) == 48 and not any("Local source not" in item for item in local_problems)
        media_qc_complete = all(
            row.has_video and row.has_audio and row.duration > 0 and row.sha256 for row in local_rows
        )
        processing_complete = all(
            not clip.processing and not clip.converting and clip.duration > 0 and clip.playable
            for clip in new_clips + correct_clips
        )
        visual_complete = args.mode != "full" or (
            len(matches) == 48
            and all(
                row.get("visual_similarity") is not None
                and float(row["visual_similarity"]) >= VISUAL_PASS_SIMILARITY
                for row in matches
            )
        )
        wall_clean = bool(wall_snapshot.get("complete")) and not wall_matches
        no_extra_clips = not extra_short_videos

        if (
            args.mode == "full"
            and exact_48_types
            and exact_8_types
            and mapping_complete
            and local_complete
            and media_qc_complete
            and processing_complete
            and visual_complete
            and wall_clean
            and no_extra_clips
            and not problems
        ):
            status = "COMPLETED_56_OF_56_EXACTLY_RECONCILED"
            exit_code = 0
        elif exact_48_types and exact_8_types and processing_complete and wall_clean:
            status = "OPERATIONAL_OK_WITH_LIMITATIONS"
            exit_code = 2
        else:
            status = "ACTION_REQUIRED"
            exit_code = 3

        payload = {
            "schema_name": "legendary-poet.manual-native-clips-postflight-result",
            "schema_version": 1,
            "generated_at": datetime.now(UTC).isoformat(),
            "mode": args.mode,
            "status": status,
            "project_key": manifest["project_key"],
            "youtube_channel_id": manifest["youtube_channel_id"],
            "vk_community_id": community_id,
            "vk_owner_id": owner_id,
            "manifest_path": str(manifest_path),
            "manifest_sha256": manifest_sha256,
            "source_dir": str(source_dir),
            "checks": {
                "local_files_48": len(local_rows) == 48,
                "local_media_qc": media_qc_complete,
                "new_clips_48_present": len(new_clips) == 48,
                "new_clips_48_short_video": exact_48_types,
                "previous_clips_8_short_video": exact_8_types,
                "total_expected_clips_56": exact_48_types and exact_8_types,
                "processing_and_playability": processing_complete,
                "mapping_48_confident": mapping_complete,
                "visual_48_complete": visual_complete if args.mode == "full" else None,
                "published_postponed_wall_complete": bool(wall_snapshot.get("complete")),
                "new_clip_wall_references_zero": not wall_matches,
                "extra_short_video_in_reviewed_window_zero": no_extra_clips,
                "old_ordinary_video_objects_untouched": True,
            },
            "counts": {
                "local_mp4": len(local_rows),
                "new_short_video": len(new_clips),
                "previous_short_video": len(correct_clips),
                "matched": len(matches),
                "confident_matched": sum(1 for row in matches if row["confident"]),
                "wall_references": len(wall_matches),
                "extra_short_video_in_reviewed_window": len(extra_short_videos),
                "old_video_objects_observed": sum(1 for row in old_rows if row["old_exists"]),
            },
            "new_clip_ids": [clip.remote_id for clip in sorted(new_clips, key=lambda item: item.video_id)],
            "previous_clip_ids": [clip.remote_id for clip in sorted(correct_clips, key=lambda item: item.video_id)],
            "extra_short_video_ids": [f"{owner_id}_{item}" for item in extra_short_videos],
            "matches": matches,
            "old_video_review": old_rows,
            "wall_snapshot_sha256": wall_snapshot.get("snapshot_sha256"),
            "wall_references": wall_matches,
            "problems": problems,
            "limitations": (
                []
                if args.mode == "full" and status == "COMPLETED_56_OF_56_EXACTLY_RECONCILED"
                else (["Visual/media-frame comparison was not requested in quick mode"] if args.mode == "quick" else [])
            ),
        }

        (output_dir / "postflight-result.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (output_dir / "wall-snapshot.json").write_text(
            json.dumps(wall_snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        write_csv(
            output_dir / "mapping-48.csv",
            matches,
            [
                "source_id",
                "canonical_title",
                "local_filename",
                "local_sha256",
                "local_duration",
                "local_width",
                "local_height",
                "local_has_video",
                "local_has_audio",
                "vk_clip_id",
                "vk_type",
                "vk_duration",
                "vk_views",
                "processing",
                "converting",
                "playable",
                "text_similarity",
                "duration_difference",
                "visual_similarity",
                "confident",
                "album_ids",
            ],
        )
        write_csv(
            output_dir / "old-ordinary-video-review.csv",
            old_rows,
            [
                "source_id",
                "canonical_title",
                "old_vk_id",
                "old_exists",
                "old_type",
                "old_views",
                "old_duration",
                "new_vk_clip_id",
                "new_views",
                "action",
            ],
        )
        if args.mode == "full":
            (output_dir / "visual-review.html").write_text(
                build_visual_html(matches, output_dir), encoding="utf-8"
            )

        summary_lines = [
            "LEGENDARY POET — VK CLIPS POSTFLIGHT",
            "=" * 72,
            f"Status: {status}",
            f"Mode: {args.mode}",
            f"Manifest SHA-256: {manifest_sha256}",
            "",
            f"Local MP4: {len(local_rows)}/48",
            f"New VK short_video: {len(new_clips)}/48",
            f"Previous correct short_video: {len(correct_clips)}/8",
            f"Total expected VK Clips: {len(new_clips) + len(correct_clips)}/56",
            f"Confident source↔clip mappings: {sum(1 for row in matches if row['confident'])}/48",
            f"Processing/playability complete: {processing_complete}",
            f"Visual comparison complete: {visual_complete if args.mode == 'full' else 'not requested'}",
            f"Wall snapshot complete: {wall_snapshot.get('complete')}",
            f"Published/postponed posts referencing new clips: {len(wall_matches)}",
            f"Extra short_video objects in reviewed ID window: {len(extra_short_videos)}",
            f"Old ordinary-video objects observed: {sum(1 for row in old_rows if row['old_exists'])}/48",
            "",
            "DECISION",
            "-" * 72,
        ]
        if status == "COMPLETED_56_OF_56_EXACTLY_RECONCILED":
            summary_lines.extend(
                [
                    "The concrete 56-clip operation is fully reconciled.",
                    "No re-upload is allowed. Old ordinary-video copies remain review-only.",
                ]
            )
        elif status == "OPERATIONAL_OK_WITH_LIMITATIONS":
            summary_lines.extend(
                [
                    "The remote clip set is operationally present and clean, but one or more",
                    "strong-evidence checks were not requested or could not be completed.",
                    "Do not re-upload. Review the problems/limitations and run Full if needed.",
                ]
            )
        else:
            summary_lines.extend(
                [
                    "One or more concrete checks failed. Do not re-upload or delete anything.",
                    "Review exact problems and reconcile by remote ID.",
                ]
            )
        summary_lines.extend(["", "PROBLEMS / LIMITATIONS", "-" * 72])
        summary_lines.extend(problems or ["None."])
        if args.mode == "quick":
            summary_lines.append("Quick mode does not perform full frame/media comparison.")
        summary_lines.extend(
            [
                "",
                "OUTPUTS",
                "-" * 72,
                str(output_dir / "postflight-result.json"),
                str(output_dir / "mapping-48.csv"),
                str(output_dir / "wall-snapshot.json"),
                str(output_dir / "old-ordinary-video-review.csv"),
            ]
        )
        if args.mode == "full":
            summary_lines.append(str(output_dir / "visual-review.html"))
        (output_dir / "SUMMARY.txt").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
        print("\n" + "\n".join(summary_lines))
        return exit_code
    finally:
        writer.close()


if __name__ == "__main__":
    raise SystemExit(main())
```

## 017. Expanded postflight PowerShell launcher

- Original: `run-legendary-poet-postflight.ps1`
- SHA-256: `b0f70320960b4171e2460b8946ad3b67e9f04ba5cc7eff3ac12de88c9fe45554`

```powershell
[CmdletBinding()]
param(
    [ValidateSet("Quick", "Full")]
    [string]$Mode = "Full",

    [string]$RepositoryRoot = "C:\Users\Fedor\Projects\video-channel-manager",

    [string]$SourceDirectory = "C:\Users\Fedor\Downloads\Legendary-Poet-48-Shorts",

    [string]$Python = "python",

    [string]$Ffmpeg = "ffmpeg",

    [string]$Ffprobe = "ffprobe",

    [switch]$DoNotOpenReport
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$ToolRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Checker = Join-Path $ToolRoot "legendary_poet_postflight.py"
$Manifest = Join-Path $ToolRoot "legendary-poet-48-manifest.json"

if (-not (Test-Path -LiteralPath $RepositoryRoot -PathType Container)) {
    throw "Repository not found: $RepositoryRoot"
}
if (-not (Test-Path -LiteralPath (Join-Path $RepositoryRoot "src") -PathType Container)) {
    throw "Not a video-channel-manager repository: $RepositoryRoot"
}
if (-not (Test-Path -LiteralPath $SourceDirectory -PathType Container)) {
    throw "Source folder not found: $SourceDirectory"
}
if (-not (Test-Path -LiteralPath $Checker -PathType Leaf)) {
    throw "Checker not found: $Checker"
}
if (-not (Test-Path -LiteralPath $Manifest -PathType Leaf)) {
    throw "Manifest not found: $Manifest"
}

$Mp4Files = @(Get-ChildItem -LiteralPath $SourceDirectory -Filter "*.mp4" -File)
Write-Host "Local MP4 files: $($Mp4Files.Count)" -ForegroundColor Cyan
if ($Mp4Files.Count -ne 48) {
    throw "Expected exactly 48 MP4 files, found $($Mp4Files.Count)."
}

foreach ($Executable in @($Python, $Ffmpeg, $Ffprobe)) {
    $Resolved = Get-Command $Executable -ErrorAction SilentlyContinue
    if (-not $Resolved -and -not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
        throw "Required executable not found: $Executable"
    }
}

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$OutputDirectory = Join-Path $RepositoryRoot "data\reports\legendary-poet-postflight-$Timestamp"
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

$ModeArgument = $Mode.ToLowerInvariant()
$Arguments = @(
    $Checker,
    "--repository-root", $RepositoryRoot,
    "--source-dir", $SourceDirectory,
    "--manifest", $Manifest,
    "--output-dir", $OutputDirectory,
    "--mode", $ModeArgument,
    "--ffmpeg", $Ffmpeg,
    "--ffprobe", $Ffprobe
)

Write-Host ""
Write-Host "Running $Mode postflight..." -ForegroundColor Cyan
Write-Host "Output: $OutputDirectory" -ForegroundColor Cyan
Write-Host ""

& $Python @Arguments
$ExitCode = $LASTEXITCODE

$Summary = Join-Path $OutputDirectory "SUMMARY.txt"
$Visual = Join-Path $OutputDirectory "visual-review.html"

if (Test-Path -LiteralPath $Summary -PathType Leaf) {
    Write-Host ""
    Get-Content -LiteralPath $Summary -Encoding UTF8
}

switch ($ExitCode) {
    0 { Write-Host "FULL COMPLETION CONFIRMED." -ForegroundColor Green }
    2 { Write-Host "OPERATIONAL RESULT IS GOOD, BUT LIMITATIONS REMAIN. Do not re-upload." -ForegroundColor Yellow }
    default { Write-Host "ACTION REQUIRED. Do not re-upload or delete anything." -ForegroundColor Red }
}

if (-not $DoNotOpenReport) {
    if ($Mode -eq "Full" -and (Test-Path -LiteralPath $Visual -PathType Leaf)) {
        Start-Process $Visual
    }
    elseif (Test-Path -LiteralPath $Summary -PathType Leaf) {
        Start-Process notepad.exe $Summary
    }
    Start-Process explorer.exe $OutputDirectory
}

exit $ExitCode
```
