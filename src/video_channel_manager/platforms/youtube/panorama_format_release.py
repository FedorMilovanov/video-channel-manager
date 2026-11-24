"""Exact-owner historical chapter format plan. No provider transport or quota grant."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.platforms.youtube.chapter_release import (
    chapter_stamp,
    digest_file,
    load_panorama_owner_evidence,
    normalize_existing_chapter_stamps,
)
from video_channel_manager.platforms.youtube.copy_plan import finalize_copy_plan, sha256_text, validate_copy_plan
from video_channel_manager.platforms.youtube.lord_god_source_preservation import LORD_GOD_OWNER_CHANNEL

FORMAT_RULESET = "lord-god-panorama-existing-chapter-format-v1"
FORMAT_SCOPE = "exact-panorama-owner-format-v1"


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("Expected format evidence object")
    return value


def _plain_inventory(before: str) -> list[tuple[str, str]]:
    result = []
    for line in before.splitlines():
        match = re.fullmatch(r"([0-9]{1,4}:[0-9]{2}(?::[0-9]{2})?) (\S.*)", line)
        if match:
            result.append((match[1], match[2]))
    return result


def _changes(chapters: list[tuple[str, str]]) -> list[dict[str, Any]]:
    changes = []
    for stamp, heading in chapters:
        second = sum(int(part) * 60**i for i, part in enumerate(reversed(stamp.split(":"))))
        canonical = chapter_stamp(second)
        if stamp != canonical:
            changes.append({"stamp": stamp, "canonical_stamp": canonical, "second": second, "heading": heading})
    return changes


def build_format_correction_plan(
    owner_file: Path,
    playlist_file: Path,
    source_file: Path,
    candidate_file: Path,
    review_file: Path,
    *,
    video_id: str,
) -> tuple[dict[str, Any], str]:
    """Re-derive exact format-only change from owner evidence, not a stale archive."""
    proof = load_panorama_owner_evidence(
        owner_file, playlist_file, source_file, video_id=video_id, existing_chapters=True
    )
    before = proof["description"]
    chapters = _plain_inventory(before)
    after = normalize_existing_chapter_stamps(before, chapters, duration_seconds=proof["duration_seconds"])
    changes = _changes(chapters)
    candidate = _read(candidate_file)
    expected_candidate = {
        "schema": "panorama-exact-owner-format-candidate-v1",
        "project_key": "lord-god-strength",
        "owner_channel_id": LORD_GOD_OWNER_CHANNEL,
        "video_id": video_id,
        "episode": proof["episode"],
        "title": proof["title"],
        "original": proof["original"],
        "owner_revision": proof["revision"],
        "owner_receipt_sha256": digest_file(owner_file).removeprefix("sha256:"),
        "playlist_sha256": digest_file(playlist_file).removeprefix("sha256:"),
        "source_register_sha256": digest_file(source_file).removeprefix("sha256:"),
        "before_description": before,
        "before_sha256": sha256_text(before),
        "proposed_description": after,
        "proposed_sha256": sha256_text(after),
        "changes": changes,
        "duration_seconds": proof["duration_seconds"],
        "provider_reads": 0,
        "provider_writes": 0,
        "is_executable_plan": False,
        "semantic_approval": False,
        "format_review": "HOLD",
        "execution": "HOLD",
    }
    if any(candidate.get(k) != v for k, v in expected_candidate.items()):
        raise ValueError("Format candidate differs from exact owner evidence")
    review = _read(review_file)
    expected_review = {
        "schema": "panorama-existing-chapter-format-review-v1",
        "owner_channel_id": LORD_GOD_OWNER_CHANNEL,
        "video_id": video_id,
        "candidate_sha256": digest_file(candidate_file),
        "before_sha256": sha256_text(before),
        "after_sha256": sha256_text(after),
        "format_review": "APPROVED",
        "semantic_approval": False,
    }
    if any(review.get(k) != v for k, v in expected_review.items()):
        raise ValueError("Missing or mismatched independent format review")
    reviewer = review.get("reviewer")
    reviewed_at = review.get("reviewed_at")
    if not isinstance(reviewer, str) or not reviewer.strip() or not isinstance(reviewed_at, str):
        raise ValueError("Format review lacks reviewer or review time")
    if datetime.fromisoformat(reviewed_at).utcoffset() is None:
        raise ValueError("Format review requires offset-aware time")
    plan: dict[str, Any] = {
        "ruleset": FORMAT_RULESET,
        "generated_at": datetime.now(UTC).isoformat(),
        "target_channel_id": LORD_GOD_OWNER_CHANNEL,
        "project_key": "lord-god-strength",
        "link_profile": "lord-god-strength",
        "youtube_channel_id": LORD_GOD_OWNER_CHANNEL,
        "vk_community_id": 60805374,
        "vk_owner_id": -60805374,
        "read_only": True,
        "scoped_review_only": True,
        "source_scope": FORMAT_SCOPE,
        "source_owner_receipt": str(owner_file.resolve()),
        "source_audit_sha256": digest_file(owner_file),
        "source_playlist_receipt": str(playlist_file.resolve()),
        "source_playlist_sha256": digest_file(playlist_file),
        "source_original_register": str(source_file.resolve()),
        "source_original_register_sha256": digest_file(source_file),
        "source_format_candidate": str(candidate_file.resolve()),
        "source_format_candidate_sha256": digest_file(candidate_file),
        "source_chapter_review": str(review_file.resolve()),
        "source_chapter_review_sha256": digest_file(review_file),
        "release_hold": "SHARED_QUOTA_AND_EXECUTION_INTEGRATION_REQUIRED",
        "semantic_approval": False,
        "videos_checked": 1,
        "operations_count": 1,
        "blocked_operations_count": 0,
        "unresolved_error_videos": 0,
        "unresolved": [],
        "fix_code_counts": {"historical_chapter_format_only": len(changes)},
        "operations": [
            {
                "operation": "replace_video_description",
                "platform": "youtube",
                "ruleset": FORMAT_RULESET,
                "channel_id": LORD_GOD_OWNER_CHANNEL,
                "video_id": video_id,
                "title": proof["title"],
                "expected_revision": proof["revision"],
                "before_description": before,
                "after_description": after,
                "before_sha256": sha256_text(before),
                "after_sha256": sha256_text(after),
                "fixes": [{"code": "historical_chapter_format_only", "count": len(changes)}],
            }
        ],
    }
    finalize_copy_plan(plan, checked_video_ids=[video_id])
    return plan, (
        f"# Exact-owner format-only review plan: {video_id}\n\n"
        f"Changed timestamp tokens: {len(changes)}. Absolute seconds and other text unchanged.\n"
        "No semantic approval or provider execution authority; shared quota integration HOLD.\n"
    )


def require_format_correction_plan(plan: dict[str, Any]) -> None:
    """Refuse forged, re-sealed or stale provenance even for a preflight."""
    validate_copy_plan(plan)
    if plan.get("ruleset") != FORMAT_RULESET or plan.get("source_scope") != FORMAT_SCOPE:
        raise ValueError("Wrong historical format plan scope")
    if len(plan["operations"]) != 1:
        raise ValueError("Historical format plan must contain exactly one operation")
    paths = []
    for field, digest in (
        ("source_owner_receipt", "source_audit_sha256"),
        ("source_playlist_receipt", "source_playlist_sha256"),
        ("source_original_register", "source_original_register_sha256"),
        ("source_format_candidate", "source_format_candidate_sha256"),
        ("source_chapter_review", "source_chapter_review_sha256"),
    ):
        value = plan.get(field)
        if not isinstance(value, str):
            raise ValueError("Missing format evidence path")
        path = Path(value)
        if not path.is_absolute() or not path.is_file() or digest_file(path) != plan.get(digest):
            raise ValueError("Bound format artifact missing or changed")
        paths.append(path)
    expected, _ = build_format_correction_plan(*paths, video_id=plan["operations"][0]["video_id"])
    ignored = {"generated_at", "plan_sha256"}
    if {k: v for k, v in plan.items() if k not in ignored} != {k: v for k, v in expected.items() if k not in ignored}:
        raise ValueError("Format plan differs from independently re-derived owner evidence")
