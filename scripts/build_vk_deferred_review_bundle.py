#!/usr/bin/env python3
"""Build a one-file review-only bundle for deferred VK editorial findings."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import tempfile
import zipfile
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from verify_vk_description_apply_bundle import verify_bundle


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apply_bundle", type=Path)
    parser.add_argument("--output", type=Path)
    return parser


def _json_bytes(raw: bytes, *, name: str) -> dict[str, Any]:
    payload = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{name} must contain a JSON object")
    return payload


def _remote_id(item: dict[str, Any]) -> str:
    ref = item.get("ref")
    if not isinstance(ref, dict) or not ref.get("remote_id"):
        raise ValueError("Snapshot item has no remote ID")
    return str(ref["remote_id"])


def _video_url(video: dict[str, Any], remote_id: str) -> str:
    metadata = video.get("metadata")
    if isinstance(metadata, dict):
        permalink = str(metadata.get("permalink") or "").strip()
        if permalink:
            return permalink
    return f"https://vk.com/video{remote_id}"


def _sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _markdown(items: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    lines = [
        "# VK deferred editorial review",
        "",
        "Этот пакет не содержит автоматических исправлений и не вызывает VK mutation API.",
        "",
        "## Сводка",
        "",
        f"- Роликов в очереди: {summary['videos']}.",
        f"- Всего маркеров: {summary['findings']}.",
        f"- Фактологическая проверка: {summary['factual_editorial_review']}.",
        f"- Чувствительные утверждения: {summary['sensitive_claim_review']}.",
        "",
    ]
    for index, item in enumerate(items, start=1):
        kinds = ", ".join(item["finding_kinds"])
        lines.extend(
            [
                f"## {index}. {item['title']}",
                "",
                f"- VK ID: `{item['video_id']}`",
                f"- URL: {item['url']}",
                f"- Категории: {kinds}",
                "",
                "### Почему в очереди",
                "",
            ]
        )
        for message in item["messages"]:
            lines.append(f"- {message}")
        lines.extend(
            [
                "",
                "### Текущее описание",
                "",
                "```text",
                item["description"],
                "```",
                "",
                "### Решение редактора",
                "",
                "- [ ] Оставить без изменений",
                "- [ ] Проверить по источникам",
                "- [ ] Подготовить отдельную reviewed correction",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _html(items: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    cards: list[str] = []
    for index, item in enumerate(items, start=1):
        messages = "".join(f"<li>{html.escape(message)}</li>" for message in item["messages"])
        kinds = " ".join(
            f'<span class="tag">{html.escape(kind)}</span>' for kind in item["finding_kinds"]
        )
        cards.append(
            f"""
<section class="card">
  <div class="number">{index}</div>
  <h2>{html.escape(item['title'])}</h2>
  <p><a href="{html.escape(item['url'])}">{html.escape(item['video_id'])}</a></p>
  <div class="tags">{kinds}</div>
  <ul>{messages}</ul>
  <details>
    <summary>Текущее описание</summary>
    <pre>{html.escape(item['description'])}</pre>
  </details>
  <div class="decision">Оставить / Проверить / Подготовить отдельную correction</div>
</section>
"""
        )
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VK deferred editorial review</title>
<style>
:root {{ color-scheme: dark; font-family: Inter, system-ui, sans-serif; }}
body {{ margin: 0; background: #0d1117; color: #e6edf3; }}
main {{ max-width: 1100px; margin: 0 auto; padding: 32px 20px 80px; }}
h1 {{ margin-bottom: 8px; }}
.summary {{ color: #9da7b3; margin-bottom: 28px; }}
.card {{ position: relative; background: #161b22; border: 1px solid #30363d; border-radius: 14px; padding: 22px; margin: 16px 0; }}
.number {{ position: absolute; right: 18px; top: 14px; color: #6e7681; }}
a {{ color: #58a6ff; }}
.tag {{ display: inline-block; margin: 0 8px 8px 0; padding: 4px 8px; border: 1px solid #3d444d; border-radius: 999px; color: #79c0ff; }}
pre {{ white-space: pre-wrap; overflow-wrap: anywhere; background: #0d1117; padding: 16px; border-radius: 10px; line-height: 1.45; }}
summary {{ cursor: pointer; color: #d2a8ff; }}
.decision {{ margin-top: 16px; padding: 12px; border-left: 3px solid #3fb950; background: #0d1117; }}
</style>
</head>
<body>
<main>
<h1>VK deferred editorial review</h1>
<p class="summary">{summary['videos']} роликов, {summary['findings']} маркеров; пакет только для проверки, без автоматических изменений.</p>
{''.join(cards)}
</main>
</body>
</html>
"""


