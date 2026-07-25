#!/usr/bin/env python3
"""Resume YouTube-to-VK uploads for an explicit allowlist of video IDs.

The command bypasses fuzzy matching and can write only the exact YouTube IDs
named by the operator. It reuses visible journaled uploads, requires verified
local MP4 files for new uploads, renders VK-native plain text, records media
fingerprints, and serializes all VK writes through the community lock.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ContextManager

from pydantic import ValidationError

from video_channel_manager.config import get_settings
from video_channel_manager.domain.enums import PlatformName
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.local_media.quality import MediaQualityError, MediaQualityReport, probe_media
from video_channel_manager.platforms.vk import VkApiClient, VkTokenStore
from video_channel_manager.platforms.vk.lock import local_vk_write_lock
from video_channel_manager.platforms.vk.publishing import VkPublicationText, render_vk_publication
from video_channel_manager.platforms.vk.writer import VkUploadTicket, VkVideoWriter, VkWriteError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="YouTube AuditPackage used for the transfer")
    parser.add_argument("video_ids", nargs="+", help="Exact YouTube video IDs allowed for this resume")
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--account", default="legendary-poet")
    parser.add_argument("--community", required=True)
    parser.add_argument("--processing-timeout", type=int, default=7200)
    parser.add_argument("--media-qc-timeout", type=float, default=180.0)
    parser.add_argument("--write-delay", type=float, default=3.0)
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--max-videos", type=int, default=50)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-community")
    parser.add_argument("--confirm-count", type=int)
    parser.add_argument("--confirm-source-snapshot")
    parser.add_argument("--confirm-manifest-sha256")
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
    uploads = payload.get("uploads")
    if not isinstance(uploads, dict):
        raise ValueError("Transfer journal uploads must be an object.")
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
        raise ValueError(f"Invalid VK remote ID: {remote_id}")
    try:
        return int(owner_text), int(video_text)
    except ValueError as exc:
        raise ValueError(f"Invalid VK remote ID: {remote_id}") from exc


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
    if not result:
        raise ValueError("At least one nonblank YouTube video ID is required.")
    return result


def _manifest_sha256(
    video_ids: list[str],
    *,
    publications: dict[str, VkPublicationText],
    media_reports: dict[str, MediaQualityReport],
) -> str:
    payload = [
        {
            "source_video_id": video_id,
            "title": publications[video_id].title,
            "description_sha256": publications[video_id].description_sha256,
            "policy_version": publications[video_id].policy_version,
            "media_sha256": media_reports[video_id].sha256,
            "media_size_bytes": media_reports[video_id].size_bytes,
            "media_duration_seconds": media_reports[video_id].duration_seconds,
        }
        for video_id in video_ids
    ]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _write_lock_context(
    *,
    execute: bool,
    data_dir: Path,
    account: str,
    community_id: int,
) -> ContextManager[None]:
    if not execute:
        return nullcontext()
    lock_path = data_dir / "locks" / f"vk-{account}-{community_id}.lock"
    return local_vk_write_lock(
        lock_path,
        account=account,
        community_id=community_id,
        operation="resume-youtube-to-vk-exact-ids",
    )


def main() -> int:
    args = _parser().parse_args()
    if args.write_delay < 0:
        raise SystemExit("--write-delay cannot be negative")
    if args.processing_timeout <= 0:
        raise SystemExit("--processing-timeout must be positive")
    if args.media_qc_timeout <= 0:
        raise SystemExit("--media-qc-timeout must be positive")
    if args.max_videos <= 0:
        raise SystemExit("--max-videos must be positive")

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

    requested_ids = _unique_ids(args.video_ids)
    if len(requested_ids) > args.max_videos:
        raise SystemExit(f"Requested count {len(requested_ids)} exceeds --max-videos {args.max_videos}.")
    source_videos = {video.ref.remote_id: video for video in source.videos}
    publications: dict[str, VkPublicationText] = {}
    for source_id in requested_ids:
        video = source_videos.get(source_id)
        if video is None:
            raise ValueError(f"YouTube video {source_id} is absent from the source snapshot.")
        if video.privacy_status != "public":
            raise ValueError(f"YouTube video {source_id} is not public in the source snapshot.")
        if (video.duration_seconds or 0) <= 180:
            raise ValueError(f"YouTube video {source_id} is not a full-length candidate (>180 seconds).")
        publications[source_id] = render_vk_publication(video.title, video.description)

    with _write_lock_context(
        execute=args.execute,
        data_dir=settings.data_dir,
        account=args.account,
        community_id=community_id,
    ):
        journal = _load_journal(args.journal, source=source, community_id=community_id)
        uploads = journal["uploads"]
        writer = VkVideoWriter(
            token_store=store,
            account_alias=args.account,
            api_version=settings.vk_api_version,
        )

        reusable: dict[str, str] = {}
        new_ids: list[str] = []
        media_paths: dict[str, Path] = {}
        missing_media: list[str] = []
        for source_id in requested_ids:
            existing = uploads.get(source_id)
            if isinstance(existing, dict) and isinstance(existing.get("remote_id"), str):
                remote_id = str(existing["remote_id"])
                owner_id, video_id = _parse_remote_id(remote_id)
                if owner_id != -community_id:
                    raise ValueError(
                        f"Journal upload {source_id} targets owner {owner_id}, expected {-community_id}."
                    )
                if writer.read_video(owner_id=owner_id, video_id=video_id) is not None:
                    reusable[source_id] = remote_id
                    continue

            new_ids.append(source_id)
            media_path = _media_path(args.cache_dir, source_id)
            if media_path is None:
                missing_media.append(source_id)
            else:
                media_paths[source_id] = media_path

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
            media = media_paths.get(source_id)
            suffix = f" — cache {media.name}" if media is not None else " — CACHE MISSING"
            print(f"  {source_id}: {state}{suffix}")

        if missing_media:
            raise SystemExit("Missing prefetched MP4 files: " + ", ".join(missing_media))

        media_reports: dict[str, MediaQualityReport] = {}
        for index, source_id in enumerate(new_ids, start=1):
            media_path = media_paths[source_id]
            print(f"  QC [{index}/{len(new_ids)}] {media_path.name}")
            media_reports[source_id] = probe_media(
                media_path,
                ffprobe=args.ffprobe,
                timeout_seconds=args.media_qc_timeout,
            )
        manifest_sha256 = _manifest_sha256(
            new_ids,
            publications=publications,
            media_reports=media_reports,
        )
        print(f"  transfer manifest: {manifest_sha256}")

        if not args.execute:
            print("Dry-run only. No remote write method was called.")
            print(
                "Re-run with --execute and exact --confirm-community, --confirm-count, "
                "--confirm-source-snapshot, and --confirm-manifest-sha256 values."
            )
            return 0

        confirmations = {
            "community": str(args.confirm_community or "") == str(community_id),
            "count": args.confirm_count == len(new_ids),
            "snapshot": str(args.confirm_source_snapshot or "") == str(source.snapshot_id),
            "manifest": str(args.confirm_manifest_sha256 or "") == manifest_sha256,
        }
        failed = [name for name, valid in confirmations.items() if not valid]
        if failed:
            raise SystemExit(f"Execution confirmation mismatch: {', '.join(failed)}")

        for index, source_id in enumerate(requested_ids, start=1):
            if source_id in reusable:
                print(f"[{index}/{len(requested_ids)}] Reusing verified journal upload {reusable[source_id]}")
                continue

            source_video = source_videos[source_id]
            publication = publications[source_id]
            media_path = media_paths[source_id]
            media_report = media_reports[source_id]
            previous = uploads.get(source_id)
            superseded_remote_id = (
                str(previous.get("remote_id"))
                if isinstance(previous, dict) and isinstance(previous.get("remote_id"), str)
                else None
            )
            print(f"[{index}/{len(requested_ids)}] Uploading {media_path.name} — {publication.title}")
            ticket: VkUploadTicket = writer.begin_upload(
                community_id=community_id,
                title=publication.title,
                description=publication.description,
            )
            uploads[source_id] = {
                "source_video_id": source_id,
                "remote_id": ticket.remote_id,
                "superseded_remote_id": superseded_remote_id,
                "source_title": source_video.title,
                "published_title": publication.title,
                "description_sha256": publication.description_sha256,
                "publication_policy_version": publication.policy_version,
                "media_path": str(media_path.resolve()),
                "media_quality": media_report.to_dict(),
                "status": "upload_reserved",
                "resume_mode": "explicit_id_allowlist",
                "reserved_at": datetime.now(UTC).isoformat(),
            }
            _save_journal(args.journal, journal)

            try:
                upload_response = writer.upload_file(ticket, media_path)
                uploads[source_id]["upload_response"] = upload_response
                uploads[source_id]["status"] = "uploaded_processing"
                _save_journal(args.journal, journal)
                processed = writer.wait_until_available(ticket, timeout_seconds=args.processing_timeout)
            except BaseException as exc:
                uploads[source_id]["status"] = "failed"
                uploads[source_id]["error"] = f"{type(exc).__name__}: {exc}"
                uploads[source_id]["failed_at"] = datetime.now(UTC).isoformat()
                _save_journal(args.journal, journal)
                raise

            uploads[source_id].update(
                {
                    "vk_type": processed.get("type"),
                    "status": "uploaded_and_verified",
                    "verified_at": datetime.now(UTC).isoformat(),
                }
            )
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
    except (OSError, RuntimeError, ValueError, MediaQualityError, VkWriteError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
