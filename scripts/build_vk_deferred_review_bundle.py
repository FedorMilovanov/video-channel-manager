#!/usr/bin/env python3
"""Build a localized one-file review-only bundle for deferred VK findings."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import tempfile
import zipfile
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from verify_vk_description_apply_bundle import verify_bundle
from video_channel_manager.platforms.vk.editorial_cleanup_plan import (
    build_vk_deferred_editorial_findings,
)


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


def _text_sha256(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _priority(finding_kinds: list[str]) -> tuple[str, str]:
    if "sensitive_claim_review" in finding_kinds:
        return "P1", "чувствительное утверждение: проверить формулировку и источник"
    if "factual_editorial_review" in finding_kinds:
        return "P2", "фактологическое утверждение: проверить по авторитетным источникам"
    return "P3", "маркер не локализован: требуется ручная проверка"


def _localized_item(
    video_id: str,
    video: dict[str, Any],
    source_findings: list[dict[str, Any]],
) -> dict[str, Any]:
    description = str(video.get("description") or "")
    expected_kinds = sorted({str(item.get("kind") or "unknown") for item in source_findings})
    localized = {str(item.get("kind")): item for item in build_vk_deferred_editorial_findings(video_id, description)}
    missing_kinds = sorted(set(expected_kinds) - set(localized))
    if missing_kinds:
        raise ValueError(f"Cannot localize deferred findings for {video_id}: {missing_kinds}")

    evidence: list[dict[str, Any]] = []
    trigger_families: set[str] = set()
    matched_terms: list[str] = []
    seen_terms: set[str] = set()
    messages: list[str] = []
    for source_finding in source_findings:
        kind = str(source_finding.get("kind") or "unknown")
        marker = localized[kind]
        message = str(source_finding.get("message") or marker.get("message") or "").strip()
        if message and message not in messages:
            messages.append(message)
        trigger_families.update(str(value) for value in marker.get("trigger_families") or [])
        for term in marker.get("matched_terms") or []:
            text = str(term)
            key = text.casefold()
            if key not in seen_terms:
                seen_terms.add(key)
                matched_terms.append(text)
        for entry in marker.get("evidence") or []:
            if not isinstance(entry, dict):
                continue
            normalized = {
                "finding_kind": kind,
                "matched_terms": [str(value) for value in entry.get("matched_terms") or []],
                "excerpt": str(entry.get("excerpt") or ""),
            }
            if normalized not in evidence:
                evidence.append(normalized)

    return {
        "video_id": video_id,
        "title": str(video.get("title") or video_id),
        "url": _video_url(video, video_id),
        "finding_kinds": expected_kinds,
        "messages": messages,
        "trigger_families": sorted(trigger_families),
        "matched_terms": matched_terms,
        "evidence": evidence,
        "description": description,
        "description_sha256": _text_sha256(description),
    }


def _research_units(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        grouped[item["description_sha256"]].append(item)

    units: list[dict[str, Any]] = []
    for description_sha256, members in grouped.items():
        members.sort(key=lambda item: (item["title"].casefold(), item["video_id"]))
        finding_kinds = sorted({kind for member in members for kind in member["finding_kinds"]})
        priority, priority_reason = _priority(finding_kinds)
        first = members[0]
        units.append(
            {
                "research_unit_id": f"review:{description_sha256.split(':', 1)[1][:16]}",
                "description_sha256": description_sha256,
                "priority": priority,
                "priority_reason": priority_reason,
                "finding_kinds": finding_kinds,
                "messages": first["messages"],
                "trigger_families": first["trigger_families"],
                "matched_terms": first["matched_terms"],
                "evidence": first["evidence"],
                "videos": [
                    {
                        "video_id": member["video_id"],
                        "title": member["title"],
                        "url": member["url"],
                    }
                    for member in members
                ],
                "description": first["description"],
            }
        )

    rank = {"P1": 1, "P2": 2, "P3": 3}
    units.sort(
        key=lambda item: (
            rank[item["priority"]],
            item["videos"][0]["title"].casefold(),
            item["research_unit_id"],
        )
    )
    return units


def _markdown(units: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    lines = [
        "# VK deferred editorial review",
        "",
        "Этот пакет локализует места для проверки, но не утверждает, что текст ошибочен.",
        "Он не содержит автоматических исправлений и не вызывает VK mutation API.",
        "",
        "## Сводка",
        "",
        f"- Роликов в очереди: {summary['videos']}.",
        f"- Всего исходных маркеров: {summary['findings']}.",
        f"- Исследовательских единиц: {summary['research_units']}.",
        f"- Групп идентичных описаний: {summary['duplicate_description_groups']}.",
        f"- Видео в таких группах: {summary['videos_in_duplicate_groups']}.",
        f"- Приоритеты: {summary['priorities']}.",
        "- Записей в VK: 0.",
        "",
    ]
    for index, unit in enumerate(units, start=1):
        title = unit["videos"][0]["title"]
        lines.extend(
            [
                f"## {index}. [{unit['priority']}] {title}",
                "",
                f"- Research unit: `{unit['research_unit_id']}`",
                f"- Видео в группе: {len(unit['videos'])}",
                f"- Категории: {', '.join(unit['finding_kinds'])}",
                f"- Семейства триггеров: {', '.join(unit['trigger_families'])}",
                f"- Причина приоритета: {unit['priority_reason']}",
                "",
                "### Видео",
                "",
            ]
        )
        for video in unit["videos"]:
            lines.append(f"- [{video['title']}]({video['url']}) — `{video['video_id']}`")
        lines.extend(["", "### Что именно проверять", ""])
        for evidence in unit["evidence"]:
            terms = ", ".join(evidence["matched_terms"])
            lines.extend(
                [
                    f"- **{evidence['finding_kind']}** (`{terms}`):",
                    f"  > {evidence['excerpt']}",
                ]
            )
        lines.extend(
            [
                "",
                "### Решение редактора",
                "",
                "- [ ] Подтверждено источниками — оставить",
                "- [ ] Нужна осторожная переформулировка",
                "- [ ] Фактическая ошибка — подготовить отдельную reviewed correction",
                "- [ ] Маркер ложноположительный",
                "",
                "Источники:",
                "",
                "Примечания:",
                "",
                "<details>",
                "<summary>Полное текущее описание</summary>",
                "",
                "```text",
                unit["description"],
                "```",
                "",
                "</details>",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _html(units: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    cards: list[str] = []
    for index, unit in enumerate(units, start=1):
        video_links = "".join(
            f'<li><a href="{html.escape(video["url"])}">{html.escape(video["title"])}</a> '
            f"<code>{html.escape(video['video_id'])}</code></li>"
            for video in unit["videos"]
        )
        evidence = "".join(
            "<li>"
            f'<span class="kind">{html.escape(entry["finding_kind"])}</span> '
            f"<code>{html.escape(', '.join(entry['matched_terms']))}</code>"
            f"<blockquote>{html.escape(entry['excerpt'])}</blockquote>"
            "</li>"
            for entry in unit["evidence"]
        )
        search_text = " ".join(
            [
                unit["priority"],
                " ".join(unit["trigger_families"]),
                " ".join(video["title"] for video in unit["videos"]),
                " ".join(entry["excerpt"] for entry in unit["evidence"]),
            ]
        ).casefold()
        cards.append(
            f"""
