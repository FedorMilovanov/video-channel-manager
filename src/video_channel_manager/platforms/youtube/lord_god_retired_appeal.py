"""Exact-owner, one-video removal of retired translator solicitations and legacy shelves.

Never edits YouTube: produces the normal SHA-bound plan consumed by the
existing official guarded apply-copy-fixes executor. This mode is deliberately
strict and does not attempt mass editing or removal of third-party credits.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.platforms.youtube.copy_plan import finalize_copy_plan, sha256_text
from video_channel_manager.platforms.youtube.lord_god_scoped import (
    LORD_GOD_CHANNEL,
    _digest,
    _exact_removals,
    _missing_metadata_exceptions,
    _owner_video,
    _validate_project_copy,
)

RULESET = "lord-god-reviewed-retired-appeal-v1"

_APPEAL_PREFIXES = (
    "➡️ Некоторые проповеди получается перевести",
    "⚠️⚠️⚠️ Всегда есть нужда в переводах библейского материала.",
)
_ALLOWED_APPEAL_URLS = {
    "https://t.me/fedormilovanov",
    "https://www.facebook.com/fedor.milovanov",
    "https://vk.com/curtmf",
}


def _is_exact_retired_appeal(line: str) -> bool:
    text = line.strip()
    if not any(text.startswith(prefix) for prefix in _APPEAL_PREFIXES):
        return False
    lower = text.casefold()
    if "перевод" not in lower or "пишите" not in lower:
        return False
    # No source, copyright, licensing or third-party attribution URL may be
    # deleted as part of a merely administrative appeal removal.
    links = [url.rstrip(".,;)]") for url in re.findall(r"https?://[^\s<>\"']+", text)]
    if any(link not in _ALLOWED_APPEAL_URLS for link in links):
        return False
    return True


def _substantive_characters(description: str) -> int:
    """A conservative lower bound; channel navigation and chapter cues don't count."""
    meaningful = []
    for line in description.splitlines():
        text = line.strip()
        if (
            not text
            or ("http" in text and len(text) < 200)
            or text.startswith("#")
            or text.startswith("━")
            or re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?\s+.*", text)
            or any(
                marker in text.casefold()
                for marker in ("телеграм:", "вконтакте:", "одноклассники:", "rutube:", "facebook:")
            )
        ):
            continue
        meaningful.append(text)
    return len("".join(meaningful).strip())


