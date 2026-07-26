from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

from video_channel_manager.config import get_settings

_SUMMARY_PATTERNS = {
    "planned": re.compile(r"(?m)^\s*planned operations:\s*(\d+)\s*$"),
    "ready": re.compile(r"(?m)^\s*ready now:\s*(\d+)\s*$"),
    "already": re.compile(r"(?m)^\s*already applied:\s*(\d+)\s*$"),
    "blockers": re.compile(r"(?m)^\s*blockers:\s*(\d+)\s*$"),
}
_ACTIONABLE_AUDIT_STATUSES = ("missing", "foreign_only")


def _configure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


def parse_preflight_summary(output: str) -> dict[str, int]:
    summary: dict[str, int] = {}
    for key, pattern in _SUMMARY_PATTERNS.items():
        match = pattern.search(output)
        if match is None:
            raise ValueError(f"Cannot parse '{key}' from YouTube comment preflight output.")
        summary[key] = int(match.group(1))
    return summary


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return payload


def actionable_tail_from_audit(payload: dict[str, Any]) -> int:
    counts = payload.get("counts")
    if not isinstance(counts, dict):
        raise ValueError("YouTube comment audit does not contain a counts object.")
    return sum(int(counts.get(status) or 0) for status in _ACTIONABLE_AUDIT_STATUSES)


def plan_mode_arguments(*, create_missing: bool, creates_only: bool) -> list[str]:
    """Translate the public workflow mode into fail-closed plan-builder flags."""

    if creates_only:
        return []
    if create_missing:
        return ["--include-updates"]
    return ["--include-updates", "--updates-only"]


