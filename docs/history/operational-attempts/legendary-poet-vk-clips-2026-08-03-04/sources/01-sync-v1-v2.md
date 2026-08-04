# Historical source snapshots

> Non-executable evidence only. Do not copy or run without a new reviewed design and tests.

## 001. Initial exact Shorts sync V1

- Original: `legendary_poet_shorts_sync.py`
- SHA-256: `b5775a828a53bdb55b3e9992dcb64909d2f60631b30aa6c8ead1818f4e7359af`

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

ROOT = Path.cwd()
SRC = ROOT / "src"
if SRC.is_dir():
    sys.path.insert(0, str(SRC))

from video_channel_manager.config import get_settings
from video_channel_manager.local_media.quality import MediaQualityError, MediaQualityReport, probe_media
from video_channel_manager.platforms.vk import VkApiClient, VkTokenStore
from video_channel_manager.platforms.vk.lock import local_vk_write_lock
from video_channel_manager.platforms.vk.publishing import VkPublicationText, render_vk_publication
from video_channel_manager.platforms.vk.writer import VkUploadTicket, VkVideoWriter, VkWriteError

BRAND_RE = re.compile(r"@thelegendarypoet|#thelegendarypoet|#theepicpoet|#shorts", re.I)
NON_WORD_RE = re.compile(r"[^a-zа-я0-9]+", re.I)
SPACE_RE = re.compile(r"\s+")
VERSION_RE = re.compile(r"\b(?:версия|version)\s*[-–—:]?\s*(\d+)\b", re.I)
STYLE_GROUPS = {
    "rock": ("рок", "rock"),
    "dj": ("dj", "диджей"),
    "reggae": ("регги", "reggae"),
    "nordic_folk": ("nordic folk", "скандинав"),
    "english": ("english", "англий"),
    "dramatic": ("драмат", "dramatic"),
    "cinematic": ("кинематограф", "cinematic"),
}
CORE_STOPWORDS = frozenset(
    """
    александр александрович сергеевич пушкин сергей есенин владимир маяковский
    михаил юрьевич лермонтов валерий брюсов анна ахматова константин симонов
    афанасий фет николай некрасов борис пастернак блок the legendary poet epic
    shorts version версия короткая короткий фрагмент полная полный стихотворения
    cover suno ai english русский русская песня стих поэт поэта style стиле вариант
    """.split()
)


@dataclass(frozen=True)
class Match:
    source_id: str
    source_title: str
    source_duration: int
    target_id: str
    target_title: str
    target_duration: int
    score: float
    duration_delta: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Exact guarded YouTube Shorts to VK Clips synchronization.")
    parser.add_argument("--youtube-audit", type=Path, required=True)
    parser.add_argument("--vk-audit", type=Path, required=True)
    parser.add_argument("--account", default="legendary-poet")
    parser.add_argument("--community", type=int, required=True)
    parser.add_argument("--shorts-url", required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--yt-dlp", default="yt-dlp")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--processing-timeout", type=int, default=7200)
    parser.add_argument("--poll-seconds", type=float, default=10.0)
    parser.add_argument("--write-delay", type=float, default=3.0)
    parser.add_argument("--minimum-matched", type=int, default=38)
    parser.add_argument("--maximum-extra-vertical", type=int, default=2)
    parser.add_argument("--expected-shorts-count", type=int, required=True)
    parser.add_argument("--expected-matched-count", type=int, required=True)
    parser.add_argument("--expected-missing-count", type=int, required=True)
    parser.add_argument("--expected-extra-vertical-count", type=int, required=True)
    parser.add_argument("--expected-ambiguous-count", type=int, default=0)
    parser.add_argument("--expected-source-snapshot", required=True)
    parser.add_argument("--expected-vk-snapshot", required=True)
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def normalize(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "").casefold().replace("ё", "е")
    text = BRAND_RE.sub(" ", text)
    text = text.replace("version", "версия")
    text = NON_WORD_RE.sub(" ", text)
    return SPACE_RE.sub(" ", text).strip()


def version_numbers(value: str) -> frozenset[int]:
    return frozenset(int(match.group(1)) for match in VERSION_RE.finditer(normalize(value)))


def style_signature(value: str) -> frozenset[str]:
    text = normalize(value)
    found = set()
    for key, needles in STYLE_GROUPS.items():
        if any(needle in text for needle in needles):
            found.add(key)
    return frozenset(found)


def title_similarity(left: str, right: str) -> float:
    a = normalize(left)
    b = normalize(right)
    sequence = SequenceMatcher(None, a, b).ratio()
    at = set(a.split())
    bt = set(b.split())
    union = at | bt
    inter = at & bt
    jaccard = len(inter) / len(union) if union else 1.0
    containment = len(inter) / min(len(at), len(bt)) if at and bt else 1.0
    return sequence * 0.55 + jaccard * 0.30 + containment * 0.15


def core_tokens(value: str) -> frozenset[str]:
    return frozenset(
        token
        for token in normalize(value).split()
        if len(token) >= 3 and token not in CORE_STOPWORDS and not token.isdigit()
    )


def compatible(source: dict[str, Any], target: dict[str, Any]) -> tuple[bool, float, int]:
    source_duration = int(source.get("duration_seconds") or 0)
    target_duration = int(target.get("duration_seconds") or 0)
    delta = abs(source_duration - target_duration)
    if delta > 3:
        return False, 0.0, delta

    source_versions = version_numbers(str(source.get("title") or ""))
    target_versions = version_numbers(str(target.get("title") or ""))
    if source_versions != target_versions:
        return False, 0.0, delta

    source_title = str(source.get("title") or "")
    target_title = str(target.get("title") or "")
    source_core = core_tokens(source_title)
    target_core = core_tokens(target_title)
    shared_core = source_core & target_core
    if not shared_core:
        return False, 0.0, delta

    source_styles = style_signature(source_title)
    target_styles = style_signature(target_title)
    if source_styles and target_styles and source_styles.isdisjoint(target_styles):
        return False, 0.0, delta

    broad = title_similarity(source_title, target_title)
    core_union = source_core | target_core
    core_jaccard = len(shared_core) / len(core_union) if core_union else 1.0
    core_containment = len(shared_core) / min(len(source_core), len(target_core))
    score = broad * 0.50 + core_jaccard * 0.30 + core_containment * 0.20
    if score < 0.35:
        return False, score, delta
    score += 0.25 if delta <= 1 else 0.15
    return True, round(score, 6), delta


