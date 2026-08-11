from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
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
EXPECTED_CLIP_COUNT = 106
KNOWN_SHREK_CLIP = "-68859909_456239130"

_ALLOWED_IMAGE_HOST_SUFFIXES = (
    "i.ytimg.com",
    "img.youtube.com",
    "okcdn.ru",
    "userapi.com",
)
_YT_THUMB_KINDS = ("0", "1", "2", "3")
_GENERIC_TOKENS = {
    "торт",
    "торты",
    "cake",
    "milovi",
    "milovi_cake",
    "milovicake",
    "виктория",
    "милованова",
    "на",
    "заказ",
    "от",
    "для",
    "в",
    "и",
    "с",
    "со",
    "спб",
    "санкт",
    "петербург",
    "тортыназаказ",
    "тортыназаказспб",
    "тортназаказ",
    "тортназаказспб",
}

# Exact target-scope rows left unresolved after metadata-only v5 review.
# This is evidence input, never an upload queue.
# fmt: off
_CANDIDATE_ROWS: tuple[tuple[str, str, int, str, str, str], ...] = (
    ("P2Bpt77k408", "2026-04-06", 41, "CAKE", "IP_HOLD_HIDE", "Торт с Ам Нямом"),
    ("jZjDWn_MNq0", "2025-07-05", 42, "CAKE", "IP_HOLD_HIDE", "Торт Игра в Кальмара"),
    ("MdQ0kNBSsa8", "2025-07-01", 40, "CAKE", "VISUAL_REVIEW", "3D Торт Мышонок с Сыром"),
    ("d48QLgOuiTs", "2025-06-26", 35, "CAKE", "LOW", "Романтичный Торт с Бантом"),
    ("Oix9s6l9vNg", "2025-02-04", 20, "CAKE", "LOW", "Классический Медовик со Сливочно-Сметанным Кремом"),
    ("uA8SbnXzJJc", "2025-02-03", 11, "CAKE", "LOW", "Торт Медовик в Зефирном Покрытии"),
    ("u-PuqjWuhKk", "2024-11-23", 57, "CAKE", "LOW", "Синий Торт с Шариками на День Рождения"),
    ("FQGxV4DRPQw", "2024-10-29", 20, "CAKE", "VISUAL_REVIEW", "3D Торт Свинка"),
    ("L6XG2_zzrPU", "2024-08-27", 15, "DESSERT", "", "Зефир и Эклеры для Пикника"),
    ("xzMgMEWz5pM", "2024-08-19", 15, "CAKE", "IP_HOLD_HIDE", "Торт Чебурашка и Гена"),
    ("pCARxxaVjTw", "2024-06-10", 58, "DESSERT", "", "Шоколадные Цветы"),
    ("OWV-KGsLdA8", "2024-04-03", 34, "CAKE", "LOW", "Чёрный Торт Сердце"),
    ("CQ29P1F8Hfo", "2024-03-28", 54, "DESSERT", "", "Меренговый Рулет с Малиновой Серцевинкой"),
    ("SiluLt5Bz1c", "2024-03-22", 27, "CAKE", "LOW", "Ванильный Торт с Миксом Ягод"),
    ("cE0ofu6WV3s", "2024-03-04", 29, "CAKE", "LOW", "Торт для Врачей Кардиологов"),
    ("2yhQ4nMWm3I", "2024-02-29", 30, "CAKE", "TRADEMARK_REVIEW", "Торт Ozon с Начинкой Ферреро"),
    ("7FCbopqeTYE", "2024-01-18", 30, "CAKE", "IP_HOLD_HIDE", "Двойной Торт Wednesday"),
    ("o1WXIMupuws", "2024-01-04", 28, "CAKE", "LOW", "Торт на День Рождения"),
    ("1_SuzeQD_1g", "2023-12-29", 30, "CAKE", "LOW", "Новогодний Бенто-Торт Снежинка"),
    ("5B9OuXbdGKc", "2023-12-19", 30, "CAKE", "LOW", "Торт Тонометр"),
    ("ZuQt6yFePO0", "2023-12-18", 31, "CAKE", "IP_HOLD_HIDE", "Торт Роблокс"),
    ("BAVKrQQ00XI", "2023-12-05", 18, "CAKE", "LOW", "Торты на Заказ в Санкт-Петербурге"),
    ("R0KjJvbxS8s", "2023-11-18", 8, "DESSERT", "", "Трайфлы Торты-Стаканчики"),
    ("qPXHrdUgPUY", "2023-06-23", 33, "CAKE", "IP_HOLD_HIDE", "Торт Радужные Друзья Roblox"),
    ("R-LknUy9BEs", "2023-06-22", 60, "CAKE", "LOW", "Торты в Санкт-Петербурге"),
)
# fmt: on

