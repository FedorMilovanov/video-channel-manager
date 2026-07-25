#!/usr/bin/env python3
"""Dry-run or apply a reviewed whole-community VK description cleanup plan."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk import VkTokenStore
from video_channel_manager.platforms.vk.lock import local_vk_write_lock
from video_channel_manager.platforms.vk.text_writer import VkVideoTextWriter, vk_texts_equivalent
from video_channel_manager.platforms.vk.writer import VkWriteError

_SCHEMA_NAME = "video-manager.vk-live-description-cleanup-plan"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--account", default="legendary-poet")
    parser.add_argument("--community", type=int, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-community", type=int)
    parser.add_argument("--confirm-count", type=int)
    parser.add_argument("--confirm-live-snapshot")
    parser.add_argument("--max-operations", type=int, default=500)
    parser.add_argument("--backup-output", type=Path)
    parser.add_argument("--result-output", type=Path)
    return parser


def _load_plan(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read cleanup plan {path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_name") != _SCHEMA_NAME:
        raise ValueError(f"Expected a {_SCHEMA_NAME} JSON object.")
    operations = payload.get("operations")
    if not isinstance(operations, list) or not all(isinstance(item, dict) for item in operations):
        raise ValueError("Cleanup plan operations must be a list of objects.")
    return payload


def _required_text(item: dict[str, Any], field: str) -> str:
    value = item.get(field)
    if not isinstance(value, str):
        raise ValueError(f"Cleanup operation is missing string field: {field}")
    return value


def _atomic_write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _preflight(
    operations: list[dict[str, Any]],
    *,
    community_id: int,
    writer: VkVideoTextWriter,
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, str]]]:
    prepared: list[dict[str, Any]] = []
    already_applied: list[str] = []
    conflicts: list[dict[str, str]] = []
    expected_owner = -community_id

    for operation in operations:
        remote_id = _required_text(operation, "remote_id")
        owner_id = int(operation.get("owner_id") or 0)
        video_id = int(operation.get("video_id") or 0)
        before = _required_text(operation, "before_description")
        after = _required_text(operation, "after_description")
        if owner_id != expected_owner or remote_id != f"{owner_id}_{video_id}":
            conflicts.append({"remote_id": remote_id, "reason": "plan identity does not match the confirmed community"})
            continue

        current = writer.read_text(owner_id=owner_id, video_id=video_id)
        if current is None:
            conflicts.append({"remote_id": remote_id, "reason": "video is no longer visible in VK"})
            continue
        if vk_texts_equivalent(current.description, after):
            already_applied.append(remote_id)
            continue
        if not vk_texts_equivalent(current.description, before):
            conflicts.append(
                {
                    "remote_id": remote_id,
                    "reason": "live description matches neither the reviewed before-state nor after-state",
                }
            )
            continue
        prepared.append({**operation, "live_title": current.title})

    return prepared, already_applied, conflicts


def _verify(
    operations: list[dict[str, Any]],
    *,
    writer: VkVideoTextWriter,
) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    for operation in operations:
        owner_id = int(operation["owner_id"])
        video_id = int(operation["video_id"])
        remote_id = str(operation["remote_id"])
        current = writer.read_text(owner_id=owner_id, video_id=video_id)
        if current is None:
            failures.append({"remote_id": remote_id, "reason": "video is not visible"})
            continue
        if not vk_texts_equivalent(current.description, str(operation["after_description"])):
            failures.append({"remote_id": remote_id, "reason": "description does not match the planned after-state"})
    return failures


def main() -> int:
    args = _parser().parse_args()
    if args.community <= 0:
        raise SystemExit("--community must be a positive community ID")

    plan = _load_plan(args.plan)
    if int(plan.get("community_id") or 0) != args.community:
        raise SystemExit("The plan belongs to a different VK community.")
    operations = list(plan["operations"])
    if len(operations) > args.max_operations:
        raise SystemExit(f"Plan has {len(operations)} operations, above --max-operations {args.max_operations}.")

    settings = get_settings()
    store = VkTokenStore(settings.data_dir)
    writer = VkVideoTextWriter(
        token_store=store,
        account_alias=args.account,
        api_version=settings.vk_api_version,
    )

    print(f"Preflighting {len(operations)} whole-community VK description operations…")
    prepared, already_applied, conflicts = _preflight(
        operations,
        community_id=args.community,
        writer=writer,
    )
    print(
        f"Full VK cleanup preflight: ready {len(prepared)} | already applied {len(already_applied)} | "
        f"conflicts {len(conflicts)} | review-only excluded {int(plan.get('review_only_count') or 0)}"
    )
    if conflicts:
        for conflict in conflicts:
            print(f"CONFLICT {conflict['remote_id']}: {conflict['reason']}")
        print("Nothing was changed.")
        return 2
    if not args.execute:
        print("Dry-run only. Re-run with --execute and exact community/count/snapshot confirmations.")
        return 0

    confirmations = {
        "community": args.confirm_community == args.community,
        "count": args.confirm_count == len(prepared),
        "snapshot": str(args.confirm_live_snapshot or "") == str(plan.get("live_snapshot_id") or ""),
    }
    failed_confirmations = [name for name, valid in confirmations.items() if not valid]
    if failed_confirmations:
        raise SystemExit(f"Execution confirmation mismatch: {', '.join(failed_confirmations)}")
    if not prepared:
        print("Nothing to change; all planned descriptions are already applied.")
        return 0

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    backup_output = args.backup_output or settings.data_dir / "reports" / f"vk-live-description-backup-{timestamp}.json"
    result_output = args.result_output or settings.data_dir / "reports" / f"vk-live-description-apply-{timestamp}.json"
    backup = {
        "schema_name": "video-manager.vk-live-description-backup",
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "source_plan": str(args.plan),
        "live_snapshot_id": plan["live_snapshot_id"],
        "account": args.account,
        "community_id": args.community,
        "operations": prepared,
    }
    _atomic_write(backup_output, backup)
    print(f"Backup written before VK mutation → {backup_output}")

    attempted: list[dict[str, Any]] = []
    applied: list[dict[str, Any]] = []
    rollback: list[dict[str, Any]] = []
    result: dict[str, Any] = {
        "schema_name": "video-manager.vk-live-description-apply-result",
        "schema_version": 1,
        "started_at": datetime.now(UTC).isoformat(),
        "source_plan": str(args.plan),
        "backup": str(backup_output),
        "live_snapshot_id": plan["live_snapshot_id"],
        "account": args.account,
        "community_id": args.community,
        "status": "running",
        "summary": {
            "planned": len(operations),
            "prepared": len(prepared),
            "already_applied": len(already_applied),
            "attempted": 0,
            "applied": 0,
            "postflight_verified": 0,
            "rollback_safe_original": 0,
            "rollback_failed": 0,
        },
        "attempted": attempted,
        "applied": applied,
        "postflight_failures": [],
        "rollback": rollback,
    }
    _atomic_write(result_output, result)

    failure: BaseException | None = None
    lock_path = settings.data_dir / "locks" / f"vk-{args.account}-{args.community}.lock"
    with local_vk_write_lock(
        lock_path,
        account=args.account,
        community_id=args.community,
        operation="apply-all-video-description-cleanup",
    ):
        try:
            for operation in prepared:
                attempt = {
                    "remote_id": operation["remote_id"],
                    "title": operation["live_title"],
                    "started_at": datetime.now(UTC).isoformat(),
                    "status": "attempting",
                }
                attempted.append(attempt)
                result["summary"]["attempted"] = len(attempted)
                _atomic_write(result_output, result)

                verified = writer.replace_text_if_current(
                    owner_id=int(operation["owner_id"]),
                    video_id=int(operation["video_id"]),
                    expected_description=str(operation["before_description"]),
                    new_description=str(operation["after_description"]),
                )
                attempt["status"] = "verified"
                attempt["finished_at"] = datetime.now(UTC).isoformat()
                applied.append(
                    {
                        "remote_id": verified.remote_id,
                        "title": verified.title,
                        "status": "verified",
                    }
                )
                result["summary"]["applied"] = len(applied)
                _atomic_write(result_output, result)
                print(f"Updated and verified https://vk.com/video{verified.remote_id} — {verified.title}")

            postflight_failures = _verify(prepared, writer=writer)
            result["postflight_failures"] = postflight_failures
            if postflight_failures:
                failed_ids = ", ".join(item["remote_id"] for item in postflight_failures)
                raise RuntimeError(f"Final VK batch postflight failed for: {failed_ids}")
            result["summary"]["postflight_verified"] = len(prepared)
        except BaseException as exc:  # rollback must also run after Ctrl+C
            failure = exc
            print(f"Apply failed; starting guarded rollback: {exc}")

        if failure is not None:
            for operation in reversed(prepared[: len(attempted)]):
                remote_id = str(operation["remote_id"])
                owner_id = int(operation["owner_id"])
                video_id = int(operation["video_id"])
                before = str(operation["before_description"])
                after = str(operation["after_description"])
                try:
                    current = writer.read_text(owner_id=owner_id, video_id=video_id)
                    if current is None:
                        raise RuntimeError("video is no longer visible")
                    if vk_texts_equivalent(current.description, before):
                        rollback.append({"remote_id": remote_id, "status": "safe_original"})
                    elif vk_texts_equivalent(current.description, after):
                        restored = writer.replace_text_if_current(
                            owner_id=owner_id,
                            video_id=video_id,
                            expected_description=after,
                            new_description=before,
                        )
                        rollback.append(
                            {"remote_id": remote_id, "status": "safe_original", "title": restored.title}
                        )
                    else:
                        raise RuntimeError("live text is neither the planned before-state nor after-state")
                    print(f"Rollback safe/original {remote_id}")
                except (RuntimeError, ValueError, VkWriteError) as rollback_exc:
                    rollback.append({"remote_id": remote_id, "status": "failed", "error": str(rollback_exc)})
                    print(f"Rollback failed {remote_id}: {rollback_exc}")
                result["summary"]["rollback_safe_original"] = sum(
                    item["status"] == "safe_original" for item in rollback
                )
                result["summary"]["rollback_failed"] = sum(item["status"] == "failed" for item in rollback)
                _atomic_write(result_output, result)

    if failure is None:
        result["status"] = "completed"
    elif int(result["summary"]["rollback_failed"]) == 0:
        result["status"] = "failed_rolled_back"
        result["error"] = f"{type(failure).__name__}: {failure}"
    else:
        result["status"] = "failed_partial_rollback"
        result["error"] = f"{type(failure).__name__}: {failure}"
    result["finished_at"] = datetime.now(UTC).isoformat()
    _atomic_write(result_output, result)
    print(f"VK cleanup result → {result_output}")

    if failure is not None:
        if isinstance(failure, KeyboardInterrupt):
            raise failure
        return 2
    print(
        f"Completed {len(applied)} verified VK description updates; final postflight verified the whole batch."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, VkWriteError) as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(2) from exc
