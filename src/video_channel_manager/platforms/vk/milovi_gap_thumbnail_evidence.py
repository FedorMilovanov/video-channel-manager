from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
import shutil
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import urlsplit, urlunsplit

import httpx

MILOVI_PROJECT_KEY = "milovi-cake"
MILOVI_COMMUNITY_ID = 68859909
MILOVI_OWNER_ID = -68859909
MILOVI_YOUTUBE_CHANNEL_ID = "UCMDnxfGZiBqcDzgUV1zjFpw"
INPUT_SCHEMA = "milovi-cake-reconciliation-input-v1"
UI_SCHEMA = "vk-clips-browser-ui-read-v1"
OUTPUT_SCHEMA = "milovi-cake-gap-thumbnail-evidence-v1"
EXPECTED_UI_CLIP_COUNT = 106
KNOWN_SHREK_CLIP = "-68859909_456239130"

_ALLOWED_DOWNLOAD_HOST_SUFFIXES = (
    "i.ytimg.com",
    "img.youtube.com",
    "okcdn.ru",
    "userapi.com",
)
_YT_THUMB_KINDS = ("0", "1", "2", "3")
_GENERIC_TOKENS = {
    "торт",
    "торты",
    "тортика",
    "cake",
    "milovi",
    "milovi_cake",
    "milovicake",
    "виктория",
    "милованова",
    "на",
    "заказ",
    "заказа",
    "от",
    "для",
    "в",
    "и",
    "с",
    "со",
    "спб",
    "санкт",
    "петербург",
    "петербурге",
    "тортыназаказ",
    "тортыназаказспб",
    "тортназаказ",
    "тортназаказспб",
    "тортспб",
}

