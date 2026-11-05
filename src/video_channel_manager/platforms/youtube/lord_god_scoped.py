"""One-video Lord God YouTube shelf cleanup from exact owner/preview evidence.

This is an intentionally narrower plan than a channel-wide auto-fix. Incomplete
uploads metadata remains an explicit unresolved ledger; no unknown IDs are skipped.
"""

from __future__ import annotations
from contextlib import closing
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
import hashlib
import re
from urllib.parse import parse_qs, urlsplit

from video_channel_manager.platforms.youtube.copy_plan import finalize_copy_plan, sha256_text, validate_copy_plan

LORD_GOD_CHANNEL = "UCeSJsC6go2c9pdJCuUI1BYA"
RULESET = "lord-god-scoped-legacy-shelf-removal-v1"
_SHELF_LINK = re.compile(
    r"https?://(?:www\.)?youtube\.com/channel/UCeSJsC6go2c9pdJCuUI1BYA/"
    r"(?:playlists|videos)\?[^\s]*\bshelf_id=\d+(?:&[^\s]*)?"
)


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _owner_video(audit: dict[str, Any], video_id: str) -> dict[str, Any]:
    if audit.get("schema_name") != "video-manager.audit-package":
        raise ValueError("Source must be an official AuditPackage")
    channel = audit.get("channel", {}).get("ref", {})
    if channel.get("remote_id") != LORD_GOD_CHANNEL:
        raise ValueError("Wrong authenticated YouTube channel")
    matches = [v for v in audit.get("videos", []) if v.get("ref", {}).get("remote_id") == video_id]
    if len(matches) != 1 or matches[0].get("ref", {}).get("channel_id") != LORD_GOD_CHANNEL:
        raise ValueError("Target ID is not one unique video of the exact channel")
    return cast(dict[str, Any], matches[0])


def _missing_metadata_exceptions(audit: dict[str, Any], video_id: str) -> list[str]:
    inventory = audit.get("metadata", {}).get("uploads_playlist_inventory", {})
    integrity = inventory.get("pagination_integrity", {})
    if not isinstance(inventory, dict) or integrity.get("validation_passes", 0) < 2:
        raise ValueError("Uploads pagination was not independently reconciled")
    if integrity.get("unique_id_set_reconciled") is not True:
        raise ValueError("Uploads unique ID sets were not reconciled")
    ids = inventory.get("missing_metadata_ids")
    if not isinstance(ids, list) or not ids or len(ids) != len(set(ids)):
        raise ValueError("Metadata exceptions must be explicit unique IDs")
    if video_id in ids:
        raise ValueError("Cannot edit an unmaterialized metadata exception")
    if inventory.get("missing_metadata_count") != len(ids):
        raise ValueError("Metadata gap count mismatch")
    if inventory.get("unique_upload_count") != len(audit.get("videos", [])) + len(ids):
        raise ValueError("Owner source video coverage not accounted for")
    if inventory.get("materialized_video_count") != len(audit.get("videos", [])):
        raise ValueError("Materialized count mismatch")
    if inventory.get("complete") is not False:
        raise ValueError("Scoped exception mode requires explicit incomplete inventory")
    error_findings = [f for f in audit.get("findings", []) if f.get("severity") == "error"]
    found = [
        f.get("details", {}).get("video_id")
        for f in error_findings
        if f.get("rule_id") == "youtube.owner-upload-metadata-gap"
    ]
    if sorted(found) != sorted(ids) or len(error_findings) != len(ids):
        raise ValueError("Unexpected error findings or unproven metadata exceptions")
    return sorted(ids)


