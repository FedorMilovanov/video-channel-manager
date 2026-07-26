from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.youtube.comment_plan import validate_comment_plan
from video_channel_manager.platforms.youtube.comments import (
    TopLevelCommentSnapshot,
    YouTubeCommentConflictError,
    YouTubeCommentError,
    YouTubeCommentWriter,
    YouTubeCommentsDisabledError,
    comments_equivalent,
)
from video_channel_manager.platforms.youtube.models import InstalledClientConfig
from video_channel_manager.platforms.youtube.store import TokenStore
from video_channel_manager.platforms.youtube.write_lock import local_youtube_write_lock

_DEFAULT_POSTFLIGHT_DELAYS_SECONDS = (0.0, 3.0, 7.0, 15.0, 30.0)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _owned_comments(
    writer: YouTubeCommentWriter,
    *,
    video_id: str,
    channel_id: str,
) -> list[TopLevelCommentSnapshot]:
    return [item for item in writer.list_top_level_comments(video_id) if item.author_channel_id == channel_id]


def _classify_operation(writer: YouTubeCommentWriter, operation: dict[str, Any]) -> tuple[str, str]:
    channel_id = str(operation["channel_id"])
    video_id = str(operation["video_id"])
    action = str(operation["action"])
    new_text = str(operation["comment_text"])
    identity = writer.read_video_identity(video_id)
    if identity.channel_id != channel_id:
        return "conflict", f"video belongs to {identity.channel_id}"

    owned = _owned_comments(writer, video_id=video_id, channel_id=channel_id)
    if action == "create":
        for item in owned:
            if comments_equivalent(item.text, new_text):
                return "already_applied", item.comment_id
        if owned:
            return "conflict", f"{len(owned)} different channel-authored comment(s) already exist"
        return "ready", "no channel-authored top-level comment"

    comment_id = str(operation.get("expected_comment_id") or "")
    expected_text = str(operation.get("expected_comment_text") or "")
    current = next((item for item in owned if item.comment_id == comment_id), None)
    if current is None:
        return "conflict", "expected channel-authored comment was not found on the target video"
    if current.video_id != video_id or current.channel_id != channel_id:
        return "conflict", "existing comment target mismatch"
    if comments_equivalent(current.text, new_text):
        return "already_applied", comment_id
    if not comments_equivalent(current.text, expected_text):
        return "conflict", "existing comment text changed after review"
    return "ready", comment_id