# This list is deliberately scoped to the 25 cake/dessert rows that remained
# unresolved after the v5 metadata-only audit. It is evidence input, not an
# upload queue. IP/trademark/visual gates remain blocking.
_GAP_CANDIDATES: tuple[dict[str, Any], ...] = (
    {"youtube_id": "P2Bpt77k408", "published": "2026-04-06", "duration_s": 41, "scope": "CAKE", "ip_class": "IP_HOLD_HIDE", "title": "Торт с Ам Нямом #АмНям #Cake #Milovi_Cake"},
    {"youtube_id": "jZjDWn_MNq0", "published": "2025-07-05", "duration_s": 42, "scope": "CAKE", "ip_class": "IP_HOLD_HIDE", "title": "Торт Игра в Кальмара 🐙 - Squid Game Cake - Milovi Cake #ТортыНаЗаказ #Cake #Milovi_Cake #Торты #Торт"},
    {"youtube_id": "MdQ0kNBSsa8", "published": "2025-07-01", "duration_s": 40, "scope": "CAKE", "ip_class": "VISUAL_REVIEW", "title": "3D Торт от Milovi Cake \"Мышонок с Сыром\""},
    {"youtube_id": "d48QLgOuiTs", "published": "2025-06-26", "duration_s": 35, "scope": "CAKE", "ip_class": "LOW", "title": "Романтичный Торт с Бантом от #Milovi_Cake #ТортыНаЗаказ #Cake #Shorts #CakeDecorating"},
    {"youtube_id": "Oix9s6l9vNg", "published": "2025-02-04", "duration_s": 20, "scope": "CAKE", "ip_class": "LOW", "title": "Классический Наивкуснейший Медовик со Сливочно-Сметанным Кремом - 4К от #Milovi_Cake #Cake #Медовик"},
    {"youtube_id": "uA8SbnXzJJc", "published": "2025-02-03", "duration_s": 11, "scope": "CAKE", "ip_class": "LOW", "title": "Торт Медовик в Зефирном Покрытии #Milovi_Cake"},
    {"youtube_id": "u-PuqjWuhKk", "published": "2024-11-23", "duration_s": 57, "scope": "CAKE", "ip_class": "LOW", "title": "Синий Торт с Шариками на День Рождения - 4К - #Milovi_Cake #ТортыНаЗаказ #Cake #CakeDesign #Торт"},
    {"youtube_id": "FQGxV4DRPQw", "published": "2024-10-29", "duration_s": 20, "scope": "CAKE", "ip_class": "VISUAL_REVIEW", "title": "3D Торт Свинка #Milovi_Cake #ТортСвинья #PigCake #ТортыНаЗаказ #ТортНаЗаказ #Cake #3DТорт #ТортыСПб"},
    {"youtube_id": "L6XG2_zzrPU", "published": "2024-08-27", "duration_s": 15, "scope": "DESSERT", "ip_class": "", "title": "Сделала Зефир и Эклеры для Пикника #Milovi_Cake #Эклеры"},
    {"youtube_id": "xzMgMEWz5pM", "published": "2024-08-19", "duration_s": 15, "scope": "CAKE", "ip_class": "IP_HOLD_HIDE", "title": "Торт \"Чебурашка и Гена\" от Milovi Cake #Чебурашка #Гена #Milovi_Cake #ТортыНаЗаказСПб #ТортыНаЗаказ"},
    {"youtube_id": "pCARxxaVjTw", "published": "2024-06-10", "duration_s": 58, "scope": "DESSERT", "ip_class": "", "title": "Шоколадные Цветы от Milovi Cake - Цветы, Которые Буквально Можно Съесть 😊 #Milovi_Cake #Цветы"},
    {"youtube_id": "OWV-KGsLdA8", "published": "2024-04-03", "duration_s": 34, "scope": "CAKE", "ip_class": "LOW", "title": "Чёрный Торт \"Сердце\" от Milovi Cake #Торты #Milovi_Cake #Cake #Кондитер #ТортыНаЗаказ"},
    {"youtube_id": "CQ29P1F8Hfo", "published": "2024-03-28", "duration_s": 54, "scope": "DESSERT", "ip_class": "", "title": "Нежный Меренговый Рулет с Малиновой Серцевинкой от Milovi Cake #Milovi_Cake #Cake #МеренговыйРулет"},
    {"youtube_id": "SiluLt5Bz1c", "published": "2024-03-22", "duration_s": 27, "scope": "CAKE", "ip_class": "LOW", "title": "Ванильный Торт с Миксом Ягод от Milovi Cake #Milovi_Cake #Cake #Торты"},
    {"youtube_id": "cE0ofu6WV3s", "published": "2024-03-04", "duration_s": 29, "scope": "CAKE", "ip_class": "LOW", "title": "Торт для Врачей Кардиологов от Milovi Cake #Milovi_Cake #Кардиолог #Торт #Cake #Сердце"},
    {"youtube_id": "2yhQ4nMWm3I", "published": "2024-02-29", "duration_s": 30, "scope": "CAKE", "ip_class": "TRADEMARK_REVIEW", "title": "Торт Ozon от Milovi Cake с Начинкой Ферреро #Ozon #Озон #Milovi_Cake #Ферреро #Cake"},
    {"youtube_id": "7FCbopqeTYE", "published": "2024-01-18", "duration_s": 30, "scope": "CAKE", "ip_class": "IP_HOLD_HIDE", "title": "Двойной #Торт #Wednesday от #Milovi_Cake #ВикторияМилованова #Cake"},
    {"youtube_id": "o1WXIMupuws", "published": "2024-01-04", "duration_s": 28, "scope": "CAKE", "ip_class": "LOW", "title": "#Торт на День Рождения от #Milovi_Cake #ВикторияМилованова"},
    {"youtube_id": "1_SuzeQD_1g", "published": "2023-12-29", "duration_s": 30, "scope": "CAKE", "ip_class": "LOW", "title": "Новогодний Бенто-Торт Снежинка от #Milovi_Cake #ВикторияМилованова #БентоТорт #Cake"},
    {"youtube_id": "5B9OuXbdGKc", "published": "2023-12-19", "duration_s": 30, "scope": "CAKE", "ip_class": "LOW", "title": "Торт #Тонометр от #Milovi_Cake"},
    {"youtube_id": "ZuQt6yFePO0", "published": "2023-12-18", "duration_s": 31, "scope": "CAKE", "ip_class": "IP_HOLD_HIDE", "title": "#Торт #Роблокс от #Milovi_Cake #ВикторияМилованова #Roblox #Торты"},
    {"youtube_id": "BAVKrQQ00XI", "published": "2023-12-05", "duration_s": 18, "scope": "CAKE", "ip_class": "LOW", "title": "Торты от #Milovi_Cake на Заказ в Санкт-Петербурге"},
    {"youtube_id": "R0KjJvbxS8s", "published": "2023-11-18", "duration_s": 8, "scope": "DESSERT", "ip_class": "", "title": "Трайфлы (Торты-Стаканчики) от #Milovi_Cake в Санкт-Петербурге #Трайфлы"},
    {"youtube_id": "qPXHrdUgPUY", "published": "2023-06-23", "duration_s": 33, "scope": "CAKE", "ip_class": "IP_HOLD_HIDE", "title": "Торт \"Радужные Друзья Roblox\" от #Milovi_Cake в Санкт-Петербурге #Roblox #ТортыСПБ #ТортыНаЗаказ"},
    {"youtube_id": "R-LknUy9BEs", "published": "2023-06-22", "duration_s": 60, "scope": "CAKE", "ip_class": "LOW", "title": "Торты в Санкт-Петербурге от #Milovi_Cake #ТортыСПБ #ТортыНаЗаказ"},
)


