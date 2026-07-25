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


def main() -> int:
    _configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description=(
            "Refresh approved YouTube top-level comments in one guarded workflow: "
            "scan, audit, build an exact create/update plan, live preflight, and optional execution."
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
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-channel", default="")
    parser.add_argument("--write-delay", type=float, default=3.0)
    parser.add_argument("--max-operations", type=int, default=200)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    settings = get_settings()
    content_dir = args.content_dir or repo_root / "content" / "youtube-comments"
    if not content_dir.is_dir():
        print(f"ERROR: content directory not found: {content_dir}", file=sys.stderr)
        return 2
    if args.execute and args.confirm_channel != args.channel:
        print("ERROR: --execute requires exact --confirm-channel.", file=sys.stderr)
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
            "--include-updates",
            "--output",
            str(plan_path),
        ]
        if not args.create_missing:
            plan_command.append("--updates-only")
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
        if not operations:
            print("\nNo approved YouTube comments require changes.")
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
            return 0

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
        return 0
    except (FileNotFoundError, OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