def _preflight(writer: YouTubeCommentWriter, operations: list[dict[str, Any]]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for index, operation in enumerate(operations, start=1):
        operation_id = str(operation["operation_id"])
        video_id = str(operation["video_id"])
        title = str(operation.get("video_title") or video_id)
        print(f"[{index}/{len(operations)}] Preflight — {title}")
        try:
            status, detail = _classify_operation(writer, operation)
        except YouTubeCommentsDisabledError as exc:
            status, detail = "comments_disabled", str(exc)
        except YouTubeCommentError as exc:
            status, detail = "error", str(exc)
        results.append(
            {
                "operation_id": operation_id,
                "video_id": video_id,
                "status": status,
                "detail": detail,
            }
        )
    return results


def _journal_payload(plan: dict[str, Any], existing: dict[str, Any] | None) -> dict[str, Any]:
    if existing is not None:
        if existing.get("plan_sha256") != plan.get("plan_sha256"):
            raise ValueError("Existing journal belongs to a different comment plan.")
        if not isinstance(existing.get("attempts"), dict):
            raise ValueError("Existing comment journal has invalid attempts.")
        return existing
    return {
        "schema_name": "video-manager.youtube-comment-apply-journal",
        "schema_version": 1,
        "plan_sha256": plan["plan_sha256"],
        "channel_id": plan["channel_id"],
        "source_snapshot": plan["source_snapshot"],
        "started_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
        "status": "pending",
        "attempts": {},
    }


def _record_attempt(
    *,
    journal: dict[str, Any],
    journal_path: Path,
    operation_id: str,
    payload: dict[str, Any],
) -> None:
    attempts = journal.setdefault("attempts", {})
    if not isinstance(attempts, dict):
        raise ValueError("Journal attempts must be an object.")
    attempts[operation_id] = payload
    journal["updated_at"] = datetime.now(UTC).isoformat()
    _write_json(journal_path, journal)


def _status_groups(
    results: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    ready = [item for item in results if item["status"] == "ready"]
    already = [item for item in results if item["status"] == "already_applied"]
    blockers = [item for item in results if item["status"] not in {"ready", "already_applied"}]
    return ready, already, blockers


def _await_complete_postflight(
    writer: YouTubeCommentWriter,
    operations: list[dict[str, Any]],
    *,
    delays_seconds: tuple[float, ...] = _DEFAULT_POSTFLIGHT_DELAYS_SECONDS,
) -> list[dict[str, str]]:
    if not delays_seconds:
        raise ValueError("Postflight delays must contain at least one attempt.")

    last_results: list[dict[str, str]] = []
    for attempt, delay in enumerate(delays_seconds, start=1):
        if delay > 0:
            print(
                f"Waiting {delay:g}s for YouTube indexing before full postflight "
                f"attempt {attempt}/{len(delays_seconds)}…"
            )
            time.sleep(delay)
        else:
            print(f"Full postflight attempt {attempt}/{len(delays_seconds)}…")

        last_results = _preflight(writer, operations)
        ready, already, blockers = _status_groups(last_results)
        if not ready and not blockers and len(already) == len(operations):
            return last_results

        print(
            "Full postflight is not complete yet: "
            f"ready={len(ready)}, already_applied={len(already)}, blockers={len(blockers)}."
        )

    ready, already, blockers = _status_groups(last_results)
    unresolved = [item for item in last_results if item["status"] != "already_applied"]
    unresolved_summary = ", ".join(
        f"{item['video_id']}:{item['status']}" for item in unresolved[:10]
    )
    if len(unresolved) > 10:
        unresolved_summary += f", +{len(unresolved) - 10} more"
    raise YouTubeCommentError(
        "Full postflight did not confirm every planned comment operation after "
        f"{len(delays_seconds)} attempt(s): ready={len(ready)}, "
        f"already_applied={len(already)}, blockers={len(blockers)}. "
        f"Unconfirmed: {unresolved_summary or 'unknown'}."
    )


def _validate_verify_only_journal(
    plan: dict[str, Any],
    journal: dict[str, Any] | None,
) -> dict[str, Any]:
    if journal is None:
        raise ValueError("--verify-only requires an existing apply journal for this signed plan.")
    attempts = journal.get("attempts")
    if not isinstance(attempts, dict):
        raise ValueError("Existing comment journal has invalid attempts.")
    operations = plan.get("operations")
    if not isinstance(operations, list):
        raise ValueError("Plan operations must be a list.")

    expected_ids = {str(item["operation_id"]) for item in operations if isinstance(item, dict)}
    missing = sorted(expected_ids - set(attempts))
    incomplete = sorted(
        operation_id
        for operation_id in expected_ids & set(attempts)
        if not isinstance(attempts[operation_id], dict)
        or attempts[operation_id].get("status") != "completed"
    )
    if missing or incomplete:
        details: list[str] = []
        if missing:
            details.append(f"missing attempts: {', '.join(missing[:10])}")
        if incomplete:
            details.append(f"non-completed attempts: {', '.join(incomplete[:10])}")
        raise ValueError(
            "--verify-only refuses an incomplete write journal; " + "; ".join(details) + "."
        )
    return journal


def _mark_journal_completed(journal: dict[str, Any], journal_path: Path) -> None:
    journal["status"] = "completed"
    journal["completed_at"] = datetime.now(UTC).isoformat()
    journal["updated_at"] = journal["completed_at"]
    journal.pop("last_error", None)
    _write_json(journal_path, journal)


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run or apply a self-validating YouTube comment plan.")
    parser.add_argument("plan", type=Path)
    parser.add_argument("--account", default="legendary-poet")
    parser.add_argument("--confirm-channel", default="")
    parser.add_argument("--confirm-count", type=int)
    parser.add_argument("--confirm-source-snapshot", default="")
    parser.add_argument("--confirm-plan-sha256", default="")
    parser.add_argument("--max-operations", type=int, default=200)
    parser.add_argument("--write-delay", type=float, default=2.0)
    parser.add_argument("--journal", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--execute", action="store_true")
    mode.add_argument(
        "--verify-only",
        action="store_true",
        help="Perform locked retrying postflight only; never call a YouTube write method.",
    )
    args = parser.parse_args()

    try:
        plan = _read_json(args.plan)
        validation_errors = validate_comment_plan(plan)
        if validation_errors:
            raise ValueError("; ".join(validation_errors))
        operations_raw = plan.get("operations")
        if not isinstance(operations_raw, list):
            raise ValueError("Plan operations must be a list.")
        operations = [item for item in operations_raw if isinstance(item, dict)]
        if len(operations) != len(operations_raw):
            raise ValueError("Every plan operation must be an object.")
        if len(operations) > args.max_operations:
            raise ValueError(f"Plan has {len(operations)} operations, above --max-operations {args.max_operations}.")
        settings = get_settings()
        config = InstalledClientConfig.from_file(settings.youtube_client_secret_file)
        store = TokenStore(settings.data_dir)
        writer = YouTubeCommentWriter(client_config=config, token_store=store, account_alias=args.account)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot load comment plan: {exc}", file=sys.stderr)
        return 2

    if args.journal is None:
        plan_digest = str(plan["plan_sha256"]).removeprefix("sha256:")[:16]
        args.journal = settings.data_dir / "reports" / f"youtube-comment-apply-{plan_digest}.json"
    existing_journal: dict[str, Any] | None = None
    if args.journal.exists():
        try:
            existing_journal = _read_json(args.journal)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"ERROR: cannot read existing journal: {exc}", file=sys.stderr)
            return 2
    try:
        journal = _journal_payload(plan, existing_journal)
        if args.verify_only:
            journal = _validate_verify_only_journal(plan, existing_journal)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print("Reading live YouTube state before any write…")
    preflight = _preflight(writer, operations)
    ready, already, blockers = _status_groups(preflight)

    print("YouTube comment preflight:")
    print(f"  channel: {plan['channel_id']}")
    print(f"  source snapshot: {plan['source_snapshot']}")
    print(f"  plan SHA-256: {plan['plan_sha256']}")
    print(f"  planned operations: {len(operations)}")
    print(f"  ready now: {len(ready)}")
    print(f"  already applied: {len(already)}")
    print(f"  blockers: {len(blockers)}")
    print(f"  estimated write quota: {len(ready) * 50} units")
    for item in blockers:
        print(f"  BLOCKED {item['video_id']} — {item['status']}: {item['detail']}")

    if not args.execute and not args.verify_only:
        print("Dry-run only. No YouTube write method was called.")
        print(
            "Re-run with --execute and exact --confirm-channel, --confirm-count, "
            "--confirm-source-snapshot, and --confirm-plan-sha256 values; or use "
            "--verify-only with the original journal after a postflight-only failure."
        )
        return 0 if not blockers else 1

    expected_channel = str(plan["channel_id"])
    expected_snapshot = str(plan["source_snapshot"])
    expected_plan_sha = str(plan["plan_sha256"])
    if args.confirm_channel != expected_channel:
        print("ERROR: --confirm-channel does not match the plan.", file=sys.stderr)
        return 2
    if args.confirm_source_snapshot != expected_snapshot:
        print("ERROR: --confirm-source-snapshot does not match the plan.", file=sys.stderr)
        return 2
    if args.confirm_plan_sha256 != expected_plan_sha:
        print("ERROR: --confirm-plan-sha256 does not match the plan.", file=sys.stderr)
        return 2

    lock_path = settings.data_dir / "locks" / f"youtube-{args.account}-{expected_channel}.lock"

    if args.verify_only:
        try:
            with local_youtube_write_lock(lock_path, account=args.account, channel_id=expected_channel):
                print("Verify-only recovery: no YouTube write method will be called.")
                _await_complete_postflight(writer, operations)
                _mark_journal_completed(journal, args.journal)
        except (OSError, ValueError, YouTubeCommentError) as exc:
            journal["status"] = "verification_pending"
            journal["last_error"] = str(exc)
            journal["updated_at"] = datetime.now(UTC).isoformat()
            _write_json(args.journal, journal)
            print(f"ERROR: {exc}", file=sys.stderr)
            print(f"Journal → {args.journal}", file=sys.stderr)
            return 1

        print("YouTube comment recovery verification completed: 0 write(s); every operation is confirmed.")
        print(f"Journal → {args.journal}")
        return 0

    if args.confirm_count != len(ready):
        print(f"ERROR: --confirm-count must equal the live ready count {len(ready)}.", file=sys.stderr)
        return 2
    if blockers:
        print("ERROR: live preflight has blockers; refusing all writes.", file=sys.stderr)
        return 2

    ready_ids = {item["operation_id"] for item in ready}
    writes_completed = 0
    try:
        with local_youtube_write_lock(lock_path, account=args.account, channel_id=expected_channel):
            print("Re-running the complete live preflight under the channel writer lock…")
            locked_preflight = _preflight(writer, operations)
            locked_ready, _, locked_blockers = _status_groups(locked_preflight)
            locked_ready_ids = {item["operation_id"] for item in locked_ready}
            if locked_blockers or locked_ready_ids != ready_ids:
                raise YouTubeCommentConflictError(
                    "Live comment state changed between review and locked execution; refusing all writes."
                )

            operation_by_id = {str(item["operation_id"]): item for item in operations}
            for index, item in enumerate(locked_ready, start=1):
                operation_id = item["operation_id"]
                operation = operation_by_id[operation_id]
                video_id = str(operation["video_id"])
                action = str(operation["action"])
                print(f"[{index}/{len(locked_ready)}] {action} — {operation.get('video_title') or video_id}")
                _record_attempt(
                    journal=journal,
                    journal_path=args.journal,
                    operation_id=operation_id,
                    payload={
                        "status": "pending",
                        "action": action,
                        "video_id": video_id,
                        "started_at": datetime.now(UTC).isoformat(),
                    },
                )
                try:
                    if action == "create":
                        result = writer.create_top_level_comment(
                            video_id=video_id,
                            expected_channel_id=expected_channel,
                            text=str(operation["comment_text"]),
                        )
                    else:
                        result = writer.update_top_level_comment(
                            comment_id=str(operation["expected_comment_id"]),
                            video_id=video_id,
                            expected_channel_id=expected_channel,
                            expected_text=str(operation["expected_comment_text"]),
                            new_text=str(operation["comment_text"]),
                        )
                except YouTubeCommentError as exc:
                    _record_attempt(
                        journal=journal,
                        journal_path=args.journal,
                        operation_id=operation_id,
                        payload={
                            "status": "failed",
                            "action": action,
                            "video_id": video_id,
                            "error": str(exc),
                            "failed_at": datetime.now(UTC).isoformat(),
                        },
                    )
                    journal["status"] = "partial_failure"
                    _write_json(args.journal, journal)
                    raise
                _record_attempt(
                    journal=journal,
                    journal_path=args.journal,
                    operation_id=operation_id,
                    payload={
                        "status": "completed",
                        "action": action,
                        "video_id": video_id,
                        "thread_id": result.thread_id,
                        "comment_id": result.comment_id,
                        "comment_sha256": result.text_sha256,
                        "verified_at": datetime.now(UTC).isoformat(),
                    },
                )
                writes_completed += 1
                if args.write_delay > 0 and index < len(locked_ready):
                    time.sleep(args.write_delay)

            _await_complete_postflight(writer, operations)
            _mark_journal_completed(journal, args.journal)
    except (OSError, ValueError, YouTubeCommentError) as exc:
        if writes_completed and journal.get("status") != "partial_failure":
            journal["status"] = "verification_pending"
            journal["last_error"] = str(exc)
            journal["updated_at"] = datetime.now(UTC).isoformat()
            _write_json(args.journal, journal)
        print(f"ERROR: {exc}", file=sys.stderr)
        print(f"Journal → {args.journal}", file=sys.stderr)
        return 1

    print(f"YouTube comment synchronization completed: {len(ready)} write(s) verified.")
    print(f"Journal → {args.journal}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