@dataclass(frozen=True)
class ImageEvidence:
    sha256: str
    dhash_hex: str
    width: int
    height: int
    safe_source: str


def _utc_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _canonical_json_sha256(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(payload)


def _safe_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme and parsed.netloc:
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    return parsed.path


def _allowed_download_url(url: str) -> bool:
    parsed = urlsplit(url)
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    return any(host == suffix or host.endswith(f".{suffix}") for suffix in _ALLOWED_DOWNLOAD_HOST_SUFFIXES)


def _walk_dicts(value: object) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _extract_wall_clips(posts: object) -> dict[str, dict[str, Any]]:
    if not isinstance(posts, list):
        raise ValueError("published wall evidence must be a list")
    clips: dict[str, dict[str, Any]] = {}
    for post in posts:
        for item in _walk_dicts(post):
            if item.get("type") != "short_video":
                continue
            owner_id = item.get("owner_id")
            video_id = item.get("id")
            if owner_id != MILOVI_OWNER_ID or not isinstance(video_id, int) or video_id <= 0:
                raise ValueError("wall evidence contains malformed or foreign native Clip")
            remote_id = f"{owner_id}_{video_id}"
            if remote_id in clips:
                continue
            clips[remote_id] = item
    return clips


def _exact_one(names: Sequence[str], suffix: str) -> str:
    matches = [name for name in names if name.endswith(suffix)]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one ZIP member ending with {suffix!r}; got {len(matches)}")
    return matches[0]


def _read_reconciliation_input(path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]], dict[str, str]]:
    if not path.is_file():
        raise ValueError(f"input reconciliation ZIP does not exist: {path}")

    outer_sha = _sha256_path(path)
    with zipfile.ZipFile(path) as outer:
        required = {"00-manifest.json", "01-vk-clips-ui-inventory.json", "02-wall-evidence-handoff.zip"}
        if set(outer.namelist()) != required:
            raise ValueError("reconciliation ZIP members do not match the exact v1 contract")

        manifest_bytes = outer.read("00-manifest.json")
        ui_bytes = outer.read("01-vk-clips-ui-inventory.json")
        wall_zip_bytes = outer.read("02-wall-evidence-handoff.zip")

    manifest = json.loads(manifest_bytes.decode("utf-8-sig"))
    ui = json.loads(ui_bytes.decode("utf-8-sig"))

    if manifest.get("schema") != INPUT_SCHEMA:
        raise ValueError(f"unexpected reconciliation input schema: {manifest.get('schema')}")
    target = manifest.get("target")
    if not isinstance(target, dict):
        raise ValueError("reconciliation input target is missing")
    if (
        target.get("project_key") != MILOVI_PROJECT_KEY
        or target.get("community_id") != MILOVI_COMMUNITY_ID
        or target.get("owner_id") != MILOVI_OWNER_ID
    ):
        raise ValueError("reconciliation input target identity is not exact Milovi Cake")

    ui_meta = manifest.get("ui_inventory")
    wall_meta = manifest.get("wall_evidence")
    if not isinstance(ui_meta, dict) or not isinstance(wall_meta, dict):
        raise ValueError("reconciliation input hash bindings are missing")
    ui_sha = _sha256_bytes(ui_bytes)
    wall_sha = _sha256_bytes(wall_zip_bytes)
    if ui_meta.get("sha256") != ui_sha:
        raise ValueError("UI inventory SHA-256 does not match manifest")
    if wall_meta.get("sha256") != wall_sha:
        raise ValueError("wall evidence SHA-256 does not match manifest")

    if (
        ui.get("schema") != UI_SCHEMA
        or ui.get("project_key") != MILOVI_PROJECT_KEY
        or ui.get("community_id") != MILOVI_COMMUNITY_ID
        or ui.get("owner_id") != MILOVI_OWNER_ID
        or ui.get("read_only") is not True
        or ui.get("provider_writes") != 0
        or ui.get("provider_mutation_authorized") is not False
    ):
        raise ValueError("UI inventory identity/read-only contract is invalid")

    probe = ui.get("browser_probe")
    coverage = ui.get("coverage")
    if not isinstance(probe, dict) or not isinstance(coverage, dict):
        raise ValueError("UI inventory browser/coverage evidence is missing")
    if probe.get("status") != "ok_bounded_ui_observation":
        raise ValueError(f"UI inventory is not a successful bounded observation: {probe.get('status')}")
    if coverage.get("bounded_ui_end_observed") is not True:
        raise ValueError("UI inventory did not observe the bounded scroll end")
    if coverage.get("surface_complete_claim") is not False:
        raise ValueError("UI inventory unexpectedly claims complete provider surface")
    if coverage.get("clip_count") != EXPECTED_UI_CLIP_COUNT:
        raise ValueError(f"unexpected UI Clip count: {coverage.get('clip_count')}")
    if KNOWN_SHREK_CLIP not in set(coverage.get("required_remote_ids_found") or []):
        raise ValueError("known Shrek control Clip is absent from successful UI evidence")

    ui_clips = ui.get("clips")
    if not isinstance(ui_clips, list):
        raise ValueError("UI inventory clip list is missing")
    ui_ids = [str(item.get("remote_id") or "") for item in ui_clips if isinstance(item, dict)]
    if len(ui_ids) != EXPECTED_UI_CLIP_COUNT or len(ui_ids) != len(set(ui_ids)):
        raise ValueError("UI inventory does not contain 106 unique exact Clip IDs")
    if any(not value.startswith(f"{MILOVI_OWNER_ID}_") for value in ui_ids):
        raise ValueError("UI inventory contains foreign normalized Clip IDs")

    with zipfile.ZipFile(io.BytesIO(wall_zip_bytes)) as nested:
        wall_name = _exact_one(nested.namelist(), "/01-published-wall-posts.json")
        posts_bytes = nested.read(wall_name)
    posts = json.loads(posts_bytes.decode("utf-8-sig"))
    wall_clips = _extract_wall_clips(posts)
    wall_ids = set(wall_clips)
    if len(wall_ids) != EXPECTED_UI_CLIP_COUNT:
        raise ValueError(f"unexpected wall native Clip count: {len(wall_ids)}")

    ui_set = set(ui_ids)
    if ui_set != wall_ids:
        raise ValueError(
            f"exact public UI/wall Clip sets diverge: ui_only={len(ui_set-wall_ids)} wall_only={len(wall_ids-ui_set)}"
        )

    hashes = {
        "outer_input_sha256": outer_sha,
        "ui_inventory_sha256": ui_sha,
        "wall_handoff_sha256": wall_sha,
        "published_wall_posts_sha256": _sha256_bytes(posts_bytes),
    }
    return manifest, ui, wall_clips, hashes