def build_one_video_retired_appeal_plan(
    audit: dict[str, Any],
    audit_file: Path,
    review: dict[str, Any],
    review_file: Path,
    *,
    video_id: str,
) -> tuple[dict[str, Any], str]:
    """Build one signed plan; retains every surviving source line exactly."""
    video = _owner_video(audit, video_id)
    missing = _missing_metadata_exceptions(audit, video_id)
    if video.get("privacy_status") != "public":
        raise ValueError("Nonpublic videos cannot use the reviewed appeal-removal plan")
    if (
        review.get("schema") != "lordgod-retired-solicitation-review-v1"
        or review.get("video_id") != video_id
        or review.get("owner_channel_id") != LORD_GOD_CHANNEL
        or review.get("archived_snapshot_only") is not True
        or review.get("owner_live_preflight_required") is not True
        or review.get("is_executable_plan") is not False
        or review.get("publisher_ready") is not False
        or review.get("provider_writes") != 0
    ):
        raise ValueError("Review is not an exact-owner non-executable source attestation")

    before = review.get("original_description")
    shelf_only = review.get("shelf_removed_only")
    after = review.get("final_description")
    if (
        not isinstance(before, str)
        or not before
        or not isinstance(shelf_only, str)
        or not shelf_only
        or not isinstance(after, str)
        or not after
    ):
        raise ValueError("Review must contain three nonblank description versions")
    if (
        before != video.get("description")
        or review.get("original_sha256") != sha256_text(before)
        or review.get("shelf_removed_only_sha256") != sha256_text(shelf_only)
        or review.get("final_sha256") != sha256_text(after)
    ):
        raise ValueError("Review SHA or archived owner description is inconsistent")
    shelf_count = _exact_removals(before, shelf_only)
    if shelf_count != review.get("expected_legacy_shelf_lines_deleted"):
        raise ValueError("Review legacy shelf deletion count drifted")
    lines = shelf_only.splitlines(keepends=True)
    removed_lines = [line for line in lines if _is_exact_retired_appeal(line)]
    if len(removed_lines) != 1:
        raise ValueError("Exactly one narrowly recognized retired solicitation is required")
    if review.get("sole_allowed_retired_solicitation_line") != removed_lines[0]:
        raise ValueError("Review does not attest exact retired solicitation source line")
    reconstructed = "".join(line for line in lines if line != removed_lines[0])
    if reconstructed != after:
        raise ValueError("Edited copy changed material beyond the two exact allowed deletions")
    if len(after.encode("utf-8")) > 5000:
        raise ValueError("YouTube description exceeds 5000 UTF-8 bytes")
    if _substantive_characters(after) < 350:
        raise ValueError("Remaining description lacks substantial editorial content")
    if any(s in after.casefold() for s in ("помочь с переводами", "нужда в переводах", "@fedormilovanov")):
        raise ValueError("Retired solicitation or personal handle remains")
    _validate_project_copy(audit, video_id=video_id, after=after)

    revision = str(video.get("revision") or "")
    if not revision:
        raise ValueError("Owner video revision must exist")
    unresolved = [
        {
            "video_id": item,
            "channel_id": LORD_GOD_CHANNEL,
            "title": "Unmaterialized owner upload",
            "errors": [
                {
                    "code": "youtube.owner-upload-metadata-gap",
                    "message": "Official owner upload metadata unavailable; never selected for modification.",
                }
            ],
        }
        for item in missing
    ]
    plan: dict[str, Any] = {
        "ruleset": RULESET,
        "generated_at": datetime.now(UTC).isoformat(),
        "source_audit_package": str(audit_file.resolve()),
        "source_audit_sha256": _digest(audit_file),
        "source_editorial_preview": str(review_file.resolve()),
        "source_editorial_sha256": _digest(review_file),
        "target_channel_id": LORD_GOD_CHANNEL,
        "project_key": "lord-god-strength",
        "link_profile": "lord-god-strength",
        "youtube_channel_id": LORD_GOD_CHANNEL,
        "vk_community_id": 60805374,
        "vk_owner_id": -60805374,
        "source_audit_snapshot_id": audit.get("snapshot_id"),
        "read_only": True,
        "scoped_review_only": True,
        "live_provider_preflight_required": True,
        "videos_checked": 1 + len(missing),
        "operations_count": 1,
        "blocked_operations_count": len(missing),
        "unresolved_error_videos": len(missing),
        "fix_code_counts": {
            "removed_vetted_legacy_shelf_lines": shelf_count,
            "removed_one_retired_translation_appeal": 1,
        },
        "operations": [
            {
                "operation": "replace_video_description",
                "platform": "youtube",
                "ruleset": RULESET,
                "channel_id": LORD_GOD_CHANNEL,
                "video_id": video_id,
                "title": video.get("title"),
                "expected_revision": revision,
                "before_description": before,
                "after_description": after,
                "before_sha256": sha256_text(before),
                "after_sha256": sha256_text(after),
                "fixes": [
                    {"code": "removed_vetted_legacy_shelf_lines", "count": shelf_count},
                    {"code": "removed_one_retired_translation_appeal", "count": 1},
                ],
            }
        ],
        "unresolved": unresolved,
    }
    finalize_copy_plan(plan, checked_video_ids=[video_id, *missing])
    report = (
        "# Lord God: one-video retired translation solicitation and legacy shelves\n\n"
        f"Channel: {LORD_GOD_CHANNEL}\nVideo ID: {video_id}\n"
        f"Vetted shelf lines removed: {shelf_count}\n"
        "Retired self-promotion line removed: 1\n"
        f"Original description SHA: {sha256_text(before)}\n"
        f"After description SHA: {sha256_text(after)}\n"
        f"Plan SHA: {plan['plan_sha256']}\n\n"
        "Archived-source preparation ONLY. Fresh exact-ID, official owner OAuth preflight, "
        "unique backup/result and independent postflight are mandatory before any write. "
        "Never retry blindly after quotaExceeded or timeout.\n"
    )
    return plan, report