<section class="card" data-priority="{unit["priority"]}" data-search="{html.escape(search_text)}">
  <div class="number">{index}</div>
  <h2><span class="priority {unit["priority"]}">{unit["priority"]}</span>
      {html.escape(unit["videos"][0]["title"])}</h2>
  <p class="meta"><code>{html.escape(unit["research_unit_id"])}</code> ·
     {len(unit["videos"])} видео · {html.escape(unit["priority_reason"])}</p>
  <ul>{video_links}</ul>
  <h3>Что именно проверять</h3>
  <ul class="evidence">{evidence}</ul>
  <div class="decision">
    □ оставить · □ переформулировать · □ исправить отдельным plan · □ ложный маркер
  </div>
  <details>
    <summary>Полное текущее описание</summary>
    <pre>{html.escape(unit["description"])}</pre>
  </details>
</section>
"""
        )
    priorities = "".join(
        f'<option value="{priority}">{priority} ({summary["priorities"].get(priority, 0)})</option>'
        for priority in ("P1", "P2", "P3")
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
main {{ max-width: 1180px; margin: 0 auto; padding: 28px 18px 80px; }}
.toolbar {{ position: sticky; top: 0; z-index: 5; background: #0d1117ee;
  padding: 12px 0; border-bottom: 1px solid #30363d; }}
input, select {{ background: #161b22; color: #e6edf3; border: 1px solid #3d444d;
  border-radius: 9px; padding: 10px; margin-right: 8px; }}
.card {{ position: relative; background: #161b22; border: 1px solid #30363d;
  border-radius: 14px; padding: 22px; margin: 16px 0; }}
.number {{ position: absolute; right: 18px; top: 14px; color: #6e7681; }}
a {{ color: #58a6ff; }} code {{ color: #79c0ff; }}
.priority {{ display: inline-block; padding: 3px 8px; border-radius: 999px; font-size: .75em; }}
.P1 {{ background: #5b1d28; }} .P2 {{ background: #594315; }} .P3 {{ background: #183d4a; }}
.meta {{ color: #9da7b3; }} .kind {{ font-weight: 700; color: #d2a8ff; }}
blockquote {{ margin: 8px 0 18px; padding: 10px 14px; border-left: 3px solid #8957e5;
  background: #0d1117; line-height: 1.45; }}
pre {{ white-space: pre-wrap; overflow-wrap: anywhere; background: #0d1117;
  padding: 16px; border-radius: 10px; line-height: 1.45; }}
summary {{ cursor: pointer; color: #d2a8ff; }}
.decision {{ margin: 16px 0; padding: 12px; border-left: 3px solid #3fb950; background: #0d1117; }}
.hidden {{ display: none; }}
</style>
</head>
<body>
<main>
<h1>VK deferred editorial review</h1>
<p>{summary["videos"]} видео · {summary["findings"]} маркеров ·
{summary["research_units"]} исследовательских единиц · remote writes: 0.</p>
<div class="toolbar">
  <input id="search" type="search" placeholder="Поиск по названию, фрагменту, триггеру">
  <select id="priority"><option value="">Все приоритеты</option>{priorities}</select>
</div>
{"".join(cards)}
</main>
<script>
const search = document.getElementById('search');
const priority = document.getElementById('priority');
function filterCards() {{
  const query = search.value.trim().toLocaleLowerCase('ru');
  const selected = priority.value;
  document.querySelectorAll('.card').forEach(card => {{
    const textMatches = !query || card.dataset.search.includes(query);
    const priorityMatches = !selected || card.dataset.priority === selected;
    card.classList.toggle('hidden', !(textMatches && priorityMatches));
  }});
}}
search.addEventListener('input', filterCards);
priority.addEventListener('change', filterCards);
</script>
</body>
</html>
"""


