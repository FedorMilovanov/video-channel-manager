"""One-video Lord God YouTube shelf cleanup from exact owner/preview evidence.

This is an intentionally narrower plan than a channel-wide auto-fix. Incomplete
uploads metadata remains an explicit unresolved ledger; no unknown IDs are skipped.
"""

from __future__ import annotations
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
import hashlib
import re
from urllib.parse import parse_qs, urlsplit

from video_channel_manager.platforms.youtube.copy_plan import finalize_copy_plan, sha256_text

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
