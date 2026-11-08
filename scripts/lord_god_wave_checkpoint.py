"""Offline candidate checkpoint for Lord God YouTube #795; never calls providers.

A candidate is NOT a signed plan, a rights approval, or permission to write.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

OWNER = "UCeSJsC6go2c9pdJCuUI1BYA"
SCAN_SCHEMA = "lordgod-retro53-all1386-owner-final-v1"
OUTPUT_SCHEMA = "lordgod-offline-wave-checkpoint-v1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def raw_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_URL = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_CHAPTER = re.compile(r"^\s*(?:\d{1,2}:)?\d{1,2}:\d{2}\s+\S")
_CREDIT_WORDS = (
    "перевод",
    "перевёл",
    "перевела",
    "первоисточник",
    "источник",
    "автор",
    "озвуч",
    "copyright",
    "original recording",
    "source:",
    "©",
)


def archive_evidence(description: str) -> dict[str, list[str]]:
    lines = [line.strip() for line in description.splitlines() if line.strip()]
    return {
        "original_urls_unverified": sorted(set(_URL.findall(description))),
        "original_chapter_lines": [line for line in lines if _CHAPTER.search(line)],
        "possible_credit_lines_for_review": [
            line for line in lines if any(word in line.lower() for word in _CREDIT_WORDS)
        ],
    }


def validate_scan(scan: dict[str, Any]) -> tuple[set[str], set[str]]:
    if scan.get("schema") != SCAN_SCHEMA or scan.get("owner") != OWNER:
        raise ValueError("wrong scan schema or owner channel")
    clean = scan.get("clean_ids")
    dirty = scan.get("dirty_ids")
    if not isinstance(clean, list) or not isinstance(dirty, list):
        raise ValueError("missing exact video-id sets")
    if any(not isinstance(x, str) or len(x) != 11 for x in clean + dirty):
        raise ValueError("invalid video identifier")
    clean_set, dirty_set = set(clean), set(dirty)
    total = scan.get("total")
    if (
        len(clean_set) != len(clean)
        or len(dirty_set) != len(dirty)
        or clean_set & dirty_set
        or total != len(clean) + len(dirty)
        or scan.get("accessible") != total
        or scan.get("clean_count") != len(clean)
        or scan.get("dirty_count") != len(dirty)
        or scan.get("missing_ids") not in (0, [])
        or scan.get("regressions") not in (0, [])
        or scan.get("unexpected_clean") not in (0, [])
    ):
        raise ValueError("owner inventory inconsistent; STOP, do not infer candidates")
    return clean_set, dirty_set


def build_checkpoint(
    scan: dict[str, Any],
    archive: sqlite3.Connection,
    holds: set[str],
    *,
    limit: int,
    scan_digest: str,
    archive_digest: str,
) -> dict[str, Any]:
    clean, dirty = validate_scan(scan)
    if not 1 <= limit <= 50:
        raise ValueError("limit must be 1..50")
    if not holds:
        raise ValueError("explicit HOLD set is mandatory")
    # Read only archived evidence; do not infer current titles/descriptions from it.
    rows = archive.execute(
        "SELECT video_id, title, description, view_count, transcript_chunks, "
        "transcript_sha256, published_at, duration, playlist_count "
        "FROM videos"
    ).fetchall()
    archive_by_id = {str(row[0]): row for row in rows}
    eligible = []
    excluded_hold = sorted(dirty & holds)
    absent_archive = []
    missing_transcript = []
    for video_id in sorted(dirty - holds):
        row = archive_by_id.get(video_id)
        if row is None:
            absent_archive.append(video_id)
            continue
        _id, title, description, views, chunks, transcript_sha, published, duration, playlist_count = row
        if not title or not description or not chunks or int(chunks) < 3 or not transcript_sha:
            missing_transcript.append(video_id)
            continue
        eligible.append(
            {
                "video_id": video_id,
                "archived_title": title,
                "archived_description_sha256_raw": raw_sha(description),
                "archived_source_evidence": archive_evidence(description),
                "archived_transcript_sha256": transcript_sha,
                "archived_transcript_chunks": int(chunks),
                "archived_views": max(0, int(views or 0)),
                "archived_published_at": published,
                "archived_duration_seconds": duration,
                "archived_playlist_count": playlist_count,
                "status": "EDITORIAL_REVIEW_ONLY",
                "needs": [
                    "fresh_official_owner_get_exact_title_and_before_sha",
                    "primary_source_and_translation_credit_review",
                    "original_chapters_and_playlist_membership_review",
                    "third_party_rights_review",
                    "individual_signed_plan_and_guarded_dry_run",
                ],
            }
        )
    eligible.sort(key=lambda x: (-x["archived_views"], -x["archived_transcript_chunks"], x["video_id"]))
    picked = eligible[:limit]
    # Machine-readable anchors from the owner's actual archived transcript, not generated chapters.
    for row in picked:
        video_id = row["video_id"]
        parts = archive.execute(
            "SELECT start_ms, text FROM transcript_chunks WHERE video_id=? ORDER BY chunk_index", (video_id,)
        ).fetchall()
        indices = sorted({0, len(parts) // 2, len(parts) - 1}) if parts else []
        row["archive_speech_samples"] = [
            {"at_seconds": int(parts[i][0] or 0) // 1000, "text_excerpt": (parts[i][1] or "")[:180]} for i in indices
        ]
    return {
        "schema": OUTPUT_SCHEMA,
        "project_key": "lord-god-strength",
        "owner": OWNER,
        "transport": "local_only",
        "provider_get_calls": 0,
        "provider_writes": 0,
        "publication_approved": False,
        "can_generate_signed_plan": False,
        "snapshot_utc": scan.get("utc"),
        "owner_scan_sha256": scan_digest,
        "archive_db_sha256": archive_digest,
        "snapshot_total": scan["total"],
        "snapshot_clean": len(clean),
        "snapshot_dirty": len(dirty),
        "snapshot_old_shelf_links": scan["remaining_shelf_links"],
        "snapshot_old_contacts": scan["remaining_old_contacts"],
        "hold_ids_excluded": excluded_hold,
        "nonhold_missing_archive_ids": absent_archive,
        "nonhold_missing_transcript_ids": missing_transcript,
        "candidate_pool_with_archived_transcripts": len(eligible),
        "candidate_count": len(picked),
        "candidates": picked,
        "next_action": "human/editorial source review; fresh official owner GET before any signed plan",
        "caveat": "Historical owner scan and archive are evidence, not live publication authority. HOLD registry completeness not independently proven.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-scan", type=Path, required=True)
    parser.add_argument("--archive-db", type=Path, required=True)
    parser.add_argument("--expected-archive-sha256", required=True)
    parser.add_argument("--holds-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()
    scan = json.loads(args.owner_scan.read_text(encoding="utf-8"))
    hold_data = json.loads(args.holds_json.read_text(encoding="utf-8"))
    if hold_data.get("owner") != OWNER or not isinstance(hold_data.get("ids"), list):
        raise ValueError("HOLD ledger must identify exact owner and explicit ids")
    holds = set(hold_data["ids"])
    if len(holds) != len(hold_data["ids"]) or not all(isinstance(x, str) and len(x) == 11 for x in holds):
        raise ValueError("duplicate or invalid HOLD IDs")
    archive_digest = sha256_file(args.archive_db)
    if archive_digest != args.expected_archive_sha256.removeprefix("sha256:"):
        raise ValueError("archive database SHA mismatch: STOP")
    # SQLite is read-only. No YouTube token or HTTP client is imported.
    with sqlite3.connect(f"file:{args.archive_db.resolve().as_posix()}?mode=ro", uri=True) as archive:
        result = build_checkpoint(
            scan,
            archive,
            holds,
            limit=args.limit,
            scan_digest=sha256_file(args.owner_scan),
            archive_digest=archive_digest,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(
        json.dumps(
            {
                "status": "OFFLINE_REVIEW_ONLY",
                "checkpoint": str(args.output),
                "candidates": result["candidate_count"],
                "excluded_hold": len(result["hold_ids_excluded"]),
                "provider_writes": 0,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