_GAP_CANDIDATES: tuple[dict[str, Any], ...] = tuple(
    {
        "youtube_id": youtube_id,
        "published": published,
        "duration_s": duration_s,
        "scope": scope,
        "ip_class": ip_class,
        "title": title,
    }
    for youtube_id, published, duration_s, scope, ip_class, title in _CANDIDATE_ROWS
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
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json_sha256(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return _sha256_bytes(raw)


def _safe_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme and parsed.netloc:
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    return parsed.path


def _allowed_image_url(url: str) -> bool:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and any(
        host == suffix or host.endswith(f".{suffix}") for suffix in _ALLOWED_IMAGE_HOST_SUFFIXES
    )


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
            clips.setdefault(f"{owner_id}_{video_id}", item)
    return clips


def _exact_member(names: Sequence[str], suffix: str) -> str:
    matches = [name for name in names if name.endswith(suffix)]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one ZIP member ending with {suffix!r}; got {len(matches)}")
    return matches[0]


def _read_input(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    if not path.is_file():
        raise ValueError(f"input ZIP does not exist: {path}")

    outer_sha = _sha256_path(path)
    with zipfile.ZipFile(path) as outer:
        required = {
            "00-manifest.json",
            "01-vk-clips-ui-inventory.json",
            "02-wall-evidence-handoff.zip",
        }
        if set(outer.namelist()) != required:
            raise ValueError("reconciliation ZIP members do not match the exact v1 contract")
        manifest_bytes = outer.read("00-manifest.json")
        ui_bytes = outer.read("01-vk-clips-ui-inventory.json")
        wall_bytes = outer.read("02-wall-evidence-handoff.zip")

    manifest = json.loads(manifest_bytes.decode("utf-8-sig"))
    ui = json.loads(ui_bytes.decode("utf-8-sig"))
    if manifest.get("schema") != INPUT_SCHEMA:
        raise ValueError(f"unexpected input schema: {manifest.get('schema')}")

    target = manifest.get("target") or {}
    if (
        target.get("project_key") != MILOVI_PROJECT_KEY
        or target.get("community_id") != MILOVI_COMMUNITY_ID
        or target.get("owner_id") != MILOVI_OWNER_ID
    ):
        raise ValueError("input target identity is not exact Milovi Cake")

    ui_sha = _sha256_bytes(ui_bytes)
    wall_sha = _sha256_bytes(wall_bytes)
    if (manifest.get("ui_inventory") or {}).get("sha256") != ui_sha:
        raise ValueError("UI inventory SHA-256 does not match manifest")
    if (manifest.get("wall_evidence") or {}).get("sha256") != wall_sha:
        raise ValueError("wall evidence SHA-256 does not match manifest")

    coverage = ui.get("coverage") or {}
    probe = ui.get("browser_probe") or {}
    if (
        ui.get("schema") != UI_SCHEMA
        or ui.get("project_key") != MILOVI_PROJECT_KEY
        or ui.get("community_id") != MILOVI_COMMUNITY_ID
        or ui.get("owner_id") != MILOVI_OWNER_ID
        or ui.get("read_only") is not True
        or ui.get("provider_writes") != 0
        or ui.get("provider_mutation_authorized") is not False
        or probe.get("status") != "ok_bounded_ui_observation"
        or coverage.get("clip_count") != EXPECTED_CLIP_COUNT
        or coverage.get("bounded_ui_end_observed") is not True
        or coverage.get("surface_complete_claim") is not False
    ):
        raise ValueError("UI inventory identity/read-only/coverage contract is invalid")
    if KNOWN_SHREK_CLIP not in set(coverage.get("required_remote_ids_found") or []):
        raise ValueError("known Shrek control Clip is absent")

    ui_clips = ui.get("clips") or []
    ui_ids = [str(row.get("remote_id") or "") for row in ui_clips if isinstance(row, dict)]
    if len(ui_ids) != EXPECTED_CLIP_COUNT or len(ui_ids) != len(set(ui_ids)):
        raise ValueError("UI inventory does not contain 106 unique Clip IDs")
    if any(not remote_id.startswith(f"{MILOVI_OWNER_ID}_") for remote_id in ui_ids):
        raise ValueError("UI inventory contains a foreign normalized Clip")

    with zipfile.ZipFile(io.BytesIO(wall_bytes)) as nested:
        member = _exact_member(
            nested.namelist(),
            "/01-published-wall-posts.json",
        )
        posts_bytes = nested.read(member)

    wall_clips = _extract_wall_clips(json.loads(posts_bytes.decode("utf-8-sig")))
    if len(wall_clips) != EXPECTED_CLIP_COUNT or set(ui_ids) != set(wall_clips):
        raise ValueError("exact public UI and wall native Clip sets are not identical 106-item sets")

    return wall_clips, {
        "outer_input_sha256": outer_sha,
        "ui_inventory_sha256": ui_sha,
        "wall_handoff_sha256": wall_sha,
        "published_wall_posts_sha256": _sha256_bytes(posts_bytes),
    }


def _pick_vk_frame_url(item: dict[str, Any]) -> str | None:
    for key in ("first_frame", "image"):
        choices: list[tuple[int, str]] = []
        entries = item.get(key) or []
        for row in entries:
            if not isinstance(row, dict):
                continue
            url = str(row.get("url") or "")
            if not _allowed_image_url(url):
                continue
            area = int(row.get("width") or 0) * int(row.get("height") or 0)
            choices.append((area, url))
        if choices:
            return max(choices)[1]
    return None


def _youtube_thumb_url(video_id: str, kind: str) -> str:
    if kind not in _YT_THUMB_KINDS:
        raise ValueError(f"invalid YouTube thumbnail kind: {kind}")
    return f"https://i.ytimg.com/vi/{video_id}/{kind}.jpg"


def _load_pillow() -> Any:
    try:
        from PIL import Image  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            'Pillow is required; install current repo with: pip install -e ".[milovi-gap-read]"'
        ) from exc
    return Image


def _dhash(data: bytes, safe_source: str) -> ImageEvidence:
    Image = _load_pillow()
    with Image.open(io.BytesIO(data)) as source:
        source.load()
        width, height = source.size
        gray = source.convert("L")
        pixels = list(gray.resize((9, 8), Image.Resampling.LANCZOS).getdata())

    value = 0
    for y in range(8):
        for x in range(8):
            value = (value << 1) | (1 if pixels[y * 9 + x] > pixels[y * 9 + x + 1] else 0)
    return ImageEvidence(
        _sha256_bytes(data),
        f"{value:016x}",
        width,
        height,
        safe_source,
    )


def _hamming(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()


def _tokens(value: str) -> set[str]:
    normalized = value.lower().replace("ё", "е")
    normalized = re.sub(r"#[0-9a-zа-я_]+", " ", normalized)
    normalized = re.sub(r"[^0-9a-zа-я]+", " ", normalized)
    return {token for token in normalized.split() if len(token) > 1 and token not in _GENERIC_TOKENS}


def _metadata_score(
    candidate: dict[str, Any],
    clip: dict[str, Any],
) -> tuple[float, int, int]:
    yt_tokens = _tokens(str(candidate["title"]))
    vk_tokens = _tokens(str(clip.get("description") or clip.get("title") or ""))
    overlap = len(yt_tokens & vk_tokens) / max(1, len(yt_tokens | vk_tokens))

    duration = clip.get("duration")
    duration_delta = abs(int(candidate["duration_s"]) - int(duration)) if isinstance(duration, int) else 9999
    date_delta = 9999
    if isinstance(clip.get("date"), int):
        vk_date = datetime.fromtimestamp(int(clip["date"]), UTC).date()
        yt_date = datetime.fromisoformat(str(candidate["published"])).date()
        date_delta = abs((vk_date - yt_date).days)

    duration_score = max(0.0, 1.0 - duration_delta / 20.0)
    date_score = max(0.0, 1.0 - date_delta / 90.0)
    return (
        0.6 * overlap + 0.3 * duration_score + 0.1 * date_score,
        duration_delta,
        date_delta,
    )


def _download_image(
    client: httpx.Client,
    *,
    url: str,
    output: Path,
    timeout_seconds: float,
) -> tuple[ImageEvidence | None, dict[str, Any]]:
    safe_source = _safe_url(url)
    if not _allowed_image_url(url):
        return None, {"status": "rejected_url", "source": safe_source}

    try:
        response = client.get(url, timeout=timeout_seconds)
        response.raise_for_status()
        content_type = str(response.headers.get("content-type") or "").lower()
        if "image" not in content_type:
            return None, {
                "status": "non_image_response",
                "source": safe_source,
                "content_type": content_type[:120],
            }
        data = response.content
        evidence = _dhash(data, safe_source)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
        return evidence, {
            "status": "downloaded",
            "source": safe_source,
            "sha256": evidence.sha256,
            "dhash": evidence.dhash_hex,
            "width": evidence.width,
            "height": evidence.height,
            "bytes": len(data),
        }
    except Exception as exc:
        return None, {
            "status": "error",
            "source": safe_source,
            "error": f"{type(exc).__name__}: {exc}"[:500],
        }


def _rank(
    candidate: dict[str, Any],
    yt_images: Sequence[ImageEvidence],
    wall_clips: dict[str, dict[str, Any]],
    vk_images: dict[str, ImageEvidence],
) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for remote_id, clip in wall_clips.items():
        distance = None
        if yt_images and remote_id in vk_images:
            distance = min(_hamming(image.dhash_hex, vk_images[remote_id].dhash_hex) for image in yt_images)
        visual_score = 0.0 if distance is None else max(0.0, 1.0 - distance / 64.0)
        metadata, duration_delta, date_delta = _metadata_score(candidate, clip)
        ranked.append(
            {
                "remote_id": remote_id,
                "support_score": round(
                    0.64 * visual_score + 0.36 * metadata,
                    6,
                ),
                "visual_dhash_distance": distance,
                "metadata_score": round(metadata, 6),
                "duration_delta_s": duration_delta,
                "date_delta_days": date_delta,
                "vk_duration_s": clip.get("duration"),
                "vk_description": str(clip.get("description") or "")[:1200],
                "vk_clip_url": f"https://vk.com/clip{remote_id}",
            }
        )
    ranked.sort(key=lambda row: float(row["support_score"]), reverse=True)
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


def _transfer_gate(ip_class: str) -> str:
    return {
        "IP_HOLD_HIDE": "IP_HOLD_DO_NOT_TRANSFER",
        "TRADEMARK_REVIEW": "TRADEMARK_REVIEW_REQUIRED",
        "VISUAL_REVIEW": "VISUAL_REVIEW_REQUIRED",
    }.get(ip_class, "MEDIA_RECONCILIATION_REQUIRED")


def build_gap_thumbnail_evidence(
    *,
    input_zip: Path,
    output_dir: Path,
    zip_output: Path,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    if not 3 <= timeout_seconds <= 120:
        raise ValueError("timeout_seconds must be between 3 and 120")
    if output_dir.exists() or zip_output.exists():
        raise ValueError("output_dir and zip_output must not already exist")

    wall_clips, input_hashes = _read_input(input_zip)
    media_root = output_dir / "media"
    yt_root = media_root / "youtube"
    vk_root = media_root / "vk"
    yt_root.mkdir(parents=True)
    vk_root.mkdir(parents=True)

    vk_images: dict[str, ImageEvidence] = {}
    vk_downloads: dict[str, dict[str, Any]] = {}
    yt_images: dict[str, list[ImageEvidence]] = {}
    yt_downloads: dict[str, list[dict[str, Any]]] = {}

    with httpx.Client(
        follow_redirects=True,
        headers={"User-Agent": "video-channel-manager/milovi-gap-read"},
    ) as client:
        for remote_id in sorted(wall_clips):
            url = _pick_vk_frame_url(wall_clips[remote_id])
            if url is None:
                vk_downloads[remote_id] = {"status": "no_frame_url"}
                continue
            evidence, download_status = _download_image(
                client,
                url=url,
                output=vk_root / f"{remote_id.replace('-', 'neg')}.jpg",
                timeout_seconds=timeout_seconds,
            )
            vk_downloads[remote_id] = download_status
            if evidence is not None:
                vk_images[remote_id] = evidence

        for candidate in _GAP_CANDIDATES:
            video_id = str(candidate["youtube_id"])
            images: list[ImageEvidence] = []
            downloads: list[dict[str, Any]] = []
            for kind in _YT_THUMB_KINDS:
                evidence, download_status = _download_image(
                    client,
                    url=_youtube_thumb_url(video_id, kind),
                    output=yt_root / video_id / f"{kind}.jpg",
                    timeout_seconds=timeout_seconds,
                )
                downloads.append({**download_status, "kind": kind})
                if evidence is not None:
                    images.append(evidence)
            yt_images[video_id] = images
            yt_downloads[video_id] = downloads

    candidates: list[dict[str, Any]] = []
    for candidate in _GAP_CANDIDATES:
        video_id = str(candidate["youtube_id"])
        ranked = _rank(
            candidate,
            yt_images.get(video_id, []),
            wall_clips,
            vk_images,
        )
        candidates.append(
            {
                **candidate,
                "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
                "transfer_gate": _transfer_gate(str(candidate.get("ip_class") or "")),
                "support_label": _support_label(ranked[0] if ranked else None),
                "top_vk_candidates": ranked,
                "youtube_thumbnail_downloads": yt_downloads.get(video_id, []),
                "same_media_claim": False,
                "missing_native_clip_claim": False,
                "upload_authorized": False,
            }
        )

    vk_downloaded = sum(row.get("status") == "downloaded" for row in vk_downloads.values())
    yt_downloaded = sum(row.get("status") == "downloaded" for rows in yt_downloads.values() for row in rows)
    expected_yt = len(_GAP_CANDIDATES) * len(_YT_THUMB_KINDS)
    run_status = (
        "completed"
        if vk_downloaded == EXPECTED_CLIP_COUNT and yt_downloaded == expected_yt
        else "partial_network_evidence"
    )

    result = {
        "schema": OUTPUT_SCHEMA,
        "generated_at": _utc_iso(),
        "status": run_status,
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
            "exact_public_ui_clip_count": EXPECTED_CLIP_COUNT,
            "exact_wall_native_clip_count": EXPECTED_CLIP_COUNT,
            "exact_ui_wall_intersection_count": EXPECTED_CLIP_COUNT,
            "ui_only_count": 0,
            "wall_only_count": 0,
            "surface_complete_claim": False,
        },
        "candidate_manifest": {
            "count": len(_GAP_CANDIDATES),
            "canonical_sha256": _canonical_json_sha256(_GAP_CANDIDATES),
            "scope": "cakes + pastries + desserts only",
            "source_role": "unresolved evidence candidates; not an upload queue",
        },
        "network_evidence": {
            "vk_frame_downloaded": vk_downloaded,
            "vk_frame_expected": EXPECTED_CLIP_COUNT,
            "youtube_thumbnail_downloaded": yt_downloaded,
            "youtube_thumbnail_expected": expected_yt,
            "download_hosts_are_allowlisted": True,
            "cookies_persisted": False,
            "authorization_data_persisted": False,
            "query_strings_persisted": False,
        },
        "candidates": candidates,
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
            "Generated YouTube thumbnails and VK preview frames are supporting visual evidence only.",
            "A visual hash match does not by itself prove identical media, and a non-match does not prove absence.",
            "Public UI and published-wall Clip ID sets are equal here, but hidden/private/draft/non-rendered objects remain outside the claim.",
            "Only cakes, pastries and desserts are in scope; personal/family/non-confectionery/process-only material is excluded.",
        ],
    }

    result_path = output_dir / "01-gap-thumbnail-reconciliation.json"
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema": f"{OUTPUT_SCHEMA}-manifest",
        "generated_at": _utc_iso(),
        "project_key": MILOVI_PROJECT_KEY,
        "provider_writes": 0,
        "result_file": result_path.name,
        "result_sha256": _sha256_path(result_path),
        "media_file_count": sum(path.is_file() for path in media_root.rglob("*")),
        "input_evidence": input_hashes,
        "candidate_manifest_sha256": _canonical_json_sha256(_GAP_CANDIDATES),
        "surface_complete_claim": False,
        "mutation_authority": False,
    }
    (output_dir / "00-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    zip_output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        zip_output,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for path in sorted(output_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(output_dir).as_posix())
    return result


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description=("Build read-only visual evidence for unresolved Milovi cake/dessert candidates.")
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
                "exact_ui_wall_clips": EXPECTED_CLIP_COUNT,
                "candidate_count": len(_GAP_CANDIDATES),
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


__all__ = ["OUTPUT_SCHEMA", "build_gap_thumbnail_evidence"]