def _exact_removals(before: str, after: str) -> int:
    old_lines = before.splitlines(keepends=True)
    new_lines = after.splitlines(keepends=True)
    kept = []
    removed = []
    for line in old_lines:
        if "shelf_id=" not in line:
            kept.append(line)
        else:
            if not _SHELF_LINK.search(line):
                raise ValueError("Unrecognized legacy shelf URL")
            urls = re.findall(r"https?://[^\s]+", line)
            if len(urls) != 1 or not _SHELF_LINK.fullmatch(urls[0]):
                raise ValueError(f"Shelf line contains other links or unverified suffix: {urls!r}")
            removed.append(line)
    if not removed or kept != new_lines:
        raise ValueError("Preview changes text beyond exact shelf-line deletions")
    if "shelf_id=" in after:
        raise ValueError("Preview retains unresolved shelf navigation")
    return len(removed)


def build_one_video_scoped_plan(
    audit: dict[str, Any],
    audit_file: Path,
    preview: dict[str, Any],
    preview_file: Path,
    *,
    video_id: str,
) -> tuple[dict[str, Any], str]:
    """Construct a signed ONE-video plan; every other upload remains explicit."""
    video = _owner_video(audit, video_id)
    missing = _missing_metadata_exceptions(audit, video_id)
    if preview.get("schema") != "lordgod-preview-not-executable-v1":
        raise ValueError("Expected vetted Lord God editorial preview")
    if preview.get("channel_id") != LORD_GOD_CHANNEL or preview.get("is_executable_plan") is not False:
        raise ValueError("Preview is not exact project-bound review-only evidence")
    rows = [r for r in preview.get("items", []) if r.get("video_id") == video_id]
    if len(rows) != 1:
        raise ValueError("Exactly one reviewed preview row is required")
    row = rows[0]
    if row.get("privacy") != "public" or video.get("privacy_status") != "public":
        raise ValueError("Nonpublic videos are excluded from this scope")
    if row.get("unmodified_manual_holds"):
        raise ValueError("Mixed/semantic shelf rows require editorial resolution")
    if row.get("owner_review_required") is not True or row.get("execution_authority") is not False:
        raise ValueError("Unexpected editorial review state")
    before = row.get("current_description")
    after = row.get("candidate_description")
    if not isinstance(before, str) or not isinstance(after, str) or not before or not after:
        raise ValueError("Target before/after must be nonempty strings")
    if video.get("description") != before or sha256_text(before)[7:] != row.get("current_sha256"):
        raise ValueError("Preview does not match immutable current AuditPackage")
    if sha256_text(after)[7:] != row.get("candidate_sha256"):
        raise ValueError("Preview after SHA is inconsistent")
    if len(after.encode("utf-8")) > 5000:
        raise ValueError("Result exceeds YouTube description byte cap")
    if any(x in after.lower() for x in ("thelegendarypoet.ru", "milovicake.ru")):
        raise ValueError("Cross-project links cannot be used in Lord God copy")
    deleted_lines = _exact_removals(before, after)
    _validate_project_copy(audit, video_id=video_id, after=after)
    revision = str(video.get("revision") or "")
    if not revision:
        raise ValueError("Official video revision is missing")
    operation = {
        "operation": "replace_video_description",
        "platform": "youtube",
        "ruleset": RULESET,
        "channel_id": LORD_GOD_CHANNEL,
        "video_id": video_id,
        "title": video.get("title") or video_id,
        "expected_revision": revision,
        "before_description": before,
        "after_description": after,
        "before_sha256": sha256_text(before),
        "after_sha256": sha256_text(after),
        "fixes": [{"code": "reviewed_legacy_shelf_lines", "count": deleted_lines}],
    }
    unresolved = [
        {
            "video_id": item,
            "channel_id": LORD_GOD_CHANNEL,
            "title": "Unmaterialized owner upload",
            "errors": [
                {
                    "code": "youtube.owner-upload-metadata-gap",
                    "message": "Exact owner upload ID inaccessible to videos.list; not selected for mutation.",
                }
            ],
        }
        for item in missing
    ]
    plan = {
        "ruleset": RULESET,
        "generated_at": datetime.now(UTC).isoformat(),
        "source_audit_package": str(audit_file.resolve()),
        "source_audit_sha256": _digest(audit_file),
        "source_editorial_preview": str(preview_file.resolve()),
        "source_editorial_sha256": _digest(preview_file),
        "target_channel_id": LORD_GOD_CHANNEL,
        "project_key": "lord-god-strength",
        "link_profile": "lord-god-strength",
        "youtube_channel_id": LORD_GOD_CHANNEL,
        "vk_community_id": 60805374,
        "vk_owner_id": -60805374,
        "source_audit_snapshot_id": audit.get("snapshot_id"),
        "read_only": True,
        "scoped_review_only": True,
        "videos_checked": 1 + len(missing),
        "operations_count": 1,
        "blocked_operations_count": len(missing),
        "unresolved_error_videos": len(missing),
        "fix_code_counts": {"reviewed_legacy_shelf_lines": deleted_lines},
        "operations": [operation],
        "unresolved": unresolved,
    }
    finalize_copy_plan(plan, checked_video_ids=[video_id, *missing])
    report = (
        "# Lord God one-video scoped editorial plan\n\n"
        f"Exact channel: {LORD_GOD_CHANNEL}\n"
        f"Video: {video_id}\n"
        f"Removed legacy shelf lines: {deleted_lines}\n"
        f"Unmaterialized metadata IDs held separately: {len(missing)}\n"
        f"Source audit SHA-256: {plan['source_audit_sha256']}\n"
        f"Plan SHA-256: {plan['plan_sha256']}\n\n"
        "This file is only a reviewed plan. The official CLI must preflight exact current "
        "description and account, take a backup before any explicit --execute, "
        "and verify every after-state. No blind retries.\n"
    )
    return plan, report


