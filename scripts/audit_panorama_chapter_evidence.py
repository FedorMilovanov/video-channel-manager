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

from video_channel_manager.platforms.youtube.chapter_release import chapter_stamp
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--playlist", type=Path, required=True)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--archive-db", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.evidence_dir, args.playlist, args.sources, args.archive_db)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({k: v for k, v in report.items() if k != "results"}, ensure_ascii=False))
    print(f"Report SHA256: {_digest(args.output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
