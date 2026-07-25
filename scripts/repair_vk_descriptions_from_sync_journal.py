#!/usr/bin/env python3
"""Repair VK descriptions uploaded by the YouTube→VK sync without touching video media."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from video_channel_manager.config import get_settings
from video_channel_manager.domain.enums import PlatformName
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk import VkTokenStore
from video_channel_manager.platforms.vk.lock import local_vk_write_lock
from video_channel_manager.platforms.vk.text import render_vk_video_description
from video_channel_manager.platforms.vk.text_writer import VkVideoTextWriter, vk_texts_equivalent
from video_channel_manager.platforms.vk.writer import VkWriteError

_SITE_URL = "https://thelegendarypoet.ru/"
_SITE_FOOTER = f"🎧 The Legendary Poet — русская поэзия, музыка и литературные материалы.\n🌐 {_SITE_URL}"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="YouTube AuditPackage used by the sync")
    parser.add_argument("journal", type=Path, help="youtube-vk-sync journal with completed upload IDs")
    parser.add_argument("--account", default="legendary-poet")
    parser.add_argument("--community", type=int, required=True, help="Positive VK community ID")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-count", type=int)
    parser.add_argument("--confirm-source-snapshot")
    parser.add_argument("--max-operations", type=int, default=200)
    parser.add_argument("--backup-output", type=Path)
    parser.add_argument("--result-output", type=Path)
    return parser


def _load_source(path: Path) -> AuditPackage:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        source = AuditPackage.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"Cannot read AuditPackage {path}: {exc}") from exc
    if source.channel.ref.platform != PlatformName.YOUTUBE:
        raise ValueError("The source AuditPackage must be YouTube.")
    return source


def _load_journal(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read sync journal {path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_name") != "video-manager.youtube-vk-sync-journal":
        raise ValueError("Expected a video-manager.youtube-vk-sync-journal JSON object.")
    uploads = payload.get("uploads")
    if not isinstance(uploads, dict):
        raise ValueError("Sync journal uploads must be an object.")
    return payload


def _parse_remote_id(remote_id: str) -> tuple[int, int]:
    owner_text, separator, video_text = remote_id.partition("_")
    if not separator:
        raise ValueError(f"Invalid VK remote ID: {remote_id}")
    try:
        return int(owner_text), int(video_text)
    except ValueError as exc:
        raise ValueError(f"Invalid VK remote ID: {remote_id}") from exc


def _legacy_description(source_description: str) -> str:
    description = source_description.strip()
    if _SITE_URL in description:
        return description
    return f"{description}\n\n{_SITE_FOOTER}" if description else _SITE_FOOTER


def _atomic_write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    args = _parser().parse_args()
    if args.community <= 0:
        raise SystemExit("--community must be a positive community ID")

    source = _load_source(args.source)
    journal = _load_journal(args.journal)
    if str(journal.get("source_snapshot_id") or "") != str(source.snapshot_id):
        raise SystemExit("The sync journal belongs to a different source snapshot.")
    if int(journal.get("community_id") or 0) != args.community:
        raise SystemExit("The sync journal belongs to a different VK community.")

    settings = get_settings()
    store = VkTokenStore(settings.data_dir)
    writer = VkVideoTextWriter(
        token_store=store,
        account_alias=args.account,
        api_version=settings.vk_api_version,
    )

    source_videos = {item.ref.remote_id: item for item in source.videos}
    uploads = journal["uploads"]
    prepared: list[dict[str, Any]] = []
    already_safe: list[str] = []
    conflicts: list[dict[str, str]] = []

    print(f"Preflighting {len(uploads)} journaled VK uploads…")
    for source_id, upload in sorted(uploads.items()):
        if not isinstance(source_id, str) or not isinstance(upload, dict):
            conflicts.append({"source_video_id": str(source_id), "reason": "invalid journal upload record"})
            continue
        source_video = source_videos.get(source_id)
        if source_video is None:
            conflicts.append({"source_video_id": source_id, "reason": "source video is absent from AuditPackage"})
            continue
        remote_id = str(upload.get("remote_id") or "")
        if not remote_id:
            conflicts.append({"source_video_id": source_id, "reason": "journal upload has no remote_id"})
            continue
        owner_id, video_id = _parse_remote_id(remote_id)
        if owner_id != -args.community:
            conflicts.append(
                {
                    "source_video_id": source_id,
                    "reason": f"journal target owner {owner_id} differs from {-args.community}",
                }
            )
            continue
        current = writer.read_text(owner_id=owner_id, video_id=video_id)
        if current is None:
            conflicts.append({"source_video_id": source_id, "reason": f"VK video {remote_id} is not visible"})
            continue

        rendered = render_vk_video_description(source_video.description)
        if rendered.has_errors:
            conflicts.append({"source_video_id": source_id, "reason": "renderer produced an error-level finding"})
            continue
        if vk_texts_equivalent(current.description, rendered.text):
            already_safe.append(source_id)
            continue

        known_before_states = (
            _legacy_description(source_video.description),
            source_video.description,
            source_video.description.strip(),
        )
        if not any(vk_texts_equivalent(current.description, candidate) for candidate in known_before_states):
            conflicts.append(
                {
                    "source_video_id": source_id,
                    "reason": "live VK description is neither a known sync output nor the new plain-text output",
                }
            )
            continue

        prepared.append(
            {
                "source_video_id": source_id,
                "owner_id": owner_id,
                "video_id": video_id,
                "remote_id": remote_id,
                "title": current.title,
                "before_description": current.description,
                "after_description": rendered.text,
                "removed_emphasis_pairs": rendered.removed_emphasis_pairs,
                "converted_markdown_links": rendered.converted_markdown_links,
                "removed_zero_width_characters": rendered.removed_zero_width_characters,
                "collapsed_blank_runs": rendered.collapsed_blank_runs,
                "footer_added": rendered.footer_added,
            }
        )

    if len(prepared) > args.max_operations:
        raise SystemExit(f"Prepared count {len(prepared)} exceeds --max-operations {args.max_operations}.")

    print(
        f"VK description repair preflight: ready {len(prepared)} | already safe {len(already_safe)} | "
        f"conflicts {len(conflicts)}"
    )
    if conflicts:
        for conflict in conflicts:
            print(f"CONFLICT {conflict['source_video_id']}: {conflict['reason']}")
        print("Nothing was changed.")
        return 2
    if not args.execute:
        print("Dry-run only. Re-run with --execute and exact count/snapshot confirmations.")
        return 0

    if args.confirm_count != len(prepared):
        raise SystemExit(f"--confirm-count must equal the live ready count {len(prepared)}")
    if str(args.confirm_source_snapshot or "") != str(source.snapshot_id):
        raise SystemExit(f"--confirm-source-snapshot must equal {source.snapshot_id}")
    if not prepared:
        print("Nothing to change; every journaled upload is already plain-text safe.")
        return 0

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    backup_output = args.backup_output or settings.data_dir / "reports" / f"vk-description-backup-{timestamp}.json"
    result_output = args.result_output or settings.data_dir / "reports" / f"vk-description-repair-{timestamp}.json"
    backup = {
        "schema_name": "video-manager.vk-description-backup",
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "source": str(args.source),
        "journal": str(args.journal),
        "source_snapshot_id": str(source.snapshot_id),
        "account": args.account,
        "community_id": args.community,
        "operations": prepared,
    }
    _atomic_write(backup_output, backup)
    print(f"Backup written before VK text mutation → {backup_output}")

    result: dict[str, Any] = {
        "schema_name": "video-manager.vk-description-repair-result",
        "schema_version": 1,
        "started_at": datetime.now(UTC).isoformat(),
        "backup": str(backup_output),
        "source_snapshot_id": str(source.snapshot_id),
        "account": args.account,
        "community_id": args.community,
        "status": "running",
        "already_safe": already_safe,
        "repaired": [],
        "failed": [],
    }
    _atomic_write(result_output, result)

    lock_path = settings.data_dir / "locks" / f"vk-{args.account}-{args.community}.lock"
    with local_vk_write_lock(
        lock_path,
        account=args.account,
        community_id=args.community,
        operation="repair-video-descriptions",
    ):
        for operation in prepared:
            source_id = str(operation["source_video_id"])
            try:
                verified = writer.replace_text_if_current(
                    owner_id=int(operation["owner_id"]),
                    video_id=int(operation["video_id"]),
                    expected_description=str(operation["before_description"]),
                    new_description=str(operation["after_description"]),
                    expected_title=str(operation["title"]),
                )
                result["repaired"].append(
                    {
                        "source_video_id": source_id,
                        "remote_id": verified.remote_id,
                        "title": verified.title,
                        "status": "verified",
                    }
                )
                print(f"Repaired and verified {source_id} → https://vk.com/video{verified.remote_id}")
            except (ValueError, VkWriteError) as exc:
                result["failed"].append(
                    {
                        "source_video_id": source_id,
                        "remote_id": operation["remote_id"],
                        "error": str(exc),
                    }
                )
                print(f"FAILED {source_id}: {exc}")
                _atomic_write(result_output, result)
                break
            _atomic_write(result_output, result)

    result["finished_at"] = datetime.now(UTC).isoformat()
    result["status"] = "completed" if not result["failed"] else "partial_failure"
    _atomic_write(result_output, result)
    print(f"VK description repair result → {result_output}")
    print(
        f"Repair finished: repaired {len(result['repaired'])} | already safe {len(already_safe)} | "
        f"failed {len(result['failed'])}"
    )
    return 0 if not result["failed"] else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, VkWriteError) as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(2) from exc