def _validate_project_copy(audit: dict[str, Any], *, video_id: str, after: str) -> None:
    """Reject known non-project contacts, empty navigation and false playlist claims."""
    text = after.lower()
    legacy_contacts = (
        "t.me/fedormilovanov",
        "facebook.com/fedor.milovanov",
        "vk.com/curtmf",
        "donatepay",
        "помочь с переводами",
        "перегрузил туда все видео",
        "пишите:",
    )
    if any(contact in text for contact in legacy_contacts):
        raise ValueError("Legacy personal contact or obsolete solicitation remains after cleanup")
    empty_nav_keywords = (
        "проповеди",
        "тематические серии",
        "семья",
        "конференции",
        "лжерелигии",
        "креационизм",
        "все, что могу",
    )
    for line in after.splitlines():
        clean = line.strip(" \t*📚🔥🏠🎓🌏➡️🔗❓")
        if clean.endswith(":") and any(word in clean.lower() for word in empty_nav_keywords):
            raise ValueError("Empty thematic navigation heading remains after shelf removal")
    owned_ids = {str(collection.get("ref", {}).get("remote_id") or "") for collection in audit.get("collections", [])}
    member_ids = {
        str(link.get("collection_ref", {}).get("remote_id") or "")
        for link in audit.get("memberships", [])
        if link.get("video_ref", {}).get("remote_id") == video_id
    }
    for candidate in re.findall(r"https?://[^\s<>\"'«»]+", after):
        parsed = urlsplit(candidate.rstrip("),.;]>"))
        if parsed.hostname not in ("www.youtube.com", "youtube.com"):
            continue
        if parsed.path != "/playlist":
            continue
        for playlist_id in parse_qs(parsed.query).get("list", []):
            if playlist_id not in owned_ids or playlist_id not in member_ids:
                raise ValueError("Unproven or unrelated YouTube playlist in cleaned description")


CHAPTER_RULESET = "lord-god-one-video-semantic-chapters-v1"


def _chapter_stamp(second: int) -> str:
    if second < 0:
        raise ValueError("Negative chapter start")
    if second >= 3600:
        return f"{second // 3600}:{second % 3600 // 60:02d}:{second % 60:02d}"
    return f"{second // 60:02d}:{second % 60:02d}"


