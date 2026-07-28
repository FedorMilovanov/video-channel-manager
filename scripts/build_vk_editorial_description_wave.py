#!/usr/bin/env python3
"""Build a signed, technical description-only VK editorial wave."""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk.editorial_description_wave import (
    build_vk_editorial_description_wave,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path, help="Fresh VK AuditPackage JSON")
    parser.add_argument(
        "--policy-json",
        type=Path,
        required=True,
        help="Reviewed VK editorial policy",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/reports/vk-editorial-description-wave.json"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("data/reports/vk-editorial-description-wave.md"),
    )
    parser.add_argument(
        "--html-report",
        type=Path,
        default=Path("data/reports/vk-editorial-description-wave.html"),
    )
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


def _markdown_report(plan: dict[str, Any]) -> str:
    summary = plan["summary"]
    lines = [
        "# VK editorial description wave",
        "",
        f"- Operation scope: `{plan['operation_scope']}`",
        f"- Component scope: `{plan['component_scope']}`",
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
        f"- Excluded review-only: **{summary['review_only']}**",
        f"- Deferred factual/sensitive review: **{summary['deferred_editorial_review']}**",
        f"- Total write operations: **{summary['total_operations']}**",
        "",
        "## Change reason counts",
        "",
    ]
    for reason, count in plan["change_reason_counts"].items():
        lines.append(f"- `{reason}`: **{count}**")
    lines.extend(["", "## Description operations", ""])
    for operation in plan["video_text_operations"]:
        before = str(operation["before_description"])
        after = str(operation["after_description"])
        reasons = ", ".join(operation["change_reasons"])
        lines.append(
            f"- `{operation['target_video_id']}` — **{operation['before_title']}** "
            f"({len(before)} → {len(after)} chars); `{reasons}`; "
            f"semantic body `{operation['semantic_body_sha256']}`"
        )
    lines.extend(["", "## Excluded review-only", ""])
    if plan["review_only"]:
        for finding in plan["review_only"]:
            lines.append(f"- `{finding['kind']}` — `{json.dumps(finding, ensure_ascii=False, sort_keys=True)}`")
    else:
        lines.append("- None")
    lines.extend(["", "## Deferred factual and sensitive review", ""])
    for finding in plan["deferred_editorial_review"]:
        lines.append(f"- `{finding['kind']}` — `{json.dumps(finding, ensure_ascii=False, sort_keys=True)}`")
    lines.append("")
    return "\n".join(lines)


def _html_report(plan: dict[str, Any]) -> str:
    summary = plan["summary"]
    rows: list[str] = []
    for operation in plan["video_text_operations"]:
        title = html.escape(str(operation["before_title"]))
        before = html.escape(str(operation["before_description"]))
        after = html.escape(str(operation["after_description"]))
        reasons = ", ".join(html.escape(str(item)) for item in operation["change_reasons"])
        rows.append(
            "<article class='card'>"
            f"<h2>{title}</h2>"
            f"<p><code>{html.escape(str(operation['target_video_id']))}</code> · "
            f"{len(str(operation['before_description']))} → "
            f"{len(str(operation['after_description']))} chars</p>"
            f"<p><strong>Причины:</strong> {reasons}</p>"
            "<div class='columns'>"
            f"<details><summary>До</summary><pre>{before}</pre></details>"
            f"<details><summary>После</summary><pre>{after}</pre></details>"
            "</div></article>"
        )
    reason_items = "".join(
        f"<li><code>{html.escape(reason)}</code>: <strong>{count}</strong></li>"
        for reason, count in plan["change_reason_counts"].items()
    )
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>VK description wave review</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#10141a;color:#e9eef5}}
main{{max-width:1500px;margin:auto;padding:24px}}
code{{color:#8bd9ff}} .summary,.card{{background:#171d25;border:1px solid #293443;border-radius:14px;padding:18px;margin:16px 0}}
.columns{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
details{{background:#0d1117;border-radius:10px;padding:12px;min-width:0}}
summary{{cursor:pointer;font-weight:700}} pre{{white-space:pre-wrap;word-break:break-word;line-height:1.45}}
@media(max-width:900px){{.columns{{grid-template-columns:1fr}}}}
</style>
</head>
<body><main>
<h1>VK — техническая волна описаний</h1>
<section class="summary">
<p>Snapshot: <code>{html.escape(str(plan["target_snapshot_id"]))}</code></p>
<p>Plan: <code>{html.escape(str(plan["plan_sha256"]))}</code></p>
<p>Видео: <strong>{summary["videos_in_snapshot"]}</strong>; описаний: <strong>{summary["descriptions_to_update"]}</strong>; названий: <strong>0</strong>; альбомов: <strong>0</strong>.</p>
<p>Содержательная часть каждого описания защищена semantic-body SHA-256.</p>
<ul>{reason_items}</ul>
</section>
{"".join(rows)}
</main></body></html>
"""


def main() -> int:
    args = _parser().parse_args()
    plan = build_vk_editorial_description_wave(
        _load_audit(args.target),
        _load_policy(args.policy_json),
    )
    _atomic_write(args.output, json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
    _atomic_write(args.report, _markdown_report(plan) + "\n")
    _atomic_write(args.html_report, _html_report(plan))
    summary = plan["summary"]
    print(
        "VK editorial description wave built:\n"
        f"  operation scope: {plan['operation_scope']}\n"
        f"  component scope: {plan['component_scope']}\n"
        f"  videos: {summary['videos_in_snapshot']}\n"
        f"  title updates: {summary['titles_to_update']}\n"
        f"  description updates: {summary['descriptions_to_update']}\n"
        f"  album renames: {summary['albums_to_rename']}\n"
        f"  review-only excluded: {summary['review_only']}\n"
        f"  deferred editorial review: {summary['deferred_editorial_review']}\n"
        f"  total operations: {summary['total_operations']}\n"
        f"  video coverage: {plan['target_video_ids_sha256']}\n"
        f"  membership state: {plan['initial_memberships_sha256']}\n"
        f"  plan sha256: {plan['plan_sha256']}\n"
        f"  JSON: {args.output}\n"
        f"  Markdown: {args.report}\n"
        f"  HTML: {args.html_report}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
