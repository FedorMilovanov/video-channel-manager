#!/usr/bin/env python3
"""Recompute a completed YouTube copy apply log with the current conservative ruleset."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from difflib import unified_diff
from pathlib import Path
from typing import Any

from video_channel_manager.editorial import autofix_youtube_description, validate_youtube_description

RULESET = "youtube-copy-safe-v2"


def _default_output(input_path: Path, suffix: str) -> Path:
    return input_path.with_name(f"{input_path.stem}{suffix}")


def _sha256_text(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _required_text(item: dict[str, Any], field: str) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Apply result item is missing required string field: {field}")
    return value


def _diff(before: str, after: str, video_id: str) -> str:
    return "\n".join(
        unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile=f"{video_id}:currently-applied",
            tofile=f"{video_id}:recomputed",
            lineterm="",
        )
    )


def build_repair_plan(payload: dict[str, Any], source: Path) -> tuple[dict[str, Any], str]:
    if payload.get("schema_name") != "video-manager.youtube-copy-apply-result":
        raise ValueError("Input must be a video-manager.youtube-copy-apply-result JSON object.")
    if payload.get("status") != "completed":
        raise ValueError("Only a completed apply result can be recomputed automatically.")
    rollback = payload.get("rollback")
    if rollback not in (None, []):
        raise ValueError("Completed apply result unexpectedly contains rollback records.")

    raw_applied = payload.get("applied")
    if not isinstance(raw_applied, list) or not all(isinstance(item, dict) for item in raw_applied):
        raise ValueError("Apply result must contain an applied operation list.")

    account = str(payload.get("account") or "").strip()
    channel_id = str(payload.get("channel_id") or "").strip()
    if not account or not channel_id:
        raise ValueError("Apply result lacks account or channel_id.")

    operations: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    for item in raw_applied:
        video_id = _required_text(item, "video_id")
        item_channel = _required_text(item, "channel_id")
        title = _required_text(item, "title")
        original_before = _required_text(item, "before_description")
        currently_applied = _required_text(item, "after_description")
        after_revision = _required_text(item, "after_revision")
        if item_channel != channel_id:
            raise ValueError(f"Applied item {video_id} targets {item_channel}, not result channel {channel_id}.")

        recomputed, fixes = autofix_youtube_description(original_before)
        if recomputed == currently_applied:
            continue

        errors = [
            asdict(finding)
            for finding in validate_youtube_description(recomputed)
            if finding.severity == "error"
        ]
        if errors:
            unresolved.append(
                {
                    "video_id": video_id,
                    "channel_id": channel_id,
                    "title": title,
                    "errors": errors,
                }
            )
            continue

        operations.append(
            {
                "operation": "replace_video_description",
                "platform": "youtube",
                "ruleset": RULESET,
                "channel_id": channel_id,
                "video_id": video_id,
                "title": title,
                "expected_revision": after_revision,
                "before_description": currently_applied,
                "after_description": recomputed,
                "before_sha256": _sha256_text(currently_applied),
                "after_sha256": _sha256_text(recomputed),
                "recomputed_from_original_before_sha256": _sha256_text(original_before),
                "fixes": [asdict(fix) for fix in fixes],
                "rationale": (
                    "Recomputed from the original backup with the current conservative ruleset; "
                    "this removes only changes no longer considered deterministic."
                ),
            }
        )

    plan = {
        "schema_name": "video-manager.youtube-copy-fix-plan",
        "schema_version": 2,
        "ruleset": RULESET,
        "generated_at": datetime.now(UTC).isoformat(),
        "source_apply_result": str(source),
        "source_apply_status": "completed",
        "account": account,
        "channel_id": channel_id,
        "read_only": True,
        "videos_checked": len(raw_applied),
        "operations_count": len(operations),
        "unresolved_error_videos": len(unresolved),
        "operations": operations,
        "unresolved": unresolved,
    }

    lines = [
        "# YouTube copy ruleset rebuild",
        "",
        f"Source apply result: `{source}`",
        f"Ruleset: `{RULESET}`",
        "",
        "> This plan does not revert the whole batch. It recomputes each original description and changes only entries whose old automatic output differs from the current conservative rules.",
        "",
        f"- Previously applied descriptions checked: **{len(raw_applied)}**",
        f"- Corrective operations: **{len(operations)}**",
        f"- Blocked by unresolved errors: **{len(unresolved)}**",
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
        lines.extend(["# Unresolved", ""])
        for item in unresolved:
            lines.extend([f"## {item['title']}", "", f"Video ID: `{item['video_id']}`", ""])
            for finding in item["errors"]:
                lines.append(f"- `{finding['code']}`: {finding['message']}")
            lines.append("")

    return plan, "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Completed youtube-copy-apply-*.json")
    parser.add_argument("--plan-output", type=Path, help="Output JSON repair plan")
    parser.add_argument("--report-output", type=Path, help="Output Markdown repair report")
    args = parser.parse_args()

    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Input JSON must be an object.")
        plan, report = build_repair_plan(payload, args.input)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))

    plan_output = args.plan_output or _default_output(args.input, "-ruleset-rebuild-plan.json")
    report_output = args.report_output or _default_output(args.input, "-ruleset-rebuild-report.md")
    plan_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.parent.mkdir(parents=True, exist_ok=True)
    plan_output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_output.write_text(report, encoding="utf-8")

    print(f"Wrote {plan_output}")
    print(f"Wrote {report_output}")
    print(f"Corrective description changes: {plan['operations_count']}")
    print(f"Unresolved error-level videos: {plan['unresolved_error_videos']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
