#!/usr/bin/env python3
"""Build a signed, reviewable VK editorial-only plan from a fresh VK snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk.editorial_cleanup_plan import build_vk_editorial_cleanup_plan


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path, help="Fresh VK AuditPackage JSON")
    parser.add_argument("--policy-json", type=Path, required=True, help="Reviewed VK editorial policy")
    parser.add_argument("--output", type=Path, default=Path("data/reports/vk-editorial-plan.json"))
    parser.add_argument("--report", type=Path, default=Path("data/reports/vk-editorial-plan.md"))
    return parser


def _load_audit(path: Path) -> AuditPackage:
    try:
        return AuditPackage.model_validate(json.loads(path.read_text(encoding="utf-8-sig")))
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"Cannot read AuditPackage {path}: {exc}") from exc


def _load_policy(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read VK editorial policy {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("VK editorial policy must be a JSON object")
    return payload


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _report(plan: dict[str, Any]) -> str:
    summary = plan["summary"]
    lines = [
        "# VK editorial cleanup plan",
        "",
        f"- Operation scope: `{plan['operation_scope']}`",
        f"- Target snapshot: `{plan['target_snapshot_id']}`",
        f"- Community: `{plan['target_community_id']}`",
        f"- Video coverage: `{plan['target_video_ids_sha256']}`",
        f"- Membership state: `{plan['initial_memberships_sha256']}`",
        f"- Policy: `{plan['policy_sha256']}`",
        f"- Plan: `{plan['plan_sha256']}`",
        "",
        "## Summary",
        "",
        f"- Videos: **{summary['videos_in_snapshot']}**",
        f"- Titles to update: **{summary['titles_to_update']}**",
        f"- Descriptions to update: **{summary['descriptions_to_update']}**",
        f"- Albums to rename: **{summary['albums_to_rename']}**",
        f"- Placements to add/remove: **{summary['placements_to_add']}/{summary['placements_to_remove']}**",
        f"- Videos to delete: **{summary['videos_to_delete']}**",
        f"- Review-only findings: **{summary['review_only']}**",
        f"- Total write operations: **{summary['total_operations']}**",
        "",
        "## Album title changes",
        "",
    ]
    for operation in plan["album_title_operations"]:
        lines.append(
            f"- `{operation['target_collection_id']}`: "
            f"`{operation['before_title']}` → `{operation['after_title']}`"
        )
    lines.extend(["", "## Video title changes", ""])
    for operation in plan["video_text_operations"]:
        if operation["title_changed"]:
            lines.append(
                f"- `{operation['target_video_id']}`: "
                f"`{operation['before_title']}` → `{operation['after_title']}`"
            )
    lines.extend(["", "## Review only — excluded from semantic automation", ""])
    for finding in plan["review_only"]:
        lines.append(f"- `{finding['kind']}` — `{json.dumps(finding, ensure_ascii=False, sort_keys=True)}`")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = _parser().parse_args()
    plan = build_vk_editorial_cleanup_plan(_load_audit(args.target), _load_policy(args.policy_json))
    _atomic_write(args.output, json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
    _atomic_write(args.report, _report(plan) + "\n")
    summary = plan["summary"]
    print(
        "VK editorial plan built:\n"
        f"  operation scope: {plan['operation_scope']}\n"
        f"  videos: {summary['videos_in_snapshot']}\n"
        f"  title updates: {summary['titles_to_update']}\n"
        f"  description updates: {summary['descriptions_to_update']}\n"
        f"  album renames: {summary['albums_to_rename']}\n"
        f"  catalog placements: {summary['placements_to_add']}/{summary['placements_to_remove']}\n"
        f"  review-only: {summary['review_only']}\n"
        f"  total operations: {summary['total_operations']}\n"
        f"  video coverage: {plan['target_video_ids_sha256']}\n"
        f"  membership state: {plan['initial_memberships_sha256']}\n"
        f"  plan sha256: {plan['plan_sha256']}\n"
        f"  JSON: {args.output}\n"
        f"  review: {args.report}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
