#!/usr/bin/env python3
"""Build a deterministic, reviewable YouTube description fix plan from an AuditPackage."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from difflib import unified_diff
from pathlib import Path
from typing import Any

from video_channel_manager.editorial import autofix_youtube_description, validate_youtube_description


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


def _build_plan(payload: dict[str, Any], source: Path) -> tuple[dict[str, Any], str, int]:
    videos = [item for item in payload.get("videos", []) if isinstance(item, dict)]
    operations: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    for video in videos:
        before = str(video.get("description") or "")
        after, fixes = autofix_youtube_description(before)
        ref = _remote_ref(video)
        video_id = str(ref.get("remote_id") or "unknown")
        channel_id = str(ref.get("channel_id") or "")
        title = str(video.get("title") or video_id)

        if after != before:
            operations.append(
                {
                    "operation": "replace_video_description",
                    "platform": "youtube",
                    "channel_id": channel_id,
                    "video_id": video_id,
                    "title": title,
                    "expected_revision": video.get("revision"),
                    "before_description": before,
                    "after_description": after,
                    "fixes": [asdict(fix) for fix in fixes],
                }
            )

        remaining_errors = [
            asdict(finding)
            for finding in validate_youtube_description(after)
            if finding.severity == "error"
        ]
        if remaining_errors:
            unresolved.append(
                {
                    "video_id": video_id,
                    "channel_id": channel_id,
                    "title": title,
                    "errors": remaining_errors,
                }
            )

    plan = {
        "schema_name": "video-manager.youtube-copy-fix-plan",
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "source_audit_package": str(source),
        "read_only": True,
        "videos_checked": len(videos),
        "operations_count": len(operations),
        "unresolved_error_videos": len(unresolved),
        "operations": operations,
        "unresolved": unresolved,
    }

    lines = [
        "# YouTube deterministic copy-fix plan",
        "",
        f"Source: `{source}`",
        "",
        "> This report changes no remote data. It contains deterministic before/after proposals only.",
        "",
        f"- Videos checked: **{len(videos)}**",
        f"- Videos with safe changes: **{len(operations)}**",
        f"- Videos with unresolved error-level findings after safe fixes: **{len(unresolved)}**",
        "",
    ]

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
            lines.extend([f"## {item['title']}", "", f"Video ID: `{item['video_id']}`", ""])
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
    except (OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    if not isinstance(payload, dict) or payload.get("schema_name") != "video-manager.audit-package":
        parser.error("Input must be a video-manager AuditPackage JSON object.")

    plan, report, unresolved_count = _build_plan(payload, args.input)
    plan_output = args.plan_output or _default_output(args.input, "-copy-fix-plan.json")
    report_output = args.report_output or _default_output(args.input, "-copy-fix-report.md")

    plan_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.parent.mkdir(parents=True, exist_ok=True)
    plan_output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_output.write_text(report, encoding="utf-8")

    print(f"Wrote {plan_output}")
    print(f"Wrote {report_output}")
    print(f"Safe description changes: {plan['operations_count']}")
    print(f"Unresolved error-level videos: {unresolved_count}")

    return 1 if args.fail_on_unresolved and unresolved_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