def _pick_vk_frame_url(item: dict[str, Any]) -> str | None:
    choices: list[tuple[int, str]] = []
    for key in ("first_frame", "image"):
        entries = item.get(key)
        if not isinstance(entries, list):
            continue
        for row in entries:
            if not isinstance(row, dict):
                continue
            url = str(row.get("url") or "")
            if not _allowed_download_url(url):
                continue
            width = row.get("width")
            height = row.get("height")
            area = int(width or 0) * int(height or 0)
            choices.append((area, url))
        if choices:
            break
    if not choices:
        return None
    choices.sort(reverse=True)
    return choices[0][1]


def _youtube_thumb_url(video_id: str, kind: str) -> str:
    if kind not in _YT_THUMB_KINDS:
        raise ValueError(f"unexpected YouTube thumbnail kind: {kind}")
    return f"https://i.ytimg.com/vi/{video_id}/{kind}.jpg"


def _load_pillow() -> Any:
    try:
        from PIL import Image  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        raise RuntimeError('Pillow is not installed; install current repo with: pip install -e ".[milovi-gap-read]"') from exc
    return Image


def _content_bbox(image: Any) -> tuple[int, int, int, int]:
    gray = image.convert("L")
    width, height = gray.size
    if width < 4 or height < 4:
        return 0, 0, width, height
    mask = gray.point(lambda value: 255 if value > 14 else 0)
    bbox = mask.getbbox()
    if bbox is None:
        return 0, 0, width, height
    left, top, right, bottom = bbox
    if right - left < width * 0.3 or bottom - top < height * 0.3:
        return 0, 0, width, height
    return left, top, right, bottom


