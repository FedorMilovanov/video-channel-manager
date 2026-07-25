#!/usr/bin/env python3
"""Resume YouTube-to-VK uploads for an explicit allowlist of video IDs.

This recovery command intentionally bypasses fuzzy cross-platform matching. It can
only upload the exact YouTube IDs named by the operator, reuses verified journal
entries, requires completed MP4 files in the transfer cache, and journals every
successful VK upload atomically.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from video_channel_manager.config import get_settings
from video_channel_manager.domain.enums import PlatformName
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk import VkApiClient, VkTokenStore
from video_channel_manager.platforms.vk.writer import VkUploadTicket, VkVideoWriter, VkWriteError

_SITE_URL = "https://thelegendarypoet.ru/"
_SITE_FOOTER = (
    "🎧 The Legendary Poet — русская поэзия, музыка и литературные материалы.\n"
    f"🌐 {_SITE_URL}"
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="YouTube AuditPackage used for the transfer")
    parser.add_argument("video_ids", nargs="+", help="Exact YouTube video IDs allowed for this resume")
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--account", default="legendary-poet")
    parser.add_argument("--community", required=True)
    parser.add_argument("--processing-timeout", type=int, default=7200)
    parser.add_argument("--write-delay", type=float, default=3.0)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-community")
    parser.add_argument("--confirm-count", type=int)
    parser.add_argument("--confirm-source-snapshot")
    return parser


def _load_audit(path: Path) -> AuditPackage:
    try:
        return AuditPackage.model_validate(json.loads(path.read_text(encoding="utf-8-sig")))
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


def _save_journal(path: Path, journal: dict[str, Any]) -> None:
    journal["updated_at"] = datetime.now(UTC).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(journal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _parse_remote_id(remote_id: str) -> tuple[int, int]:
    owner_text, separator, video_text = remote_id.partition("_")
    if not separator:
        raise ValueError(f"Invalid VK video remote ID: {remote_id}")
    try:
        return int(owner_text), int(video_text)
    except ValueError as exc:
        raise ValueError(f"Invalid VK video remote ID: {remote_id}") from exc


def _published_title(source_title: str) -> str:
    title = " ".join(source_title.split())
    if "⚡" in title:
        return title
    if "🔥" in title:
        return title.replace("🔥", "⚡", 1)
    return f"{title} ⚡"


def _published_description(source_description: str) -> str:
    description = source_description.strip()
    if _SITE_URL in description:
        return description
    return f"{description}\n\n{_SITE_FOOTER}" if description else _SITE_FOOTER


def _media_path(cache_dir: Path, video_id: str) -> Path | None:
    exact = cache_dir / f"{video_id}.mp4"
    if exact.is_file() and exact.stat().st_size > 0:
        return exact
    candidates = sorted(
        path
        for path in cache_dir.glob(f"{video_id}*.mp4")
        if path.is_file() and path.stat().st_size > 0
    )
    return candidates[0] if candidates else None


def _unique_ids(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = raw.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def main() -> int:
    args = _parser().parse_args()
    if args.write_delay < 0:
        raise SystemExit("--write-delay cannot be negative")
    if args.processing_timeout <= 0:
        raise SystemExit("--processing-timeout must be positive")

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
    community = reader.get_community(args.community)
    community_id = int(community.ref.channel_id)
    if not bool(community.metadata.get("managed_by_token")):
        raise SystemExit("The authorized VK user is not reported as an administrator of this community.")

    journal = _load_journal(args.journal, source=source, community_id=community_id)
    writer = VkVideoWriter(
        token_store=store,
        account_alias=args.account,
        api_version=settings.vk_api_version,
    )
    uploads = journal.setdefault("uploads", {})
    source_videos = {video.ref.remote_id: video for video in source.videos}
    requested_ids = _unique_ids(args.video_ids)

    reusable: dict[str, str] = {}
    new_ids: list[str] = []
    missing_media: list[str] = []
    for source_id in requested_ids:
        video = source_videos.get(source_id)
        if video is None:
            raise ValueError(f"YouTube video {source_id} is absent from the source snapshot.")
        if video.privacy_status != "public":
            raise ValueError(f"YouTube video {source_id} is not public in the source snapshot.")
        if (video.duration_seconds or 0) <= 180:
            raise ValueError(f"YouTube video {source_id} is not a full-length candidate (>180 seconds).")

        existing = uploads.get(source_id)
        if isinstance(existing, dict) and isinstance(existing.get("remote_id"), str):
            remote_id = str(existing["remote_id"])
            owner_id, video_id = _parse_remote_id(remote_id)
            if writer.read_video(owner_id=owner_id, video_id=video_id) is not None:
                reusable[source_id] = remote_id
                continue

        new_ids.append(source_id)
        if _media_path(args.cache_dir, source_id) is None:
            missing_media.append(source_id)

    print(
        "Exact-ID YouTube → VK resume preflight:\n"
        f"  source snapshot: {source.snapshot_id}\n"
        f"  target community: {community_id} — {community.title}\n"
        f"  explicitly allowed IDs: {len(requested_ids)}\n"
        f"  verified journal uploads to reuse: {len(reusable)}\n"
        f"  new VK uploads required: {len(new_ids)}\n"
        f"  required MP4 files missing from cache: {len(missing_media)}\n"
        f"  write delay: {args.write_delay:.2f}s"
    )
    for source_id in requested_ids:
        state = f"reuse {reusable[source_id]}" if source_id in reusable else "upload"
        media = _media_path(args.cache_dir, source_id)
        suffix = f" — cache {media.name}" if media is not None else " — CACHE MISSING"
        print(f"  {source_id}: {state}{suffix}")

    if missing_media:
        raise SystemExit("Missing prefetched MP4 files: " + ", ".join(missing_media))

    if not args.execute:
        print("Dry-run only. No remote write method was called.")
        print(
            "Re-run with --execute and exact --confirm-community, --confirm-count, "
            "and --confirm-source-snapshot values."
        )
        return 0

    confirmations = {
        "community": str(args.confirm_community or "") == str(community_id),
        "count": args.confirm_count == len(new_ids),
        "snapshot": str(args.confirm_source_snapshot or "") == str(source.snapshot_id),
    }
    failed = [name for name, valid in confirmations.items() if not valid]
    if failed:
        raise SystemExit(f"Execution confirmation mismatch: {', '.join(failed)}")

    for index, source_id in enumerate(requested_ids, start=1):
        if source_id in reusable:
            print(f"[{index}/{len(requested_ids)}] Reusing verified journal upload {reusable[source_id]}")
            continue

        source_video = source_videos[source_id]
        media_path = _media_path(args.cache_dir, source_id)
        assert media_path is not None
        title = _published_title(source_video.title)
        description = _published_description(source_video.description)
        print(f"[{index}/{len(requested_ids)}] Uploading {media_path.name} — {title}")
        ticket: VkUploadTicket = writer.begin_upload(
            community_id=community_id,
            title=title,
            description=description,
        )
        upload_response = writer.upload_file(ticket, media_path)
        processed = writer.wait_until_available(ticket, timeout_seconds=args.processing_timeout)
        uploads[source_id] = {
            "source_video_id": source_id,
            "remote_id": ticket.remote_id,
            "source_title": source_video.title,
            "published_title": title,
            "site_url": _SITE_URL,
            "media_path": str(media_path),
            "upload_response": upload_response,
            "vk_type": processed.get("type"),
            "status": "uploaded_and_verified",
            "resume_mode": "explicit_id_allowlist",
        }
        _save_journal(args.journal, journal)
        print(f"[{index}/{len(requested_ids)}] Verified https://vk.com/video{ticket.remote_id}")
        if index < len(requested_ids) and args.write_delay > 0:
            time.sleep(args.write_delay)

    print(f"Exact-ID resume completed: {len(new_ids)} new video(s) uploaded; {len(reusable)} reused.")
    print(f"Journal → {args.journal}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, VkWriteError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
