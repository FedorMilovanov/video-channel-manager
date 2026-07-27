#!/usr/bin/env python3
"""Build a legacy-safe localized review-only bundle for deferred VK findings."""

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
from video_channel_manager.platforms.vk.editorial_review import build_vk_deferred_editorial_findings


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


def _by_kind(findings: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item.get("kind") or "unknown"): item for item in findings}


def _normalized_evidence(
    marker: dict[str, Any],
    *,
    kind: str,
    status: str,
    source: str,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for entry in marker.get("evidence") or []:
        if not isinstance(entry, dict):
            continue
        output.append(
            {
                "finding_kind": kind,
                "localization_status": status,
                "evidence_source": source,
                "matched_terms": [str(value) for value in entry.get("matched_terms") or []],
                "excerpt": str(entry.get("excerpt") or ""),
            }
        )
    return output


def _localize_item(
    video_id: str,
    video: dict[str, Any],
    source_findings: list[dict[str, Any]],
    before_description: str,
) -> dict[str, Any]:
    final_description = str(video.get("description") or "")
    current = _by_kind(build_vk_deferred_editorial_findings(video_id, final_description))
    legacy_raw = _by_kind(
        build_vk_deferred_editorial_findings(
            video_id,
            before_description,
            include_technical_surfaces=True,
        )
    )

    markers: list[dict[str, Any]] = []
    for source_finding in source_findings:
        kind = str(source_finding.get("kind") or "unknown")
        message = str(source_finding.get("message") or "").strip()
        if kind in current:
            marker = current[kind]
            status = "present_in_final"
            evidence_source = "final_description"
            active = True
        elif kind in legacy_raw:
            marker = legacy_raw[kind]
            status = "legacy_not_present_in_final"
            evidence_source = "reviewed_before_description"
            active = False
        else:
            marker = {}
            status = "legacy_unlocalized"
            evidence_source = "source_plan_only"
            active = False

        evidence = _normalized_evidence(
            marker,
            kind=kind,
            status=status,
            source=evidence_source,
        )
        if not evidence:
            evidence = [
                {
                    "finding_kind": kind,
                    "localization_status": status,
                    "evidence_source": evidence_source,
                    "matched_terms": [],
                    "excerpt": message or "Legacy marker has no localizable passage in the verified final description.",
                }
            ]
        markers.append(
            {
                "kind": kind,
                "message": message or str(marker.get("message") or ""),
                "active": active,
                "localization_status": status,
                "trigger_families": [str(value) for value in marker.get("trigger_families") or []],
                "matched_terms": [str(value) for value in marker.get("matched_terms") or []],
                "evidence": evidence,
            }
        )

    return {
        "video_id": video_id,
        "title": str(video.get("title") or video_id),
        "url": _video_url(video, video_id),
        "markers": markers,
        "active_finding_kinds": sorted({marker["kind"] for marker in markers if marker["active"]}),
        "legacy_finding_kinds": sorted({marker["kind"] for marker in markers if not marker["active"]}),
        "description": final_description,
        "description_sha256": _text_sha256(final_description),
    }


def _priority(active_kinds: list[str], legacy_kinds: list[str]) -> tuple[str, str]:
    if "sensitive_claim_review" in active_kinds:
        return "P1", "активное чувствительное утверждение присутствует в финальном описании"
    if "factual_editorial_review" in active_kinds:
        return "P2", "активное фактологическое утверждение присутствует в финальном описании"
    if legacy_kinds:
        return "P3", "старый маркер отсутствует в финальном содержательном тексте"
    return "P3", "маркер требует ручной классификации"


def _research_units(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        grouped[item["description_sha256"]].append(item)

    units: list[dict[str, Any]] = []
    for description_sha256, members in grouped.items():
        members.sort(key=lambda item: (item["title"].casefold(), item["video_id"]))
        active_kinds = sorted({kind for member in members for kind in member["active_finding_kinds"]})
        legacy_kinds = sorted({kind for member in members for kind in member["legacy_finding_kinds"]})
        priority, priority_reason = _priority(active_kinds, legacy_kinds)
        evidence: list[dict[str, Any]] = []
        seen_evidence: set[str] = set()
        statuses: Counter[str] = Counter()
        trigger_families: set[str] = set()
        for member in members:
            for marker in member["markers"]:
                statuses[marker["localization_status"]] += 1
                trigger_families.update(marker["trigger_families"])
                for entry in marker["evidence"]:
                    key = json.dumps(entry, ensure_ascii=False, sort_keys=True)
                    if key not in seen_evidence:
                        seen_evidence.add(key)
                        evidence.append(entry)
        first = members[0]
        units.append(
            {
                "research_unit_id": f"review:{description_sha256.split(':', 1)[1][:16]}",
                "description_sha256": description_sha256,
                "priority": priority,
                "priority_reason": priority_reason,
                "active_finding_kinds": active_kinds,
                "legacy_finding_kinds": legacy_kinds,
                "localization_statuses": dict(sorted(statuses.items())),
                "trigger_families": sorted(trigger_families),
                "evidence": evidence,
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
        "Этот пакет только локализует места для проверки и не вызывает VK mutation API.",
        "Старые маркеры, отсутствующие в финальном тексте, не считаются активными утверждениями.",
        "",
        "## Сводка",
        "",
        f"- Видео: {summary['videos']}.",
        f"- Исходных маркеров: {summary['source_findings']}.",
        f"- Активных маркеров в финальном тексте: {summary['active_findings']}.",
        f"- Legacy-маркеров вне финального текста: {summary['legacy_findings']}.",
        f"- Исследовательских единиц: {summary['research_units']}.",
        f"- Приоритеты: {summary['priorities']}.",
        "- Записей в VK: 0.",
        "",
    ]
    for index, unit in enumerate(units, start=1):
        lines.extend(
            [
                f"## {index}. [{unit['priority']}] {unit['videos'][0]['title']}",
                "",
                f"- Research unit: `{unit['research_unit_id']}`",
                f"- Видео в группе: {len(unit['videos'])}",
                f"- Активные категории: {', '.join(unit['active_finding_kinds']) or 'нет'}",
                f"- Legacy-категории: {', '.join(unit['legacy_finding_kinds']) or 'нет'}",
                f"- Статусы: {unit['localization_statuses']}",
                f"- Причина приоритета: {unit['priority_reason']}",
                "",
                "### Видео",
                "",
            ]
        )
        for video in unit["videos"]:
            lines.append(f"- [{video['title']}]({video['url']}) — `{video['video_id']}`")
        lines.extend(["", "### Что именно проверять", ""])
        for entry in unit["evidence"]:
            terms = ", ".join(entry["matched_terms"])
            lines.extend(
                [
                    f"- **{entry['finding_kind']} / {entry['localization_status']}** (`{terms}`):",
                    f"  > {entry['excerpt']}",
                ]
            )
        lines.extend(
            [
                "",
                "### Решение редактора",
                "",
                "- [ ] Подтверждено источниками — оставить",
                "- [ ] Нужна осторожная переформулировка",
                "- [ ] Доказанная ошибка — подготовить отдельную reviewed correction",
                "- [ ] Legacy/ложный маркер — исправление не требуется",
                "",
                "<details>",
                "<summary>Полное финальное описание</summary>",
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
            f'<code>{html.escape(video["video_id"])}</code></li>'
            for video in unit["videos"]
        )
        evidence = "".join(
            "<li>"
            f'<strong>{html.escape(entry["finding_kind"])}</strong> '
            f'<span>{html.escape(entry["localization_status"])}</span> '
            f'<code>{html.escape(", ".join(entry["matched_terms"]))}</code>'
            f'<blockquote>{html.escape(entry["excerpt"])}</blockquote>'
            "</li>"
            for entry in unit["evidence"]
        )
        search_text = " ".join(
            [
                unit["priority"],
                " ".join(unit["active_finding_kinds"]),
                " ".join(unit["legacy_finding_kinds"]),
                " ".join(video["title"] for video in unit["videos"]),
                " ".join(entry["excerpt"] for entry in unit["evidence"]),
            ]
        ).casefold()
        cards.append(
            f"""
<section class="card" data-priority="{unit['priority']}" data-search="{html.escape(search_text)}">
  <div class="number">{index}</div>
  <h2><span class="priority {unit['priority']}">{unit['priority']}</span>
      {html.escape(unit['videos'][0]['title'])}</h2>
  <p class="meta">{html.escape(unit['priority_reason'])}</p>
  <p>Активные: {html.escape(', '.join(unit['active_finding_kinds']) or 'нет')}<br>
     Legacy: {html.escape(', '.join(unit['legacy_finding_kinds']) or 'нет')}</p>
  <ul>{video_links}</ul>
  <h3>Что именно проверять</h3>
  <ul>{evidence}</ul>
  <details><summary>Полное финальное описание</summary>
    <pre>{html.escape(unit['description'])}</pre>
  </details>
</section>
"""
        )
    options = "".join(
        f'<option value="{priority}">{priority} ({summary["priorities"].get(priority, 0)})</option>'
        for priority in ("P1", "P2", "P3")
    )
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>VK deferred editorial review</title>
<style>
:root{{color-scheme:dark;font-family:Inter,Segoe UI,system-ui,sans-serif}}body{{margin:0;background:#0d1117;color:#e6edf3}}
main{{max-width:1180px;margin:auto;padding:28px 18px 80px}}.toolbar{{position:sticky;top:0;background:#0d1117ee;padding:12px 0}}
input,select{{background:#161b22;color:#e6edf3;border:1px solid #3d444d;border-radius:9px;padding:10px;margin-right:8px}}
.card{{position:relative;background:#161b22;border:1px solid #30363d;border-radius:14px;padding:22px;margin:16px 0}}
.number{{position:absolute;right:18px;top:14px;color:#6e7681}}a{{color:#58a6ff}}code{{color:#79c0ff}}
.priority{{padding:3px 8px;border-radius:999px;font-size:.75em}}.P1{{background:#5b1d28}}.P2{{background:#594315}}.P3{{background:#183d4a}}
blockquote{{margin:8px 0 18px;padding:10px 14px;border-left:3px solid #8957e5;background:#0d1117}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}
.hidden{{display:none}}.meta{{color:#9da7b3}}
</style></head><body><main>
<h1>VK deferred editorial review</h1>
<p>{summary['videos']} видео · {summary['source_findings']} исходных маркеров · {summary['active_findings']} активных · remote writes: 0.</p>
<div class="toolbar"><input id="search" type="search" placeholder="Поиск"><select id="priority"><option value="">Все</option>{options}</select></div>
{''.join(cards)}
</main><script>
const search=document.getElementById('search');const priority=document.getElementById('priority');
function filterCards(){{const q=search.value.trim().toLocaleLowerCase('ru');const p=priority.value;document.querySelectorAll('.card').forEach(card=>{{card.classList.toggle('hidden',!((!q||card.dataset.search.includes(q))&&(!p||card.dataset.priority===p)));}});}}
search.addEventListener('input',filterCards);priority.addEventListener('change',filterCards);
</script></body></html>"""


def _csv(units: list[dict[str, Any]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "research_unit_id",
            "priority",
            "video_ids",
            "titles",
            "active_finding_kinds",
            "legacy_finding_kinds",
            "localization_statuses",
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
                " | ".join(video["video_id"] for video in unit["videos"]),
                " | ".join(video["title"] for video in unit["videos"]),
                " | ".join(unit["active_finding_kinds"]),
                " | ".join(unit["legacy_finding_kinds"]),
                json.dumps(unit["localization_statuses"], ensure_ascii=False, sort_keys=True),
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
        final = _json_bytes(archive.read("04-final-vk-snapshot.json"), name="04-final-vk-snapshot.json")

    videos_raw = final.get("videos")
    findings_raw = plan.get("deferred_editorial_review")
    operations_raw = plan.get("video_text_operations")
    if not isinstance(videos_raw, list) or not isinstance(findings_raw, list) or not isinstance(operations_raw, list):
        raise ValueError("Apply bundle does not contain deferred review data")

    videos = {_remote_id(item): item for item in videos_raw if isinstance(item, dict)}
    before_descriptions = {
        str(item.get("target_video_id")): str(item.get("before_description") or "")
        for item in operations_raw
        if isinstance(item, dict) and item.get("target_video_id")
    }
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for finding in findings_raw:
        if isinstance(finding, dict) and finding.get("target_video_id"):
            grouped[str(finding["target_video_id"])].append(finding)

    items: list[dict[str, Any]] = []
    for video_id, findings in grouped.items():
        video = videos.get(video_id)
        if video is None:
            raise ValueError(f"Deferred review target is absent from final snapshot: {video_id}")
        items.append(_localize_item(video_id, video, findings, before_descriptions.get(video_id, "")))
    items.sort(key=lambda item: (item["title"].casefold(), item["video_id"]))

    units = _research_units(items)
    status_counts = Counter(
        marker["localization_status"] for item in items for marker in item["markers"]
    )
    priority_counts = Counter(unit["priority"] for unit in units)
    duplicate_units = [unit for unit in units if len(unit["videos"]) > 1]
    summary = {
        "videos": len(items),
        "source_findings": len(findings_raw),
        "active_findings": status_counts["present_in_final"],
        "legacy_findings": status_counts["legacy_not_present_in_final"] + status_counts["legacy_unlocalized"],
        "localization_statuses": dict(sorted(status_counts.items())),
        "research_units": len(units),
        "duplicate_description_groups": len(duplicate_units),
        "videos_in_duplicate_groups": sum(len(unit["videos"]) for unit in duplicate_units),
        "priorities": dict(sorted(priority_counts.items())),
        "remote_writes": 0,
    }
    payload = {
        "schema_name": "video-manager.vk-deferred-editorial-review",
        "schema_version": 3,
        "created_at": datetime.now(UTC).isoformat(),
        "source_apply_bundle": str(apply_bundle),
        "source_apply_bundle_sha256": _sha256(apply_bundle),
        "source_plan_sha256": plan.get("plan_sha256"),
        "community_id": plan.get("target_community_id"),
        "mode": "review_only",
        "remote_writes": 0,
        "notice": (
            "Only findings present in the verified final claim text receive active P1/P2 priority. "
            "Legacy findings are preserved for audit but do not authorize corrections."
        ),
        "summary": summary,
        "research_units": units,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="vk-deferred-review-v3-") as temp_dir:
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
            "VK deferred editorial review v3\n\n"
            "Пакет предназначен только для проверки и не вызывает VK mutation API.\n"
            "P1/P2 означают, что маркер присутствует в финальном содержательном тексте.\n"
            "P3 legacy означает, что старый маркер отсутствует в финальном тексте или был только в технической поверхности.\n",
            encoding="utf-8",
        )

        members = [json_path, md_path, html_path, csv_path, readme_path]
        manifest = {
            "schema_name": "video-manager.vk-review-handoff",
            "schema_version": 3,
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

    return {"status": "review_only_completed", "output": str(output), "summary": summary}


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
