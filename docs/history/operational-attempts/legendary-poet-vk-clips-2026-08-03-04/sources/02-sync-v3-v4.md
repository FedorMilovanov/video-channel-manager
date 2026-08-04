# Historical source snapshots

> Non-executable evidence only. Do not copy or run without a new reviewed design and tests.

## 005. Reviewed exact-map Shorts sync V3

- Original: `legendary_poet_shorts_sync.py`
- SHA-256: `1461932a42e571b5269a102460f70134222d72e0898b7d1e99c5b0ec4906bf26`

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
from datetime import UTC, datetime
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reviewed exact YouTube Shorts to VK synchronization.")
    parser.add_argument("--youtube-audit", type=Path, required=True)
    parser.add_argument("--vk-audit", type=Path, required=True)
    parser.add_argument("--review-map", type=Path, required=True)
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


def canonical_sha256(payload: dict[str, Any], *, omit_key: str | None = None) -> str:
    body = dict(payload)
    if omit_key is not None:
        body.pop(omit_key, None)
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def normalize(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "").casefold().replace("ё", "е")
    text = BRAND_RE.sub(" ", text).replace("version", "версия")
    text = NON_WORD_RE.sub(" ", text)
    return SPACE_RE.sub(" ", text).strip()


def version_numbers(value: str) -> frozenset[int]:
    return frozenset(int(match.group(1)) for match in VERSION_RE.finditer(normalize(value)))


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
    try:
        payload = json.loads(completed.stdout.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
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
        if video_id and video_id not in seen:
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
        raise ValueError(f"Timed out hydrating Shorts ID {video_id}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace")[-4000:]
        raise ValueError(f"Cannot hydrate Shorts ID {video_id}: {detail}")
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
    timestamp = payload.get("timestamp") or payload.get("release_timestamp")
    published_at = None
    if isinstance(timestamp, (int, float)) and timestamp > 0:
        published_at = datetime.fromtimestamp(float(timestamp), UTC).isoformat().replace("+00:00", "Z")
    return {
        "ref": {"platform": "youtube", "channel_id": expected_channel_id, "remote_id": video_id},
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
            "width": payload.get("width"),
            "height": payload.get("height"),
        },
    }


