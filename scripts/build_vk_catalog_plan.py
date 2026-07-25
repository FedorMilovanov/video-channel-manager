#!/usr/bin/env python3
"""Build a reviewable, self-validating VK catalog plan from fresh snapshots."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk.catalog import build_vk_catalog_plan


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Fresh YouTube AuditPackage JSON")
    parser.add_argument("target", type=Path, help="Fresh VK AuditPackage JSON")
    parser.add_argument("--mapping-json", type=Path, help="Reviewed exact source-ID to target-ID mappings")
    parser.add_argument("--output", type=Path, default=Path("data/reports/vk-catalog-plan.json"))
    parser.add_argument("--report", type=Path, default=Path("data/reports/vk-catalog-plan.md"))
    return parser


def _load_audit(path: Path) -> AuditPackage:
    try:
        return AuditPackage.model_validate(json.loads(path.read_text(encoding="utf-8-sig")))
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"Cannot read AuditPackage {path}: {exc}") from exc


def _load_mapping(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read reviewed mapping {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Reviewed mapping JSON must be an object of source IDs to target IDs")
    return {str(key): str(value) for key, value in payload.items()}


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _report(plan: dict[str, Any]) -> str:
    summary = plan["summary"]
    lines = [
        "# VK catalog plan",
        "",
        f"- Source snapshot: `{plan['source_snapshot_id']}`",
        f"- Target snapshot: `{plan['target_snapshot_id']}`",
        f"- Community: `{plan['target_community_id']}`",
        f"- Video coverage: `{plan['target_video_ids_sha256']}`",
        f"- Plan: `{plan['plan_sha256']}`",
        "",
        "## Summary",
        "",
        f"- Resolved video mappings: **{summary['resolved_video_mappings']}**",
        f"- Albums to create: **{summary['albums_to_create']}**",
        f"- Placements to add: **{summary['placements_to_add']}**",
        f"- Video texts to update: **{summary['video_texts_to_update']}**",
        f"- Review-only findings: **{summary['review_only']}**",
        "",
    ]
    if plan["album_operations"]:
        lines.extend(["## Albums", ""])
        for item in plan["album_operations"]:
            lines.append(f"- CREATE `{item['title']}` from `{item['source_collection_id']}`")
        lines.append("")
    if plan["placement_operations"]:
        lines.extend(["## Placements", ""])
        for item in plan["placement_operations"]:
            destination = item["target_collection_id"] or "planned-new-album"
            lines.append(f"- `{item['target_video_id']}` → `{item['album_title']}` ({destination})")
        lines.append("")
    if plan["text_operations"]:
        lines.extend(["## Video text changes", ""])
        for item in plan["text_operations"]:
            lines.extend(
                [
                    f"### `{item['target_video_id']}`",
                    "",
                    f"Title: `{item['before_title']}` → `{item['after_title']}`",
                    "",
                    "```diff",
                    f"- {item['before_description']}",
                    f"+ {item['after_description']}",
                    "```",
                    "",
                ]
            )
    if plan["review_only"]:
        lines.extend(["## Review only — automation excluded", ""])
        for item in plan["review_only"]:
            lines.append(f"- `{item['kind']}` — `{json.dumps(item, ensure_ascii=False, sort_keys=True)}`")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = _parser().parse_args()
    plan = build_vk_catalog_plan(
        _load_audit(args.source),
        _load_audit(args.target),
        reviewed_mappings=_load_mapping(args.mapping_json),
    )
    _atomic_write(args.output, json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
    _atomic_write(args.report, _report(plan) + "\n")
    summary = plan["summary"]
    print(
        "VK catalog plan built:\n"
        f"  operations: {summary['total_operations']}\n"
        f"  review-only: {summary['review_only']}\n"
        f"  plan sha256: {plan['plan_sha256']}\n"
        f"  JSON: {args.output}\n"
        f"  review: {args.report}"
    )
    if summary["review_only"]:
        print(
            "Review-only findings are excluded from automation. Add exact mappings or edit source text, then rebuild."
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
