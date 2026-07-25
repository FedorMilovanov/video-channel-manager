#!/usr/bin/env python3
"""Copy the already-set YouTube thumbnails to journaled VK video uploads.

The script never selects a frame or generates artwork. It downloads each video's
current AuditPackage.thumbnail_url and sets those exact image bytes as the VK
video thumbnail. The default run is a read-only preflight.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

from video_channel_manager.config import get_settings
from video_channel_manager.domain.enums import PlatformName
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk import VkApiClient, VkTokenStore
from video_channel_manager.platforms.vk.thumbnails import VkThumbnailWriter
from video_channel_manager.platforms.vk.writer import VkVideoWriter, VkWriteError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="YouTube AuditPackage used for the video transfer")
    parser.add_argument("--journal", type=Path, required=True, help="Existing YouTube-to-VK transfer journal")
    parser.add_argument("--account", default="legendary-poet", help="Local VK token alias")
    parser.add_argument("--community", required=True, help="Exact VK community ID or screen name")
    parser.add_argument("--cache-dir", type=Path, default=Path("data/cache/vk-thumbnails"))
    parser.add_argument("--execute", action="store_true", help="Set the thumbnails in VK")
    parser.add_argument("--confirm-community", help="Exact numeric community ID required with --execute")
    parser.add_argument("--confirm-count", type=int, help="Exact current thumbnail candidate count")
    parser.add_argument("--confirm-source-snapshot", help="Exact source snapshot UUID")
    parser.add_argument("--max-thumbnails", type=int, default=100)
    parser.add_argument("--write-delay", type=float, default=3.0)
    return parser


def _load_audit(path: Path) -> AuditPackage:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        return AuditPackage.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"Cannot read AuditPackage {path}: {exc}") from exc


def _load_journal(path: Path, *, source: AuditPackage, community_id: int) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read transfer journal {path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_name") != "video-manager.youtube-vk-sync-journal":
        raise ValueError(f"Unexpected transfer journal schema: {path}")
    if payload.get("source_snapshot_id") != str(source.snapshot_id):
        raise ValueError("Transfer journal belongs to a different YouTube snapshot.")
    if payload.get("community_id") != community_id:
        raise ValueError("Transfer journal belongs to a different VK community.")
    return payload


def _atomic_write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _save_journal(path: Path, journal: dict[str, Any]) -> None:
    journal["updated_at"] = datetime.now(UTC).isoformat()
    _atomic_write(path, journal)


def _parse_remote_id(remote_id: str) -> tuple[int, int]:
    owner_text, separator, video_text = remote_id.partition("_")
    if not separator:
        raise ValueError(f"Invalid VK video remote ID: {remote_id}")
    try:
        return int(owner_text), int(video_text)
    except ValueError as exc:
        raise ValueError(f"Invalid VK video remote ID: {remote_id}") from exc


def _thumbnail_extension(url: str, content_type: str) -> str:
    lowered = content_type.casefold()
    if "png" in lowered or url.casefold().split("?", 1)[0].endswith(".png"):
        return ".png"
    return ".jpg"


def _download_thumbnail(*, url: str, video_id: str, cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(
        path
        for path in cache_dir.glob(f"{video_id}.*")
        if path.is_file() and path.suffix.casefold() in {".jpg", ".jpeg", ".png"} and path.stat().st_size > 0
    )
    if existing:
        return existing[0]

    delay_seconds = 1.0
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            with httpx.Client(timeout=120.0, follow_redirects=True) as client:
                response = client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 video-channel-manager/0.1",
                        "Referer": "https://www.youtube.com/",
                    },
                )
            response.raise_for_status()
            content_type = response.headers.get("content-type", "image/jpeg")
            if not content_type.casefold().startswith("image/"):
                raise RuntimeError(f"YouTube thumbnail returned unexpected content type {content_type!r}")
            if not response.content:
                raise RuntimeError("YouTube thumbnail response was empty")
            destination = cache_dir / f"{video_id}{_thumbnail_extension(url, content_type)}"
            destination.write_bytes(response.content)
            return destination
        except (httpx.HTTPError, OSError, RuntimeError) as exc:
            last_error = exc
            if attempt + 1 < 4:
                time.sleep(delay_seconds)
                delay_seconds *= 2
    assert last_error is not None
    raise RuntimeError(f"Cannot download the installed YouTube thumbnail for {video_id}: {last_error}") from last_error


def _candidates(source: AuditPackage, journal: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    uploads = journal.get("uploads")
    covers = journal.get("covers")
    if not isinstance(uploads, dict):
        raise ValueError("Transfer journal has no uploads map.")
    completed_covers = covers if isinstance(covers, dict) else {}

    result: list[tuple[str, str, str, str]] = []
    for video in source.videos:
        source_id = video.ref.remote_id
        upload = uploads.get(source_id)
        if not isinstance(upload, dict):
            continue
        remote_id = upload.get("remote_id")
        if not isinstance(remote_id, str):
            continue
        thumbnail_url = video.thumbnail_url
        if not isinstance(thumbnail_url, str) or not thumbnail_url.strip():
            continue
        if source_id in completed_covers:
            continue
        result.append((source_id, video.title, thumbnail_url, remote_id))
    result.sort(key=lambda item: item[0])
    return result


def main() -> int:
    args = _parser().parse_args()
    if args.write_delay < 0:
        raise SystemExit("--write-delay cannot be negative")

    settings = get_settings()
    source = _load_audit(args.source)
    if source.channel.ref.platform != PlatformName.YOUTUBE:
        raise SystemExit("The source AuditPackage must be YouTube.")

    store = VkTokenStore(settings.data_dir)
    reader = VkApiClient(
        token_store=store,
        account_alias=args.account,
        api_version=settings.vk_api_version,
    )
    community_record = reader.get_community(args.community)
    community_id = int(community_record.ref.channel_id)
    if not bool(community_record.metadata.get("managed_by_token")):
        raise SystemExit("The authorized VK user is not reported as an administrator of this community.")

    journal = _load_journal(args.journal, source=source, community_id=community_id)
    candidates = _candidates(source, journal)
    if len(candidates) > args.max_thumbnails:
        raise SystemExit(f"Thumbnail candidate count {len(candidates)} exceeds --max-thumbnails {args.max_thumbnails}.")

    print(
        "YouTube → VK thumbnail preflight:\n"
        f"  source snapshot: {source.snapshot_id}\n"
        f"  target community: {community_id} — {community_record.title}\n"
        f"  journaled VK uploads: {len(journal.get('uploads', {}))}\n"
        f"  thumbnails already completed: {len(journal.get('covers', {}))}\n"
        f"  installed YouTube thumbnails to copy now: {len(candidates)}\n"
        f"  write delay: {args.write_delay:.2f}s"
    )

    if not args.execute:
        print("Dry-run only. No thumbnail was changed in VK.")
        print(
            "Re-run with --execute and exact --confirm-community, --confirm-count, "
            "and --confirm-source-snapshot values."
        )
        return 0

    confirmations = {
        "community": str(args.confirm_community or "") == str(community_id),
        "count": args.confirm_count == len(candidates),
        "snapshot": str(args.confirm_source_snapshot or "") == str(source.snapshot_id),
    }
    failed = [name for name, valid in confirmations.items() if not valid]
    if failed:
        raise SystemExit(f"Execution confirmation mismatch: {', '.join(failed)}")

    read_writer = VkVideoWriter(
        token_store=store,
        account_alias=args.account,
        api_version=settings.vk_api_version,
    )
    thumbnail_writer = VkThumbnailWriter(
        token_store=store,
        account_alias=args.account,
        api_version=settings.vk_api_version,
    )
    covers = journal.setdefault("covers", {})

    for index, (source_id, title, thumbnail_url, remote_id) in enumerate(candidates, start=1):
        owner_id, video_id = _parse_remote_id(remote_id)
        if read_writer.read_video(owner_id=owner_id, video_id=video_id) is None:
            raise RuntimeError(f"Journaled VK video {remote_id} is not visible; refusing to set its thumbnail.")

        print(f"[{index}/{len(candidates)}] Downloading installed thumbnail — {title}")
        image_path = _download_thumbnail(
            url=thumbnail_url,
            video_id=source_id,
            cache_dir=args.cache_dir,
        )
        print(f"[{index}/{len(candidates)}] Setting thumbnail on https://vk.com/video{remote_id}")
        result = thumbnail_writer.set_thumbnail(
            owner_id=owner_id,
            video_id=video_id,
            path=image_path,
        )
        covers[source_id] = {
            "source_video_id": source_id,
            "remote_id": remote_id,
            "source_thumbnail_url": thumbnail_url,
            "local_path": str(image_path),
            "photo_id": result.get("photo_id"),
            "photo_owner_id": result.get("photo_owner_id"),
            "photo_hash": result.get("photo_hash"),
            "status": "installed_youtube_thumbnail_copied_to_vk",
        }
        _save_journal(args.journal, journal)
        print(f"[{index}/{len(candidates)}] Thumbnail confirmed for https://vk.com/video{remote_id}")
        if index < len(candidates) and args.write_delay > 0:
            time.sleep(args.write_delay)

    print(f"Thumbnail synchronization completed: {len(candidates)} thumbnail(s) set.")
    print(f"Journal → {args.journal}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError, VkWriteError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
