#!/usr/bin/env python3
"""Build a signed correction-only VK wave from a verified review bundle."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk.editorial_correction_wave import build_vk_reviewed_correction_wave


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path, help="Verified final VK AuditPackage JSON")
    parser.add_argument("--decisions-json", type=Path, required=True)
    parser.add_argument("--review-bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--html-report", type=Path, required=True)
    return parser


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _load_audit(path: Path) -> AuditPackage:
    try:
        return AuditPackage.model_validate(json.loads(path.read_text(encoding="utf-8-sig")))
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"Cannot read AuditPackage {path}: {exc}") from exc


def _sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _verify_review_bundle(path: Path, decisions: dict[str, Any]) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(path) as archive:
            manifest = json.loads(archive.read("manifest.json").decode("utf-8-sig"))
            queue = json.loads(archive.read("review-queue.json").decode("utf-8-sig"))
            for item in manifest.get("files", []):
                name = str(item.get("name") or "")
                content = archive.read(name)
                if len(content) != int(item.get("size_bytes", -1)):
                    raise ValueError(f"Review bundle size mismatch: {name}")
                digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
                if digest != str(item.get("sha256") or ""):
                    raise ValueError(f"Review bundle SHA-256 mismatch: {name}")
    except (OSError, KeyError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        raise ValueError(f"Cannot verify review bundle {path}: {exc}") from exc

    if manifest.get("status") != "review_only_completed" or int(manifest.get("remote_writes", -1)) != 0:
        raise ValueError("Review bundle is not a completed review-only handoff")
    if queue.get("mode") != "review_only" or int(queue.get("remote_writes", -1)) != 0:
        raise ValueError("Review queue is not review-only")
    if str(queue.get("source_plan_sha256") or "") != str(decisions.get("source_plan_sha256") or ""):
        raise ValueError("Review queue source plan differs from correction decisions")
    actual_sha = _sha256(path)
    if actual_sha != str(decisions.get("source_review_bundle_sha256") or ""):
        raise ValueError("Review bundle file SHA-256 differs from correction decisions")
    return queue


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# VK reviewed correction-only wave",
        "",
        f"- Decision set: `{plan['decision_set_id']}`",
        f"- Plan: `{plan['plan_sha256']}`",
        f"- Source review bundle: `{plan['source_review_bundle_sha256']}`",
        f"- Videos in snapshot: **{plan['summary']['videos_in_snapshot']}**",
        f"- Exact description corrections: **{plan['summary']['descriptions_to_update']}**",
        "- Title changes: **0**",
        "- Album changes: **0**",
        "- Membership changes: **0**",
        "",
        "## Reviewed operations",
        "",
    ]
    for operation in plan["video_text_operations"]:
        lines.extend(
            [
                f"## {operation['before_title']}",
                "",
                f"- Video: `{operation['target_video_id']}`",
                f"- Decision: `{operation['decision_id']}`",
                f"- Before SHA-256: `{operation['before_description_sha256']}`",
                f"- After SHA-256: `{operation['after_description_sha256']}`",
                "- Replacements:",
            ]
        )
        for replacement in operation["applied_replacements"]:
            lines.append(f"  - `{replacement['replacement_id']}` — {replacement['reason']}")
        lines.extend(["- Sources:"])
        for source in operation["source_evidence"]:
            lines.append(f"  - {source['authority']}: {source['url']}")
        lines.extend(
            [
                "",
                "### До",
                "",
                "```text",
                operation["before_description"],
                "```",
                "",
                "### После",
                "",
                "```text",
                operation["after_description"],
                "```",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _html(plan: dict[str, Any]) -> str:
    cards: list[str] = []
    for operation in plan["video_text_operations"]:
        sources = "".join(
            f'<li><a href="{html.escape(str(source["url"]))}">{html.escape(str(source["authority"]))}</a></li>'
            for source in operation["source_evidence"]
        )
        reasons = "".join(
            f'<li><code>{html.escape(str(item["replacement_id"]))}</code> — {html.escape(str(item["reason"]))}</li>'
            for item in operation["applied_replacements"]
        )
        cards.append(
            f"""
<article class="card">
<h2>{html.escape(str(operation['before_title']))}</h2>
<p><code>{html.escape(str(operation['target_video_id']))}</code> · <code>{html.escape(str(operation['decision_id']))}</code></p>
<h3>Причины</h3><ul>{reasons}</ul>
<h3>Источники</h3><ul>{sources}</ul>
<div class="columns">
<details><summary>До</summary><pre>{html.escape(str(operation['before_description']))}</pre></details>
<details open><summary>После</summary><pre>{html.escape(str(operation['after_description']))}</pre></details>
</div>
</article>
"""
        )
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>VK reviewed correction wave</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#10141a;color:#e9eef5}}main{{max-width:1500px;margin:auto;padding:24px}}
a{{color:#7cc7ff}}code{{color:#8bd9ff}}.card{{background:#171d25;border:1px solid #293443;border-radius:14px;padding:18px;margin:16px 0}}.columns{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}details{{background:#0d1117;border-radius:10px;padding:12px;min-width:0}}summary{{cursor:pointer;font-weight:700}}pre{{white-space:pre-wrap;word-break:break-word;line-height:1.45}}@media(max-width:900px){{.columns{{grid-template-columns:1fr}}}}
</style></head><body><main>
<h1>VK — reviewed correction-only dry-run</h1>
<p>План <code>{html.escape(str(plan['plan_sha256']))}</code>; точных исправлений: <strong>{plan['summary']['descriptions_to_update']}</strong>; названий/альбомов/memberships: <strong>0</strong>.</p>
{''.join(cards)}
</main></body></html>"""


def main() -> int:
    args = _parser().parse_args()
    decisions = _load_json(args.decisions_json)
    _verify_review_bundle(args.review_bundle, decisions)
    plan = build_vk_reviewed_correction_wave(
        _load_audit(args.target),
        decisions,
        source_review_bundle_sha256=_sha256(args.review_bundle),
    )
    _atomic_write(args.output, json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
    _atomic_write(args.report, _markdown(plan))
    _atomic_write(args.html_report, _html(plan))
    print(
        json.dumps(
            {
                "status": "reviewed_correction_plan_built",
                "plan_sha256": plan["plan_sha256"],
                "descriptions_to_update": plan["summary"]["descriptions_to_update"],
                "titles_to_update": 0,
                "albums_to_rename": 0,
                "remote_writes": 0,
                "output": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        raise SystemExit(2) from exc
