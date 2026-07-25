#!/usr/bin/env python3
"""Dry-run or apply a self-validating YouTube copy-fix plan v3.

This is the strict executor for future description batches. It rejects legacy
plans, verifies every operation/hash/target, requires the exact plan digest and
live ready count, acquires a Windows-safe channel lock, repeats preflight after
lock acquisition, writes a backup before mutation, journals each attempt, runs a
whole-batch postflight, and performs guarded rollback on failure.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.youtube import (
    InstalledClientConfig,
    TokenStore,
    YOUTUBE_FORCE_SSL_SCOPE,
    YouTubeDescriptionWriter,
    YouTubeWriteError,
)
from video_channel_manager.platforms.youtube.copy_execution import (
    CopyPreflight,
    preflight_copy_operations,
    verify_copy_operations,
)
from video_channel_manager.platforms.youtube.copy_plan import validate_copy_plan
from video_channel_manager.platforms.youtube.write_lock import local_youtube_write_lock


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--account", default="legendary-poet")
    parser.add_argument("--confirm-channel", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-count", type=int)
    parser.add_argument("--confirm-plan-sha256")
    parser.add_argument("--max-operations", type=int, default=100)
    parser.add_argument("--backup-output", type=Path)
    parser.add_argument("--result-output", type=Path)
    parser.add_argument("--client-secret", type=Path)
    return parser


def _load_plan(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read YouTube copy plan {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("YouTube copy plan JSON must be an object.")
    validate_copy_plan(payload)
    return payload


def _atomic_write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _validate_output_paths(*paths: Path) -> None:
    resolved = [path.resolve() for path in paths]
    if len(resolved) != len(set(resolved)):
        raise ValueError("Backup and result output paths must be different.")
    existing = [str(path) for path in resolved if path.exists()]
    if existing:
        raise ValueError("Refusing to overwrite existing evidence file(s): " + ", ".join(existing))


def _writer(account: str, client_secret: Path | None) -> tuple[TokenStore, YouTubeDescriptionWriter]:
    settings = get_settings()
    secret_path = client_secret or settings.youtube_client_secret_file
    config = InstalledClientConfig.from_file(secret_path)
    store = TokenStore(settings.data_dir)
    return store, YouTubeDescriptionWriter(
        client_config=config,
        token_store=store,
        account_alias=account,
    )


def _preflight(
    plan: dict[str, Any],
    *,
    confirm_channel: str,
    writer: YouTubeDescriptionWriter,
) -> CopyPreflight:
    operations = list(plan["operations"])
    return preflight_copy_operations(
        operations,
        confirm_channel=confirm_channel,
        writer=writer,
    )


def _result_status(failure: BaseException | None, rollback_failed: int) -> str:
    if failure is None:
        return "completed"
    return "failed_rolled_back" if rollback_failed == 0 else "failed_partial_rollback"


def main() -> int:
    args = _parser().parse_args()
    if args.max_operations <= 0:
        raise SystemExit("--max-operations must be positive")

    settings = get_settings()
    plan = _load_plan(args.plan)
    target_channel = str(plan["target_channel_id"])
    if args.confirm_channel != target_channel:
        raise SystemExit(f"--confirm-channel {args.confirm_channel!r} differs from plan target {target_channel!r}.")
    operations = list(plan["operations"])
    if not operations:
        raise SystemExit("YouTube copy plan has no operations.")
    if len(operations) > args.max_operations:
        raise SystemExit(f"Plan has {len(operations)} operations, above --max-operations {args.max_operations}.")

    store, writer = _writer(args.account, args.client_secret)
    print(
        f"Validated YouTube plan {plan['plan_sha256']} | channel {target_channel} | "
        f"checked videos {plan['videos_checked']} | operations {len(operations)} | "
        f"unresolved excluded {plan['unresolved_error_videos']}"
    )

    if not args.execute:
        preflight = _preflight(plan, confirm_channel=target_channel, writer=writer)
        print(
            f"YouTube plan v3 preflight: ready {len(preflight.prepared)} | "
            f"already applied {preflight.already_applied} | "
            f"revision drift tolerated {preflight.revision_drift_tolerated}"
        )
        print("Dry-run only. No remote write method was called.")
        print("Execute requires exact --confirm-channel, --confirm-count and --confirm-plan-sha256 values.")
        return 0

    token = store.load_token(args.account)
    if YOUTUBE_FORCE_SSL_SCOPE not in token.scopes:
        raise SystemExit(
            "Stored OAuth token is read-only. Re-authorize with: "
            f"video-manager youtube login --account {args.account} --write --force"
        )

    lock_path = settings.data_dir / "locks" / f"youtube-{args.account}-{target_channel}.lock"
    with local_youtube_write_lock(lock_path, account=args.account, channel_id=target_channel):
        # This preflight occurs only after this process owns the channel writer
        # lock, eliminating the dry-run→execute race with another local writer.
        preflight = _preflight(plan, confirm_channel=target_channel, writer=writer)
        print(
            f"Locked YouTube preflight: ready {len(preflight.prepared)} | "
            f"already applied {preflight.already_applied} | "
            f"revision drift tolerated {preflight.revision_drift_tolerated}"
        )
        confirmations = {
            "count": args.confirm_count == len(preflight.prepared),
            "plan": str(args.confirm_plan_sha256 or "") == str(plan["plan_sha256"]),
        }
        failed_confirmations = [name for name, valid in confirmations.items() if not valid]
        if failed_confirmations:
            raise SystemExit(f"Execution confirmation mismatch: {', '.join(failed_confirmations)}")
        if not preflight.prepared:
            print("Nothing to change; every planned description is already applied.")
            return 0

        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        backup_output = args.backup_output or settings.data_dir / "reports" / f"youtube-copy-backup-v3-{timestamp}.json"
        result_output = args.result_output or settings.data_dir / "reports" / f"youtube-copy-apply-v3-{timestamp}.json"
        _validate_output_paths(backup_output, result_output)

        backup_payload = {
            "schema_name": "video-manager.youtube-copy-backup",
            "schema_version": 3,
            "created_at": datetime.now(UTC).isoformat(),
            "source_plan": str(args.plan.resolve()),
            "plan_sha256": plan["plan_sha256"],
            "checked_video_ids_sha256": plan["checked_video_ids_sha256"],
            "source_audit_sha256": plan["source_audit_sha256"],
            "account": args.account,
            "channel_id": target_channel,
            "already_applied": preflight.already_applied,
            "revision_drift_tolerated": preflight.revision_drift_tolerated,
            "operations": preflight.prepared,
        }
        _atomic_write(backup_output, backup_payload)
        print(f"Backup written before mutation → {backup_output}")

        attempted: list[dict[str, Any]] = []
        applied: list[dict[str, Any]] = []
        rollback_results: list[dict[str, Any]] = []
        result: dict[str, Any] = {
            "schema_name": "video-manager.youtube-copy-apply-result",
            "schema_version": 3,
            "started_at": datetime.now(UTC).isoformat(),
            "source_plan": str(args.plan.resolve()),
            "plan_sha256": plan["plan_sha256"],
            "checked_video_ids_sha256": plan["checked_video_ids_sha256"],
            "source_audit_sha256": plan["source_audit_sha256"],
            "backup": str(backup_output.resolve()),
            "account": args.account,
            "channel_id": target_channel,
            "status": "running",
            "summary": {
                "planned": len(operations),
                "prepared": len(preflight.prepared),
                "already_applied": preflight.already_applied,
                "revision_drift_tolerated": preflight.revision_drift_tolerated,
                "attempted": 0,
                "applied": 0,
                "postflight_verified": 0,
                "rollback_safe_original": 0,
                "rollback_failed": 0,
            },
            "attempted": attempted,
            "applied": applied,
            "postflight_failures": [],
            "rollback": rollback_results,
        }
        _atomic_write(result_output, result)

        failure: BaseException | None = None
        try:
            for operation in preflight.prepared:
                attempt_record = {
                    "video_id": operation["video_id"],
                    "title": operation["title"],
                    "started_at": datetime.now(UTC).isoformat(),
                    "status": "attempting",
                }
                attempted.append(attempt_record)
                result["summary"]["attempted"] = len(attempted)
                _atomic_write(result_output, result)

                verified = writer.replace_description(
                    video_id=str(operation["video_id"]),
                    expected_channel_id=str(operation["channel_id"]),
                    expected_revision=str(operation["expected_revision"]),
                    expected_description=str(operation["before_description"]),
                    new_description=str(operation["after_description"]),
                )
                attempt_record["status"] = "verified"
                attempt_record["finished_at"] = datetime.now(UTC).isoformat()
                applied.append(
                    {
                        **operation,
                        "after_revision": verified.revision,
                        "verified": True,
                    }
                )
                result["summary"]["applied"] = len(applied)
                _atomic_write(result_output, result)
                print(f"Updated and verified {verified.video_id} — {verified.title}")

            postflight_failures = verify_copy_operations(
                preflight.prepared,
                confirm_channel=target_channel,
                writer=writer,
            )
            result["postflight_failures"] = postflight_failures
            if postflight_failures:
                failed_ids = ", ".join(item["video_id"] for item in postflight_failures)
                raise YouTubeWriteError(f"Final batch postflight failed for: {failed_ids}")
            result["summary"]["postflight_verified"] = len(preflight.prepared)
        except BaseException as exc:  # rollback must also run after Ctrl+C
            failure = exc
            print(f"Apply failed; starting guarded rollback: {exc}")

        if failure is not None:
            for operation in reversed(preflight.prepared[: len(attempted)]):
                video_id = str(operation["video_id"])
                try:
                    restored = writer.restore_description_if_current(
                        video_id=video_id,
                        expected_channel_id=str(operation["channel_id"]),
                        expected_current_description=str(operation["after_description"]),
                        restore_description=str(operation["before_description"]),
                    )
                    rollback_results.append(
                        {
                            "video_id": video_id,
                            "status": "safe_original",
                            "revision": restored.revision,
                        }
                    )
                    print(f"Rollback safe/original {video_id}")
                except YouTubeWriteError as rollback_exc:
                    rollback_results.append({"video_id": video_id, "status": "failed", "error": str(rollback_exc)})
                    print(f"Rollback failed {video_id}: {rollback_exc}")
                result["summary"]["rollback_safe_original"] = sum(
                    item["status"] == "safe_original" for item in rollback_results
                )
                result["summary"]["rollback_failed"] = sum(item["status"] == "failed" for item in rollback_results)
                _atomic_write(result_output, result)

        rollback_failed = int(result["summary"]["rollback_failed"])
        result["status"] = _result_status(failure, rollback_failed)
        if failure is not None:
            result["error"] = f"{type(failure).__name__}: {failure}"
        result["finished_at"] = datetime.now(UTC).isoformat()
        _atomic_write(result_output, result)
        print(f"Result log → {result_output}")

        if failure is not None:
            if isinstance(failure, KeyboardInterrupt):
                raise failure
            return 2
        print(f"Completed {len(applied)} verified description updates; final postflight verified the whole batch.")
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, YouTubeWriteError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
