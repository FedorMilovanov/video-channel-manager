#!/usr/bin/env python3
"""Recover original YouTube descriptions from a copy-apply backup.

The script is intentionally idempotent. It restores a video only when the live
text is still equal to the planned after-state. Videos already equal to the
backup are skipped, and any third state blocks the full preflight.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.youtube import InstalledClientConfig, TokenStore, YouTubeDescriptionWriter
from video_channel_manager.platforms.youtube.writer import descriptions_equivalent


def _load_backup(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read backup: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_name") != "video-manager.youtube-copy-backup":
        raise ValueError("Expected a video-manager.youtube-copy-backup JSON object.")
    operations = payload.get("operations")
    if not isinstance(operations, list) or not all(isinstance(item, dict) for item in operations):
        raise ValueError("Backup operations must be a list of objects.")
    return payload


def _required_text(operation: dict[str, Any], field: str) -> str:
    value = operation.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Backup operation is missing required string field: {field}")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", type=Path, help="youtube-copy-backup-*.json created before mutation")
    parser.add_argument("--account", help="OAuth account alias; defaults to the alias stored in the backup")
    parser.add_argument("--confirm-channel", required=True, help="Exact YouTube channel ID")
    parser.add_argument("--client-secret", type=Path, help="Override the configured Desktop OAuth JSON")
    parser.add_argument("--execute", action="store_true", help="Restore after a successful full live preflight")
    parser.add_argument("--max-operations", type=int, default=100)
    parser.add_argument("--result-output", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    backup = _load_backup(args.backup)
    operations = [item for item in backup["operations"] if isinstance(item, dict)]
    if not operations:
        raise SystemExit("Backup has no operations.")
    if len(operations) > args.max_operations:
        raise SystemExit(
            f"Backup has {len(operations)} operations, above --max-operations {args.max_operations}."
        )

    backup_channel = str(backup.get("channel_id") or "")
    if backup_channel != args.confirm_channel:
        raise SystemExit(
            f"Backup targets {backup_channel or 'no channel'}, not confirmed channel {args.confirm_channel}."
        )
    account = args.account or str(backup.get("account") or "")
    if not account:
        raise SystemExit("--account is required because the backup does not contain an account alias.")

    settings = get_settings()
    config = InstalledClientConfig.from_file(args.client_secret or settings.youtube_client_secret_file)
    store = TokenStore(settings.data_dir)
    writer = YouTubeDescriptionWriter(
        client_config=config,
        token_store=store,
        account_alias=account,
    )

    prepared: list[dict[str, str]] = []
    already_original: list[str] = []
    conflicts: list[dict[str, str]] = []

    print(f"Preflighting {len(operations)} backup operations against live YouTube…")
    for operation in operations:
        video_id = _required_text(operation, "video_id")
        channel_id = _required_text(operation, "channel_id")
        before = _required_text(operation, "before_description")
        after = _required_text(operation, "after_description")
        if channel_id != args.confirm_channel:
            conflicts.append(
                {
                    "video_id": video_id,
                    "reason": f"backup channel {channel_id} differs from confirmed channel",
                }
            )
            continue
        current = writer.read_description(video_id)
        if current.channel_id != args.confirm_channel:
            conflicts.append(
                {
                    "video_id": video_id,
                    "reason": f"live channel {current.channel_id} differs from confirmed channel",
                }
            )
        elif descriptions_equivalent(current.description, before):
            already_original.append(video_id)
        elif descriptions_equivalent(current.description, after):
            prepared.append(
                {
                    "video_id": video_id,
                    "channel_id": channel_id,
                    "title": current.title,
                    "live_description": current.description,
                    "before_description": before,
                    "after_description": after,
                }
            )
        else:
            conflicts.append(
                {
                    "video_id": video_id,
                    "reason": "live description is neither the original backup nor the planned after-state",
                }
            )

    print(
        f"Recovery preflight: restore {len(prepared)} | already original {len(already_original)} | "
        f"conflicts {len(conflicts)}"
    )
    if conflicts:
        for conflict in conflicts:
            print(f"CONFLICT {conflict['video_id']}: {conflict['reason']}")
        print("Nothing was changed.")
        return 2
    if not args.execute:
        print("Dry-run only. Re-run with --execute to restore the prepared descriptions.")
        return 0

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    result_output = args.result_output or settings.data_dir / "reports" / f"youtube-copy-recovery-{timestamp}.json"
    restored: list[dict[str, str]] = []
    failed: list[dict[str, str]] = []

    for operation in prepared:
        video_id = operation["video_id"]
        try:
            snapshot = writer.restore_description_if_current(
                video_id=video_id,
                expected_channel_id=operation["channel_id"],
                expected_current_description=operation["live_description"],
                restore_description=operation["before_description"],
            )
            restored.append(
                {
                    "video_id": video_id,
                    "title": snapshot.title,
                    "revision": snapshot.revision,
                    "status": "restored",
                }
            )
            print(f"Restored and verified {video_id} — {snapshot.title}")
        except Exception as exc:  # keep recovering independent videos; record every failure
            failed.append({"video_id": video_id, "status": "failed", "error": str(exc)})
            print(f"FAILED {video_id}: {exc}")

    result = {
        "schema_name": "video-manager.youtube-copy-recovery-result",
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "source_backup": str(args.backup),
        "account": account,
        "channel_id": args.confirm_channel,
        "already_original": already_original,
        "restored": restored,
        "failed": failed,
        "status": "completed" if not failed else "partial_failure",
    }
    result_output.parent.mkdir(parents=True, exist_ok=True)
    result_output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Recovery result → {result_output}")
    print(
        f"Recovery finished: restored {len(restored)} | already original {len(already_original)} | "
        f"failed {len(failed)}"
    )
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