def _csv(units: list[dict[str, Any]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "research_unit_id",
            "priority",
            "video_count",
            "video_ids",
            "titles",
            "trigger_families",
            "first_evidence_excerpt",
            "decision",
            "sources",
            "notes",
        ]
    )
    for unit in units:
        writer.writerow(
            [
                unit["research_unit_id"],
                unit["priority"],
                len(unit["videos"]),
                " | ".join(video["video_id"] for video in unit["videos"]),
                " | ".join(video["title"] for video in unit["videos"]),
                " | ".join(unit["trigger_families"]),
                unit["evidence"][0]["excerpt"] if unit["evidence"] else "",
                "",
                "",
                "",
            ]
        )
    return output.getvalue()


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

    videos = {_remote_id(item): item for item in videos_raw if isinstance(item, dict)}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    kind_counts: Counter[str] = Counter()
    for finding in findings_raw:
        if not isinstance(finding, dict):
            continue
        target = str(finding.get("target_video_id") or "")
        if not target:
            continue
        grouped[target].append(finding)
        kind_counts[str(finding.get("kind") or "unknown")] += 1

    items: list[dict[str, Any]] = []
    for video_id, findings in grouped.items():
        video = videos.get(video_id)
        if video is None:
            raise ValueError(f"Deferred review target is absent from final snapshot: {video_id}")
        items.append(_localized_item(video_id, video, findings))
    items.sort(key=lambda item: (item["title"].casefold(), item["video_id"]))

    units = _research_units(items)
    duplicate_units = [unit for unit in units if len(unit["videos"]) > 1]
    priority_counts = Counter(unit["priority"] for unit in units)
    summary = {
        "videos": len(items),
        "findings": len(findings_raw),
        "factual_editorial_review": kind_counts["factual_editorial_review"],
        "sensitive_claim_review": kind_counts["sensitive_claim_review"],
        "research_units": len(units),
        "duplicate_description_groups": len(duplicate_units),
        "videos_in_duplicate_groups": sum(len(unit["videos"]) for unit in duplicate_units),
        "priorities": dict(sorted(priority_counts.items())),
    }
    payload = {
        "schema_name": "video-manager.vk-deferred-editorial-review",
        "schema_version": 2,
        "created_at": datetime.now(UTC).isoformat(),
        "source_apply_bundle": str(apply_bundle),
        "source_apply_bundle_sha256": _sha256(apply_bundle),
        "source_plan_sha256": plan.get("plan_sha256"),
        "community_id": plan.get("target_community_id"),
        "mode": "review_only",
        "remote_writes": 0,
        "notice": (
            "Triggers only locate passages for research. They do not assert that a claim is false "
            "and do not authorize an automatic correction."
        ),
        "summary": summary,
        "research_units": units,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="vk-deferred-review-") as temp_dir:
        root = Path(temp_dir)
        json_path = root / "review-queue.json"
        md_path = root / "review-queue.md"
        html_path = root / "review-queue.html"
        csv_path = root / "review-queue.csv"
        readme_path = root / "README.txt"
        manifest_path = root / "manifest.json"

        _write_json(json_path, payload)
        md_path.write_text(_markdown(units, summary), encoding="utf-8")
        html_path.write_text(_html(units, summary), encoding="utf-8")
        csv_path.write_text(_csv(units), encoding="utf-8-sig")
        readme_path.write_text(
            "VK deferred editorial review\n\n"
            "Этот ZIP предназначен только для редакционной проверки.\n"
            "Он не содержит плана записи и не вызывает VK mutation API.\n"
            "Откройте review-queue.html: там есть поиск, приоритеты и точные фрагменты.\n"
            "Идентичные описания объединены; похожие, но разные, не склеиваются.\n",
            encoding="utf-8",
        )

        members = [json_path, md_path, html_path, csv_path, readme_path]
        manifest = {
            "schema_name": "video-manager.vk-review-handoff",
            "schema_version": 2,
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