def _dhash_image_bytes(data: bytes, safe_source: str) -> ImageEvidence:
    Image = _load_pillow()
    with Image.open(io.BytesIO(data)) as source:
        source.load()
        width, height = source.size
        bbox = _content_bbox(source)
        cropped = source.crop(bbox).convert("L")
        resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
        resized = cropped.resize((9, 8), resampling)
        pixels = list(resized.getdata())

    value = 0
    for y in range(8):
        row = y * 9
        for x in range(8):
            value <<= 1
            value |= 1 if pixels[row + x] > pixels[row + x + 1] else 0

    return ImageEvidence(
        sha256=_sha256_bytes(data),
        dhash_hex=f"{value:016x}",
        width=width,
        height=height,
        safe_source=safe_source,
    )


def _hamming_hex(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()


def _tokenize(value: str) -> set[str]:
    normalized = value.lower().replace("ё", "е")
    normalized = re.sub(r"#[0-9a-zа-я_]+", " ", normalized)
    normalized = re.sub(r"[^0-9a-zа-я]+", " ", normalized)
    return {token for token in normalized.split() if len(token) > 1 and token not in _GENERIC_TOKENS}


def _metadata_scores(candidate: dict[str, Any], clip: dict[str, Any]) -> tuple[float, int, int]:
    yt_tokens = _tokenize(str(candidate["title"]))
    vk_text = str(clip.get("description") or clip.get("title") or "")
    vk_tokens = _tokenize(vk_text)
    if yt_tokens and vk_tokens:
        overlap = len(yt_tokens & vk_tokens)
        union = len(yt_tokens | vk_tokens)
        token_score = overlap / union if union else 0.0
    else:
        token_score = 0.0

    duration = clip.get("duration")
    duration_delta = abs(int(candidate["duration_s"]) - int(duration)) if isinstance(duration, int) else 9999
    duration_score = max(0.0, 1.0 - duration_delta / 20.0)

    date_value = clip.get("date")
    date_delta = 9999
    if isinstance(date_value, int):
        vk_date = datetime.fromtimestamp(date_value, UTC).date()
        yt_date = datetime.fromisoformat(str(candidate["published"])).date()
        date_delta = abs((vk_date - yt_date).days)
    date_score = max(0.0, 1.0 - date_delta / 90.0)

    return 0.60 * token_score + 0.30 * duration_score + 0.10 * date_score, duration_delta, date_delta


def _transfer_gate(ip_class: str) -> str:
    if ip_class == "IP_HOLD_HIDE":
        return "IP_HOLD_DO_NOT_TRANSFER"
    if ip_class == "TRADEMARK_REVIEW":
        return "TRADEMARK_REVIEW_REQUIRED"
    if ip_class == "VISUAL_REVIEW":
        return "VISUAL_REVIEW_REQUIRED"
    return "MEDIA_RECONCILIATION_REQUIRED"


def _download(
    client: httpx.Client,
    *,
    url: str,
    output: Path,
    timeout_seconds: float,
) -> tuple[ImageEvidence | None, dict[str, Any]]:
    if not _allowed_download_url(url):
        return None, {"status": "rejected_url", "source": _safe_url(url)}
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        response = client.get(url, timeout=timeout_seconds)
        response.raise_for_status()
        content_type = str(response.headers.get("content-type") or "").lower()
        if "image" not in content_type:
            return None, {"status": "non_image_response", "source": _safe_url(url), "content_type": content_type[:120]}
        data = response.content
        evidence = _dhash_image_bytes(data, _safe_url(url))
        output.write_bytes(data)
        return evidence, {
            "status": "downloaded",
            "source": evidence.safe_source,
            "sha256": evidence.sha256,
            "dhash": evidence.dhash_hex,
            "width": evidence.width,
            "height": evidence.height,
            "bytes": len(data),
        }
    except Exception as exc:
        return None, {"status": "error", "source": _safe_url(url), "error": f"{type(exc).__name__}: {exc}"[:500]}


def _rank_candidate(
    candidate: dict[str, Any],
    yt_images: Sequence[ImageEvidence],
    wall_clips: dict[str, dict[str, Any]],
    vk_images: dict[str, ImageEvidence],
) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for remote_id, clip in wall_clips.items():
        visual_distance: int | None = None
        if yt_images and remote_id in vk_images:
            visual_distance = min(_hamming_hex(yt.dhash_hex, vk_images[remote_id].dhash_hex) for yt in yt_images)
        visual_score = 0.0 if visual_distance is None else max(0.0, 1.0 - visual_distance / 64.0)
        metadata_score, duration_delta, date_delta = _metadata_scores(candidate, clip)
        combined = 0.64 * visual_score + 0.36 * metadata_score
        ranked.append(
            {
                "remote_id": remote_id,
                "combined_support_score": round(combined, 6),
                "visual_dhash_distance": visual_distance,
                "metadata_score": round(metadata_score, 6),
                "duration_delta_s": duration_delta,
                "date_delta_days": date_delta,
                "vk_duration_s": clip.get("duration"),
                "vk_date_utc": (
                    datetime.fromtimestamp(int(clip["date"]), UTC).date().isoformat()
                    if isinstance(clip.get("date"), int)
                    else None
                ),
                "vk_description": str(clip.get("description") or "")[:1200],
                "vk_clip_url": f"https://vk.com/clip{remote_id}",
            }
        )
    ranked.sort(
        key=lambda row: (
            row["combined_support_score"],
            -(row["visual_dhash_distance"] if isinstance(row["visual_dhash_distance"], int) else 9999),
        ),
        reverse=True,
    )
    return ranked[:5]


def _support_label(top: dict[str, Any] | None) -> str:
    if top is None:
        return "NO_SUPPORTING_VISUAL_EVIDENCE"
    distance = top.get("visual_dhash_distance")
    duration_delta = int(top.get("duration_delta_s") or 9999)
    metadata = float(top.get("metadata_score") or 0.0)
    if isinstance(distance, int) and distance <= 7 and duration_delta <= 3 and metadata >= 0.22:
        return "STRONG_SUPPORTING_CANDIDATE"
    if isinstance(distance, int) and distance <= 11 and (duration_delta <= 5 or metadata >= 0.28):
        return "POSSIBLE_SUPPORTING_CANDIDATE"
    if metadata >= 0.62 and duration_delta <= 3:
        return "METADATA_SUPPORTING_CANDIDATE"
    return "NO_STRONG_MATCH_OBSERVED"


def build_gap_thumbnail_evidence(
    *,
    input_zip: Path,
    output_dir: Path,
    zip_output: Path,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    _, _, wall_clips, input_hashes = _read_reconciliation_input(input_zip)

    if timeout_seconds < 3 or timeout_seconds > 120:
        raise ValueError("timeout_seconds must be between 3 and 120")

    if output_dir.exists():
        raise ValueError(f"output directory already exists: {output_dir}")
    if zip_output.exists():
        raise ValueError(f"zip output already exists: {zip_output}")

    output_dir.mkdir(parents=True, exist_ok=False)
    media_root = output_dir / "media"
    yt_root = media_root / "youtube"
    vk_root = media_root / "vk"
    yt_root.mkdir(parents=True, exist_ok=True)
    vk_root.mkdir(parents=True, exist_ok=True)

    candidate_digest = _canonical_json_sha256(_GAP_CANDIDATES)
    vk_downloads: dict[str, dict[str, Any]] = {}
    vk_images: dict[str, ImageEvidence] = {}
    yt_downloads: dict[str, list[dict[str, Any]]] = {}
    yt_images_by_id: dict[str, list[ImageEvidence]] = {}

    with httpx.Client(
        follow_redirects=True,
        headers={"User-Agent": "video-channel-manager/milovi-gap-thumbnail-evidence"},
    ) as client:
        for remote_id in sorted(wall_clips):
            clip = wall_clips[remote_id]
            frame_url = _pick_vk_frame_url(clip)
            if frame_url is None:
                vk_downloads[remote_id] = {"status": "no_frame_url"}
                continue
            target = vk_root / f"{remote_id.replace('-', 'neg')}.jpg"
            evidence, status = _download(client, url=frame_url, output=target, timeout_seconds=timeout_seconds)
            vk_downloads[remote_id] = status
            if evidence is not None:
                vk_images[remote_id] = evidence

        for candidate in _GAP_CANDIDATES:
            video_id = str(candidate["youtube_id"])
            yt_images: list[ImageEvidence] = []
            statuses: list[dict[str, Any]] = []
            for kind in _YT_THUMB_KINDS:
                url = _youtube_thumb_url(video_id, kind)
                target = yt_root / video_id / f"{kind}.jpg"
                evidence, status = _download(client, url=url, output=target, timeout_seconds=timeout_seconds)
                status["kind"] = kind
                statuses.append(status)
                if evidence is not None:
                    yt_images.append(evidence)
            yt_downloads[video_id] = statuses
            yt_images_by_id[video_id] = yt_images

    candidates_out: list[dict[str, Any]] = []
    for candidate in _GAP_CANDIDATES:
        video_id = str(candidate["youtube_id"])
        ranked = _rank_candidate(candidate, yt_images_by_id.get(video_id, []), wall_clips, vk_images)
        top = ranked[0] if ranked else None
        candidates_out.append(
            {
                **candidate,
                "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
                "transfer_gate": _transfer_gate(str(candidate.get("ip_class") or "")),
                "support_label": _support_label(top),
                "top_vk_candidates": ranked,
                "youtube_thumbnail_downloads": yt_downloads.get(video_id, []),
                "same_media_claim": False,
                "missing_native_clip_claim": False,
                "upload_authorized": False,
            }
        )

    downloaded_vk = sum(1 for row in vk_downloads.values() if row.get("status") == "downloaded")
    downloaded_yt = sum(
        1
        for rows in yt_downloads.values()
        for row in rows
        if row.get("status") == "downloaded"
    )
    status = "completed" if downloaded_vk == EXPECTED_UI_CLIP_COUNT and downloaded_yt == len(_GAP_CANDIDATES) * 4 else "partial_network_evidence"

    result = {
        "schema": OUTPUT_SCHEMA,
        "generated_at": _utc_iso(),
        "status": status,
        "project_key": MILOVI_PROJECT_KEY,
        "youtube_channel_id": MILOVI_YOUTUBE_CHANNEL_ID,
        "community_id": MILOVI_COMMUNITY_ID,
        "owner_id": MILOVI_OWNER_ID,
        "transport": "internal_web_read",
        "read_only": True,
        "provider_writes": 0,
        "provider_mutation_authorized": False,
        "input_evidence": {
            **input_hashes,
            "exact_public_ui_clip_count": EXPECTED_UI_CLIP_COUNT,
            "exact_wall_native_clip_count": EXPECTED_UI_CLIP_COUNT,
            "exact_ui_wall_intersection_count": EXPECTED_UI_CLIP_COUNT,
            "ui_only_count": 0,
            "wall_only_count": 0,
            "surface_complete_claim": False,
        },
        "candidate_manifest": {
            "count": len(_GAP_CANDIDATES),
            "canonical_sha256": candidate_digest,
            "scope": "cakes + pastries + desserts only",
            "source_role": "unresolved metadata-review candidates; not an upload queue",
        },
        "network_evidence": {
            "vk_frame_downloaded": downloaded_vk,
            "vk_frame_expected": EXPECTED_UI_CLIP_COUNT,
            "youtube_thumbnail_downloaded": downloaded_yt,
            "youtube_thumbnail_expected": len(_GAP_CANDIDATES) * 4,
            "download_hosts_are_allowlisted": True,
            "cookies_persisted": False,
            "authorization_data_persisted": False,
            "query_strings_persisted": False,
        },
        "candidates": candidates_out,
        "safety": {
            "same_media_claim_from_thumbnail_hash": False,
            "missing_native_clip_claim_from_no_thumbnail_match": False,
            "upload_authorized": False,
            "delete_authorized": False,
            "hide_authorized": False,
            "wall_post_authorized": False,
            "schedule_authorized": False,
            "ip_hold_is_blocking": True,
            "visual_review_is_blocking": True,
            "trademark_review_is_blocking": True,
        },
        "known_limitations": [
            "YouTube generated thumbnails and VK preview frames are supporting visual evidence only; edits, crops, timing, color, overlays, or custom thumbnails can prevent a true source match.",
            "No visual hash result by itself proves identical media and no non-match proves absence.",
            "The public UI and published wall exact Clip ID sets are equal for the accepted evidence, but hidden/private/draft/non-rendered provider objects remain outside this claim.",
            "Only cakes, pastries and desserts are in scope; personal/family/non-confectionery/process-only material is excluded.",
        ],
    }

    result_path = output_dir / "01-gap-thumbnail-reconciliation.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "schema": f"{OUTPUT_SCHEMA}-manifest",
        "generated_at": _utc_iso(),
        "project_key": MILOVI_PROJECT_KEY,
        "provider_writes": 0,
        "result_file": result_path.name,
        "result_sha256": _sha256_path(result_path),
        "media_file_count": sum(1 for path in media_root.rglob("*") if path.is_file()),
        "input_evidence": input_hashes,
        "candidate_manifest_sha256": candidate_digest,
        "surface_complete_claim": False,
        "mutation_authority": False,
    }
    manifest_path = output_dir / "00-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    zip_output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(output_dir).as_posix())

    return result


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Build provider-inert visual thumbnail evidence for unresolved Milovi Cake cake/dessert source candidates."
    )
    root.add_argument("--input", type=Path, required=True)
    root.add_argument("--output-dir", type=Path, required=True)
    root.add_argument("--zip-output", type=Path, required=True)
    root.add_argument("--timeout-seconds", type=float, default=20.0)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        result = build_gap_thumbnail_evidence(
            input_zip=args.input,
            output_dir=args.output_dir,
            zip_output=args.zip_output,
            timeout_seconds=args.timeout_seconds,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "provider_writes": 0,
                    "provider_mutation_authorized": False,
                    "error": f"{type(exc).__name__}: {exc}",
                },
                ensure_ascii=False,
            )
        )
        return 2

    labels: dict[str, int] = {}
    for row in result["candidates"]:
        label = str(row["support_label"])
        labels[label] = labels.get(label, 0) + 1

    print(
        json.dumps(
            {
                "status": result["status"],
                "exact_ui_wall_clips": result["input_evidence"]["exact_ui_wall_intersection_count"],
                "candidate_count": result["candidate_manifest"]["count"],
                "support_labels": labels,
                "provider_writes": 0,
                "provider_mutation_authorized": False,
                "surface_complete_claim": False,
                "output_dir": str(args.output_dir),
                "zip_output": str(args.zip_output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "OUTPUT_SCHEMA",
    "build_gap_thumbnail_evidence",
]