def build_one_video_chapter_plan(
    audit: dict[str, Any],
    audit_file: Path,
    previous_plan: dict[str, Any],
    previous_file: Path,
    review: dict[str, Any],
    review_file: Path,
    transcript_database: Path,
    *,
    video_id: str,
) -> tuple[dict[str, Any], str]:
    """Sign one transcript-grounded chapter appendix; no API or provider writes.

    The existing guarded YouTube copy executor MUST separately preflight the
    current description, OAuth identity, and complete before/after postflight.
    """
    video = _owner_video(audit, video_id)
    missing = _missing_metadata_exceptions(audit, video_id)
    validate_copy_plan(previous_plan)
    if video.get("privacy_status") != "public":
        raise ValueError("Chapter edits require a public owner video")
    if (
        previous_plan.get("target_channel_id") != LORD_GOD_CHANNEL
        or previous_plan.get("project_key") != "lord-god-strength"
        or previous_plan.get("link_profile") != "lord-god-strength"
        or previous_plan.get("source_audit_sha256") != _digest(audit_file)
        or previous_plan.get("source_audit_snapshot_id") != audit.get("snapshot_id")
    ):
        raise ValueError("Previous editorial plan is not bound to the exact owner source")
    ops = previous_plan["operations"]
    if len(ops) != 1 or ops[0].get("video_id") != video_id:
        raise ValueError("Previous editorial plan must contain exactly the target video")
    old = ops[0]
    if (
        old.get("channel_id") != LORD_GOD_CHANNEL
        or old.get("title") != video.get("title")
        or old.get("expected_revision") != video.get("revision")
        or old.get("before_description") != video.get("description")
    ):
        raise ValueError("Original owner video and prior editorial plan have drifted")
    expected_ids = sorted([video_id, *missing])
    if previous_plan.get("checked_video_ids") != expected_ids:
        raise ValueError("Previous plan lost explicit owner metadata gaps")
    unresolved = previous_plan["unresolved"]
    if sorted(str(x.get("video_id")) for x in unresolved) != missing or any(
        x.get("channel_id") != LORD_GOD_CHANNEL
        or not any(e.get("code") == "youtube.owner-upload-metadata-gap" for e in x.get("errors", []))
        for x in unresolved
    ):
        raise ValueError("Previous plan unresolved metadata exception ledger changed")
    if (
        review.get("schema") != "lordgod-chapter-editorial-review-v1"
        or review.get("owner_channel_id") != LORD_GOD_CHANNEL
        or review.get("video_id") != video_id
        or review.get("is_executable_plan") is not False
        or review.get("requires_fresh_youtube_api_preflight") is not True
        or review.get("recording_player_review_required") is not True
        or review.get("provider_writes") != 0
    ):
        raise ValueError("Chapter review is not a non-executable exact-owner review")
    before = old["after_description"]
    if (
        review.get("source_description_sha256") != sha256_text(before)
        or "Таймкоды:" in before
        or "shelf_id=" in before
        or not before.strip()
    ):
        raise ValueError("Chapter review must append to exact previously published clean description")
    chapters = review.get("chapters")
    if not isinstance(chapters, list) or not 3 <= len(chapters) <= 40:
        raise ValueError("Chapters must contain between three and forty source-anchored entries")
    if not transcript_database.is_file():
        raise ValueError("Transcript evidence database is missing")

    import sqlite3 as _sqlite3

    with closing(_sqlite3.connect(transcript_database.as_uri() + "?mode=ro", uri=True)) as connection:
        fragments = connection.execute(
            "SELECT start_ms, end_ms, text FROM transcript_chunks WHERE video_id=? ORDER BY start_ms", (video_id,)
        ).fetchall()
    recorded_count = review.get("source_transcript_chunks", review.get("archived_transcript_chunks"))
    if not fragments or recorded_count != len(fragments) or fragments[0][0] > 60_000:
        raise ValueError("Transcript source coverage or chunk count does not match review")
    ends_at = int(fragments[-1][1] // 1000)
    times: list[int] = []
    rendered: list[str] = []
    for index, chapter in enumerate(chapters):
        if not isinstance(chapter, dict):
            raise ValueError("Every reviewed chapter must be an object")
        chunk_index = chapter.get("index")
        second = chapter.get("second")
        heading = chapter.get("heading")
        cue = chapter.get("cue", chapter.get("source_cue"))
        excerpt = chapter.get("source_excerpt")
        if (
            type(chunk_index) is not int
            or not 0 <= chunk_index < len(fragments)
            or type(second) is not int
            or second < 0
            or not isinstance(heading, str)
            or not 5 <= len(heading.strip()) <= 90
            or "\n" in heading
            or not isinstance(cue, str)
            or not cue.strip()
            or not isinstance(excerpt, str)
            or len(excerpt) < 8
        ):
            raise ValueError("Invalid source-anchored chapter metadata")
        start_ms, _, source_text = fragments[chunk_index]
        source_text = str(source_text or "")
        anchored_seconds = int(start_ms // 1000)
        if (
            (index == 0 and (second != 0 or chunk_index != 0))
            or (index > 0 and anchored_seconds != second)
            or cue.casefold() not in source_text.casefold()
            or not source_text.startswith(excerpt)
        ):
            raise ValueError("Chapter title/time does not match its archival transcript cue")
        if times and second - times[-1] < 10:
            raise ValueError("Chapter timestamps not increasing or too close")
        if chapter.get("stamp") != _chapter_stamp(second):
            raise ValueError("Chapter stamp does not match absolute seconds")
        times.append(second)
        rendered.append(f"{_chapter_stamp(second)} {heading.strip()}")
    if ends_at - times[-1] < 10:
        raise ValueError("Final chapter has less than ten seconds of evidence")
    appendix = "\n\nТаймкоды:\n" + "\n".join(rendered)
    after = before + appendix
    if len(after.encode("utf-8")) > 5000 or sha256_text(after) != review.get("proposed_description_sha256"):
        raise ValueError("Review final description hash or size is inconsistent")

    plan = deepcopy(previous_plan)
    plan["ruleset"] = CHAPTER_RULESET
    plan["generated_at"] = datetime.now(UTC).isoformat()
    plan["source_chapter_review"] = str(review_file.resolve())
    plan["source_chapter_review_sha256"] = _digest(review_file)
    plan["source_previous_editorial_plan"] = str(previous_file.resolve())
    plan["source_previous_editorial_plan_sha256"] = _digest(previous_file)
    plan["chapter_evidence"] = {
        "transcript_database": str(transcript_database.resolve()),
        "video_id": video_id,
        "source_chunk_count": len(fragments),
        "chapter_source_chunk_indices": [x["index"] for x in chapters],
        "source_first_ms": fragments[0][0],
        "source_last_ms": fragments[-1][1],
        "all_cues_verified": True,
        "player_ui_visual_check_pending": True,
    }
    plan["fix_code_counts"] = {"reviewed_transcript_semantic_chapters": len(chapters)}
    plan["operations"][0].update(
        ruleset=CHAPTER_RULESET,
        before_description=before,
        after_description=after,
        before_sha256=sha256_text(before),
        after_sha256=sha256_text(after),
        fixes=[{"code": "reviewed_transcript_semantic_chapters", "count": len(chapters)}],
    )
    plan.pop("plan_sha256", None)
    finalize_copy_plan(plan, checked_video_ids=expected_ids)
    report = (
        "# One-video Lord God source-anchored chapter plan\n\n"
        f"Target video: {video_id}\n"
        f"Chapters: {len(chapters)}\n"
        f"Explicit owner uploads without metadata: {len(missing)}\n"
        f"Original description SHA-256: {sha256_text(before)}\n"
        f"New description SHA-256: {sha256_text(after)}\n"
        f"Plan SHA-256: {plan['plan_sha256']}\n\n"
        "This is a signed offline plan only; run official guarded youtube "
        "apply-copy-fixes without --execute for fresh live preflight. "
        "Publish only after source/editorial review and exact owner verification. "
        "Player chapter UI confirmation remains separate.\n"
    )
    return plan, report
