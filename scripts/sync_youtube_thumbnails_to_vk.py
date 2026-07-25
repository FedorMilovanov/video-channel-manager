#!/usr/bin/env python3
"""Copy the exact installed YouTube thumbnails to journaled VK video uploads.

The script never selects a frame or generates artwork. Dry-run downloads and
validates the exact source image bytes, builds a confirmed SHA-256 manifest, and
performs no VK mutation. Execute serializes writes through the VK community lock
and journals every attempt before and after the provider calls.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

from video_channel_manager.config import get_settings
from video_channel_manager.domain.enums import PlatformName
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.local_media.image_quality import ImageQualityError, ImageQualityReport, inspect_image
from video_channel_manager.platforms.vk import VkApiClient, VkTokenStore
from video_channel_manager.platforms.vk.lock import local_vk_write_lock
from video_channel_manager.platforms.vk.thumbnails import VkThumbnailWriter
from video_channel_manager.platforms.vk.writer import VkVideoWriter, VkWriteError

_SUCCESS_STATUS = "installed_youtube_thumbnail_copied_to_vk"


@dataclass(frozen=True, slots=True)
class ThumbnailCandidate:
    source_video_id: str
    title: str
    thumbnail_url: str
    remote_id: str


@dataclass(frozen=True, slots=True)
class PreparedThumbnail:
    candidate: ThumbnailCandidate
    path: Path
    quality: ImageQualityReport


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
    parser.add_argument("--confirm-manifest-sha256", help="Exact dry-run thumbnail manifest")
    parser.add_argument("--max-thumbnails", type=int, default=100)
    parser.add_argument("--max-image-bytes", type=int, default=25 * 1024 * 1024)
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
    if not isinstance(payload.get("uploads"), dict):
        raise ValueError("Transfer journal has no uploads map.")
    covers = payload.get("covers")
    if covers is not None and not isinstance(covers, dict):
        raise ValueError("Transfer journal covers must be an object when present.")
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
        owner_id = int(owner_text)
        video_id = int(video_text)
    except ValueError as exc:
        raise ValueError(f"Invalid VK video remote ID: {remote_id}") from exc
    if owner_id == 0 or video_id <= 0:
        raise ValueError(f"Invalid VK video remote ID: {remote_id}")
    return owner_id, video_id


def _thumbnail_extension(url: str, content_type: str) -> str:
    lowered = content_type.casefold()
    if "png" in lowered or url.casefold().split("?", 1)[0].endswith(".png"):
        return ".png"
    return ".jpg"


def _download_thumbnail(
    *,
    url: str,
    video_id: str,
    cache_dir: Path,
    max_image_bytes: int,
) -> Path:
    parsed = urlsplit(url.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"YouTube thumbnail URL is not absolute http(s): {url!r}")
    cache_dir.mkdir(parents=True, exist_ok=True)
    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    existing = sorted(
        path
        for path in cache_dir.glob(f"{video_id}-{url_hash}.*")
        if path.is_file() and path.suffix.casefold() in {".jpg", ".jpeg", ".png"} and path.stat().st_size > 0
    )
    if existing:
        inspect_image(existing[0], max_size_bytes=max_image_bytes)
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
            if len(response.content) > max_image_bytes:
                raise RuntimeError(
                    f"YouTube thumbnail is {len(response.content)} bytes, above limit {max_image_bytes}"
                )
            destination = cache_dir / f"{video_id}-{url_hash}{_thumbnail_extension(url, content_type)}"
            temporary = destination.with_suffix(destination.suffix + ".tmp")
            temporary.write_bytes(response.content)
            temporary.replace(destination)
            inspect_image(destination, max_size_bytes=max_image_bytes)
            return destination
        except (httpx.HTTPError, OSError, RuntimeError, ImageQualityError) as exc:
            last_error = exc
            if attempt + 1 < 4:
                time.sleep(delay_seconds)
                delay_seconds *= 2
    assert last_error is not None
    raise RuntimeError(f"Cannot download the installed YouTube thumbnail for {video_id}: {last_error}") from last_error


def _cover_complete(value: object) -> bool:
    return isinstance(value, dict) and value.get("status") == _SUCCESS_STATUS


def _candidates(source: AuditPackage, journal: dict[str, Any]) -> list[ThumbnailCandidate]:
    uploads = journal["uploads"]
    covers = journal.get("covers")
    completed_covers = covers if isinstance(covers, dict) else {}

    result: list[ThumbnailCandidate] = []
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
        if _cover_complete(completed_covers.get(source_id)):
            continue
        result.append(
            ThumbnailCandidate(
                source_video_id=source_id,
                title=video.title,
                thumbnail_url=thumbnail_url.strip(),
                remote_id=remote_id,
            )
        )
    result.sort(key=lambda item: item.source_video_id)
    if len({item.source_video_id for item in result}) != len(result):
        raise ValueError("Thumbnail candidate source IDs are not unique.")
    if len({item.remote_id for item in result}) != len(result):
        raise ValueError("Thumbnail candidate VK remote IDs are not unique.")
    return result


def _candidate_identity(candidates: list[ThumbnailCandidate]) -> list[dict[str, str]]:
    return [
        {
            "source_video_id": item.source_video_id,
            "remote_id": item.remote_id,
            "thumbnail_url": item.thumbnail_url,
        }
        for item in candidates
    ]


def _prepare(
    candidates: list[ThumbnailCandidate],
    *,
    cache_dir: Path,
    max_image_bytes: int,
) -> list[PreparedThumbnail]:
    prepared: list[PreparedThumbnail] = []
    for index, candidate in enumerate(candidates, start=1):
        print(f"  Fetch/QC [{index}/{len(candidates)}] {candidate.source_video_id} — {candidate.title}")
        path = _download_thumbnail(
            url=candidate.thumbnail_url,
            video_id=candidate.source_video_id,
            cache_dir=cache_dir,
            max_image_bytes=max_image_bytes,
        )
        quality = inspect_image(path, max_size_bytes=max_image_bytes)
        prepared.append(PreparedThumbnail(candidate=candidate, path=path, quality=quality))
    return prepared


def _manifest_sha256(prepared: list[PreparedThumbnail]) -> str:
    payload = [
        {
            "source_video_id": item.candidate.source_video_id,
            "remote_id": item.candidate.remote_id,
            "thumbnail_url": item.candidate.thumbnail_url,
            "image_sha256": item.quality.sha256,
            "image_size_bytes": item.quality.size_bytes,
            "image_format": item.quality.format,
            "width": item.quality.width,
            "height": item.quality.height,
        }
        for item in prepared
    ]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def main() -> int:
    args = _parser().parse_args()
    if args.write_delay < 0:
        raise SystemExit("--write-delay cannot be negative")
    if args.max_thumbnails <= 0:
        raise SystemExit("--max-thumbnails must be positive")
    if args.max_image_bytes <= 0:
        raise SystemExit("--max-image-bytes must be positive")

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
        f"  journaled VK uploads: {len(journal['uploads'])}\n"
        f"  thumbnails already completed: {sum(_cover_complete(value) for value in (journal.get('covers') or {}).values())}\n"
        f"  installed YouTube thumbnails to copy now: {len(candidates)}\n"
        f"  write delay: {args.write_delay:.2f}s"
    )
    if not candidates:
        print("Nothing to change; every eligible journaled video already has a completed cover record.")
        return 0

    prepared = _prepare(
        candidates,
        cache_dir=args.cache_dir,
        max_image_bytes=args.max_image_bytes,
    )
    manifest_sha256 = _manifest_sha256(prepared)
    print(f"  thumbnail manifest: {manifest_sha256}")

    if not args.execute:
        print("Dry-run only. Thumbnail bytes were cached and validated; no VK thumbnail was changed.")
        print(
            "Re-run with --execute and exact --confirm-community, --confirm-count, "
            "--confirm-source-snapshot, and --confirm-manifest-sha256 values."
        )
        return 0

    lock_path = settings.data_dir / "locks" / f"vk-{args.account}-{community_id}.lock"
    with local_vk_write_lock(
        lock_path,
        account=args.account,
        community_id=community_id,
        operation="sync-youtube-thumbnails-to-vk",
    ):
        locked_journal = _load_journal(args.journal, source=source, community_id=community_id)
        locked_candidates = _candidates(source, locked_journal)
        if _candidate_identity(locked_candidates) != _candidate_identity(candidates):
            raise RuntimeError("Thumbnail candidates changed after dry-run/preparation; generate a fresh manifest.")

        confirmations = {
            "community": str(args.confirm_community or "") == str(community_id),
            "count": args.confirm_count == len(prepared),
            "snapshot": str(args.confirm_source_snapshot or "") == str(source.snapshot_id),
            "manifest": str(args.confirm_manifest_sha256 or "") == manifest_sha256,
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
        covers = locked_journal.setdefault("covers", {})

        for index, item in enumerate(prepared, start=1):
            candidate = item.candidate
            owner_id, video_id = _parse_remote_id(candidate.remote_id)
            if owner_id != -community_id:
                raise RuntimeError(
                    f"Journaled VK video {candidate.remote_id} belongs to owner {owner_id}, expected {-community_id}."
                )
            if read_writer.read_video(owner_id=owner_id, video_id=video_id) is None:
                raise RuntimeError(
                    f"Journaled VK video {candidate.remote_id} is not visible; refusing to set its thumbnail."
                )

            previous = covers.get(candidate.source_video_id)
            covers[candidate.source_video_id] = {
                "source_video_id": candidate.source_video_id,
                "remote_id": candidate.remote_id,
                "source_thumbnail_url": candidate.thumbnail_url,
                "local_path": str(item.path.resolve()),
                "image_quality": item.quality.to_dict(),
                "manifest_sha256": manifest_sha256,
                "status": "thumbnail_upload_pending",
                "previous_attempt": previous if isinstance(previous, dict) else None,
                "started_at": datetime.now(UTC).isoformat(),
            }
            _save_journal(args.journal, locked_journal)

            print(f"[{index}/{len(prepared)}] Setting thumbnail on https://vk.com/video{candidate.remote_id}")
            try:
                result = thumbnail_writer.set_thumbnail(
                    owner_id=owner_id,
                    video_id=video_id,
                    path=item.path,
                )
                if read_writer.read_video(owner_id=owner_id, video_id=video_id) is None:
                    raise RuntimeError("Target VK video disappeared after thumbnail API call.")
            except BaseException as exc:
                covers[candidate.source_video_id].update(
                    {
                        "status": "thumbnail_upload_failed",
                        "error": f"{type(exc).__name__}: {exc}",
                        "failed_at": datetime.now(UTC).isoformat(),
                    }
                )
                _save_journal(args.journal, locked_journal)
                raise

            covers[candidate.source_video_id].update(
                {
                    "photo_id": result.get("photo_id"),
                    "photo_owner_id": result.get("photo_owner_id"),
                    "photo_hash": result.get("photo_hash"),
                    "status": _SUCCESS_STATUS,
                    "completed_at": datetime.now(UTC).isoformat(),
                    "target_visible_after_api_call": True,
                }
            )
            _save_journal(args.journal, locked_journal)
            print(f"[{index}/{len(prepared)}] Thumbnail API result journaled for https://vk.com/video{candidate.remote_id}")
            if index < len(prepared) and args.write_delay > 0:
                time.sleep(args.write_delay)

    print(f"Thumbnail synchronization completed: {len(prepared)} thumbnail(s) set and journaled.")
    print(f"Journal → {args.journal}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError, ImageQualityError, VkWriteError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
