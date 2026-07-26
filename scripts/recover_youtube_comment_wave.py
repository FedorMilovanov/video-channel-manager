from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.youtube.comment_plan import validate_comment_plan

_AUDIT_SCHEMA = "video-manager.youtube-comment-audit"
_JOURNAL_SCHEMA = "video-manager.youtube-comment-apply-journal"
_CERTIFICATE_SCHEMA = "video-manager.youtube-comment-coverage-certificate"
_AUDIT_STATUSES = frozenset({"owned_present", "foreign_only", "missing", "comments_disabled", "error"})


def _configure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _strict_nonnegative_int(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer.")
    return value


def _run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    print("\n$ " + subprocess.list2cmdline(list(command)))
    return subprocess.run(
        list(command),
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _require_success(completed: subprocess.CompletedProcess[str], *, stage: str) -> None:
    if completed.returncode != 0:
        raise RuntimeError(f"{stage} failed with exit code {completed.returncode}.")


def _script(repo_root: Path, name: str) -> str:
    path = repo_root / "scripts" / name
    if not path.is_file():
        raise FileNotFoundError(path)
    return str(path)


def _latest_snapshot(data_dir: Path, *, account: str, channel: str) -> Path:
    candidates = sorted(
        (data_dir / "exports").glob(f"youtube-{account}-{channel}-*.json"),
        key=lambda item: item.stat().st_mtime_ns,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(f"No YouTube snapshot found for account={account} channel={channel}.")
    return candidates[0]


def validate_recovery_journal(
    journal: dict[str, Any],
    *,
    plan: dict[str, Any],
    require_completed_status: bool,
) -> dict[str, int]:
    if journal.get("schema_name") != _JOURNAL_SCHEMA or journal.get("schema_version") != 1:
        raise ValueError("Unsupported YouTube comment apply journal schema.")
    for key in ("plan_sha256", "channel_id", "source_snapshot"):
        if journal.get(key) != plan.get(key):
            raise ValueError(f"Apply journal {key} does not match the signed plan.")
    if require_completed_status and journal.get("status") != "completed":
        raise ValueError("Apply journal is not completed after verify-only recovery.")

    operations = plan.get("operations")
    attempts = journal.get("attempts")
    if not isinstance(operations, list) or not all(isinstance(item, dict) for item in operations):
        raise ValueError("Signed plan operations must be a list of objects.")
    if not isinstance(attempts, dict):
        raise ValueError("Apply journal attempts must be an object.")

    operation_by_id = {str(item["operation_id"]): item for item in operations}
    if set(attempts) != set(operation_by_id):
        missing = sorted(set(operation_by_id) - set(attempts))
        extra = sorted(set(attempts) - set(operation_by_id))
        details: list[str] = []
        if missing:
            details.append(f"missing={','.join(missing[:10])}")
        if extra:
            details.append(f"extra={','.join(extra[:10])}")
        raise ValueError("Apply journal operation set does not match the signed plan: " + "; ".join(details))

    completed = 0
    for operation_id, operation in operation_by_id.items():
        attempt = attempts[operation_id]
        if not isinstance(attempt, dict) or attempt.get("status") != "completed":
            raise ValueError(f"Apply journal attempt {operation_id} is not completed.")
        if attempt.get("video_id") != operation.get("video_id"):
            raise ValueError(f"Apply journal attempt {operation_id} has a different video_id.")
        if attempt.get("action") != operation.get("action"):
            raise ValueError(f"Apply journal attempt {operation_id} has a different action.")
        completed += 1

    return {"planned": len(operation_by_id), "completed_attempts": completed}


def strict_coverage_summary(audit: dict[str, Any], *, expected_channel: str) -> dict[str, int]:
    if audit.get("schema_name") != _AUDIT_SCHEMA or audit.get("schema_version") != 1:
        raise ValueError("Unsupported YouTube comment audit schema.")
    if audit.get("channel_id") != expected_channel:
        raise ValueError("YouTube comment audit channel does not match the requested channel.")

    inventory_count = _strict_nonnegative_int(audit.get("inventory_video_count"), field="inventory_video_count")
    videos = audit.get("videos")
    raw_counts = audit.get("counts")
    if not isinstance(videos, list) or not all(isinstance(item, dict) for item in videos):
        raise ValueError("YouTube comment audit videos must be a list of objects.")
    if len(videos) != inventory_count:
        raise ValueError("YouTube comment audit video list length does not match inventory_video_count.")
    if not isinstance(raw_counts, dict):
        raise ValueError("YouTube comment audit does not contain a counts object.")

    declared_counts: dict[str, int] = {}
    for raw_status, raw_value in raw_counts.items():
        status = str(raw_status)
        if status not in _AUDIT_STATUSES:
            raise ValueError(f"YouTube comment audit contains an unknown status: {status}.")
        declared_counts[status] = _strict_nonnegative_int(raw_value, field=f"counts.{status}")

    actual_counts: Counter[str] = Counter()
    seen_video_ids: set[str] = set()
    duplicate_owned_video_ids: list[str] = []
    non_owned_video_ids: list[str] = []
    for item in videos:
        video_id = item.get("video_id")
        status = item.get("status")
        if not isinstance(video_id, str) or not video_id:
            raise ValueError("YouTube comment audit contains an invalid video_id.")
        if video_id in seen_video_ids:
            raise ValueError(f"YouTube comment audit contains duplicate video_id {video_id}.")
        seen_video_ids.add(video_id)
        if not isinstance(status, str) or status not in _AUDIT_STATUSES:
            raise ValueError(f"YouTube comment audit video {video_id} has an invalid status.")
        actual_counts[status] += 1

        owned_count = _strict_nonnegative_int(
            item.get("owned_comment_count"),
            field=f"videos[{video_id}].owned_comment_count",
        )
        if status == "owned_present" and owned_count != 1:
            duplicate_owned_video_ids.append(video_id)
        if status != "owned_present":
            non_owned_video_ids.append(video_id)

    normalized_declared = {status: declared_counts.get(status, 0) for status in _AUDIT_STATUSES}
    normalized_actual = {status: actual_counts.get(status, 0) for status in _AUDIT_STATUSES}
    if normalized_declared != normalized_actual:
        raise ValueError("YouTube comment audit counts do not match the per-video statuses.")
    if sum(normalized_declared.values()) != inventory_count:
        raise ValueError("YouTube comment audit counts do not account for every inventory video.")
    if duplicate_owned_video_ids:
        sample = ", ".join(duplicate_owned_video_ids[:10])
        raise ValueError(f"Public videos with duplicate channel-authored comments: {sample}.")
    if non_owned_video_ids:
        sample = ", ".join(non_owned_video_ids[:10])
        raise ValueError(f"Public videos without exactly one channel-authored comment: {sample}.")
    if normalized_declared["owned_present"] != inventory_count:
        raise ValueError("owned_present does not equal the public inventory size.")

    return {
        "inventory_video_count": inventory_count,
        "owned_present": normalized_declared["owned_present"],
        "foreign_only": normalized_declared["foreign_only"],
        "missing": normalized_declared["missing"],
        "comments_disabled": normalized_declared["comments_disabled"],
        "error": normalized_declared["error"],
    }


def main() -> int:
    _configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description=(
            "Recover a previously written YouTube comment wave without writing, then prove exact-one-comment "
            "coverage across the fresh public inventory."
        )
    )
    parser.add_argument("plan", type=Path, help="Original signed YouTube comment plan")
    parser.add_argument("--journal", type=Path, required=True, help="Original apply journal for the same plan")
    parser.add_argument("--account", default="legendary-poet")
    parser.add_argument("--channel", required=True)
    parser.add_argument("--snapshot", type=Path, help="Use an explicitly supplied fresh snapshot instead of scanning")
    parser.add_argument("--max-operations", type=int, default=200)
    parser.add_argument("--certificate", type=Path)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    settings = get_settings()
    plan_path = args.plan.resolve()
    journal_path = args.journal.resolve()

    try:
        plan = _read_json(plan_path)
        validation_errors = validate_comment_plan(plan)
        if validation_errors:
            raise ValueError("; ".join(validation_errors))
        if plan.get("channel_id") != args.channel:
            raise ValueError("Signed plan channel does not match --channel.")
        operations = plan.get("operations")
        if not isinstance(operations, list):
            raise ValueError("Signed plan operations must be a list.")
        if len(operations) > args.max_operations:
            raise ValueError(f"Plan has {len(operations)} operations, above --max-operations {args.max_operations}.")

        journal_before = _read_json(journal_path)
        journal_summary = validate_recovery_journal(
            journal_before,
            plan=plan,
            require_completed_status=False,
        )

        verify = _run(
            [
                sys.executable,
                "-X",
                "utf8",
                _script(repo_root, "apply_youtube_comment_plan.py"),
                str(plan_path),
                "--account",
                args.account,
                "--verify-only",
                "--journal",
                str(journal_path),
                "--confirm-channel",
                args.channel,
                "--confirm-source-snapshot",
                str(plan["source_snapshot"]),
                "--confirm-plan-sha256",
                str(plan["plan_sha256"]),
                "--max-operations",
                str(args.max_operations),
            ]
        )
        _require_success(verify, stage="Verify-only recovery")

        journal_after = _read_json(journal_path)
        journal_summary = validate_recovery_journal(
            journal_after,
            plan=plan,
            require_completed_status=True,
        )

        if args.snapshot is not None:
            snapshot = args.snapshot.resolve()
            if not snapshot.is_file():
                raise FileNotFoundError(snapshot)
        else:
            manager = shutil.which("video-manager")
            if manager is None:
                raise FileNotFoundError("video-manager executable is not available in the active environment")
            scan = _run(
                [
                    manager,
                    "youtube",
                    "scan",
                    "--account",
                    args.account,
                    "--channel",
                    args.channel,
                ]
            )
            _require_success(scan, stage="Fresh YouTube scan")
            snapshot = _latest_snapshot(settings.data_dir, account=args.account, channel=args.channel)

        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        reports_dir = settings.data_dir / "reports"
        audit_path = reports_dir / f"youtube-comment-audit-closure-{args.channel}-{timestamp}.json"
        audit = _run(
            [
                sys.executable,
                "-X",
                "utf8",
                _script(repo_root, "audit_youtube_comments.py"),
                str(snapshot),
                "--account",
                args.account,
                "--channel",
                args.channel,
                "--output",
                str(audit_path),
            ]
        )
        _require_success(audit, stage="Fresh channel-wide comment audit")
        coverage = strict_coverage_summary(_read_json(audit_path), expected_channel=args.channel)

        certificate_path = args.certificate
        if certificate_path is None:
            certificate_path = reports_dir / f"youtube-comment-coverage-certificate-{args.channel}-{timestamp}.json"
        certificate_path = certificate_path.resolve()
        certificate = {
            "schema_name": _CERTIFICATE_SCHEMA,
            "schema_version": 1,
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "completed",
            "mode": "verify-only-plus-fresh-audit",
            "remote_writes": 0,
            "account_alias": args.account,
            "channel_id": args.channel,
            "plan_path": str(plan_path),
            "plan_sha256": plan["plan_sha256"],
            "plan_file_sha256": _sha256_file(plan_path),
            "journal_path": str(journal_path),
            "journal_file_sha256": _sha256_file(journal_path),
            "planned_operations": journal_summary["planned"],
            "completed_attempts": journal_summary["completed_attempts"],
            "snapshot_path": str(snapshot),
            "snapshot_file_sha256": _sha256_file(snapshot),
            "audit_path": str(audit_path),
            "audit_file_sha256": _sha256_file(audit_path),
            "coverage": coverage,
        }
        _write_json(certificate_path, certificate)

        print("\nYOUTUBE COMMENT COVERAGE PROVED")
        print(f"  public videos:       {coverage['inventory_video_count']}")
        print(f"  exactly one owned:   {coverage['owned_present']}")
        print("  missing:             0")
        print("  foreign_only:        0")
        print("  comments_disabled:   0")
        print("  API errors:          0")
        print("  remote writes:       0")
        print(f"  audit:                {audit_path}")
        print(f"  certificate:          {certificate_path}")
        return 0
    except (FileNotFoundError, OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
