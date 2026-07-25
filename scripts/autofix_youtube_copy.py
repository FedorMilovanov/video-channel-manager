#!/usr/bin/env python3
"""Build a deterministic, conservative YouTube description fix plan from an AuditPackage."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from difflib import unified_diff
from pathlib import Path
from typing import Any

from video_channel_manager.editorial import autofix_youtube_description, validate_youtube_description

RULESET = "youtube-copy-safe-v2"


def _default_output(input_path: Path, suffix: str) -> Path:
    report_dir = input_path.parent.parent / "reports" if input_path.parent.name == "exports" else input_path.parent
    return report_dir / f"{input_path.stem}{suffix}"


def _remote_ref(video: dict[str, Any]) -> dict[str, Any]:
    value = video.get("ref")
    return value if isinstance(value, dict) else {}


def _diff(before: str, after: str, video_id: str) -> str:
    lines = unified_diff(
        before.splitlines(),
        after.splitlines(),
        fromfile=f"{video_id}:before",
        tofile=f"{video_id}:after",
        lineterm="",
    )
    return "\n".join(lines)


def _sha256_text(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _source_sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _required_identity(video: dict[str, Any]) -> tuple[str, str, str, str]:
    ref = _remote_ref(video)
    video_id = str(ref.get("remote_id") or "").strip()
    channel_id = str(ref.get("channel_id") or "").strip()
    revision = str(video.get("revision") or "").strip()
    title = str(video.get("title") or video_id).strip()
    if not video_id or not channel_id or not revision:
        raise ValueError(
            f"Audit video lacks video_id/channel_id/revision: title={title!r}, "
            f"video_id={video_id!r}, channel_id={channel_id!r}, revision={revision!r}"
        )
    return video_id, channel_id, revision, title


def _build_plan(payload: dict[str, Any], source: Path) -> tuple[dict[str, Any], str, int]:
    videos = [item for item in payload.get("videos", []) if isinstance(item, dict)]
    operations: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    seen_video_ids: set[str] = set()
    fix_counts: Counter[str] = Counter()
    blocked_operations = 0

    for video in videos:
        video_id, channel_id, revision, title = _required_identity(video)
        if video_id in seen_video_ids:
            raise ValueError(f"Duplicate video_id in audit package: {video_id}")
        seen_video_ids.add(video_id)

        before = str(video.get("description") or "")
        after, fixes = autofix_youtube_description(before)
        remaining_errors = [
            asdict(finding)
            for finding in validate_youtube_description(after)
            if finding.severity == "error"
        ]

        if remaining_errors:
            blocked = after != before
            blocked_operations += int(blocked)
            unresolved.append(
                {
                    "video_id": video_id,
                    "channel_id": channel_id,
                    "title": title,
                    "blocked_from_automatic_apply": blocked,
                    "proposed_safe_fixes": [asdict(fix) for fix in fixes],
                    "errors": remaining_errors,
                }
            )
            # A description with a remaining structural error never enters an
            # automatic write plan, even when unrelated deterministic fixes exist.
            continue

        if after == before:
            continue

        for fix in fixes:
            fix_counts[fix.code] += 1
        operations.append(
            {
                "operation": "replace_video_description",
                "platform": "youtube",
                "ruleset": RULESET,
                "channel_id": channel_id,
                "video_id": video_id,
                "title": title,
                "expected_revision": revision,
                "before_description": before,
                "after_description": after,
                "before_sha256": _sha256_text(before),
                "after_sha256": _sha256_text(after),
                "fixes": [asdict(fix) for fix in fixes],
            }
        )

    plan = {
        "schema_name": "video-manager.youtube-copy-fix-plan",
        "schema_version": 2,
        "ruleset": RULESET,
        "generated_at": datetime.now(UTC).isoformat(),
        "source_audit_package": str(source),
        "source_audit_sha256": _source_sha256(source),
        "read_only": True,
        "videos_checked": len(videos),
        "operations_count": len(operations),
        "blocked_operations_count": blocked_operations,
        "unresolved_error_videos": len(unresolved),
        "fix_code_counts": dict(sorted(fix_counts.items())),
        "operations": operations,
        "unresolved": unresolved,
    }

    lines = [
        "# YouTube conservative copy-fix plan",
        "",
        f"Source: `{source}`",
        f"Ruleset: `{RULESET}`",
        "",
        "> This report changes no remote data. Punctuation scope that may belong to the surrounding sentence is review-only.",
        "",
        f"- Videos checked: **{len(videos)}**",
        f"- Videos with automatic safe changes: **{len(operations)}**",
        f"- Proposed operations blocked by remaining errors: **{blocked_operations}**",
        f"- Videos with unresolved error-level findings: **{len(unresolved)}**",
        "",
    ]

    if fix_counts:
        lines.extend(["## Automatic fix counts", ""])
        for code, count in sorted(fix_counts.items()):
            lines.append(f"- `{code}`: **{count}**")
        lines.append("")

    for operation in operations:
        video_id = str(operation["video_id"])
        lines.extend(
            [
                f"## {operation['title']}",
                "",
                f"Video ID: `{video_id}`",
                "",
                "Safe fixes:",
                "",
            ]
        )
        for fix in operation["fixes"]:
            before_excerpt = " ".join(str(fix["before"]).split())[:120]
            after_excerpt = " ".join(str(fix["after"]).split())[:120]
            lines.append(f"- `{fix['code']}`: `{before_excerpt}` → `{after_excerpt}`")
        lines.extend(
            [
                "",
                "```diff",
                _diff(
                    str(operation["before_description"]),
                    str(operation["after_description"]),
                    video_id,
                ),
                "```",
                "",
            ]
        )

    if unresolved:
        lines.extend(["# Unresolved error-level findings", ""])
        for item in unresolved:
            lines.extend(
                [
                    f"## {item['title']}",
                    "",
                    f"Video ID: `{item['video_id']}`",
                    f"Blocked from automatic apply: **{item['blocked_from_automatic_apply']}**",
                    "",
                ]
            )
            for finding in item["errors"]:
                excerpt = f" — `{finding['excerpt']}`" if finding.get("excerpt") else ""
                lines.append(f"- `{finding['code']}`: {finding['message']}{excerpt}")
            lines.append("")

    return plan, "\n".join(lines), len(unresolved)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="video-manager AuditPackage JSON")
    parser.add_argument("--plan-output", type=Path, help="Output JSON plan path")
    parser.add_argument("--report-output", type=Path, help="Output Markdown diff path")
    parser.add_argument(
        "--fail-on-unresolved",
        action="store_true",
        help="Exit with code 1 when safe fixes cannot resolve every error-level finding",
    )
    args = parser.parse_args()

    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema_name") != "video-manager.audit-package":
            raise ValueError("Input must be a video-manager AuditPackage JSON object.")
        plan, report, unresolved_count = _build_plan(payload, args.input)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))

    plan_output = args.plan_output or _default_output(args.input, "-copy-fix-plan.json")
    report_output = args.report_output or _default_output(args.input, "-copy-fix-report.md")

    plan_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.parent.mkdir(parents=True, exist_ok=True)
    plan_output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_output.write_text(report, encoding="utf-8")

    print(f"Wrote {plan_output}")
    print(f"Wrote {report_output}")
    print(f"Safe description changes: {plan['operations_count']}")
    print(f"Blocked operations: {plan['blocked_operations_count']}")
    print(f"Unresolved error-level videos: {unresolved_count}")

    return 1 if args.fail_on_unresolved and unresolved_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
