"""Provider-inert audit of historical Panorama chapter evidence, including legacy schemas."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from video_channel_manager.platforms.youtube.chapter_release import (
    chapter_stamp,
    load_panorama_owner_evidence,
    normalize_existing_chapter_stamps,
)
from video_channel_manager.platforms.youtube.copy_plan import sha256_text
from video_channel_manager.platforms.youtube.lord_god_source_preservation import LORD_GOD_OWNER_CHANNEL


def parse_stamp(value: str) -> int:
    if not isinstance(value, str) or not re.fullmatch(r"\d{1,4}:\d{2}(?::\d{2})?", value):
        raise ValueError("Invalid historical chapter stamp")
    parts = list(map(int, value.split(":")))
    if parts[-1] >= 60 or (len(parts) == 3 and parts[-2] >= 60):
        raise ValueError("Invalid historical chapter clock component")
    return sum(x * 60**i for i, x in enumerate(reversed(parts)))


def _digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def audit(directory: Path, playlist: Path, sources: Path, archive: Path) -> dict[str, Any]:
    members = _read(playlist)["memberships"]
    register = _read(sources)["items"]
    if (
        len(members) != 68
        or len({m["video_id"] for m in members}) != 68
        or {m["position"] for m in members} != set(range(68))
        or any(m["video_owner"] != LORD_GOD_OWNER_CHANNEL for m in members)
        or len(register) != 68
        or {s["number"] for s in register} != set(range(1, 69))
    ):
        raise ValueError("Expected complete frozen exact-owner Panorama registers")
    by_id = {m["video_id"]: m["position"] + 1 for m in members}
    source_by_ep = {s["number"]: s for s in register}
    results: list[dict[str, Any]] = []
    seen = set()
    with closing(sqlite3.connect(archive.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        for evidence in sorted(directory.glob("*evidence*.json")):
            item = _read(evidence)
            if not isinstance(item, dict) or not isinstance(item.get("chapters"), list):
                continue
            video_id = item["video_id"]
            if video_id not in by_id or video_id in seen:
                raise ValueError(f"Duplicate or foreign historical evidence: {evidence.name}")
            seen.add(video_id)
            episode = by_id[video_id]
            if item.get("episode", episode) != episode:
                raise ValueError(f"Episode mismatch: {evidence.name}")
            source = next(
                (item[k] for k in ("original", "source_url", "source_original", "original_url") if k in item), None
            )
            src = source_by_ep[episode]
            duration_ms = item.get("duration_ms")
            if type(duration_ms) is not int or duration_ms <= 0:
                raise ValueError(f"Missing recording duration: {evidence.name}")
            caption_path = directory / f"{video_id}.ru-orig.json3"
            expected_caption_sha = item.get("caption_sha256", item.get("captions_sha256"))
            caption_sha = _digest(caption_path)
            caption_matches = isinstance(
                expected_caption_sha, str
            ) and caption_sha == expected_caption_sha.removeprefix("sha256:")
            caption_events = _read(caption_path)["events"]
            caption_times = {
                e["tStartMs"] for e in caption_events if isinstance(e, dict) and e.get("segs") and "tStartMs" in e
            }
            archive_rows = db.execute(
                "SELECT start_ms, end_ms FROM transcript_chunks WHERE video_id=? ORDER BY start_ms", (video_id,)
            ).fetchall()
            archive_times = {a[0] for a in archive_rows}
            rows = []
            for chapter in item["chapters"]:
                # Historical schemas are deliberately mapped without rewriting input.
                stamp = chapter.get("time", chapter.get("timestamp"))
                label = chapter.get("title", chapter.get("label", chapter.get("chapter_title")))
                second = parse_stamp(stamp)
                cap = next(
                    (
                        chapter[k]
                        for k in (
                            "nearest_caption_ms",
                            "youtube_nearest_ms",
                            "nearest_youtube_ms",
                            "caption_timestamp_ms",
                            "caption_time_ms",
                        )
                        if k in chapter
                    ),
                    None,
                )
                asr = next(
                    (
                        chapter[k]
                        for k in (
                            "nearest_archive_ms",
                            "archive_nearest_ms",
                            "nearest_archived_ms",
                            "archived_transcript_time_ms",
                        )
                        if k in chapter
                    ),
                    None,
                )
                rows.append(
                    {
                        "stamp": stamp,
                        "canonical_stamp": chapter_stamp(second),
                        "second": second,
                        "heading": label,
                        "caption_anchor_ms": cap,
                        "archive_anchor_ms": asr,
                        "caption_anchor_exists": cap in caption_times,
                        "archive_anchor_exists": asr in archive_times,
                        "caption_delta_ms": abs(cap - second * 1000) if type(cap) is int else None,
                    }
                )
            seconds = [r["second"] for r in rows]
            if not seconds:
                raise ValueError(f"Empty chapter list: {evidence.name}")
            gaps = [b - a for a, b in zip(seconds, seconds[1:], strict=False)]
            results.append(
                {
                    "episode": episode,
                    "video_id": video_id,
                    "historical_evidence": evidence.name,
                    "evidence_sha256": _digest(evidence),
                    "source_url_matches_register": bool(src["ok"] and source == src["url"]),
                    "caption_sha256_matches": caption_matches,
                    "archive_chunk_count": len(archive_rows),
                    "chapters": rows,
                    "chapter_count": len(rows),
                    "legacy_stamp_count": sum(r["stamp"] != r["canonical_stamp"] for r in rows),
                    "four_minute_grid_count_excluding_zero": sum(s != 0 and s % 240 == 0 for s in seconds),
                    "first_zero": seconds[0] == 0,
                    "min_gap_seconds": min(gaps) if gaps else None,
                    "last_tail_ms": duration_ms - seconds[-1] * 1000,
                    "caption_anchors_missing": sum(not r["caption_anchor_exists"] for r in rows),
                    "archive_anchors_missing": sum(not r["archive_anchor_exists"] for r in rows),
                    "semantic_status": "REQUIRES_EXACT_BOUNDARY_REVIEW",
                    "provider_state": "NOT_CHECKED_IN_THIS_OFFLINE_AUDIT",
                }
            )
    results.sort(key=lambda r: r["episode"])
    return {
        "schema": "panorama-historical-chapter-evidence-audit-v2",
        "project_key": "lord-god-strength",
        "owner_channel_id": LORD_GOD_OWNER_CHANNEL,
        "read_only": True,
        "provider_reads": 0,
        "provider_writes": 0,
        "semantic_approval": False,
        "is_executable_plan": False,
        "frozen_playlist_sha256": _digest(playlist),
        "source_register_sha256": _digest(sources),
        "videos": len(results),
        "chapter_count": sum(r["chapter_count"] for r in results),
        "legacy_stamp_count": sum(r["legacy_stamp_count"] for r in results),
        "videos_with_legacy_stamps": sum(r["legacy_stamp_count"] > 0 for r in results),
        "four_minute_grid_count_excluding_zero": sum(r["four_minute_grid_count_excluding_zero"] for r in results),
        "caption_sha256_matches": sum(r["caption_sha256_matches"] for r in results),
        "source_url_matches": sum(r["source_url_matches_register"] for r in results),
        "caption_anchors_missing": sum(r["caption_anchors_missing"] for r in results),
        "archive_anchors_missing": sum(r["archive_anchors_missing"] for r in results),
        "results": results,
    }


def verify_format_preview(audit_file: Path, preview_file: Path) -> dict[str, Any]:
    """Re-derive an archived format-only preview without accepting it as a write plan."""
    baseline = _read(audit_file)
    preview = _read(preview_file)
    if (
        baseline.get("schema") != "panorama-historical-chapter-evidence-audit-v2"
        or baseline.get("owner_channel_id") != LORD_GOD_OWNER_CHANNEL
        or baseline.get("is_executable_plan") is not False
        or preview.get("schema") != "panorama-format-only-review-report-v1"
        or preview.get("owner_channel_id") != LORD_GOD_OWNER_CHANNEL
        or preview.get("project_key") != "lord-god-strength"
        or preview.get("source_audit") != audit_file.name
        or preview.get("source_audit_sha256") != _digest(audit_file)
        or preview.get("is_executable_plan") is not False
        or preview.get("semantic_approval") is not False
        or preview.get("fresh_owner_snapshot") is not False
        or preview.get("provider_reads") != 0
        or preview.get("provider_writes") != 0
    ):
        raise ValueError("Unbound or executable format preview")
    rows = {row["video_id"]: row for row in baseline["results"]}
    if len(rows) != len(baseline["results"]):
        raise ValueError("Duplicate historical audit identity")
    seen: set[str] = set()
    count = 0
    for item in preview["items"]:
        video_id = item["video_id"]
        row = rows.get(video_id)
        if row is None or video_id in seen or item["episode"] != row["episode"]:
            raise ValueError("Foreign or duplicate format preview identity")
        seen.add(video_id)
        source_name = item["historical_plan"]
        if Path(source_name).name != source_name or not source_name.startswith(video_id + "-"):
            raise ValueError("Invalid archived plan filename")
        source_path = preview_file.parent / source_name
        if _digest(source_path) != item["historical_plan_sha256"]:
            raise ValueError("Archived plan digest mismatch")
        ops = [op for op in _read(source_path)["operations"] if op["video_id"] == video_id]
        before = item["before_description"]
        if (
            len(ops) != 1
            or ops[0]["after_description"] != before
            or ops[0]["after_sha256"] != sha256_text(before)
            or item["before_sha256"] != sha256_text(before).removeprefix("sha256:")
        ):
            raise ValueError("Archived exact description mismatch")
        chapters = row["chapters"]
        if not chapters or any(
            c["second"] != parse_stamp(c["stamp"]) or c["canonical_stamp"] != chapter_stamp(parse_stamp(c["stamp"]))
            for c in chapters
        ):
            raise ValueError("Historical audit timestamp evidence is inconsistent")
        duration = chapters[-1]["second"] + row["last_tail_ms"] // 1000
        after = normalize_existing_chapter_stamps(
            before, [(c["stamp"], c["heading"]) for c in chapters], duration_seconds=duration
        )
        changes = [
            {k: c[k] for k in ("stamp", "canonical_stamp", "second", "heading")}
            for c in chapters
            if c["stamp"] != c["canonical_stamp"]
        ]
        if (
            changes != item["changes"]
            or after != item["proposed_description"]
            or item["proposed_sha256"] != sha256_text(after).removeprefix("sha256:")
            or item["proposed_utf8_bytes"] != len(after.encode("utf-8"))
        ):
            raise ValueError("Format preview differs from canonical re-derivation")
        count += len(changes)
    if not seen:
        raise ValueError("Empty format preview")
    return {
        "schema": "panorama-format-preview-qa-v1",
        "audit_sha256": _digest(audit_file),
        "preview_sha256": _digest(preview_file),
        "videos_checked": len(seen),
        "stamps_verified": count,
        "provider_reads": 0,
        "provider_writes": 0,
        "is_executable_plan": False,
        "semantic_approval": False,
    }


def bind_format_preview_to_owner(
    audit_file: Path,
    preview_file: Path,
    owner_file: Path,
    playlist_file: Path,
    source_file: Path,
    *,
    video_id: str,
) -> dict[str, Any]:
    """Prepare one exact-owner review candidate, never an executable plan."""
    qa = verify_format_preview(audit_file, preview_file)
    baseline = _read(audit_file)
    if baseline["frozen_playlist_sha256"] != _digest(playlist_file) or baseline["source_register_sha256"] != _digest(
        source_file
    ):
        raise ValueError("Frozen series registers differ from the archived audit")
    preview = _read(preview_file)
    matches = [item for item in preview["items"] if item["video_id"] == video_id]
    if len(matches) != 1:
        raise ValueError("Expected exactly one selected historical preview")
    item = matches[0]
    proof = load_panorama_owner_evidence(
        owner_file, playlist_file, source_file, video_id=video_id, existing_chapters=True
    )
    if proof["episode"] != item["episode"]:
        raise ValueError("Exact owner episode differs from archived preview")
    if proof["description"] != item["before_description"]:
        raise ValueError("Exact owner description differs from archived preview; re-audit, never overwrite")
    row = next(r for r in baseline["results"] if r["video_id"] == video_id)
    after = normalize_existing_chapter_stamps(
        proof["description"],
        [(c["stamp"], c["heading"]) for c in row["chapters"]],
        duration_seconds=proof["duration_seconds"],
    )
    if after != item["proposed_description"]:
        raise ValueError("Owner-bound correction differs from verified preview")
    return {
        "schema": "panorama-exact-owner-format-candidate-v1",
        "project_key": "lord-god-strength",
        "owner_channel_id": LORD_GOD_OWNER_CHANNEL,
        "video_id": video_id,
        "episode": proof["episode"],
        "title": proof["title"],
        "original": proof["original"],
        "owner_revision": proof["revision"],
        "owner_receipt_sha256": _digest(owner_file),
        "playlist_sha256": _digest(playlist_file),
        "source_register_sha256": _digest(source_file),
        "audit_sha256": qa["audit_sha256"],
        "preview_sha256": qa["preview_sha256"],
        "before_description": proof["description"],
        "before_sha256": sha256_text(proof["description"]),
        "proposed_description": after,
        "proposed_sha256": sha256_text(after),
        "changes": item["changes"],
        "duration_seconds": proof["duration_seconds"],
        "provider_reads": 0,
        "provider_writes": 0,
        "is_executable_plan": False,
        "semantic_approval": False,
        "format_review": "HOLD",
        "execution": "HOLD",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--playlist", type=Path)
    parser.add_argument("--sources", type=Path)
    parser.add_argument("--archive-db", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify-format-preview", type=Path)
    parser.add_argument("--existing-audit", type=Path)
    parser.add_argument("--owner-receipt", type=Path)
    parser.add_argument("--target-video-id")
    args = parser.parse_args()
    historical_args = (args.evidence_dir, args.playlist, args.sources, args.archive_db)
    if args.owner_receipt or args.target_video_id:
        if (
            not all(
                (
                    args.owner_receipt,
                    args.target_video_id,
                    args.verify_format_preview,
                    args.existing_audit,
                    args.playlist,
                    args.sources,
                )
            )
            or args.evidence_dir
            or args.archive_db
        ):
            parser.error("Owner binding requires receipt, target, both registers, audit and preview")
        report = bind_format_preview_to_owner(
            args.existing_audit,
            args.verify_format_preview,
            args.owner_receipt,
            args.playlist,
            args.sources,
            video_id=args.target_video_id,
        )
    elif args.verify_format_preview or args.existing_audit:
        if not (args.verify_format_preview and args.existing_audit) or any(historical_args):
            parser.error("Format preview QA requires --verify-format-preview and --existing-audit only")
        report = verify_format_preview(args.existing_audit, args.verify_format_preview)
    else:
        if not all(historical_args):
            parser.error("Historical audit requires --evidence-dir, --playlist, --sources and --archive-db")
        report = audit(args.evidence_dir, args.playlist, args.sources, args.archive_db)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k not in {"results", "before_description", "proposed_description", "changes"}
            },
            ensure_ascii=False,
        )
    )
    print(f"Report SHA256: {_digest(args.output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