def enumerate_shorts(yt_dlp: str, url: str, output: Path) -> list[str]:
    command = [yt_dlp, "--flat-playlist", "--dump-single-json", "--no-warnings", url]
    try:
        completed = subprocess.run(command, capture_output=True, check=False, timeout=300)
    except FileNotFoundError as exc:
        raise ValueError(f"yt-dlp not found: {yt_dlp}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError("YouTube Shorts enumeration timed out") from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace")[-4000:]
        raise ValueError(f"yt-dlp Shorts enumeration failed: {detail}")
    text = completed.stdout.decode("utf-8", errors="strict")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("yt-dlp returned invalid Shorts JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("entries"), list):
        raise ValueError("yt-dlp Shorts result has no entries list")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result: list[str] = []
    seen: set[str] = set()
    for entry in payload["entries"]:
        if not isinstance(entry, dict):
            continue
        video_id = str(entry.get("id") or entry.get("url") or "").strip()
        if not video_id or video_id in seen:
            continue
        seen.add(video_id)
        result.append(video_id)
    if not result:
        raise ValueError("YouTube Shorts enumeration returned zero IDs")
    return result


def classify(shorts: list[dict[str, Any]], vk_videos: list[dict[str, Any]]) -> tuple[list[Match], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    vertical = [
        item
        for item in vk_videos
        if int(item.get("metadata", {}).get("height") or 0) > int(item.get("metadata", {}).get("width") or 0)
    ]
    candidates: list[tuple[float, int, int, int]] = []
    per_source: dict[int, list[tuple[float, int]]] = {}
    per_target: dict[int, list[tuple[float, int]]] = {}
    for si, source in enumerate(shorts):
        for ti, target in enumerate(vertical):
            ok, score, delta = compatible(source, target)
            if not ok:
                continue
            candidates.append((score, si, ti, delta))
            per_source.setdefault(si, []).append((score, ti))
            per_target.setdefault(ti, []).append((score, si))

    ambiguous: list[dict[str, Any]] = []
    blocked_source: set[int] = set()
    blocked_target: set[int] = set()
    for si, values in per_source.items():
        ranked = sorted(values, reverse=True)
        if len(ranked) > 1 and ranked[0][0] - ranked[1][0] <= 0.02:
            blocked_source.add(si)
            ambiguous.append({
                "kind": "source",
                "source_id": shorts[si]["ref"]["remote_id"],
                "source_title": shorts[si]["title"],
                "candidate_target_ids": [vertical[ti]["ref"]["remote_id"] for _, ti in ranked[:3]],
            })
    for ti, values in per_target.items():
        ranked = sorted(values, reverse=True)
        if len(ranked) > 1 and ranked[0][0] - ranked[1][0] <= 0.02:
            blocked_target.add(ti)
            ambiguous.append({
                "kind": "target",
                "target_id": vertical[ti]["ref"]["remote_id"],
                "target_title": vertical[ti]["title"],
                "candidate_source_ids": [shorts[si]["ref"]["remote_id"] for _, si in ranked[:3]],
            })

    candidates.sort(key=lambda row: (-row[0], row[1], row[2]))
    used_source: set[int] = set()
    used_target: set[int] = set()
    matches: list[Match] = []
    for score, si, ti, delta in candidates:
        if si in blocked_source or ti in blocked_target or si in used_source or ti in used_target:
            continue
        source = shorts[si]
        target = vertical[ti]
        used_source.add(si)
        used_target.add(ti)
        matches.append(Match(
            source_id=str(source["ref"]["remote_id"]),
            source_title=str(source["title"]),
            source_duration=int(source.get("duration_seconds") or 0),
            target_id=str(target["ref"]["remote_id"]),
            target_title=str(target["title"]),
            target_duration=int(target.get("duration_seconds") or 0),
            score=score,
            duration_delta=delta,
        ))

    missing = [source for si, source in enumerate(shorts) if si not in used_source and si not in blocked_source]
    extras = [target for ti, target in enumerate(vertical) if ti not in used_target and ti not in blocked_target]
    return matches, missing, extras, ambiguous


def download_video(yt_dlp: str, video_id: str, cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    exact = cache_dir / f"{video_id}.mp4"
    if exact.is_file() and exact.stat().st_size > 0:
        return exact
    command = [
        yt_dlp,
        "--no-playlist",
        "--no-progress",
        "--newline",
        "--merge-output-format", "mp4",
        "--remux-video", "mp4",
        "--format", "bv*+ba/b",
        "--output", str(cache_dir / f"{video_id}.%(ext)s"),
        f"https://www.youtube.com/watch?v={video_id}",
    ]
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise ValueError(f"yt-dlp failed before any VK upload for {video_id}")
    if not exact.is_file() or exact.stat().st_size <= 0:
        candidates = sorted(cache_dir.glob(f"{video_id}*.mp4"))
        if not candidates:
            raise ValueError(f"Downloaded MP4 not found for {video_id}")
        exact = candidates[0]
    return exact


def manifest_hash(queue: list[dict[str, Any]], publications: dict[str, VkPublicationText], reports: dict[str, MediaQualityReport]) -> str:
    payload = []
    for item in queue:
        source_id = str(item["ref"]["remote_id"])
        report = reports[source_id]
        publication = publications[source_id]
        payload.append({
            "source_id": source_id,
            "source_title": item["title"],
            "source_duration": item.get("duration_seconds"),
            "published_title": publication.title,
            "description_sha256": publication.description_sha256,
            "media_sha256": report.sha256,
            "media_size_bytes": report.size_bytes,
            "media_duration_seconds": report.duration_seconds,
            "width": report.width,
            "height": report.height,
        })
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def begin_clip_upload(writer: VkVideoWriter, *, community_id: int, title: str, description: str) -> VkUploadTicket:
    response = writer._call(  # Deliberately use exact video.save flags absent from the older wrapper.
        "video.save",
        params={
            "group_id": community_id,
            "name": title.strip(),
            "description": description,
            "wallpost": False,
            "auto_publish": False,
            "repeat": False,
            "is_private": False,
            "no_comments": False,
        },
    )
    if not isinstance(response, dict):
        raise VkWriteError("video.save returned a non-object response", method="video.save")
    owner_id = response.get("owner_id")
    video_id = response.get("video_id")
    upload_url = response.get("upload_url")
    if owner_id != -community_id or not isinstance(video_id, int) or video_id <= 0 or not isinstance(upload_url, str):
        raise VkWriteError("video.save returned an invalid clip upload ticket", method="video.save")
    return VkUploadTicket(owner_id=owner_id, video_id=video_id, upload_url=upload_url)


def parse_remote_id(value: str) -> tuple[int, int]:
    owner, sep, video = value.partition("_")
    if not sep:
        raise ValueError(f"Invalid VK remote ID: {value}")
    return int(owner), int(video)


def load_or_create_journal(path: Path, *, source_snapshot: str, vk_snapshot: str, community: int, manifest: str, queue: list[dict[str, Any]]) -> dict[str, Any]:
    if path.exists():
        journal = read_json(path)
        expected = (source_snapshot, vk_snapshot, community, manifest)
        actual = (
            str(journal.get("source_snapshot_id")),
            str(journal.get("vk_snapshot_id")),
            int(journal.get("community_id") or 0),
            str(journal.get("manifest_sha256")),
        )
        if actual != expected:
            raise ValueError("Existing Shorts journal belongs to another snapshots/manifest/community")
        return journal
    now = datetime.now(UTC).isoformat()
    journal = {
        "schema_name": "video-manager.legendary-poet-shorts-journal",
        "schema_version": 1,
        "created_at": now,
        "updated_at": now,
        "source_snapshot_id": source_snapshot,
        "vk_snapshot_id": vk_snapshot,
        "community_id": community,
        "manifest_sha256": manifest,
        "wall_mutation_authorized": False,
        "queue": [str(item["ref"]["remote_id"]) for item in queue],
        "uploads": {},
    }
    write_json(path, journal)
    return journal


def save_journal(path: Path, journal: dict[str, Any]) -> None:
    journal["updated_at"] = datetime.now(UTC).isoformat()
    write_json(path, journal)


def ensure_clip_type(item: dict[str, Any], remote_id: str) -> None:
    observed = str(item.get("type") or "")
    if observed != "short_video":
        raise ValueError(f"VK object {remote_id} completed with type={observed!r}, expected 'short_video'")


def main() -> int:
    args = parse_args()
    youtube = read_json(args.youtube_audit)
    vk = read_json(args.vk_audit)
    source_snapshot = str(youtube.get("snapshot_id") or "")
    vk_snapshot = str(vk.get("snapshot_id") or "")
    if source_snapshot != args.expected_source_snapshot:
        raise ValueError(f"YouTube snapshot mismatch: {source_snapshot}")
    if vk_snapshot != args.expected_vk_snapshot:
        raise ValueError(f"VK snapshot mismatch: {vk_snapshot}")

    raw_youtube_videos = youtube.get("videos")
    raw_vk_videos = vk.get("videos")
    if not isinstance(raw_youtube_videos, list) or not isinstance(raw_vk_videos, list):
        raise ValueError("Audit videos must be lists")

    youtube_by_id: dict[str, dict[str, Any]] = {}
    duplicate_source_ids: list[str] = []
    for item in raw_youtube_videos:
        if not isinstance(item, dict):
            continue
        ref = item.get("ref")
        source_id = str(ref.get("remote_id") or "") if isinstance(ref, dict) else ""
        if not source_id:
            continue
        if source_id in youtube_by_id:
            duplicate_source_ids.append(source_id)
            continue
        youtube_by_id[source_id] = item

    args.report_dir.mkdir(parents=True, exist_ok=True)
    shorts_json = args.report_dir / "legendary-poet-youtube-shorts-flat.json"
    shorts_ids = enumerate_shorts(args.yt_dlp, args.shorts_url, shorts_json)
    missing_from_audit = [source_id for source_id in shorts_ids if source_id not in youtube_by_id]
    if missing_from_audit:
        raise ValueError("Shorts IDs absent from YouTube audit: " + ", ".join(missing_from_audit))
    shorts = [youtube_by_id[source_id] for source_id in shorts_ids]

    matches, missing, extras, ambiguous = classify(shorts, [item for item in raw_vk_videos if isinstance(item, dict)])
    report = {
        "schema_name": "video-manager.legendary-poet-shorts-classification",
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "source_snapshot_id": source_snapshot,
        "vk_snapshot_id": vk_snapshot,
        "youtube_short_count": len(shorts),
        "vk_video_count": len(raw_vk_videos),
        "vk_vertical_count": sum(
            int(item.get("metadata", {}).get("height") or 0) > int(item.get("metadata", {}).get("width") or 0)
            for item in raw_vk_videos if isinstance(item, dict)
        ),
        "duplicate_source_ids_in_audit": sorted(set(duplicate_source_ids)),
        "matched_count": len(matches),
        "confirmed_missing_count": len(missing),
        "extra_vertical_vk_count": len(extras),
        "ambiguous_count": len(ambiguous),
        "matches": [match.__dict__ for match in matches],
        "confirmed_missing": [
            {
                "source_id": item["ref"]["remote_id"],
                "title": item["title"],
                "duration_seconds": item.get("duration_seconds"),
                "published_at": item.get("published_at"),
            }
            for item in missing
        ],
        "extra_vertical_vk": [
            {
                "target_id": item["ref"]["remote_id"],
                "title": item["title"],
                "duration_seconds": item.get("duration_seconds"),
                "width": item.get("metadata", {}).get("width"),
                "height": item.get("metadata", {}).get("height"),
            }
            for item in extras
        ],
        "ambiguous": ambiguous,
    }
    classification_path = args.report_dir / "legendary-poet-shorts-classification.json"
    write_json(classification_path, report)

    print("Legendary Poet Shorts classification:")
    print(f"  exact YouTube Shorts IDs: {len(shorts)}")
    print(f"  matched to vertical VK objects: {len(matches)}")
    print(f"  confirmed missing: {len(missing)}")
    print(f"  extra vertical VK objects: {len(extras)}")
    print(f"  ambiguous: {len(ambiguous)}")
    print(f"  duplicate source IDs in audit: {sorted(set(duplicate_source_ids))}")
    print(f"  report: {classification_path}")

    exact_counts = {
        "youtube_short_count": (len(shorts), args.expected_shorts_count),
        "matched_count": (len(matches), args.expected_matched_count),
        "confirmed_missing_count": (len(missing), args.expected_missing_count),
        "extra_vertical_vk_count": (len(extras), args.expected_extra_vertical_count),
        "ambiguous_count": (len(ambiguous), args.expected_ambiguous_count),
    }
    mismatches = [
        f"{name}: observed={observed}, expected={expected}"
        for name, (observed, expected) in exact_counts.items()
        if observed != expected
    ]
    if mismatches:
        raise ValueError(
            "Exact Shorts classification changed; zero VK writes performed: " + "; ".join(mismatches)
        )

    if ambiguous:
        raise ValueError("Ambiguous Shorts matches exist; zero VK writes performed")
    if len(matches) < args.minimum_matched:
        raise ValueError(
            f"Only {len(matches)} existing Shorts were matched; minimum authoritative coverage is {args.minimum_matched}; "
            "zero VK writes performed"
        )
    if len(extras) > args.maximum_extra_vertical:
        raise ValueError(
            f"Observed {len(extras)} unmatched vertical VK objects, above safety maximum {args.maximum_extra_vertical}; "
            "zero VK writes performed"
        )
    if not missing:
        print("No missing Shorts. Zero VK writes required.")
        return 0

    # Download and validate every missing source before any VK mutation.
    publications: dict[str, VkPublicationText] = {}
    media_paths: dict[str, Path] = {}
    media_reports: dict[str, MediaQualityReport] = {}
    for index, item in enumerate(missing, start=1):
        source_id = str(item["ref"]["remote_id"])
        print(f"Download/QC [{index}/{len(missing)}] {source_id} — {item['title']}")
        path = download_video(args.yt_dlp, source_id, args.cache_dir)
        quality = probe_media(path, ffprobe=args.ffprobe, timeout_seconds=180.0)
        if not quality.width or not quality.height or quality.height <= quality.width:
            raise ValueError(f"Source {source_id} is not vertical after download: {quality.width}x{quality.height}")
        audit_duration = int(item.get("duration_seconds") or 0)
        if abs(quality.duration_seconds - audit_duration) > 4.0:
            raise ValueError(
                f"Source {source_id} duration mismatch: audit={audit_duration}, file={quality.duration_seconds}"
            )
        publications[source_id] = render_vk_publication(str(item["title"]), str(item.get("description") or ""))
        media_paths[source_id] = path
        media_reports[source_id] = quality

    manifest = manifest_hash(missing, publications, media_reports)
    report["manifest_sha256"] = manifest
    report["media"] = {source_id: quality.to_dict() for source_id, quality in media_reports.items()}
    write_json(classification_path, report)
    print(f"  transfer manifest: {manifest}")

    if not args.execute:
        print("Dry-run only. All source files were downloaded and validated; zero VK writes performed.")
        return 0

    settings = get_settings()
    token_store = VkTokenStore(settings.data_dir)
    reader = VkApiClient(
        token_store=token_store,
        account_alias=args.account,
        api_version=settings.vk_api_version,
    )
    community = reader.get_community(str(args.community))
    live_community = int(community.ref.channel_id)
    if live_community != args.community:
        raise ValueError(f"Live VK community mismatch: {live_community}")
    if not bool(community.metadata.get("managed_by_token")):
        raise ValueError("Authorized VK user is not reported as administrator of the target community")

    journal = load_or_create_journal(
        args.journal,
        source_snapshot=source_snapshot,
        vk_snapshot=vk_snapshot,
        community=args.community,
        manifest=manifest,
        queue=missing,
    )
    uploads = journal["uploads"]
    writer = VkVideoWriter(
        token_store=token_store,
        account_alias=args.account,
        api_version=settings.vk_api_version,
    )

    # Shortest source is the canary. Remaining order follows publication date/title.
    queue = sorted(missing, key=lambda item: (int(item.get("duration_seconds") or 0), str(item["ref"]["remote_id"])))
    lock_path = settings.data_dir / "locks" / f"vk-{args.account}-{args.community}.lock"
    with local_vk_write_lock(
        lock_path,
        account=args.account,
        community_id=args.community,
        operation="legendary-poet-shorts-exact-sync",
    ):
        canary_confirmed = False
        for index, item in enumerate(queue, start=1):
            source_id = str(item["ref"]["remote_id"])
            publication = publications[source_id]
            existing = uploads.get(source_id)

            if isinstance(existing, dict) and isinstance(existing.get("remote_id"), str):
                remote_id = str(existing["remote_id"])
                owner_id, video_id = parse_remote_id(remote_id)
                live = writer.read_video(owner_id=owner_id, video_id=video_id)
                if live is None:
                    raise ValueError(f"Previously accepted VK object {remote_id} is not visible; refusing retransmission")
                if bool(live.get("processing")) or bool(live.get("converting")):
                    ticket = VkUploadTicket(owner_id=owner_id, video_id=video_id, upload_url="reconcile-only")
                    live = writer.wait_until_available(
                        ticket,
                        timeout_seconds=args.processing_timeout,
                        poll_seconds=args.poll_seconds,
                    )
                ensure_clip_type(live, remote_id)
                existing["status"] = "confirmed_short_video"
                existing["vk_type"] = live.get("type")
                existing["confirmed_at"] = datetime.now(UTC).isoformat()
                save_journal(args.journal, journal)
                print(f"[{index}/{len(queue)}] Reused confirmed {remote_id}")
                if index == 1:
                    canary_confirmed = True
                continue

            if index > 1 and not canary_confirmed:
                raise ValueError("Canary was not confirmed as short_video; batch stopped")

            print(f"[{index}/{len(queue)}] Uploading {source_id} — {publication.title}")
            ticket = begin_clip_upload(
                writer,
                community_id=args.community,
                title=publication.title,
                description=publication.description,
            )
            uploads[source_id] = {
                "source_id": source_id,
                "source_title": item["title"],
                "published_title": publication.title,
                "remote_id": ticket.remote_id,
                "status": "upload_reserved",
                "media": media_reports[source_id].to_dict(),
                "reserved_at": datetime.now(UTC).isoformat(),
                "wallpost": False,
                "auto_publish": False,
                "repeat": False,
            }
            save_journal(args.journal, journal)
            try:
                response = writer.upload_file(ticket, media_paths[source_id])
                uploads[source_id]["upload_response"] = response
                uploads[source_id]["status"] = "uploaded_processing"
                save_journal(args.journal, journal)
                live = writer.wait_until_available(
                    ticket,
                    timeout_seconds=args.processing_timeout,
                    poll_seconds=args.poll_seconds,
                )
                ensure_clip_type(live, ticket.remote_id)
            except BaseException as exc:
                uploads[source_id]["status"] = "stopped_needs_reconciliation"
                uploads[source_id]["error"] = f"{type(exc).__name__}: {exc}"
                uploads[source_id]["stopped_at"] = datetime.now(UTC).isoformat()
                save_journal(args.journal, journal)
                raise

            uploads[source_id]["status"] = "confirmed_short_video"
            uploads[source_id]["vk_type"] = live.get("type")
            uploads[source_id]["confirmed_at"] = datetime.now(UTC).isoformat()
            save_journal(args.journal, journal)
            print(f"[{index}/{len(queue)}] Verified https://vk.com/video{ticket.remote_id} type=short_video")
            if index == 1:
                canary_confirmed = True
                print("Canary confirmed as short_video; continuing exact missing batch.")
            if index < len(queue) and args.write_delay > 0:
                time.sleep(args.write_delay)

    print(f"Completed: {len(queue)} exact missing Shorts confirmed as VK short_video.")
    print(f"Journal: {args.journal}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, MediaQualityError, VkWriteError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
```

## 002. Initial PowerShell launcher V1

- Original: `run-legendary-poet-shorts-sync.ps1`
- SHA-256: `859c0704cee50cf93921b39d15d984460dff179e097851c2b738fd69b54b3465`

```powershell
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$YouTubeAudit = ".\data\exports\youtube-legendary-poet-current.json"
$VkAudit      = ".\data\exports\vk-legendary-poet-after-full.json"
$CacheDir    = ".\data\cache\legendary-poet-shorts-exact"
$ReportDir   = ".\data\reports\legendary-poet-shorts-exact"
$Journal     = ".\data\reports\legendary-poet-shorts-exact-journal.json"
$Script      = Join-Path $PSScriptRoot "legendary_poet_shorts_sync.py"

foreach ($Required in @($YouTubeAudit, $VkAudit, $Script)) {
    if (-not (Test-Path -LiteralPath $Required)) {
        throw "Не найден обязательный файл: $Required"
    }
}

python $Script `
    --youtube-audit $YouTubeAudit `
    --vk-audit $VkAudit `
    --account legendary-poet `
    --community 235216998 `
    --shorts-url "https://www.youtube.com/channel/UC-78ys2S3cQ3lpqgXfo-SvQ/shorts" `
    --cache-dir $CacheDir `
    --report-dir $ReportDir `
    --journal $Journal `
    --minimum-matched 40 `
    --maximum-extra-vertical 1 `
    --expected-shorts-count 59 `
    --expected-matched-count 40 `
    --expected-missing-count 19 `
    --expected-extra-vertical-count 1 `
    --expected-ambiguous-count 0 `
    --expected-source-snapshot 251142b8-5541-4baf-9a35-ed8787ff0af4 `
    --expected-vk-snapshot 2461c5ee-0154-464d-8510-e9c486438df0 `
    --execute

if ($LASTEXITCODE -ne 0) {
    throw "Синхронизация остановлена защитой. Смотрите отчёт: $ReportDir"
}
```

## 003. Fresh-audit Shorts sync V2

- Original: `legendary_poet_shorts_sync.py`
- SHA-256: `b56a67dd621ce8d1e0d6abce07ee349fae8a07d0789c935b06e83413c265c371`

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

ROOT = Path.cwd()
SRC = ROOT / "src"
if SRC.is_dir():
    sys.path.insert(0, str(SRC))

from video_channel_manager.config import get_settings
from video_channel_manager.local_media.quality import MediaQualityError, MediaQualityReport, probe_media
from video_channel_manager.platforms.vk import VkApiClient, VkTokenStore
from video_channel_manager.platforms.vk.lock import local_vk_write_lock
from video_channel_manager.platforms.vk.publishing import VkPublicationText, render_vk_publication
from video_channel_manager.platforms.vk.writer import VkUploadTicket, VkVideoWriter, VkWriteError

BRAND_RE = re.compile(r"@thelegendarypoet|#thelegendarypoet|#theepicpoet|#shorts", re.I)
NON_WORD_RE = re.compile(r"[^a-zа-я0-9]+", re.I)
SPACE_RE = re.compile(r"\s+")
VERSION_RE = re.compile(r"\b(?:версия|version)\s*[-–—:]?\s*(\d+)\b", re.I)
STYLE_GROUPS = {
    "rock": ("рок", "rock"),
    "dj": ("dj", "диджей"),
    "reggae": ("регги", "reggae"),
    "nordic_folk": ("nordic folk", "скандинав"),
    "english": ("english", "англий"),
    "dramatic": ("драмат", "dramatic"),
    "cinematic": ("кинематограф", "cinematic"),
}
CORE_STOPWORDS = frozenset(
    """
    александр александрович сергеевич пушкин сергей есенин владимир маяковский
    михаил юрьевич лермонтов валерий брюсов анна ахматова константин симонов
    афанасий фет николай некрасов борис пастернак блок the legendary poet epic
    shorts version версия короткая короткий фрагмент полная полный стихотворения
    cover suno ai english русский русская песня стих поэт поэта style стиле вариант
    """.split()
)


@dataclass(frozen=True)
class Match:
    source_id: str
    source_title: str
    source_duration: int
    target_id: str
    target_title: str
    target_duration: int
    score: float
    duration_delta: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Exact guarded YouTube Shorts to VK Clips synchronization.")
    parser.add_argument("--youtube-audit", type=Path, required=True)
    parser.add_argument("--vk-audit", type=Path, required=True)
    parser.add_argument("--account", default="legendary-poet")
    parser.add_argument("--community", type=int, required=True)
    parser.add_argument("--shorts-url", required=True)
    parser.add_argument("--expected-youtube-channel-id", required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--yt-dlp", default="yt-dlp")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--processing-timeout", type=int, default=7200)
    parser.add_argument("--poll-seconds", type=float, default=10.0)
    parser.add_argument("--write-delay", type=float, default=3.0)
    parser.add_argument("--minimum-matched", type=int, default=38)
    parser.add_argument("--maximum-extra-vertical", type=int, default=2)
    parser.add_argument("--expected-shorts-count", type=int, required=True)
    parser.add_argument("--expected-matched-count", type=int, required=True)
    parser.add_argument("--expected-missing-count", type=int, required=True)
    parser.add_argument("--expected-extra-vertical-count", type=int, required=True)
    parser.add_argument("--expected-ambiguous-count", type=int, default=0)
    parser.add_argument("--expected-source-snapshot", required=True)
    parser.add_argument("--expected-vk-snapshot", required=True)
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def normalize(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "").casefold().replace("ё", "е")
    text = BRAND_RE.sub(" ", text)
    text = text.replace("version", "версия")
    text = NON_WORD_RE.sub(" ", text)
    return SPACE_RE.sub(" ", text).strip()


def version_numbers(value: str) -> frozenset[int]:
    return frozenset(int(match.group(1)) for match in VERSION_RE.finditer(normalize(value)))


def style_signature(value: str) -> frozenset[str]:
    text = normalize(value)
    found = set()
    for key, needles in STYLE_GROUPS.items():
        if any(needle in text for needle in needles):
            found.add(key)
    return frozenset(found)


def title_similarity(left: str, right: str) -> float:
    a = normalize(left)
    b = normalize(right)
    sequence = SequenceMatcher(None, a, b).ratio()
    at = set(a.split())
    bt = set(b.split())
    union = at | bt
    inter = at & bt
    jaccard = len(inter) / len(union) if union else 1.0
    containment = len(inter) / min(len(at), len(bt)) if at and bt else 1.0
    return sequence * 0.55 + jaccard * 0.30 + containment * 0.15


def core_tokens(value: str) -> frozenset[str]:
    return frozenset(
        token
        for token in normalize(value).split()
        if len(token) >= 3 and token not in CORE_STOPWORDS and not token.isdigit()
    )


def compatible(source: dict[str, Any], target: dict[str, Any]) -> tuple[bool, float, int]:
    source_duration = int(source.get("duration_seconds") or 0)
    target_duration = int(target.get("duration_seconds") or 0)
    delta = abs(source_duration - target_duration)
    if delta > 3:
        return False, 0.0, delta

    source_versions = version_numbers(str(source.get("title") or ""))
    target_versions = version_numbers(str(target.get("title") or ""))
    if source_versions != target_versions:
        return False, 0.0, delta

    source_title = str(source.get("title") or "")
    target_title = str(target.get("title") or "")
    source_core = core_tokens(source_title)
    target_core = core_tokens(target_title)
    shared_core = source_core & target_core
    if not shared_core:
        return False, 0.0, delta

    source_styles = style_signature(source_title)
    target_styles = style_signature(target_title)
    if source_styles and target_styles and source_styles.isdisjoint(target_styles):
        return False, 0.0, delta

    broad = title_similarity(source_title, target_title)
    core_union = source_core | target_core
    core_jaccard = len(shared_core) / len(core_union) if core_union else 1.0
    core_containment = len(shared_core) / min(len(source_core), len(target_core))
    score = broad * 0.50 + core_jaccard * 0.30 + core_containment * 0.20
    if score < 0.35:
        return False, score, delta
    score += 0.25 if delta <= 1 else 0.15
    return True, round(score, 6), delta


def enumerate_shorts(yt_dlp: str, url: str, output: Path) -> list[str]:
    command = [yt_dlp, "--flat-playlist", "--dump-single-json", "--no-warnings", url]
    try:
        completed = subprocess.run(command, capture_output=True, check=False, timeout=300)
    except FileNotFoundError as exc:
        raise ValueError(f"yt-dlp not found: {yt_dlp}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError("YouTube Shorts enumeration timed out") from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace")[-4000:]
        raise ValueError(f"yt-dlp Shorts enumeration failed: {detail}")
    text = completed.stdout.decode("utf-8", errors="strict")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("yt-dlp returned invalid Shorts JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("entries"), list):
        raise ValueError("yt-dlp Shorts result has no entries list")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result: list[str] = []
    seen: set[str] = set()
    for entry in payload["entries"]:
        if not isinstance(entry, dict):
            continue
        video_id = str(entry.get("id") or entry.get("url") or "").strip()
        if not video_id or video_id in seen:
            continue
        seen.add(video_id)
        result.append(video_id)
    if not result:
        raise ValueError("YouTube Shorts enumeration returned zero IDs")
    return result



def hydrate_short_metadata(yt_dlp: str, video_id: str, expected_channel_id: str) -> dict[str, Any]:
    command = [
        yt_dlp,
        "--dump-single-json",
        "--no-playlist",
        "--no-warnings",
        f"https://www.youtube.com/watch?v={video_id}",
    ]
    try:
        completed = subprocess.run(command, capture_output=True, check=False, timeout=300)
    except FileNotFoundError as exc:
        raise ValueError(f"yt-dlp not found: {yt_dlp}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f"Timed out hydrating missing Shorts ID {video_id}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace")[-4000:]
        raise ValueError(f"Cannot hydrate missing Shorts ID {video_id}: {detail}")
    try:
        payload = json.loads(completed.stdout.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"yt-dlp returned invalid metadata JSON for {video_id}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"yt-dlp returned non-object metadata for {video_id}")

    observed_id = str(payload.get("id") or "").strip()
    if observed_id != video_id:
        raise ValueError(f"Hydrated ID mismatch: expected {video_id}, observed {observed_id!r}")
    observed_channel = str(payload.get("channel_id") or payload.get("uploader_id") or "").strip()
    if observed_channel != expected_channel_id:
        raise ValueError(
            f"Hydrated Short {video_id} belongs to channel {observed_channel!r}, expected {expected_channel_id}"
        )
    title = str(payload.get("title") or "").strip()
    if not title:
        raise ValueError(f"Hydrated Short {video_id} has no title")
    try:
        duration = int(round(float(payload.get("duration") or 0)))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Hydrated Short {video_id} has invalid duration") from exc
    if duration <= 0 or duration > 180:
        raise ValueError(f"Hydrated Short {video_id} has unsupported duration {duration}s")

    availability = str(payload.get("availability") or "public").strip().casefold()
    if availability not in {"public", "unlisted"}:
        raise ValueError(f"Hydrated Short {video_id} is not publicly downloadable: availability={availability!r}")

    timestamp = payload.get("timestamp") or payload.get("release_timestamp")
    published_at = None
    if isinstance(timestamp, (int, float)) and timestamp > 0:
        published_at = datetime.fromtimestamp(float(timestamp), UTC).isoformat().replace("+00:00", "Z")
    upload_date = str(payload.get("upload_date") or "").strip()
    if published_at is None and len(upload_date) == 8 and upload_date.isdigit():
        published_at = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}T00:00:00Z"

    return {
        "ref": {
            "platform": "youtube",
            "channel_id": expected_channel_id,
            "remote_id": video_id,
        },
        "title": title,
        "description": str(payload.get("description") or ""),
        "duration_seconds": duration,
        "published_at": published_at,
        "privacy_status": "public",
        "tags": [str(item) for item in (payload.get("tags") or []) if isinstance(item, str)],
        "thumbnail_url": str(payload.get("thumbnail") or "").strip() or None,
        "revision": None,
        "metadata": {
            "source": "yt-dlp-live-hydration",
            "webpage_url": str(payload.get("webpage_url") or f"https://www.youtube.com/watch?v={video_id}"),
            "availability": availability,
            "width": payload.get("width"),
            "height": payload.get("height"),
            "live_status": payload.get("live_status"),
        },
    }

def classify(shorts: list[dict[str, Any]], vk_videos: list[dict[str, Any]]) -> tuple[list[Match], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    vertical = [
        item
        for item in vk_videos
        if int(item.get("metadata", {}).get("height") or 0) > int(item.get("metadata", {}).get("width") or 0)
    ]
    candidates: list[tuple[float, int, int, int]] = []
    per_source: dict[int, list[tuple[float, int]]] = {}
    per_target: dict[int, list[tuple[float, int]]] = {}
    for si, source in enumerate(shorts):
        for ti, target in enumerate(vertical):
            ok, score, delta = compatible(source, target)
            if not ok:
                continue
            candidates.append((score, si, ti, delta))
            per_source.setdefault(si, []).append((score, ti))
            per_target.setdefault(ti, []).append((score, si))

    ambiguous: list[dict[str, Any]] = []
    blocked_source: set[int] = set()
    blocked_target: set[int] = set()
    for si, values in per_source.items():
        ranked = sorted(values, reverse=True)
        if len(ranked) > 1 and ranked[0][0] - ranked[1][0] <= 0.02:
            blocked_source.add(si)
            ambiguous.append({
                "kind": "source",
                "source_id": shorts[si]["ref"]["remote_id"],
                "source_title": shorts[si]["title"],
                "candidate_target_ids": [vertical[ti]["ref"]["remote_id"] for _, ti in ranked[:3]],
            })
    for ti, values in per_target.items():
        ranked = sorted(values, reverse=True)
        if len(ranked) > 1 and ranked[0][0] - ranked[1][0] <= 0.02:
            blocked_target.add(ti)
            ambiguous.append({
                "kind": "target",
                "target_id": vertical[ti]["ref"]["remote_id"],
                "target_title": vertical[ti]["title"],
                "candidate_source_ids": [shorts[si]["ref"]["remote_id"] for _, si in ranked[:3]],
            })

    candidates.sort(key=lambda row: (-row[0], row[1], row[2]))
    used_source: set[int] = set()
    used_target: set[int] = set()
    matches: list[Match] = []
    for score, si, ti, delta in candidates:
        if si in blocked_source or ti in blocked_target or si in used_source or ti in used_target:
            continue
        source = shorts[si]
        target = vertical[ti]
        used_source.add(si)
        used_target.add(ti)
        matches.append(Match(
            source_id=str(source["ref"]["remote_id"]),
            source_title=str(source["title"]),
            source_duration=int(source.get("duration_seconds") or 0),
            target_id=str(target["ref"]["remote_id"]),
            target_title=str(target["title"]),
            target_duration=int(target.get("duration_seconds") or 0),
            score=score,
            duration_delta=delta,
        ))

    missing = [source for si, source in enumerate(shorts) if si not in used_source and si not in blocked_source]
    extras = [target for ti, target in enumerate(vertical) if ti not in used_target and ti not in blocked_target]
    return matches, missing, extras, ambiguous


def download_video(yt_dlp: str, video_id: str, cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    exact = cache_dir / f"{video_id}.mp4"
    if exact.is_file() and exact.stat().st_size > 0:
        return exact
    command = [
        yt_dlp,
        "--no-playlist",
        "--no-progress",
        "--newline",
        "--merge-output-format", "mp4",
        "--remux-video", "mp4",
        "--format", "bv*+ba/b",
        "--output", str(cache_dir / f"{video_id}.%(ext)s"),
        f"https://www.youtube.com/watch?v={video_id}",
    ]
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise ValueError(f"yt-dlp failed before any VK upload for {video_id}")
    if not exact.is_file() or exact.stat().st_size <= 0:
        candidates = sorted(cache_dir.glob(f"{video_id}*.mp4"))
        if not candidates:
            raise ValueError(f"Downloaded MP4 not found for {video_id}")
        exact = candidates[0]
    return exact


def manifest_hash(queue: list[dict[str, Any]], publications: dict[str, VkPublicationText], reports: dict[str, MediaQualityReport]) -> str:
    payload = []
    for item in queue:
        source_id = str(item["ref"]["remote_id"])
        report = reports[source_id]
        publication = publications[source_id]
        payload.append({
            "source_id": source_id,
            "source_title": item["title"],
            "source_duration": item.get("duration_seconds"),
            "published_title": publication.title,
            "description_sha256": publication.description_sha256,
            "media_sha256": report.sha256,
            "media_size_bytes": report.size_bytes,
            "media_duration_seconds": report.duration_seconds,
            "width": report.width,
            "height": report.height,
        })
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def begin_clip_upload(writer: VkVideoWriter, *, community_id: int, title: str, description: str) -> VkUploadTicket:
    response = writer._call(  # Deliberately use exact video.save flags absent from the older wrapper.
        "video.save",
        params={
            "group_id": community_id,
            "name": title.strip(),
            "description": description,
            "wallpost": False,
            "auto_publish": False,
            "repeat": False,
            "is_private": False,
            "no_comments": False,
        },
    )
    if not isinstance(response, dict):
        raise VkWriteError("video.save returned a non-object response", method="video.save")
    owner_id = response.get("owner_id")
    video_id = response.get("video_id")
    upload_url = response.get("upload_url")
    if owner_id != -community_id or not isinstance(video_id, int) or video_id <= 0 or not isinstance(upload_url, str):
        raise VkWriteError("video.save returned an invalid clip upload ticket", method="video.save")
    return VkUploadTicket(owner_id=owner_id, video_id=video_id, upload_url=upload_url)


def parse_remote_id(value: str) -> tuple[int, int]:
    owner, sep, video = value.partition("_")
    if not sep:
        raise ValueError(f"Invalid VK remote ID: {value}")
    return int(owner), int(video)


def load_or_create_journal(path: Path, *, source_snapshot: str, vk_snapshot: str, community: int, manifest: str, queue: list[dict[str, Any]]) -> dict[str, Any]:
    if path.exists():
        journal = read_json(path)
        expected = (source_snapshot, vk_snapshot, community, manifest)
        actual = (
            str(journal.get("source_snapshot_id")),
            str(journal.get("vk_snapshot_id")),
            int(journal.get("community_id") or 0),
            str(journal.get("manifest_sha256")),
        )
        if actual != expected:
            raise ValueError("Existing Shorts journal belongs to another snapshots/manifest/community")
        return journal
    now = datetime.now(UTC).isoformat()
    journal = {
        "schema_name": "video-manager.legendary-poet-shorts-journal",
        "schema_version": 1,
        "created_at": now,
        "updated_at": now,
        "source_snapshot_id": source_snapshot,
        "vk_snapshot_id": vk_snapshot,
        "community_id": community,
        "manifest_sha256": manifest,
        "wall_mutation_authorized": False,
        "queue": [str(item["ref"]["remote_id"]) for item in queue],
        "uploads": {},
    }
    write_json(path, journal)
    return journal


def save_journal(path: Path, journal: dict[str, Any]) -> None:
    journal["updated_at"] = datetime.now(UTC).isoformat()
    write_json(path, journal)


def ensure_clip_type(item: dict[str, Any], remote_id: str) -> None:
    observed = str(item.get("type") or "")
    if observed != "short_video":
        raise ValueError(f"VK object {remote_id} completed with type={observed!r}, expected 'short_video'")


def main() -> int:
    args = parse_args()
    youtube = read_json(args.youtube_audit)
    vk = read_json(args.vk_audit)
    source_snapshot = str(youtube.get("snapshot_id") or "")
    vk_snapshot = str(vk.get("snapshot_id") or "")
    if source_snapshot != args.expected_source_snapshot:
        raise ValueError(f"YouTube snapshot mismatch: {source_snapshot}")
    if vk_snapshot != args.expected_vk_snapshot:
        raise ValueError(f"VK snapshot mismatch: {vk_snapshot}")

    raw_youtube_videos = youtube.get("videos")
    raw_vk_videos = vk.get("videos")
    if not isinstance(raw_youtube_videos, list) or not isinstance(raw_vk_videos, list):
        raise ValueError("Audit videos must be lists")

    youtube_by_id: dict[str, dict[str, Any]] = {}
    duplicate_source_ids: list[str] = []
    for item in raw_youtube_videos:
        if not isinstance(item, dict):
            continue
        ref = item.get("ref")
        source_id = str(ref.get("remote_id") or "") if isinstance(ref, dict) else ""
        if not source_id:
            continue
        if source_id in youtube_by_id:
            duplicate_source_ids.append(source_id)
            continue
        youtube_by_id[source_id] = item

    args.report_dir.mkdir(parents=True, exist_ok=True)
    shorts_json = args.report_dir / "legendary-poet-youtube-shorts-flat.json"
    shorts_ids = enumerate_shorts(args.yt_dlp, args.shorts_url, shorts_json)
    missing_from_audit = [source_id for source_id in shorts_ids if source_id not in youtube_by_id]
    hydrated_source_ids: list[str] = []
    for source_id in missing_from_audit:
        print(f"Hydrating exact Shorts ID absent from fresh YouTube audit: {source_id}")
        youtube_by_id[source_id] = hydrate_short_metadata(
            args.yt_dlp,
            source_id,
            args.expected_youtube_channel_id,
        )
        hydrated_source_ids.append(source_id)
    shorts = [youtube_by_id[source_id] for source_id in shorts_ids]

    matches, missing, extras, ambiguous = classify(shorts, [item for item in raw_vk_videos if isinstance(item, dict)])
    report = {
        "schema_name": "video-manager.legendary-poet-shorts-classification",
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "source_snapshot_id": source_snapshot,
        "vk_snapshot_id": vk_snapshot,
        "youtube_short_count": len(shorts),
        "vk_video_count": len(raw_vk_videos),
        "vk_vertical_count": sum(
            int(item.get("metadata", {}).get("height") or 0) > int(item.get("metadata", {}).get("width") or 0)
            for item in raw_vk_videos if isinstance(item, dict)
        ),
        "duplicate_source_ids_in_audit": sorted(set(duplicate_source_ids)),
        "shorts_ids_absent_from_fresh_audit": missing_from_audit,
        "live_hydrated_source_ids": hydrated_source_ids,
        "matched_count": len(matches),
        "confirmed_missing_count": len(missing),
        "extra_vertical_vk_count": len(extras),
        "ambiguous_count": len(ambiguous),
        "matches": [match.__dict__ for match in matches],
        "confirmed_missing": [
            {
                "source_id": item["ref"]["remote_id"],
                "title": item["title"],
                "duration_seconds": item.get("duration_seconds"),
                "published_at": item.get("published_at"),
            }
            for item in missing
        ],
        "extra_vertical_vk": [
            {
                "target_id": item["ref"]["remote_id"],
                "title": item["title"],
                "duration_seconds": item.get("duration_seconds"),
                "width": item.get("metadata", {}).get("width"),
                "height": item.get("metadata", {}).get("height"),
            }
            for item in extras
        ],
        "ambiguous": ambiguous,
    }
    classification_path = args.report_dir / "legendary-poet-shorts-classification.json"
    write_json(classification_path, report)

    print("Legendary Poet Shorts classification:")
    print(f"  exact YouTube Shorts IDs: {len(shorts)}")
    print(f"  matched to vertical VK objects: {len(matches)}")
    print(f"  confirmed missing: {len(missing)}")
    print(f"  extra vertical VK objects: {len(extras)}")
    print(f"  ambiguous: {len(ambiguous)}")
    print(f"  duplicate source IDs in audit: {sorted(set(duplicate_source_ids))}")
    print(f"  exact IDs hydrated live: {hydrated_source_ids}")
    print(f"  report: {classification_path}")

    exact_counts = {
        "youtube_short_count": (len(shorts), args.expected_shorts_count),
        "matched_count": (len(matches), args.expected_matched_count),
        "confirmed_missing_count": (len(missing), args.expected_missing_count),
        "extra_vertical_vk_count": (len(extras), args.expected_extra_vertical_count),
        "ambiguous_count": (len(ambiguous), args.expected_ambiguous_count),
    }
    mismatches = [
        f"{name}: observed={observed}, expected={expected}"
        for name, (observed, expected) in exact_counts.items()
        if observed != expected
    ]
    if mismatches:
        raise ValueError(
            "Exact Shorts classification changed; zero VK writes performed: " + "; ".join(mismatches)
        )

    if ambiguous:
        raise ValueError("Ambiguous Shorts matches exist; zero VK writes performed")
    if len(matches) < args.minimum_matched:
        raise ValueError(
            f"Only {len(matches)} existing Shorts were matched; minimum authoritative coverage is {args.minimum_matched}; "
            "zero VK writes performed"
        )
    if len(extras) > args.maximum_extra_vertical:
        raise ValueError(
            f"Observed {len(extras)} unmatched vertical VK objects, above safety maximum {args.maximum_extra_vertical}; "
            "zero VK writes performed"
        )
    if not missing:
        print("No missing Shorts. Zero VK writes required.")
        return 0

    # Download and validate every missing source before any VK mutation.
    publications: dict[str, VkPublicationText] = {}
    media_paths: dict[str, Path] = {}
    media_reports: dict[str, MediaQualityReport] = {}
    for index, item in enumerate(missing, start=1):
        source_id = str(item["ref"]["remote_id"])
        print(f"Download/QC [{index}/{len(missing)}] {source_id} — {item['title']}")
        path = download_video(args.yt_dlp, source_id, args.cache_dir)
        quality = probe_media(path, ffprobe=args.ffprobe, timeout_seconds=180.0)
        if not quality.width or not quality.height or quality.height <= quality.width:
            raise ValueError(f"Source {source_id} is not vertical after download: {quality.width}x{quality.height}")
        audit_duration = int(item.get("duration_seconds") or 0)
        if abs(quality.duration_seconds - audit_duration) > 4.0:
            raise ValueError(
                f"Source {source_id} duration mismatch: audit={audit_duration}, file={quality.duration_seconds}"
            )
        publications[source_id] = render_vk_publication(str(item["title"]), str(item.get("description") or ""))
        media_paths[source_id] = path
        media_reports[source_id] = quality

    manifest = manifest_hash(missing, publications, media_reports)
    report["manifest_sha256"] = manifest
    report["media"] = {source_id: quality.to_dict() for source_id, quality in media_reports.items()}
    write_json(classification_path, report)
    print(f"  transfer manifest: {manifest}")

    if not args.execute:
        print("Dry-run only. All source files were downloaded and validated; zero VK writes performed.")
        return 0

    settings = get_settings()
    token_store = VkTokenStore(settings.data_dir)
    reader = VkApiClient(
        token_store=token_store,
        account_alias=args.account,
        api_version=settings.vk_api_version,
    )
    community = reader.get_community(str(args.community))
    live_community = int(community.ref.channel_id)
    if live_community != args.community:
        raise ValueError(f"Live VK community mismatch: {live_community}")
    if not bool(community.metadata.get("managed_by_token")):
        raise ValueError("Authorized VK user is not reported as administrator of the target community")

    journal = load_or_create_journal(
        args.journal,
        source_snapshot=source_snapshot,
        vk_snapshot=vk_snapshot,
        community=args.community,
        manifest=manifest,
        queue=missing,
    )
    uploads = journal["uploads"]
    writer = VkVideoWriter(
        token_store=token_store,
        account_alias=args.account,
        api_version=settings.vk_api_version,
    )

    # Shortest source is the canary. Remaining order follows publication date/title.
    queue = sorted(missing, key=lambda item: (int(item.get("duration_seconds") or 0), str(item["ref"]["remote_id"])))
    lock_path = settings.data_dir / "locks" / f"vk-{args.account}-{args.community}.lock"
    with local_vk_write_lock(
        lock_path,
        account=args.account,
        community_id=args.community,
        operation="legendary-poet-shorts-exact-sync",
    ):
        canary_confirmed = False
        for index, item in enumerate(queue, start=1):
            source_id = str(item["ref"]["remote_id"])
            publication = publications[source_id]
            existing = uploads.get(source_id)

            if isinstance(existing, dict) and isinstance(existing.get("remote_id"), str):
                remote_id = str(existing["remote_id"])
                owner_id, video_id = parse_remote_id(remote_id)
                live = writer.read_video(owner_id=owner_id, video_id=video_id)
                if live is None:
                    raise ValueError(f"Previously accepted VK object {remote_id} is not visible; refusing retransmission")
                if bool(live.get("processing")) or bool(live.get("converting")):
                    ticket = VkUploadTicket(owner_id=owner_id, video_id=video_id, upload_url="reconcile-only")
                    live = writer.wait_until_available(
                        ticket,
                        timeout_seconds=args.processing_timeout,
                        poll_seconds=args.poll_seconds,
                    )
                ensure_clip_type(live, remote_id)
                existing["status"] = "confirmed_short_video"
                existing["vk_type"] = live.get("type")
                existing["confirmed_at"] = datetime.now(UTC).isoformat()
                save_journal(args.journal, journal)
                print(f"[{index}/{len(queue)}] Reused confirmed {remote_id}")
                if index == 1:
                    canary_confirmed = True
                continue

            if index > 1 and not canary_confirmed:
                raise ValueError("Canary was not confirmed as short_video; batch stopped")

            print(f"[{index}/{len(queue)}] Uploading {source_id} — {publication.title}")
            ticket = begin_clip_upload(
                writer,
                community_id=args.community,
                title=publication.title,
                description=publication.description,
            )
            uploads[source_id] = {
                "source_id": source_id,
                "source_title": item["title"],
                "published_title": publication.title,
                "remote_id": ticket.remote_id,
                "status": "upload_reserved",
                "media": media_reports[source_id].to_dict(),
                "reserved_at": datetime.now(UTC).isoformat(),
                "wallpost": False,
                "auto_publish": False,
                "repeat": False,
            }
            save_journal(args.journal, journal)
            try:
                response = writer.upload_file(ticket, media_paths[source_id])
                uploads[source_id]["upload_response"] = response
                uploads[source_id]["status"] = "uploaded_processing"
                save_journal(args.journal, journal)
                live = writer.wait_until_available(
                    ticket,
                    timeout_seconds=args.processing_timeout,
                    poll_seconds=args.poll_seconds,
                )
                ensure_clip_type(live, ticket.remote_id)
            except BaseException as exc:
                uploads[source_id]["status"] = "stopped_needs_reconciliation"
                uploads[source_id]["error"] = f"{type(exc).__name__}: {exc}"
                uploads[source_id]["stopped_at"] = datetime.now(UTC).isoformat()
                save_journal(args.journal, journal)
                raise

            uploads[source_id]["status"] = "confirmed_short_video"
            uploads[source_id]["vk_type"] = live.get("type")
            uploads[source_id]["confirmed_at"] = datetime.now(UTC).isoformat()
            save_journal(args.journal, journal)
            print(f"[{index}/{len(queue)}] Verified https://vk.com/video{ticket.remote_id} type=short_video")
            if index == 1:
                canary_confirmed = True
                print("Canary confirmed as short_video; continuing exact missing batch.")
            if index < len(queue) and args.write_delay > 0:
                time.sleep(args.write_delay)

    print(f"Completed: {len(queue)} exact missing Shorts confirmed as VK short_video.")
    print(f"Journal: {args.journal}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, MediaQualityError, VkWriteError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
```

## 004. Fresh-audit PowerShell launcher V2

- Original: `run-legendary-poet-shorts-sync.ps1`
- SHA-256: `f69d6009ec2507837d9b30dd63974e98fd60a70fa42f002898f9e8e53f8559da`

```powershell
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$YouTubeAudit = ".\data\exports\youtube-legendary-poet-current.json"
$VkAudit      = ".\data\exports\vk-legendary-poet-after-full.json"
$CacheDir    = ".\data\cache\legendary-poet-shorts-exact"
$ReportDir   = ".\data\reports\legendary-poet-shorts-exact"
$Journal     = ".\data\reports\legendary-poet-shorts-exact-journal.json"
$Script      = Join-Path $PSScriptRoot "legendary_poet_shorts_sync.py"
$ChannelId   = "UC-78ys2S3cQ3lpqgXfo-SvQ"
$CommunityId = 235216998

if (-not (Test-Path -LiteralPath $Script)) {
    throw "Не найден скрипт пакета: $Script"
}

Write-Host "`n========== ОБНОВЛЕНИЕ YOUTUBE-АУДИТА ==========" -ForegroundColor Cyan
video-manager youtube scan `
    --account legendary-poet `
    --channel $ChannelId `
    --output $YouTubeAudit
if ($LASTEXITCODE -ne 0) {
    throw "Не удалось обновить YouTube-аудит. VK не изменён."
}

Write-Host "`n========== ОБНОВЛЕНИЕ VK-АУДИТА ==========" -ForegroundColor Cyan
video-manager vk scan `
    --account legendary-poet `
    --community $CommunityId `
    --output $VkAudit
if ($LASTEXITCODE -ne 0) {
    throw "Не удалось обновить VK-аудит. VK не изменён."
}

$YouTubeSnapshot = [string]((Get-Content -LiteralPath $YouTubeAudit -Raw | ConvertFrom-Json -Depth 100).snapshot_id)
$VkSnapshot      = [string]((Get-Content -LiteralPath $VkAudit -Raw | ConvertFrom-Json -Depth 100).snapshot_id)

if ([string]::IsNullOrWhiteSpace($YouTubeSnapshot)) {
    throw "Свежий YouTube-аудит не содержит snapshot_id."
}
if ([string]::IsNullOrWhiteSpace($VkSnapshot)) {
    throw "Свежий VK-аудит не содержит snapshot_id."
}

Write-Host "YouTube snapshot: $YouTubeSnapshot" -ForegroundColor Green
Write-Host "VK snapshot:      $VkSnapshot" -ForegroundColor Green

# Старый незавершённый журнал относится к другой паре снимков и не должен
# блокировать новый точный запуск. Удаляем только если в нём нет VK remote_id.
if (Test-Path -LiteralPath $Journal) {
    $OldJournal = Get-Content -LiteralPath $Journal -Raw | ConvertFrom-Json -Depth 100
    $RemoteIds = @(
        $OldJournal.uploads.PSObject.Properties |
            ForEach-Object { [string]$_.Value.remote_id } |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    )
    if ($RemoteIds.Count -gt 0) {
        throw "В существующем Shorts-журнале уже есть VK ID. Автоматическая замена запрещена: $Journal"
    }
    Remove-Item -LiteralPath $Journal -Force
}

Write-Host "`n========== ТОЧНАЯ СВЕРКА И ПЕРЕНОС ==========" -ForegroundColor Cyan
python $Script `
    --youtube-audit $YouTubeAudit `
    --vk-audit $VkAudit `
    --account legendary-poet `
    --community $CommunityId `
    --shorts-url "https://www.youtube.com/channel/$ChannelId/shorts" `
    --expected-youtube-channel-id $ChannelId `
    --cache-dir $CacheDir `
    --report-dir $ReportDir `
    --journal $Journal `
    --minimum-matched 40 `
    --maximum-extra-vertical 1 `
    --expected-shorts-count 59 `
    --expected-matched-count 40 `
    --expected-missing-count 19 `
    --expected-extra-vertical-count 1 `
    --expected-ambiguous-count 0 `
    --expected-source-snapshot $YouTubeSnapshot `
    --expected-vk-snapshot $VkSnapshot `
    --execute

if ($LASTEXITCODE -ne 0) {
    throw "Синхронизация остановлена защитой. Смотрите отчёт: $ReportDir"
}
```
