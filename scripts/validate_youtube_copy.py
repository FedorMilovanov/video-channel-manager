#!/usr/bin/env python3
"""Validate YouTube descriptions against The Legendary Poet rendering rules."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from video_channel_manager.editorial import CopyFinding, validate_youtube_description


def _format_finding(finding: CopyFinding) -> str:
    location = f" paragraph {finding.paragraph_index}" if finding.paragraph_index is not None else ""
    excerpt = f" — `{finding.excerpt}`" if finding.excerpt else ""
    return f"- **{finding.severity.upper()}** `{finding.code}`{location}: {finding.message}{excerpt}"


def _audit_package_report(payload: dict[str, Any], source: Path) -> tuple[str, int]:
    videos = [item for item in payload.get("videos", []) if isinstance(item, dict)]
    affected = 0
    errors = 0
    lines = [
        "# YouTube copy validation",
        "",
        f"Source: `{source}`",
        "",
        "> Structural lint only. Literary facts still require source verification.",
        "",
    ]

    for video in videos:
        description = str(video.get("description") or "")
        findings = validate_youtube_description(description)
        if not findings:
            continue
        affected += 1
        errors += sum(finding.severity == "error" for finding in findings)
        ref = video.get("ref") if isinstance(video.get("ref"), dict) else {}
        video_id = str(ref.get("remote_id") or "unknown")
        title = str(video.get("title") or video_id)
        lines.extend([f"## {title}", "", f"Video ID: `{video_id}`", ""])
        lines.extend(_format_finding(finding) for finding in findings)
        lines.append("")

    lines[5:5] = [
        f"- Videos checked: **{len(videos)}**",
        f"- Videos with findings: **{affected}**",
        f"- Error-level findings: **{errors}**",
        "",
    ]
    if not affected:
        lines.extend(["No structural findings.", ""])
    return "\n".join(lines), errors


def _plain_text_report(text: str, source: Path) -> tuple[str, int]:
    findings = validate_youtube_description(text)
    errors = sum(finding.severity == "error" for finding in findings)
    lines = ["# YouTube copy validation", "", f"Source: `{source}`", ""]
    if findings:
        lines.extend(_format_finding(finding) for finding in findings)
    else:
        lines.append("No structural findings.")
    lines.append("")
    return "\n".join(lines), errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Text file or video-manager AuditPackage JSON")
    parser.add_argument("--output", "-o", type=Path, help="Optional Markdown report path")
    parser.add_argument("--strict", action="store_true", help="Exit with code 1 when error-level findings exist")
    args = parser.parse_args()

    try:
        raw = args.input.read_text(encoding="utf-8")
    except OSError as exc:
        parser.error(str(exc))

    report: str
    errors: int
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        report, errors = _plain_text_report(raw, args.input)
    else:
        if isinstance(payload, dict) and payload.get("schema_name") == "video-manager.audit-package":
            report, errors = _audit_package_report(payload, args.input)
        else:
            report, errors = _plain_text_report(raw, args.input)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        print(report)

    return 1 if args.strict and errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