def _run(command: Sequence[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    print("\n$ " + subprocess.list2cmdline(list(command)))
    completed = subprocess.run(
        list(command),
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=capture,
    )
    if capture:
        if completed.stdout:
            print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n")
        if completed.stderr:
            print(completed.stderr, file=sys.stderr, end="" if completed.stderr.endswith("\n") else "\n")
    return completed


def _require_success(completed: subprocess.CompletedProcess[str], *, stage: str) -> None:
    if completed.returncode != 0:
        raise RuntimeError(f"{stage} failed with exit code {completed.returncode}.")


def _latest_snapshot(data_dir: Path, *, account: str, channel: str) -> Path:
    candidates = sorted(
        (data_dir / "exports").glob(f"youtube-{account}-{channel}-*.json"),
        key=lambda item: item.stat().st_mtime_ns,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(f"No YouTube snapshot found for account={account} channel={channel}.")
    return candidates[0]


def _script(repo_root: Path, name: str) -> str:
    path = repo_root / "scripts" / name
    if not path.is_file():
        raise FileNotFoundError(path)
    return str(path)


def _audit_command(
    *,
    repo_root: Path,
    snapshot: Path,
    account: str,
    channel: str,
    output: Path,
) -> list[str]:
    return [
        sys.executable,
        "-X",
        "utf8",
        _script(repo_root, "audit_youtube_comments.py"),
        str(snapshot),
        "--account",
        account,
        "--channel",
        channel,
        "--output",
        str(output),
    ]


def main() -> int:
    _configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description=(
            "Refresh approved YouTube top-level comments in one guarded workflow: "
            "scan, audit, build an exact create/update plan, live preflight, optional execution, "
            "and optional channel-wide postflight."
        )
    )
    parser.add_argument("--account", default="legendary-poet")
    parser.add_argument("--channel", required=True)
    parser.add_argument("--content-dir", type=Path)
    parser.add_argument("--snapshot", type=Path, help="Use an existing snapshot instead of running a fresh scan.")
    parser.add_argument(
        "--skip-scan", action="store_true", help="Use the newest matching snapshot in the data directory."
    )
    parser.add_argument(
        "--create-missing", action="store_true", help="Also create approved comments where none exists."
    )
    parser.add_argument(
        "--creates-only",
        action="store_true",
        help="Build a create-only plan and refuse any update operation. Requires --create-missing.",
    )
    parser.add_argument(
        "--require-complete-coverage",
        action="store_true",
        help="Fail before plan signing unless every live missing/foreign_only video has a valid approved create operation.",
    )
    parser.add_argument(
        "--require-no-review-only",
        action="store_true",
        help="Fail before plan signing if any approved record is excluded into review-only.",
    )
    parser.add_argument(
        "--postflight-audit",
        action="store_true",
        help="Run a fresh channel-wide comment audit after verified execution.",
    )
    parser.add_argument(
        "--require-zero-tail",
        action="store_true",
        help="After execution, fail if the postflight audit still has missing or foreign_only public videos.",
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-channel", default="")
    parser.add_argument("--write-delay", type=float, default=3.0)
    parser.add_argument("--max-operations", type=int, default=200)
    args = parser.parse_args()

    if args.execute and args.confirm_channel != args.channel:
        print("ERROR: --execute requires exact --confirm-channel.", file=sys.stderr)
        return 2
    if args.creates_only and not args.create_missing:
        print("ERROR: --creates-only requires --create-missing.", file=sys.stderr)
        return 2
    if args.require_complete_coverage and not args.create_missing:
        print("ERROR: --require-complete-coverage requires --create-missing.", file=sys.stderr)
        return 2
    if args.require_zero_tail and not args.execute:
        print("ERROR: --require-zero-tail requires --execute.", file=sys.stderr)
        return 2

    repo_root = Path(__file__).resolve().parents[1]
    settings = get_settings()
    content_dir = args.content_dir or repo_root / "content" / "youtube-comments"
    if not content_dir.is_dir():
        print(f"ERROR: content directory not found: {content_dir}", file=sys.stderr)
        return 2

    try:
        if args.snapshot is not None:
            snapshot = args.snapshot.resolve()
            if not snapshot.is_file():
                raise FileNotFoundError(snapshot)
        else:
            if not args.skip_scan:
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
                _require_success(scan, stage="YouTube scan")
            snapshot = _latest_snapshot(settings.data_dir, account=args.account, channel=args.channel)

        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        reports_dir = settings.data_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        audit_path = reports_dir / f"youtube-comment-audit-refresh-{args.channel}-{timestamp}.json"
        plan_path = reports_dir / f"youtube-comment-update-plan-{args.channel}-{timestamp}.json"

        print(f"\nSnapshot: {snapshot}")
        print(f"Content:  {content_dir}")

        audit = _run(
            _audit_command(
                repo_root=repo_root,
                snapshot=snapshot,
                account=args.account,
                channel=args.channel,
                output=audit_path,
            )
        )
        _require_success(audit, stage="YouTube comment audit")

        plan_command = [
            sys.executable,
            "-X",
            "utf8",
            _script(repo_root, "build_youtube_comment_plan.py"),
            str(snapshot),
            str(audit_path),
            "--account",
            args.account,
            "--content-dir",
            str(content_dir),
            "--output",
            str(plan_path),
        ]
        plan_command.extend(plan_mode_arguments(create_missing=args.create_missing, creates_only=args.creates_only))
        if args.require_complete_coverage:
            plan_command.append("--require-complete-coverage")
        if args.require_no_review_only:
            plan_command.append("--require-no-review-only")
        plan_result = _run(plan_command)
        _require_success(plan_result, stage="YouTube comment plan build")

        plan = _read_json(plan_path)
        operations = plan.get("operations")
        if not isinstance(operations, list):
            raise ValueError("Generated plan does not contain an operations list.")
        if len(operations) > args.max_operations:
            raise ValueError(
                f"Generated plan has {len(operations)} operations, above --max-operations {args.max_operations}."
            )
        if args.creates_only:
            non_create = [
                str(item.get("video_id") or "")
                for item in operations
                if not isinstance(item, dict) or item.get("action") != "create"
            ]
            if non_create:
                raise ValueError("Create-only mode generated a non-create operation for: " + ", ".join(non_create))
        if not operations:
            print("\nNo approved YouTube comments require changes.")
            if args.require_zero_tail:
                tail = actionable_tail_from_audit(_read_json(audit_path))
                if tail:
                    raise RuntimeError(f"No operations were planned, but the live actionable tail is still {tail}.")
            return 0

        apply_script = _script(repo_root, "apply_youtube_comment_plan_compat.py")
        dry = _run(
            [
                sys.executable,
                "-X",
                "utf8",
                apply_script,
                str(plan_path),
                "--account",
                args.account,
                "--max-operations",
                str(args.max_operations),
            ],
            capture=True,
        )
        _require_success(dry, stage="YouTube comment live preflight")
        dry_text = (dry.stdout or "") + "\n" + (dry.stderr or "")
        summary = parse_preflight_summary(dry_text)
        if summary["planned"] != len(operations):
            raise ValueError("Live preflight operation count does not match the signed plan.")
        if summary["ready"] + summary["already"] + summary["blockers"] != summary["planned"]:
            raise ValueError("Live preflight summary does not account for every planned operation.")
        if summary["blockers"]:
            raise RuntimeError(f"Live preflight has {summary['blockers']} blocker(s); refusing all writes.")

        print("\nPrepared artifacts:")
        print(f"  audit: {audit_path}")
        print(f"  plan:  {plan_path}")

        if not args.execute:
            print("\nDry-run completed. No YouTube write method was called.")
            return 0
        if summary["ready"] == 0:
            print("\nAll approved changes are already present on YouTube.")
        else:
            execute = _run(
                [
                    sys.executable,
                    "-X",
                    "utf8",
                    apply_script,
                    str(plan_path),
                    "--account",
                    args.account,
                    "--execute",
                    "--confirm-channel",
                    str(plan["channel_id"]),
                    "--confirm-count",
                    str(summary["ready"]),
                    "--confirm-source-snapshot",
                    str(plan["source_snapshot"]),
                    "--confirm-plan-sha256",
                    str(plan["plan_sha256"]),
                    "--max-operations",
                    str(args.max_operations),
                    "--write-delay",
                    str(args.write_delay),
                ]
            )
            _require_success(execute, stage="YouTube comment execution")
            print("\nYouTube comment refresh completed and verified.")

        if args.postflight_audit or args.require_zero_tail:
            postflight_timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
            postflight_path = (
                reports_dir / f"youtube-comment-audit-postflight-{args.channel}-{postflight_timestamp}.json"
            )
            postflight = _run(
                _audit_command(
                    repo_root=repo_root,
                    snapshot=snapshot,
                    account=args.account,
                    channel=args.channel,
                    output=postflight_path,
                )
            )
            _require_success(postflight, stage="YouTube comment postflight audit")
            postflight_payload = _read_json(postflight_path)
            tail = actionable_tail_from_audit(postflight_payload)
            print("\nChannel-wide postflight:")
            print(f"  actionable tail (missing + foreign_only): {tail}")
            print(f"  audit: {postflight_path}")
            if args.require_zero_tail and tail:
                raise RuntimeError(
                    f"Verified writes completed, but the channel-wide postflight still has {tail} actionable video(s)."
                )
            if args.require_zero_tail:
                print("  zero-tail requirement satisfied")
        return 0
    except (FileNotFoundError, OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