def build_bundle(apply_bundle: Path, output: Path) -> dict[str, Any]:
    verification = verify_bundle(apply_bundle)
    if verification.get("status") != "verified_completed":
        raise ValueError("Apply bundle did not pass independent verification")

    with zipfile.ZipFile(apply_bundle) as archive:
        plan = _json_bytes(archive.read("plan.json"), name="plan.json")
        final = _json_bytes(
            archive.read("04-final-vk-snapshot.json"),
            name="04-final-vk-snapshot.json",
        )

    videos_raw = final.get("videos")
    findings_raw = plan.get("deferred_editorial_review")
    if not isinstance(videos_raw, list) or not isinstance(findings_raw, list):
        raise ValueError("Apply bundle does not contain deferred review data")

    videos = {
        _remote_id(item): item
        for item in videos_raw
        if isinstance(item, dict)
    }
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for finding in findings_raw:
        if not isinstance(finding, dict):
            continue
        target = str(finding.get("target_video_id") or "")
        if not target:
            continue
        grouped[target].append(finding)

    items: list[dict[str, Any]] = []
    kind_counts: Counter[str] = Counter()
    for video_id, findings in grouped.items():
        video = videos.get(video_id)
        if video is None:
            raise ValueError(f"Deferred review target is absent from final snapshot: {video_id}")
        kinds = sorted({str(item.get("kind") or "unknown") for item in findings})
        messages = [str(item.get("message") or "").strip() for item in findings]
        kind_counts.update(kinds)
        items.append(
            {
                "video_id": video_id,
                "title": str(video.get("title") or video_id),
                "url": _video_url(video, video_id),
                "finding_kinds": kinds,
                "messages": messages,
                "description": str(video.get("description") or ""),
            }
        )
    items.sort(key=lambda item: (item["title"].casefold(), item["video_id"]))

    summary = {
        "videos": len(items),
        "findings": len(findings_raw),
        "factual_editorial_review": kind_counts["factual_editorial_review"],
        "sensitive_claim_review": kind_counts["sensitive_claim_review"],
    }
    payload = {
        "schema_name": "video-manager.vk-deferred-editorial-review",
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "source_apply_bundle": str(apply_bundle),
        "source_apply_bundle_sha256": _sha256(apply_bundle),
        "source_plan_sha256": plan.get("plan_sha256"),
        "community_id": plan.get("target_community_id"),
        "mode": "review_only",
        "remote_writes": 0,
        "summary": summary,
        "items": items,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="vk-deferred-review-") as temp_dir:
        root = Path(temp_dir)
        json_path = root / "review-queue.json"
        md_path = root / "review-queue.md"
        html_path = root / "review-queue.html"
        readme_path = root / "README.txt"
        manifest_path = root / "manifest.json"

        _write_json(json_path, payload)
        md_path.write_text(_markdown(items, summary), encoding="utf-8")
        html_path.write_text(_html(items, summary), encoding="utf-8")
        readme_path.write_text(
            "VK deferred editorial review\n\n"
            "Этот ZIP предназначен только для ручной редакционной проверки.\n"
            "Он не содержит плана автоматической записи и не вызывает VK mutation API.\n"
            "Откройте review-queue.html для удобного просмотра.\n",
            encoding="utf-8",
        )

        members = [json_path, md_path, html_path, readme_path]
        manifest = {
            "schema_name": "video-manager.vk-review-handoff",
            "schema_version": 1,
            "created_at": datetime.now(UTC).isoformat(),
            "status": "review_only_completed",
            "remote_writes": 0,
            "source_apply_bundle_sha256": payload["source_apply_bundle_sha256"],
            "source_plan_sha256": payload["source_plan_sha256"],
            "summary": summary,
            "files": [
                {
                    "name": member.name,
                    "size_bytes": member.stat().st_size,
                    "sha256": _sha256(member),
                }
                for member in members
            ],
        }
        _write_json(manifest_path, manifest)
        members.append(manifest_path)

        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for member in members:
                archive.write(member, arcname=member.name)

    return {
        "status": "review_only_completed",
        "output": str(output),
        "summary": summary,
    }


def main() -> int:
    args = _parser().parse_args()
    output = args.output
    if output is None:
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        output = Path("data/handoffs") / f"vk-deferred-editorial-review-{stamp}.zip"
    try:
        report = build_bundle(args.apply_bundle, output)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