def source_map(audit: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    raw = audit.get("videos")
    if not isinstance(raw, list):
        raise ValueError("YouTube audit videos must be a list")
    result: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        ref = item.get("ref")
        source_id = str(ref.get("remote_id") or "") if isinstance(ref, dict) else ""
        if not source_id:
            continue
        if source_id in result:
            duplicates.append(source_id)
            continue
        result[source_id] = item
    return result, sorted(set(duplicates))


def target_map(audit: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = audit.get("videos")
    if not isinstance(raw, list):
        raise ValueError("VK audit videos must be a list")
    result: dict[str, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        ref = item.get("ref")
        target_id = str(ref.get("remote_id") or "") if isinstance(ref, dict) else ""
        if target_id:
            result[target_id] = item
    return result


def verify_review_map(review: dict[str, Any], *, channel_id: str, community_id: int) -> None:
    if review.get("schema_name") != "video-manager.legendary-poet-shorts-reviewed-map":
        raise ValueError("Unexpected reviewed map schema")
    if str(review.get("youtube_channel_id") or "") != channel_id:
        raise ValueError("Reviewed map belongs to another YouTube channel")
    if int(review.get("vk_community_id") or 0) != community_id:
        raise ValueError("Reviewed map belongs to another VK community")
    expected_hash = str(review.get("review_sha256") or "")
    actual_hash = canonical_sha256(review, omit_key="review_sha256")
    if expected_hash != actual_hash:
        raise ValueError(f"Reviewed map SHA-256 mismatch: expected {expected_hash}, observed {actual_hash}")
    matches = review.get("reviewed_matches")
    missing = review.get("reviewed_missing")
    expected_ids = review.get("expected_shorts_ids")
    if not isinstance(matches, list) or not isinstance(missing, list) or not isinstance(expected_ids, list):
        raise ValueError("Reviewed map lists are malformed")
    source_ids = [str(item.get("source_id") or "") for item in matches + missing if isinstance(item, dict)]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("Reviewed map contains duplicate source IDs")
    if sorted(source_ids) != sorted(str(item) for item in expected_ids):
        raise ValueError("Reviewed map expected Shorts set does not equal matches + missing")
    target_ids = [str(item.get("target_id") or "") for item in matches if isinstance(item, dict)]
    if len(target_ids) != len(set(target_ids)):
        raise ValueError("Reviewed map contains duplicate VK target IDs")


def verify_source(item: dict[str, Any], reviewed: dict[str, Any]) -> None:
    source_id = str(reviewed["source_id"])
    actual_title = str(item.get("title") or "")
    reviewed_title = str(reviewed.get("source_title") or "")
    if normalize(actual_title) != normalize(reviewed_title):
        raise ValueError(
            f"YouTube title changed for {source_id}: reviewed={reviewed_title!r}, current={actual_title!r}"
        )
    actual_duration = int(item.get("duration_seconds") or 0)
    reviewed_duration = int(reviewed.get("source_duration_seconds") or 0)
    if actual_duration != reviewed_duration:
        raise ValueError(
            f"YouTube duration changed for {source_id}: reviewed={reviewed_duration}, current={actual_duration}"
        )
    if version_numbers(actual_title) != version_numbers(reviewed_title):
        raise ValueError(f"YouTube version markers changed for {source_id}")
    if str(item.get("privacy_status") or "public") != "public":
        raise ValueError(f"YouTube source {source_id} is no longer public")


def verify_target(item: dict[str, Any], reviewed: dict[str, Any]) -> None:
    target_id = str(reviewed["target_id"])
    actual_title = str(item.get("title") or "")
    reviewed_title = str(reviewed.get("target_title") or "")
    if normalize(actual_title) != normalize(reviewed_title):
        raise ValueError(
            f"VK title changed for {target_id}: reviewed={reviewed_title!r}, current={actual_title!r}"
        )
    actual_duration = int(item.get("duration_seconds") or 0)
    reviewed_duration = int(reviewed.get("target_duration_seconds") or 0)
    if actual_duration != reviewed_duration:
        raise ValueError(
            f"VK duration changed for {target_id}: reviewed={reviewed_duration}, current={actual_duration}"
        )
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    width = int(metadata.get("width") or 0)
    height = int(metadata.get("height") or 0)
    if width <= 0 or height <= width:
        raise ValueError(f"Reviewed VK target {target_id} is no longer a vertical object: {width}x{height}")
    if version_numbers(actual_title) != version_numbers(reviewed_title):
        raise ValueError(f"VK version markers changed for {target_id}")


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


def transfer_manifest_hash(
    queue: list[dict[str, Any]],
    publications: dict[str, VkPublicationText],
    reports: dict[str, MediaQualityReport],
    review_sha256: str,
) -> str:
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
    body = {"review_sha256": review_sha256, "queue": payload}
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def begin_clip_upload(writer: VkVideoWriter, *, community_id: int, title: str, description: str) -> VkUploadTicket:
    response = writer._call(
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


def load_or_create_journal(
    path: Path,
    *,
    review_sha256: str,
    transfer_sha256: str,
    community: int,
    queue_ids: list[str],
) -> dict[str, Any]:
    if path.exists():
        journal = read_json(path)
        if journal.get("schema_name") != "video-manager.legendary-poet-shorts-reviewed-journal":
            raise ValueError("Existing journal has an unexpected schema")
        expected = (review_sha256, transfer_sha256, community, queue_ids)
        actual = (
            str(journal.get("review_sha256") or ""),
            str(journal.get("transfer_manifest_sha256") or ""),
            int(journal.get("community_id") or 0),
            [str(item) for item in (journal.get("queue") or [])],
        )
        if actual != expected:
            raise ValueError("Existing Shorts journal belongs to another review/manifest/community/queue")
        return journal
    now = datetime.now(UTC).isoformat()
    journal = {
        "schema_name": "video-manager.legendary-poet-shorts-reviewed-journal",
        "schema_version": 1,
        "created_at": now,
        "updated_at": now,
        "review_sha256": review_sha256,
        "transfer_manifest_sha256": transfer_sha256,
        "community_id": community,
        "wall_mutation_authorized": False,
        "queue": queue_ids,
        "uploads": {},
    }
    write_json(path, journal)
    return journal


def save_journal(path: Path, journal: dict[str, Any]) -> None:
    journal["updated_at"] = datetime.now(UTC).isoformat()
    write_json(path, journal)


def wait_and_require_short_video(
    writer: VkVideoWriter,
    ticket: VkUploadTicket,
    *,
    timeout_seconds: int,
    poll_seconds: float,
) -> dict[str, Any]:
    live = writer.read_video(owner_id=ticket.owner_id, video_id=ticket.video_id)
    if live is None or bool(live.get("processing")) or bool(live.get("converting")):
        live = writer.wait_until_available(
            ticket,
            timeout_seconds=timeout_seconds,
            poll_seconds=poll_seconds,
        )
    observed = str(live.get("type") or "")
    if observed != "short_video":
        raise ValueError(f"VK object {ticket.remote_id} completed with type={observed!r}, expected 'short_video'")
    return live


def build_group_order(missing_items: list[dict[str, Any]], review: dict[str, Any]) -> list[tuple[str, list[dict[str, Any]]]]:
    by_id = {str(item["ref"]["remote_id"]): item for item in missing_items}
    short = [item for item in missing_items if int(item.get("duration_seconds") or 0) <= 60]
    long = [item for item in missing_items if int(item.get("duration_seconds") or 0) > 60]

    def ordered(group: list[dict[str, Any]], canary_id: str) -> list[dict[str, Any]]:
        if not group:
            return []
        ids = {str(item["ref"]["remote_id"]) for item in group}
        if canary_id not in ids:
            raise ValueError(f"Reviewed canary {canary_id} is absent from its duration group")
        rest = sorted(
            (item for item in group if str(item["ref"]["remote_id"]) != canary_id),
            key=lambda item: (int(item.get("duration_seconds") or 0), str(item["ref"]["remote_id"])),
        )
        return [by_id[canary_id], *rest]

    return [
        ("up_to_60_seconds", ordered(short, str(review["short_canary_source_id"]))),
        ("over_60_seconds", ordered(long, str(review["long_canary_source_id"]))),
    ]


def main() -> int:
    args = parse_args()
    youtube = read_json(args.youtube_audit)
    vk = read_json(args.vk_audit)
    review = read_json(args.review_map)
    verify_review_map(review, channel_id=args.expected_youtube_channel_id, community_id=args.community)
    review_sha256 = str(review["review_sha256"])

    youtube_by_id, duplicate_source_ids = source_map(youtube)
    vk_by_id = target_map(vk)

    args.report_dir.mkdir(parents=True, exist_ok=True)
    shorts_flat_path = args.report_dir / "legendary-poet-youtube-shorts-flat.json"
    current_shorts_ids = enumerate_shorts(args.yt_dlp, args.shorts_url, shorts_flat_path)
    expected_shorts_ids = [str(item) for item in review["expected_shorts_ids"]]
    if set(current_shorts_ids) != set(expected_shorts_ids) or len(current_shorts_ids) != len(expected_shorts_ids):
        added = sorted(set(current_shorts_ids) - set(expected_shorts_ids))
        removed = sorted(set(expected_shorts_ids) - set(current_shorts_ids))
        raise ValueError(
            "Live YouTube Shorts set differs from the reviewed 56-ID set; zero VK writes performed: "
            f"added={added}, removed={removed}, observed={len(current_shorts_ids)}, reviewed={len(expected_shorts_ids)}"
        )

    hydrated: list[str] = []
    for source_id in current_shorts_ids:
        if source_id not in youtube_by_id:
            print(f"Hydrating exact reviewed Shorts ID absent from fresh YouTube audit: {source_id}")
            youtube_by_id[source_id] = hydrate_short_metadata(
                args.yt_dlp,
                source_id,
                args.expected_youtube_channel_id,
            )
            hydrated.append(source_id)

    reviewed_matches = [item for item in review["reviewed_matches"] if isinstance(item, dict)]
    reviewed_missing = [item for item in review["reviewed_missing"] if isinstance(item, dict)]

    for item in reviewed_matches + reviewed_missing:
        source_id = str(item["source_id"])
        current = youtube_by_id.get(source_id)
        if current is None:
            raise ValueError(f"Reviewed YouTube source disappeared: {source_id}")
        verify_source(current, item)

    for item in reviewed_matches:
        target_id = str(item["target_id"])
        current = vk_by_id.get(target_id)
        if current is None:
            raise ValueError(f"Reviewed VK target disappeared: {target_id}")
        verify_target(current, item)

    journal_remote_ids: set[str] = set()
    if args.journal.exists():
        previous = read_json(args.journal)
        uploads = previous.get("uploads")
        if isinstance(uploads, dict):
            for entry in uploads.values():
                if isinstance(entry, dict) and isinstance(entry.get("remote_id"), str):
                    journal_remote_ids.add(str(entry["remote_id"]))

    reviewed_target_ids = {str(item["target_id"]) for item in reviewed_matches}
    current_vertical_ids = {
        remote_id
        for remote_id, item in vk_by_id.items()
        if int((item.get("metadata") or {}).get("height") or 0) > int((item.get("metadata") or {}).get("width") or 0)
    }
    unexpected_vertical = sorted(current_vertical_ids - reviewed_target_ids - journal_remote_ids)
    missing_reviewed_targets = sorted(reviewed_target_ids - current_vertical_ids)
    if unexpected_vertical or missing_reviewed_targets:
        raise ValueError(
            "Live VK vertical catalog differs from reviewed map; zero VK writes performed: "
            f"unexpected={unexpected_vertical}, missing_reviewed={missing_reviewed_targets}"
        )

    missing_items = [youtube_by_id[str(item["source_id"])] for item in reviewed_missing]
    report = {
        "schema_name": "video-manager.legendary-poet-shorts-reviewed-preflight",
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "youtube_snapshot_id": youtube.get("snapshot_id"),
        "vk_snapshot_id": vk.get("snapshot_id"),
        "review_sha256": review_sha256,
        "youtube_short_count": len(current_shorts_ids),
        "reviewed_match_count": len(reviewed_matches),
        "reviewed_missing_count": len(reviewed_missing),
        "duplicate_source_ids_in_audit": duplicate_source_ids,
        "live_hydrated_source_ids": hydrated,
        "reviewed_matches": reviewed_matches,
        "reviewed_missing": reviewed_missing,
    }
    report_path = args.report_dir / "legendary-poet-shorts-reviewed-preflight.json"
    write_json(report_path, report)

    print("Reviewed Legendary Poet Shorts preflight:")
    print(f"  exact live YouTube Shorts IDs: {len(current_shorts_ids)}")
    print(f"  exact reviewed existing pairs: {len(reviewed_matches)}")
    print(f"  exact reviewed missing IDs: {len(reviewed_missing)}")
    print(f"  ambiguous IDs: 0")
    print(f"  unexpected vertical VK objects: 0")
    print(f"  duplicate source IDs outside Shorts set: {duplicate_source_ids}")
    print(f"  exact IDs hydrated live: {hydrated}")
    print(f"  reviewed map: {review_sha256}")
    print(f"  report: {report_path}")

    publications: dict[str, VkPublicationText] = {}
    media_paths: dict[str, Path] = {}
    media_reports: dict[str, MediaQualityReport] = {}
    for index, item in enumerate(missing_items, start=1):
        source_id = str(item["ref"]["remote_id"])
        print(f"Download/QC [{index}/{len(missing_items)}] {source_id} — {item['title']}")
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

    transfer_sha256 = transfer_manifest_hash(missing_items, publications, media_reports, review_sha256)
    report["transfer_manifest_sha256"] = transfer_sha256
    report["media"] = {source_id: quality.to_dict() for source_id, quality in media_reports.items()}
    write_json(report_path, report)
    print(f"  transfer manifest: {transfer_sha256}")

    if not args.execute:
        print("Dry-run only. All 15 source files were downloaded and validated; zero VK writes performed.")
        return 0

    settings = get_settings()
    token_store = VkTokenStore(settings.data_dir)
    reader = VkApiClient(token_store=token_store, account_alias=args.account, api_version=settings.vk_api_version)
    community = reader.get_community(str(args.community))
    if int(community.ref.channel_id) != args.community:
        raise ValueError("Live VK community mismatch")
    if not bool(community.metadata.get("managed_by_token")):
        raise ValueError("Authorized VK user is not reported as administrator of the target community")

    queue_ids = [str(item["source_id"]) for item in reviewed_missing]
    journal = load_or_create_journal(
        args.journal,
        review_sha256=review_sha256,
        transfer_sha256=transfer_sha256,
        community=args.community,
        queue_ids=queue_ids,
    )
    uploads = journal["uploads"]
    writer = VkVideoWriter(token_store=token_store, account_alias=args.account, api_version=settings.vk_api_version)

    groups = build_group_order(missing_items, review)
    lock_path = settings.data_dir / "locks" / f"vk-{args.account}-{args.community}.lock"
    with local_vk_write_lock(
        lock_path,
        account=args.account,
        community_id=args.community,
        operation="legendary-poet-shorts-reviewed-sync",
    ):
        completed_count = 0
        total_count = len(missing_items)
        for group_name, group in groups:
            if not group:
                continue
            canary_id = str(group[0]["ref"]["remote_id"])
            canary_confirmed = False
            print(f"Starting duration group {group_name}; canary={canary_id}; items={len(group)}")
            for group_index, item in enumerate(group, start=1):
                source_id = str(item["ref"]["remote_id"])
                publication = publications[source_id]
                existing = uploads.get(source_id)
                if isinstance(existing, dict) and isinstance(existing.get("remote_id"), str):
                    remote_id = str(existing["remote_id"])
                    owner_id, video_id = parse_remote_id(remote_id)
                    ticket = VkUploadTicket(owner_id=owner_id, video_id=video_id, upload_url="reconcile-only")
                    try:
                        live = wait_and_require_short_video(
                            writer,
                            ticket,
                            timeout_seconds=args.processing_timeout,
                            poll_seconds=args.poll_seconds,
                        )
                    except BaseException as exc:
                        existing["status"] = "stopped_needs_reconciliation"
                        existing["error"] = f"{type(exc).__name__}: {exc}"
                        existing["stopped_at"] = datetime.now(UTC).isoformat()
                        save_journal(args.journal, journal)
                        raise
                    existing["status"] = "confirmed_short_video"
                    existing["vk_type"] = live.get("type")
                    existing["confirmed_at"] = datetime.now(UTC).isoformat()
                    save_journal(args.journal, journal)
                    completed_count += 1
                    print(f"[{completed_count}/{total_count}] Reused confirmed https://vk.com/video{remote_id}")
                    if source_id == canary_id:
                        canary_confirmed = True
                    continue

                if group_index > 1 and not canary_confirmed:
                    raise ValueError(f"Canary {canary_id} was not confirmed as short_video; group {group_name} stopped")

                print(f"[{completed_count + 1}/{total_count}] Uploading {source_id} — {publication.title}")
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
                    "duration_group": group_name,
                    "is_group_canary": source_id == canary_id,
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
                    live = wait_and_require_short_video(
                        writer,
                        ticket,
                        timeout_seconds=args.processing_timeout,
                        poll_seconds=args.poll_seconds,
                    )
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
                completed_count += 1
                print(f"[{completed_count}/{total_count}] Verified https://vk.com/video{ticket.remote_id} type=short_video")
                if source_id == canary_id:
                    canary_confirmed = True
                    print(f"Canary for {group_name} confirmed; continuing only this duration group.")
                if completed_count < total_count and args.write_delay > 0:
                    time.sleep(args.write_delay)

    print(f"Completed: {len(missing_items)} exact reviewed missing Shorts confirmed as VK short_video.")
    print(f"Journal: {args.journal}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, MediaQualityError, VkWriteError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
```

## 006. Reviewed PowerShell launcher V3

- Original: `run-legendary-poet-shorts-sync.ps1`
- SHA-256: `8cf6e47799ea3f4492fb415dcadc51e996379ff53dd626e277ef87c6f18331b2`

```powershell
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$YouTubeAudit = ".\data\exports\youtube-legendary-poet-current.json"
$VkAudit      = ".\data\exports\vk-legendary-poet-after-full.json"
$CacheDir    = ".\data\cache\legendary-poet-shorts-reviewed-v3"
$ReportDir   = ".\data\reports\legendary-poet-shorts-reviewed-v3"
$Journal     = ".\data\reports\legendary-poet-shorts-reviewed-v3-journal.json"
$Script      = Join-Path $PSScriptRoot "legendary_poet_shorts_sync.py"
$ReviewMap   = Join-Path $PSScriptRoot "reviewed_shorts_map.json"
$ChannelId   = "UC-78ys2S3cQ3lpqgXfo-SvQ"
$CommunityId = 235216998

foreach ($required in @($Script, $ReviewMap)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Не найден обязательный файл пакета: $required"
    }
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

Write-Host "`n========== ПРОВЕРЕННАЯ КАРТА 56 SHORTS ==========" -ForegroundColor Cyan
Write-Host "Карта: 41 точная существующая пара + 15 точных отсутствующих ID" -ForegroundColor Green
Write-Host "Canary до 60 сек:  LnLJaOQnQWg (Бородино)" -ForegroundColor Green
Write-Host "Canary свыше 60 сек: M5hNecL_MsQ (Последняя буря)" -ForegroundColor Green

python $Script `
    --youtube-audit $YouTubeAudit `
    --vk-audit $VkAudit `
    --review-map $ReviewMap `
    --account legendary-poet `
    --community $CommunityId `
    --shorts-url "https://www.youtube.com/channel/$ChannelId/shorts" `
    --expected-youtube-channel-id $ChannelId `
    --cache-dir $CacheDir `
    --report-dir $ReportDir `
    --journal $Journal `
    --processing-timeout 7200 `
    --poll-seconds 10 `
    --write-delay 3 `
    --execute

if ($LASTEXITCODE -ne 0) {
    throw "Пакет безопасно остановлен. Не повторяйте отдельные загрузки вручную. Отчёт: $ReportDir; журнал: $Journal"
}

Write-Host "`nВсе 15 проверенных отсутствующих Shorts перенесены и подтверждены как short_video." -ForegroundColor Green
Write-Host "Журнал: $Journal" -ForegroundColor Green
```

## 007. Long-video fallback Shorts sync V4

- Original: `legendary_poet_shorts_sync.py`
- SHA-256: `b5766567be2e00874f1c7da5a5348a8cd7d64def84b650062c1fea968e60a1d7`

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
from datetime import UTC, datetime
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reviewed exact YouTube Shorts to VK synchronization.")
    parser.add_argument("--youtube-audit", type=Path, required=True)
    parser.add_argument("--vk-audit", type=Path, required=True)
    parser.add_argument("--review-map", type=Path, required=True)
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


def canonical_sha256(payload: dict[str, Any], *, omit_key: str | None = None) -> str:
    body = dict(payload)
    if omit_key is not None:
        body.pop(omit_key, None)
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def normalize(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "").casefold().replace("ё", "е")
    text = BRAND_RE.sub(" ", text).replace("version", "версия")
    text = NON_WORD_RE.sub(" ", text)
    return SPACE_RE.sub(" ", text).strip()


def version_numbers(value: str) -> frozenset[int]:
    return frozenset(int(match.group(1)) for match in VERSION_RE.finditer(normalize(value)))


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
    try:
        payload = json.loads(completed.stdout.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
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
        if video_id and video_id not in seen:
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
        raise ValueError(f"Timed out hydrating Shorts ID {video_id}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace")[-4000:]
        raise ValueError(f"Cannot hydrate Shorts ID {video_id}: {detail}")
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
    timestamp = payload.get("timestamp") or payload.get("release_timestamp")
    published_at = None
    if isinstance(timestamp, (int, float)) and timestamp > 0:
        published_at = datetime.fromtimestamp(float(timestamp), UTC).isoformat().replace("+00:00", "Z")
    return {
        "ref": {"platform": "youtube", "channel_id": expected_channel_id, "remote_id": video_id},
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
            "width": payload.get("width"),
            "height": payload.get("height"),
        },
    }


def source_map(audit: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    raw = audit.get("videos")
    if not isinstance(raw, list):
        raise ValueError("YouTube audit videos must be a list")
    result: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        ref = item.get("ref")
        source_id = str(ref.get("remote_id") or "") if isinstance(ref, dict) else ""
        if not source_id:
            continue
        if source_id in result:
            duplicates.append(source_id)
            continue
        result[source_id] = item
    return result, sorted(set(duplicates))


def target_map(audit: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = audit.get("videos")
    if not isinstance(raw, list):
        raise ValueError("VK audit videos must be a list")
    result: dict[str, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        ref = item.get("ref")
        target_id = str(ref.get("remote_id") or "") if isinstance(ref, dict) else ""
        if target_id:
            result[target_id] = item
    return result


def verify_review_map(review: dict[str, Any], *, channel_id: str, community_id: int) -> None:
    if review.get("schema_name") != "video-manager.legendary-poet-shorts-reviewed-map":
        raise ValueError("Unexpected reviewed map schema")
    if str(review.get("youtube_channel_id") or "") != channel_id:
        raise ValueError("Reviewed map belongs to another YouTube channel")
    if int(review.get("vk_community_id") or 0) != community_id:
        raise ValueError("Reviewed map belongs to another VK community")
    expected_hash = str(review.get("review_sha256") or "")
    actual_hash = canonical_sha256(review, omit_key="review_sha256")
    if expected_hash != actual_hash:
        raise ValueError(f"Reviewed map SHA-256 mismatch: expected {expected_hash}, observed {actual_hash}")
    matches = review.get("reviewed_matches")
    missing = review.get("reviewed_missing")
    expected_ids = review.get("expected_shorts_ids")
    if not isinstance(matches, list) or not isinstance(missing, list) or not isinstance(expected_ids, list):
        raise ValueError("Reviewed map lists are malformed")
    source_ids = [str(item.get("source_id") or "") for item in matches + missing if isinstance(item, dict)]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("Reviewed map contains duplicate source IDs")
    if sorted(source_ids) != sorted(str(item) for item in expected_ids):
        raise ValueError("Reviewed map expected Shorts set does not equal matches + missing")
    target_ids = [str(item.get("target_id") or "") for item in matches if isinstance(item, dict)]
    if len(target_ids) != len(set(target_ids)):
        raise ValueError("Reviewed map contains duplicate VK target IDs")


def verify_source(item: dict[str, Any], reviewed: dict[str, Any]) -> None:
    source_id = str(reviewed["source_id"])
    actual_title = str(item.get("title") or "")
    reviewed_title = str(reviewed.get("source_title") or "")
    if normalize(actual_title) != normalize(reviewed_title):
        raise ValueError(
            f"YouTube title changed for {source_id}: reviewed={reviewed_title!r}, current={actual_title!r}"
        )
    actual_duration = int(item.get("duration_seconds") or 0)
    reviewed_duration = int(reviewed.get("source_duration_seconds") or 0)
    if actual_duration != reviewed_duration:
        raise ValueError(
            f"YouTube duration changed for {source_id}: reviewed={reviewed_duration}, current={actual_duration}"
        )
    if version_numbers(actual_title) != version_numbers(reviewed_title):
        raise ValueError(f"YouTube version markers changed for {source_id}")
    if str(item.get("privacy_status") or "public") != "public":
        raise ValueError(f"YouTube source {source_id} is no longer public")


def verify_target(item: dict[str, Any], reviewed: dict[str, Any]) -> None:
    target_id = str(reviewed["target_id"])
    actual_title = str(item.get("title") or "")
    reviewed_title = str(reviewed.get("target_title") or "")
    if normalize(actual_title) != normalize(reviewed_title):
        raise ValueError(
            f"VK title changed for {target_id}: reviewed={reviewed_title!r}, current={actual_title!r}"
        )
    actual_duration = int(item.get("duration_seconds") or 0)
    reviewed_duration = int(reviewed.get("target_duration_seconds") or 0)
    if actual_duration != reviewed_duration:
        raise ValueError(
            f"VK duration changed for {target_id}: reviewed={reviewed_duration}, current={actual_duration}"
        )
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    width = int(metadata.get("width") or 0)
    height = int(metadata.get("height") or 0)
    if width <= 0 or height <= width:
        raise ValueError(f"Reviewed VK target {target_id} is no longer a vertical object: {width}x{height}")
    if version_numbers(actual_title) != version_numbers(reviewed_title):
        raise ValueError(f"VK version markers changed for {target_id}")


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


def transfer_manifest_hash(
    queue: list[dict[str, Any]],
    publications: dict[str, VkPublicationText],
    reports: dict[str, MediaQualityReport],
    review_sha256: str,
) -> str:
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
    body = {"review_sha256": review_sha256, "queue": payload}
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def begin_clip_upload(writer: VkVideoWriter, *, community_id: int, title: str, description: str) -> VkUploadTicket:
    response = writer._call(
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


def load_or_create_journal(
    path: Path,
    *,
    review_sha256: str,
    transfer_sha256: str,
    community: int,
    queue_ids: list[str],
) -> dict[str, Any]:
    if path.exists():
        journal = read_json(path)
        if journal.get("schema_name") != "video-manager.legendary-poet-shorts-reviewed-journal":
            raise ValueError("Existing journal has an unexpected schema")
        expected = (review_sha256, transfer_sha256, community, queue_ids)
        actual = (
            str(journal.get("review_sha256") or ""),
            str(journal.get("transfer_manifest_sha256") or ""),
            int(journal.get("community_id") or 0),
            [str(item) for item in (journal.get("queue") or [])],
        )
        if actual != expected:
            raise ValueError("Existing Shorts journal belongs to another review/manifest/community/queue")
        return journal
    now = datetime.now(UTC).isoformat()
    journal = {
        "schema_name": "video-manager.legendary-poet-shorts-reviewed-journal",
        "schema_version": 1,
        "created_at": now,
        "updated_at": now,
        "review_sha256": review_sha256,
        "transfer_manifest_sha256": transfer_sha256,
        "community_id": community,
        "wall_mutation_authorized": False,
        "queue": queue_ids,
        "uploads": {},
    }
    write_json(path, journal)
    return journal


def save_journal(path: Path, journal: dict[str, Any]) -> None:
    journal["updated_at"] = datetime.now(UTC).isoformat()
    write_json(path, journal)


def wait_and_require_target(
    writer: VkVideoWriter,
    ticket: VkUploadTicket,
    *,
    group_name: str,
    expected_duration: float,
    timeout_seconds: int,
    poll_seconds: float,
) -> dict[str, Any]:
    """Confirm the exact VK object without retransmitting it.

    Short sources (<=60s) must be exposed as ``short_video``.
    Long YouTube Shorts are accepted as ``short_video`` when VK classifies
    them that way, or as a playable vertical ordinary ``video`` fallback.
    VK can leave ``processing=1`` set after all renditions and the player
    are already available, so playability is the decisive long-form gate.
    """

    if group_name not in {"up_to_60_seconds", "over_60_seconds"}:
        raise ValueError(f"Unexpected duration group: {group_name}")
    if timeout_seconds <= 0 or poll_seconds <= 0:
        raise ValueError("timeout_seconds and poll_seconds must be positive")

    deadline = time.monotonic() + timeout_seconds
    last_live: dict[str, Any] | None = None

    while time.monotonic() < deadline:
        live = writer.read_video(owner_id=ticket.owner_id, video_id=ticket.video_id)
        if live is not None:
            last_live = live
            observed_type = str(live.get("type") or "")
            processing = bool(live.get("processing")) or bool(live.get("converting"))

            if observed_type == "short_video":
                return live

            if group_name == "over_60_seconds" and observed_type == "video":
                try:
                    duration = float(live.get("duration") or 0)
                    width = int(live.get("width") or 0)
                    height = int(live.get("height") or 0)
                except (TypeError, ValueError):
                    duration, width, height = 0.0, 0, 0

                files = live.get("files")
                playable = (
                    (isinstance(files, dict) and bool(files))
                    or bool(live.get("player"))
                    or bool(live.get("direct_url"))
                    or bool(live.get("share_url"))
                )
                duration_ok = duration > 0 and abs(duration - expected_duration) <= 4.0
                vertical = width > 0 and height > width

                if playable and duration_ok and vertical:
                    return live

            if not processing:
                raise ValueError(
                    f"VK object {ticket.remote_id} completed with type={observed_type!r}; "
                    f"group={group_name!r}, expected short_video or a playable vertical video fallback"
                )

        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(poll_seconds, remaining))

    state = json.dumps(last_live, ensure_ascii=False)[:1500] if last_live else "not visible"
    raise ValueError(
        f"VK object {ticket.remote_id} did not reach an accepted state within "
        f"{timeout_seconds}s; last state: {state}"
    )


def build_group_order(missing_items: list[dict[str, Any]], review: dict[str, Any]) -> list[tuple[str, list[dict[str, Any]]]]:
    by_id = {str(item["ref"]["remote_id"]): item for item in missing_items}
    short = [item for item in missing_items if int(item.get("duration_seconds") or 0) <= 60]
    long = [item for item in missing_items if int(item.get("duration_seconds") or 0) > 60]

    def ordered(group: list[dict[str, Any]], canary_id: str) -> list[dict[str, Any]]:
        if not group:
            return []
        ids = {str(item["ref"]["remote_id"]) for item in group}
        if canary_id not in ids:
            raise ValueError(f"Reviewed canary {canary_id} is absent from its duration group")
        rest = sorted(
            (item for item in group if str(item["ref"]["remote_id"]) != canary_id),
            key=lambda item: (int(item.get("duration_seconds") or 0), str(item["ref"]["remote_id"])),
        )
        return [by_id[canary_id], *rest]

    return [
        ("up_to_60_seconds", ordered(short, str(review["short_canary_source_id"]))),
        ("over_60_seconds", ordered(long, str(review["long_canary_source_id"]))),
    ]


def main() -> int:
    args = parse_args()
    youtube = read_json(args.youtube_audit)
    vk = read_json(args.vk_audit)
    review = read_json(args.review_map)
    verify_review_map(review, channel_id=args.expected_youtube_channel_id, community_id=args.community)
    review_sha256 = str(review["review_sha256"])

    youtube_by_id, duplicate_source_ids = source_map(youtube)
    vk_by_id = target_map(vk)

    args.report_dir.mkdir(parents=True, exist_ok=True)
    shorts_flat_path = args.report_dir / "legendary-poet-youtube-shorts-flat.json"
    current_shorts_ids = enumerate_shorts(args.yt_dlp, args.shorts_url, shorts_flat_path)
    expected_shorts_ids = [str(item) for item in review["expected_shorts_ids"]]
    if set(current_shorts_ids) != set(expected_shorts_ids) or len(current_shorts_ids) != len(expected_shorts_ids):
        added = sorted(set(current_shorts_ids) - set(expected_shorts_ids))
        removed = sorted(set(expected_shorts_ids) - set(current_shorts_ids))
        raise ValueError(
            "Live YouTube Shorts set differs from the reviewed 56-ID set; zero VK writes performed: "
            f"added={added}, removed={removed}, observed={len(current_shorts_ids)}, reviewed={len(expected_shorts_ids)}"
        )

    hydrated: list[str] = []
    for source_id in current_shorts_ids:
        if source_id not in youtube_by_id:
            print(f"Hydrating exact reviewed Shorts ID absent from fresh YouTube audit: {source_id}")
            youtube_by_id[source_id] = hydrate_short_metadata(
                args.yt_dlp,
                source_id,
                args.expected_youtube_channel_id,
            )
            hydrated.append(source_id)

    reviewed_matches = [item for item in review["reviewed_matches"] if isinstance(item, dict)]
    reviewed_missing = [item for item in review["reviewed_missing"] if isinstance(item, dict)]

    for item in reviewed_matches + reviewed_missing:
        source_id = str(item["source_id"])
        current = youtube_by_id.get(source_id)
        if current is None:
            raise ValueError(f"Reviewed YouTube source disappeared: {source_id}")
        verify_source(current, item)

    for item in reviewed_matches:
        target_id = str(item["target_id"])
        current = vk_by_id.get(target_id)
        if current is None:
            raise ValueError(f"Reviewed VK target disappeared: {target_id}")
        verify_target(current, item)

    journal_remote_ids: set[str] = set()
    if args.journal.exists():
        previous = read_json(args.journal)
        uploads = previous.get("uploads")
        if isinstance(uploads, dict):
            for entry in uploads.values():
                if isinstance(entry, dict) and isinstance(entry.get("remote_id"), str):
                    journal_remote_ids.add(str(entry["remote_id"]))

    reviewed_target_ids = {str(item["target_id"]) for item in reviewed_matches}
    current_vertical_ids = {
        remote_id
        for remote_id, item in vk_by_id.items()
        if int((item.get("metadata") or {}).get("height") or 0) > int((item.get("metadata") or {}).get("width") or 0)
    }
    unexpected_vertical = sorted(current_vertical_ids - reviewed_target_ids - journal_remote_ids)
    missing_reviewed_targets = sorted(reviewed_target_ids - current_vertical_ids)
    if unexpected_vertical or missing_reviewed_targets:
        raise ValueError(
            "Live VK vertical catalog differs from reviewed map; zero VK writes performed: "
            f"unexpected={unexpected_vertical}, missing_reviewed={missing_reviewed_targets}"
        )

    missing_items = [youtube_by_id[str(item["source_id"])] for item in reviewed_missing]
    report = {
        "schema_name": "video-manager.legendary-poet-shorts-reviewed-preflight",
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "youtube_snapshot_id": youtube.get("snapshot_id"),
        "vk_snapshot_id": vk.get("snapshot_id"),
        "review_sha256": review_sha256,
        "youtube_short_count": len(current_shorts_ids),
        "reviewed_match_count": len(reviewed_matches),
        "reviewed_missing_count": len(reviewed_missing),
        "duplicate_source_ids_in_audit": duplicate_source_ids,
        "live_hydrated_source_ids": hydrated,
        "reviewed_matches": reviewed_matches,
        "reviewed_missing": reviewed_missing,
    }
    report_path = args.report_dir / "legendary-poet-shorts-reviewed-preflight.json"
    write_json(report_path, report)

    print("Reviewed Legendary Poet Shorts preflight:")
    print(f"  exact live YouTube Shorts IDs: {len(current_shorts_ids)}")
    print(f"  exact reviewed existing pairs: {len(reviewed_matches)}")
    print(f"  exact reviewed missing IDs: {len(reviewed_missing)}")
    print(f"  ambiguous IDs: 0")
    print(f"  unexpected vertical VK objects: 0")
    print(f"  duplicate source IDs outside Shorts set: {duplicate_source_ids}")
    print(f"  exact IDs hydrated live: {hydrated}")
    print(f"  reviewed map: {review_sha256}")
    print(f"  report: {report_path}")

    publications: dict[str, VkPublicationText] = {}
    media_paths: dict[str, Path] = {}
    media_reports: dict[str, MediaQualityReport] = {}
    for index, item in enumerate(missing_items, start=1):
        source_id = str(item["ref"]["remote_id"])
        print(f"Download/QC [{index}/{len(missing_items)}] {source_id} — {item['title']}")
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

    transfer_sha256 = transfer_manifest_hash(missing_items, publications, media_reports, review_sha256)
    report["transfer_manifest_sha256"] = transfer_sha256
    report["media"] = {source_id: quality.to_dict() for source_id, quality in media_reports.items()}
    write_json(report_path, report)
    print(f"  transfer manifest: {transfer_sha256}")

    if not args.execute:
        print("Dry-run only. All 15 source files were downloaded and validated; zero VK writes performed.")
        return 0

    settings = get_settings()
    token_store = VkTokenStore(settings.data_dir)
    reader = VkApiClient(token_store=token_store, account_alias=args.account, api_version=settings.vk_api_version)
    community = reader.get_community(str(args.community))
    if int(community.ref.channel_id) != args.community:
        raise ValueError("Live VK community mismatch")
    if not bool(community.metadata.get("managed_by_token")):
        raise ValueError("Authorized VK user is not reported as administrator of the target community")

    queue_ids = [str(item["source_id"]) for item in reviewed_missing]
    journal = load_or_create_journal(
        args.journal,
        review_sha256=review_sha256,
        transfer_sha256=transfer_sha256,
        community=args.community,
        queue_ids=queue_ids,
    )
    uploads = journal["uploads"]
    writer = VkVideoWriter(token_store=token_store, account_alias=args.account, api_version=settings.vk_api_version)

    groups = build_group_order(missing_items, review)
    lock_path = settings.data_dir / "locks" / f"vk-{args.account}-{args.community}.lock"
    with local_vk_write_lock(
        lock_path,
        account=args.account,
        community_id=args.community,
        operation="legendary-poet-shorts-reviewed-sync",
    ):
        completed_count = 0
        total_count = len(missing_items)
        for group_name, group in groups:
            if not group:
                continue
            canary_id = str(group[0]["ref"]["remote_id"])
            canary_confirmed = False
            print(f"Starting duration group {group_name}; canary={canary_id}; items={len(group)}")
            for group_index, item in enumerate(group, start=1):
                source_id = str(item["ref"]["remote_id"])
                publication = publications[source_id]
                existing = uploads.get(source_id)
                if isinstance(existing, dict) and isinstance(existing.get("remote_id"), str):
                    remote_id = str(existing["remote_id"])
                    owner_id, video_id = parse_remote_id(remote_id)
                    ticket = VkUploadTicket(owner_id=owner_id, video_id=video_id, upload_url="reconcile-only")
                    try:
                        live = wait_and_require_target(
                            writer,
                            ticket,
                            group_name=group_name,
                            expected_duration=media_reports[source_id].duration_seconds,
                            timeout_seconds=args.processing_timeout,
                            poll_seconds=args.poll_seconds,
                        )
                    except BaseException as exc:
                        existing["status"] = "stopped_needs_reconciliation"
                        existing["error"] = f"{type(exc).__name__}: {exc}"
                        existing["stopped_at"] = datetime.now(UTC).isoformat()
                        save_journal(args.journal, journal)
                        raise
                    existing["status"] = (
                        "confirmed_short_video"
                        if live.get("type") == "short_video"
                        else "confirmed_video_fallback"
                    )
                    existing["vk_type"] = live.get("type")
                    existing["confirmed_at"] = datetime.now(UTC).isoformat()
                    save_journal(args.journal, journal)
                    completed_count += 1
                    print(
                        f"[{completed_count}/{total_count}] Reused confirmed "
                        f"https://vk.com/video{remote_id} type={live.get('type')}"
                    )
                    if source_id == canary_id:
                        canary_confirmed = True
                    continue

                if group_index > 1 and not canary_confirmed:
                    raise ValueError(f"Canary {canary_id} was not confirmed for group {group_name}; group stopped")

                print(f"[{completed_count + 1}/{total_count}] Uploading {source_id} — {publication.title}")
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
                    "duration_group": group_name,
                    "is_group_canary": source_id == canary_id,
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
                    live = wait_and_require_target(
                        writer,
                        ticket,
                        group_name=group_name,
                        expected_duration=media_reports[source_id].duration_seconds,
                        timeout_seconds=args.processing_timeout,
                        poll_seconds=args.poll_seconds,
                    )
                except BaseException as exc:
                    uploads[source_id]["status"] = "stopped_needs_reconciliation"
                    uploads[source_id]["error"] = f"{type(exc).__name__}: {exc}"
                    uploads[source_id]["stopped_at"] = datetime.now(UTC).isoformat()
                    save_journal(args.journal, journal)
                    raise

                uploads[source_id]["status"] = (
                    "confirmed_short_video"
                    if live.get("type") == "short_video"
                    else "confirmed_video_fallback"
                )
                uploads[source_id]["vk_type"] = live.get("type")
                uploads[source_id]["confirmed_at"] = datetime.now(UTC).isoformat()
                save_journal(args.journal, journal)
                completed_count += 1
                print(
                    f"[{completed_count}/{total_count}] Verified "
                    f"https://vk.com/video{ticket.remote_id} type={live.get('type')}"
                )
                if source_id == canary_id:
                    canary_confirmed = True
                    print(f"Canary for {group_name} confirmed; continuing only this duration group.")
                if completed_count < total_count and args.write_delay > 0:
                    time.sleep(args.write_delay)

    print(
        f"Completed: {len(missing_items)} exact reviewed missing sources transferred; "
        "short sources require short_video, long sources may use playable vertical video fallback."
    )
    print(f"Journal: {args.journal}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, MediaQualityError, VkWriteError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
```

## 008. Long-video fallback PowerShell launcher V4

- Original: `run-legendary-poet-shorts-sync.ps1`
- SHA-256: `3f0b316f613be52750f9ea2a5f395888a1be30aa11c04bc45221eff083e0317d`

```powershell
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$YouTubeAudit = ".\data\exports\youtube-legendary-poet-current.json"
$VkAudit      = ".\data\exports\vk-legendary-poet-after-full.json"
$CacheDir    = ".\data\cache\legendary-poet-shorts-reviewed-v3"
$ReportDir   = ".\data\reports\legendary-poet-shorts-reviewed-v3"
$Journal     = ".\data\reports\legendary-poet-shorts-reviewed-v3-journal.json"
$Script      = Join-Path $PSScriptRoot "legendary_poet_shorts_sync.py"
$ReviewMap   = Join-Path $PSScriptRoot "reviewed_shorts_map.json"
$ChannelId   = "UC-78ys2S3cQ3lpqgXfo-SvQ"
$CommunityId = 235216998

foreach ($required in @($Script, $ReviewMap)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Не найден обязательный файл пакета: $required"
    }
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

Write-Host "`n========== V4: КЛИПЫ + ДЛИННЫЙ VIDEO FALLBACK ==========" -ForegroundColor Cyan
Write-Host "Карта: 41 точная существующая пара + 15 точных отсутствующих ID" -ForegroundColor Green
Write-Host "Canary до 60 сек:  LnLJaOQnQWg (Бородино)" -ForegroundColor Green
Write-Host "Canary свыше 60 сек: M5hNecL_MsQ (short_video или воспроизводимый вертикальный video)" -ForegroundColor Yellow

python $Script `
    --youtube-audit $YouTubeAudit `
    --vk-audit $VkAudit `
    --review-map $ReviewMap `
    --account legendary-poet `
    --community $CommunityId `
    --shorts-url "https://www.youtube.com/channel/$ChannelId/shorts" `
    --expected-youtube-channel-id $ChannelId `
    --cache-dir $CacheDir `
    --report-dir $ReportDir `
    --journal $Journal `
    --processing-timeout 7200 `
    --poll-seconds 10 `
    --write-delay 3 `
    --execute

if ($LASTEXITCODE -ne 0) {
    throw "Пакет безопасно остановлен. Не повторяйте отдельные загрузки вручную. Отчёт: $ReportDir; журнал: $Journal"
}

Write-Host "`nВсе 15 источников перенесены: короткие подтверждены как short_video; длинные — как short_video или воспроизводимый вертикальный video fallback." -ForegroundColor Green
Write-Host "Журнал: $Journal" -ForegroundColor Green
```
