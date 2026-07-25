#!/usr/bin/env python3
"""Preview how YouTube descriptions will render as plain text in VK Video."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from difflib import unified_diff
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from video_channel_manager.domain.enums import PlatformName
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk.text import render_vk_video_description


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="YouTube AuditPackage JSON")
    parser.add_argument("--video-id", action="append", default=[], help="Limit the audit to exact YouTube video IDs")
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--report-output", type=Path)
    parser.add_argument("--fail-on-errors", action="store_true")
    return parser


def _load(path: Path) -> AuditPackage:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        package = AuditPackage.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"Cannot read AuditPackage {path}: {exc}") from exc
    if package.channel.ref.platform != PlatformName.YOUTUBE:
        raise ValueError("The source AuditPackage must be YouTube.")
    return package


def _diff(before: str, after: str, video_id: str) -> str:
    return "\n".join(
        unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile=f"{video_id}:youtube-source",
            tofile=f"{video_id}:vk-plain-text",
            lineterm="",
        )
    )


def main() -> int:
    args = _parser().parse_args()
    source = _load(args.source)
    selected = set(args.video_id)
    videos = [item for item in source.videos if not selected or item.ref.remote_id in selected]
    missing = selected - {item.ref.remote_id for item in videos}
    if missing:
        raise SystemExit(f"Unknown video IDs: {', '.join(sorted(missing))}")

    records: list[dict[str, Any]] = []
    issue_counts: Counter[str] = Counter()
    total_removed = 0
    total_links = 0
    total_zero_width = 0
    total_collapsed = 0
    footer_added = 0
    changed = 0
    errors = 0

    for video in videos:
        rendered = render_vk_video_description(video.description)
        changed += int(rendered.changed)
        total_removed += rendered.removed_emphasis_pairs
        total_links += rendered.converted_markdown_links
        total_zero_width += rendered.removed_zero_width_characters
        total_collapsed += rendered.collapsed_blank_runs
        footer_added += int(rendered.footer_added)
        errors += int(rendered.has_errors)
        for issue in rendered.issues:
            issue_counts[issue.code] += 1
        records.append(
            {
                "video_id": video.ref.remote_id,
                "title": video.title,
                "source_revision": video.revision,
                "source_description": video.description,
                "vk_description": rendered.text,
                "source_sha256": rendered.source_sha256,
                "vk_sha256": rendered.rendered_sha256,
                "changed": rendered.changed,
                "removed_emphasis_pairs": rendered.removed_emphasis_pairs,
                "converted_markdown_links": rendered.converted_markdown_links,
                "removed_zero_width_characters": rendered.removed_zero_width_characters,
                "collapsed_blank_runs": rendered.collapsed_blank_runs,
                "footer_added": rendered.footer_added,
                "issues": [asdict(issue) for issue in rendered.issues],
            }
        )

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    json_output = args.json_output or Path("data/reports") / f"vk-description-render-audit-{timestamp}.json"
    report_output = args.report_output or Path("data/reports") / f"vk-description-render-audit-{timestamp}.md"
    payload = {
        "schema_name": "video-manager.vk-description-render-audit",
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "source": str(args.source),
        "source_snapshot_id": str(source.snapshot_id),
        "channel_id": source.channel.ref.remote_id,
        "videos_checked": len(videos),
        "videos_changed": changed,
        "videos_with_errors": errors,
        "removed_emphasis_pairs": total_removed,
        "converted_markdown_links": total_links,
        "removed_zero_width_characters": total_zero_width,
        "collapsed_blank_runs": total_collapsed,
        "footers_added": footer_added,
        "issue_counts": dict(sorted(issue_counts.items())),
        "records": records,
    }
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# VK Video plain-text rendering audit",
        "",
        f"Source: `{args.source}`",
        f"Snapshot: `{source.snapshot_id}`",
        "",
        f"- Videos checked: **{len(videos)}**",
        f"- Descriptions changed for VK: **{changed}**",
        f"- YouTube emphasis pairs removed: **{total_removed}**",
        f"- Markdown links converted: **{total_links}**",
        f"- Invisible characters removed: **{total_zero_width}**",
        f"- Excess blank-line runs collapsed: **{total_collapsed}**",
        f"- Site footers added: **{footer_added}**",
        f"- Videos with error-level findings: **{errors}**",
        "",
    ]
    for record in records:
        if not record["changed"] and not record["issues"]:
            continue
        lines.extend(
            [
                f"## {record['title']}",
                "",
                f"Video ID: `{record['video_id']}`",
                "",
                f"Removed emphasis pairs: `{record['removed_emphasis_pairs']}`",
                "",
            ]
        )
        for issue in record["issues"]:
            excerpt = f" — `{issue['excerpt']}`" if issue.get("excerpt") else ""
            lines.append(f"- **{issue['severity']}** `{issue['code']}`: {issue['message']}{excerpt}")
        if record["issues"]:
            lines.append("")
        lines.extend(
            ["```diff", _diff(record["source_description"], record["vk_description"], record["video_id"]), "```", ""]
        )

    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text("\n".join(lines), encoding="utf-8")

    print(f"VK description audit → {json_output}")
    print(f"Readable diff report → {report_output}")
    print(
        f"Checked {len(videos)} | changed {changed} | emphasis pairs removed {total_removed} | "
        f"error-level videos {errors}"
    )
    return 2 if args.fail_on_errors and errors else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(2) from exc
