#!/usr/bin/env python3
"""Internal YouTube→VK synchronization engine.

This module contains the shared guarded workflow and is intentionally not a
standalone provider entrypoint. A supported caller must supply one immutable
``SyncRuntime`` with exact project/source/community identity plus explicit text
rendering and media-download dependencies.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from pydantic import ValidationError

from video_channel_manager.application.cross_platform import (
    CrossPlatformComparison,
    compare_audit_packages,
    normalize_title,
)
from video_channel_manager.config import get_settings
from video_channel_manager.domain.enums import PlatformName
from video_channel_manager.editorial._project_profiles import PROJECT_KEYS
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk import VkApiClient, VkInventoryService, VkTokenStore
from video_channel_manager.platforms.vk.upload_lifecycle import (
    UploadStage,
    VkUploadReadiness,
    ensure_upload_record,
    execute_upload_operation,
    ticket_from_record,
)
from video_channel_manager.platforms.vk.writer import VkVideoWriter, VkWriteError


class MediaDownloader(Protocol):
    def __call__(self, *, yt_dlp: str, video_id: str, cache_dir: Path) -> Path: ...


@dataclass(frozen=True, slots=True)
class SyncRuntime:
    project_key: str
    expected_source_channel_id: str
    expected_community_id: int
    render_title: Callable[[str], str]
    render_description: Callable[[str], str]
    download_media: MediaDownloader

    def __post_init__(self) -> None:
        if self.project_key not in PROJECT_KEYS:
            raise ValueError(f"Unsupported sync project_key: {self.project_key}")
        if not self.expected_source_channel_id.strip():
            raise ValueError("Sync runtime requires expected_source_channel_id")
        if self.expected_community_id <= 0:
            raise ValueError("Sync runtime requires a positive expected_community_id")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Fresh YouTube AuditPackage JSON")
    parser.add_argument("--account", default="legendary-poet", help="Local VK token alias")
    parser.add_argument("--community", required=True, help="Exact VK community ID or screen name")
    parser.add_argument(
        "--scope",
        choices=("full-length", "all-public"),
        default="full-length",
        help="full-length transfers public videos over 180 seconds; all-public includes shorter candidates",
    )
    parser.add_argument(
        "--phase",
        choices=("videos", "albums", "all"),
        default="all",
        help="videos uploads only; albums organizes albums only; all performs both phases",
    )
    parser.add_argument("--cache-dir", type=Path, default=Path("data/cache/vk-transfer"))
    parser.add_argument("--journal", type=Path, default=Path("data/reports/youtube-vk-sync-journal.json"))
    parser.add_argument("--result-output", type=Path)
    parser.add_argument("--execute", action="store_true", help="Perform the guarded remote writes")
    parser.add_argument("--confirm-community", help="Exact numeric community ID required with --execute")
    parser.add_argument("--confirm-count", type=int, help="Exact current transfer candidate count")
    parser.add_argument("--confirm-ambiguous", type=int, help="Exact current ambiguous match count")
    parser.add_argument("--confirm-source-snapshot", help="Exact source snapshot UUID")
    parser.add_argument("--max-videos", type=int, default=100)
    parser.add_argument("--processing-timeout", type=int, default=3600)
    parser.add_argument(
        "--write-delay",
        type=float,
        default=1.0,
        help="Pause in seconds after successful remote mutations",
    )
    parser.add_argument("--yt-dlp", default="yt-dlp", help="yt-dlp executable name or path")
    return parser


def load_audit(path: Path) -> AuditPackage:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        return AuditPackage.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"Cannot read AuditPackage {path}: {exc}") from exc


def _atomic_write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(serialized)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    try:
        directory_fd = os.open(path.parent, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(directory_fd)
    except OSError:
        pass
    finally:
        os.close(directory_fd)


def _load_journal(path: Path, *, source: AuditPackage, community_id: int) -> dict[str, Any]:
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema_name") != "video-manager.youtube-vk-sync-journal":
            raise ValueError(f"Unexpected journal schema: {path}")
        raw_version = payload.get("schema_version", 2)
        if not isinstance(raw_version, int) or raw_version not in {2, 3}:
            raise ValueError(f"Unsupported journal version {raw_version!r}: {path}")
        if payload.get("source_snapshot_id") != str(source.snapshot_id):
            raise ValueError("Existing journal belongs to a different YouTube snapshot.")
        if payload.get("community_id") != community_id:
            raise ValueError("Existing journal belongs to a different VK community.")
        payload["schema_version"] = 3
        return payload
    return {
        "schema_name": "video-manager.youtube-vk-sync-journal",
        "schema_version": 3,
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
        "source_snapshot_id": str(source.snapshot_id),
        "community_id": community_id,
        "albums": {},
        "placements": {},
        "uploads": {},
        "unsupported_album_descriptions": {},
        "completed_phases": [],
    }


def _save_journal(path: Path, journal: dict[str, Any]) -> None:
    journal["updated_at"] = datetime.now(UTC).isoformat()
    _atomic_write(path, journal)


def _parse_vk_remote_id(remote_id: str) -> tuple[int, int]:
    owner_text, separator, video_text = remote_id.partition("_")
    if not separator:
        raise ValueError(f"Invalid VK video remote ID: {remote_id}")
    try:
        return int(owner_text), int(video_text)
    except ValueError as exc:
        raise ValueError(f"Invalid VK video remote ID: {remote_id}") from exc


def _transfer_candidates(comparison: CrossPlatformComparison, *, scope: str) -> list[str]:
    candidates = []
    for item in comparison.missing_on_target:
        if item.privacy_status != "public":
            continue
        if scope == "full-length" and (item.duration_seconds or 0) <= 180:
            continue
        candidates.append(item.ref.remote_id)
    return sorted(candidates)


def _source_memberships(source: AuditPackage) -> dict[str, list[str]]:
    collection_titles = {item.ref.remote_id: item.title for item in source.collections}
    result: dict[str, list[str]] = {}
    for membership in source.memberships:
        title = collection_titles.get(membership.collection_ref.remote_id)
        if title is None:
            continue
        result.setdefault(membership.video_ref.remote_id, []).append(title)
    for titles in result.values():
        titles.sort(key=str.casefold)
    return result


def _minimum_duration_seconds(source_duration_seconds: int | None) -> int:
    if source_duration_seconds is None or source_duration_seconds <= 0:
        return 1
    tolerance = max(5, min(30, round(source_duration_seconds * 0.02)))
    return max(1, source_duration_seconds - tolerance)


def _pause(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)


def resolve_executable(value: str) -> str:
    path = shutil.which(value)
    if path is None:
        candidate = Path(value)
        if candidate.is_file():
            return str(candidate)
        raise ValueError(f"Required executable not found: {value}")
    return path


def download_media_file(*, yt_dlp: str, video_id: str, cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(path for path in cache_dir.glob(f"{video_id}.*") if path.is_file() and path.suffix != ".part")
    mp4 = next((path for path in existing if path.suffix.lower() == ".mp4"), None)
    if mp4 is not None:
        return mp4

    output_template = str(cache_dir / f"{video_id}.%(ext)s")
    command = [
        yt_dlp,
        "--no-playlist",
        "--no-progress",
        "--newline",
        "--merge-output-format",
        "mp4",
        "--remux-video",
        "mp4",
        "--format",
        "bv*+ba/b",
        "--output",
        output_template,
        "--print",
        "after_move:filepath",
        f"https://www.youtube.com/watch?v={video_id}",
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8")
    if completed.returncode != 0:
        stderr = completed.stderr.strip()[-2000:]
        raise RuntimeError(f"yt-dlp failed for {video_id}: {stderr}")
    reported_paths = [Path(line.strip()) for line in completed.stdout.splitlines() if line.strip()]
    for path in reversed(reported_paths):
        if path.is_file():
            return path
    created = sorted(path for path in cache_dir.glob(f"{video_id}.*") if path.is_file() and path.suffix != ".part")
    if not created:
        raise RuntimeError(f"yt-dlp did not produce a media file for {video_id}")
    return created[-1]


def _album_map_from_live(live: AuditPackage) -> dict[str, int]:
    result: dict[str, int] = {}
    for collection in live.collections:
        if bool(collection.metadata.get("is_system")):
            continue
        try:
            album_id = int(collection.ref.remote_id)
        except ValueError:
            continue
        result[normalize_title(collection.title)] = album_id
    return result


def _ensure_albums(
    *,
    source: AuditPackage,
    comparison: CrossPlatformComparison,
    community_id: int,
    writer: VkVideoWriter,
    album_map: dict[str, int],
    journal: dict[str, Any],
    journal_path: Path,
    write_delay: float,
) -> None:
    source_collections = {item.ref.remote_id: item for item in source.collections}
    albums = journal.setdefault("albums", {})
    descriptions = journal.setdefault("unsupported_album_descriptions", {})
    for gap in comparison.collection_gaps:
        normalized = normalize_title(gap.source_title)
        album_id = album_map.get(normalized)
        if album_id is None:
            saved = albums.get(gap.source_collection_id)
            if isinstance(saved, dict) and isinstance(saved.get("album_id"), int):
                album_id = int(saved["album_id"])
            else:
                album_id = writer.create_album(community_id=community_id, title=gap.source_title)
                albums[gap.source_collection_id] = {
                    "album_id": album_id,
                    "title": gap.source_title,
                    "status": "created",
                }
                _save_journal(journal_path, journal)
                _pause(write_delay)
            album_map[normalized] = album_id
        source_collection = source_collections.get(gap.source_collection_id)
        if source_collection is not None and source_collection.description.strip():
            descriptions[gap.source_collection_id] = {
                "title": source_collection.title,
                "description": source_collection.description,
                "reason": "VK video albums have no description field in API 5.199",
            }
    _save_journal(journal_path, journal)


def _place_existing_videos(
    *,
    comparison: CrossPlatformComparison,
    community_id: int,
    writer: VkVideoWriter,
    album_map: dict[str, int],
    journal: dict[str, Any],
    journal_path: Path,
    write_delay: float,
) -> None:
    placements = journal.setdefault("placements", {})
    for gap in comparison.collection_gaps:
        album_id = album_map[normalize_title(gap.source_title)]
        for remote_id in gap.missing_target_video_ids:
            key = f"{remote_id}:{album_id}"
            if key in placements:
                continue
            owner_id, video_id = _parse_vk_remote_id(remote_id)
            added = writer.add_to_album(
                community_id=community_id,
                album_id=album_id,
                owner_id=owner_id,
                video_id=video_id,
            )
            placements[key] = {
                "remote_id": remote_id,
                "album_id": album_id,
                "album_title": gap.source_title,
                "status": "added" if added else "already_present",
            }
            _save_journal(journal_path, journal)
            if added:
                _pause(write_delay)


def _media_path_for_stage(
    *,
    record: dict[str, Any],
    source_id: str,
    yt_dlp: str,
    cache_dir: Path,
    runtime: SyncRuntime,
) -> Path | None:
    stage = UploadStage(str(record["stage"]))
    if stage not in {
        UploadStage.PLANNED,
        UploadStage.MEDIA_VERIFIED,
        UploadStage.RESERVATION_INTENT_COMMITTED,
        UploadStage.RESERVED,
    }:
        return None
    media = record.get("media")
    if isinstance(media, dict):
        raw_path = media.get("path")
        if isinstance(raw_path, str):
            stored_path = Path(raw_path)
            if stored_path.is_file():
                return stored_path
    return runtime.download_media(yt_dlp=yt_dlp, video_id=source_id, cache_dir=cache_dir)


def _upload_candidates(
    *,
    source: AuditPackage,
    candidate_ids: list[str],
    community_id: int,
    writer: VkVideoWriter,
    album_map: dict[str, int],
    journal: dict[str, Any],
    journal_path: Path,
    memberships: dict[str, list[str]],
    yt_dlp: str,
    cache_dir: Path,
    processing_timeout: int,
    place_in_albums: bool,
    write_delay: float,
    runtime: SyncRuntime,
) -> None:
    source_videos = {item.ref.remote_id: item for item in source.videos}
    uploads = journal.setdefault("uploads", {})
    placements = journal.setdefault("placements", {})

    for index, source_id in enumerate(candidate_ids, start=1):
        source_video = source_videos[source_id]
        published_title = runtime.render_title(source_video.title)
        published_description = runtime.render_description(source_video.description)
        readiness = VkUploadReadiness(
            expected_title=published_title,
            minimum_duration_seconds=_minimum_duration_seconds(source_video.duration_seconds),
            allowed_types=("video",),
            require_playable=True,
        )
        existing = uploads.get(source_id)
        record, changed = ensure_upload_record(
            existing if isinstance(existing, dict) else None,
            source_snapshot_id=str(source.snapshot_id),
            community_id=community_id,
            source_video_id=source_id,
            source_title=source_video.title,
            source_duration_seconds=source_video.duration_seconds,
            published_title=published_title,
            published_description=published_description,
            readiness=readiness,
        )
        uploads[source_id] = record
        if changed:
            _save_journal(journal_path, journal)

        initial_stage = UploadStage(str(record["stage"]))
        media_path = _media_path_for_stage(
            record=record,
            source_id=source_id,
            yt_dlp=yt_dlp,
            cache_dir=cache_dir,
            runtime=runtime,
        )
        if media_path is not None:
            print(f"[{index}/{len(candidate_ids)}] Media ready {source_id} — {media_path.name}")
        else:
            print(f"[{index}/{len(candidate_ids)}] Reconciling {source_id} from stage {initial_stage.value}")

        execute_upload_operation(
            record,
            writer=writer,
            community_id=community_id,
            title=published_title,
            description=published_description,
            media_path=media_path,
            readiness=readiness,
            processing_timeout=processing_timeout,
            persist=lambda: _save_journal(journal_path, journal),
        )
        if UploadStage(str(record["stage"])) != UploadStage.VERIFIED:
            raise RuntimeError(f"Upload operation did not reach verified stage: {source_id}")
        ticket = ticket_from_record(record)
        if initial_stage == UploadStage.VERIFIED:
            print(f"[{index}/{len(candidate_ids)}] Verified journal no-op {ticket.remote_id}")
        else:
            print(f"[{index}/{len(candidate_ids)}] Verified https://vk.com/video{ticket.remote_id}")
            _pause(write_delay)

        if not place_in_albums:
            continue
        for collection_title in memberships.get(source_id, []):
            album_id = album_map[normalize_title(collection_title)]
            key = f"{ticket.remote_id}:{album_id}"
            if key in placements:
                continue
            added = writer.add_to_album(
                community_id=community_id,
                album_id=album_id,
                owner_id=ticket.owner_id,
                video_id=ticket.video_id,
            )
            placements[key] = {
                "remote_id": ticket.remote_id,
                "album_id": album_id,
                "album_title": collection_title,
                "status": "added" if added else "already_present",
            }
            _save_journal(journal_path, journal)
            if added:
                _pause(write_delay)


def run(args: argparse.Namespace, *, runtime: SyncRuntime) -> int:
    if args.write_delay < 0:
        raise SystemExit("--write-delay cannot be negative")

    settings = get_settings()
    source = load_audit(args.source)
    if source.channel.ref.platform != PlatformName.YOUTUBE:
        raise SystemExit("The source AuditPackage must be YouTube.")
    source_channel_id = str(source.channel.ref.channel_id)
    if source_channel_id != runtime.expected_source_channel_id:
        raise SystemExit(
            f"Source channel {source_channel_id} does not match runtime project "
            f"{runtime.project_key} channel {runtime.expected_source_channel_id}."
        )

    store = VkTokenStore(settings.data_dir)
    reader = VkApiClient(
        token_store=store,
        account_alias=args.account,
        api_version=settings.vk_api_version,
    )
    community_record = reader.get_community(args.community)
    community_id = int(community_record.ref.channel_id)
    if community_id != runtime.expected_community_id:
        raise SystemExit(
            f"Target community {community_id} does not match runtime project "
            f"{runtime.project_key} community {runtime.expected_community_id}."
        )
    if not bool(community_record.metadata.get("managed_by_token")):
        raise SystemExit("The authorized VK user is not reported as an administrator of this community.")

    print("Reading live VK inventory before any write…")
    live_before = VkInventoryService(reader).build_audit_package(community_id)
    comparison = compare_audit_packages(source, live_before)
    all_candidate_ids = _transfer_candidates(comparison, scope=args.scope)
    candidate_ids = all_candidate_ids if args.phase in {"videos", "all"} else []
    if len(candidate_ids) > args.max_videos:
        raise SystemExit(f"Candidate count {len(candidate_ids)} exceeds --max-videos {args.max_videos}.")

    missing_albums = sum(gap.target_collection_id is None for gap in comparison.collection_gaps)
    placement_count = sum(gap.missing_placement_count for gap in comparison.collection_gaps)
    nonempty_playlist_descriptions = sum(bool(item.description.strip()) for item in source.collections)
    source_videos = {item.ref.remote_id: item for item in source.videos}
    title_changes = sum(
        runtime.render_title(source_videos[video_id].title) != source_videos[video_id].title
        for video_id in candidate_ids
    )
    description_changes = sum(
        runtime.render_description(source_videos[video_id].description) != source_videos[video_id].description.strip()
        for video_id in candidate_ids
    )
    print(
        "VK synchronization preflight:\n"
        f"  project: {runtime.project_key}\n"
        f"  source snapshot: {source.snapshot_id}\n"
        f"  source channel: {source_channel_id}\n"
        f"  target community: {community_id} — {community_record.title}\n"
        f"  scope: {args.scope}\n"
        f"  phase: {args.phase}\n"
        f"  videos to upload now: {len(candidate_ids)}\n"
        f"  titles changed by project renderer: {title_changes}\n"
        f"  descriptions changed by project renderer: {description_changes}\n"
        f"  write delay: {args.write_delay:.2f}s\n"
        f"  ambiguous existing matches: {comparison.ambiguous_match_count}\n"
        f"  albums to create: {missing_albums}\n"
        f"  existing-video album placements: {placement_count}\n"
        f"  source playlist descriptions not supported by VK albums: {nonempty_playlist_descriptions}"
    )

    yt_dlp: str | None = None
    if args.phase in {"videos", "all"}:
        yt_dlp = resolve_executable(args.yt_dlp)
        resolve_executable("ffmpeg")
    if not args.execute:
        print("Dry-run only. No remote write method was called.")
        print(
            "Re-run with --execute and exact --confirm-community, --confirm-count, "
            "--confirm-ambiguous, and --confirm-source-snapshot values."
        )
        return 0

    confirmations = {
        "community": str(args.confirm_community or "") == str(community_id),
        "count": args.confirm_count == len(candidate_ids),
        "ambiguous": args.confirm_ambiguous == comparison.ambiguous_match_count,
        "snapshot": str(args.confirm_source_snapshot or "") == str(source.snapshot_id),
    }
    failed_confirmations = [name for name, valid in confirmations.items() if not valid]
    if failed_confirmations:
        raise SystemExit(f"Execution confirmation mismatch: {', '.join(failed_confirmations)}")

    writer = VkVideoWriter(
        token_store=store,
        account_alias=args.account,
        api_version=settings.vk_api_version,
    )
    journal = _load_journal(args.journal, source=source, community_id=community_id)
    album_map = _album_map_from_live(live_before)

    if args.phase in {"albums", "all"}:
        _ensure_albums(
            source=source,
            comparison=comparison,
            community_id=community_id,
            writer=writer,
            album_map=album_map,
            journal=journal,
            journal_path=args.journal,
            write_delay=args.write_delay,
        )
        _place_existing_videos(
            comparison=comparison,
            community_id=community_id,
            writer=writer,
            album_map=album_map,
            journal=journal,
            journal_path=args.journal,
            write_delay=args.write_delay,
        )

    if args.phase in {"videos", "all"}:
        assert yt_dlp is not None
        _upload_candidates(
            source=source,
            candidate_ids=candidate_ids,
            community_id=community_id,
            writer=writer,
            album_map=album_map,
            journal=journal,
            journal_path=args.journal,
            memberships=_source_memberships(source),
            yt_dlp=yt_dlp,
            cache_dir=args.cache_dir,
            processing_timeout=args.processing_timeout,
            place_in_albums=args.phase == "all",
            write_delay=args.write_delay,
            runtime=runtime,
        )

    print("Reading final live VK inventory…")
    live_after = VkInventoryService(reader).build_audit_package(community_id)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    result_output = (
        args.result_output or settings.data_dir / "exports" / f"vk-{args.account}-{community_id}-{timestamp}.json"
    )
    result_output.parent.mkdir(parents=True, exist_ok=True)
    result_output.write_text(live_after.model_dump_json(indent=2), encoding="utf-8")
    final_comparison = compare_audit_packages(source, live_after)
    completed_phases = journal.setdefault("completed_phases", [])
    if args.phase not in completed_phases:
        completed_phases.append(args.phase)
    journal["final_snapshot_id"] = str(live_after.snapshot_id)
    journal["final_export"] = str(result_output)
    journal["remaining_missing_on_target"] = len(final_comparison.missing_on_target)
    journal["status"] = "completed"
    _save_journal(args.journal, journal)
    print(
        f"Synchronization completed. VK videos: {len(live_after.videos)} | "
        f"albums: {len(live_after.collections)} | remaining source videos absent: "
        f"{len(final_comparison.missing_on_target)}"
    )
    print(f"Final VK AuditPackage → {result_output}")
    print(f"Journal → {args.journal}")
    return 0


def main(argv: list[str] | None = None, *, runtime: SyncRuntime | None = None) -> int:
    if runtime is None:
        raise SystemExit(
            "sync_youtube_to_vk.py is an internal engine. "
            "Use scripts/sync_youtube_to_vk_textsafe.py so project rendering, media QC, and writer locking are bound."
        )
    args = build_parser().parse_args(argv)
    return run(args, runtime=runtime)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError, VkWriteError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
