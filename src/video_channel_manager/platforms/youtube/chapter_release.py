"""Execution-only safety gate for newly authored Lord God chapters.

Content hashes prove binding, not human identity or publication permission.
Old receipts remain readable; this gate is not an alternate writer.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from video_channel_manager.platforms.youtube.copy_plan import canonical_sha256, sha256_text
from video_channel_manager.platforms.youtube.lord_god_source_preservation import LORD_GOD_OWNER_CHANNEL

CHAPTER_RULESET = "lord-god-one-video-semantic-chapters-v2"
# Exact rejected effects from #795, 2026-11-23. Check the effect as well as
# the plan digest, so renaming/resealing the old plan does not restore authority.
RETIRED_EFFECTS = {
    "FgXzTeSj3ro": "sha256:9fbbdd9adef6f35394d2ff69595511417b4b6243bfce7b779e12d1d5f0e22a73",
    "LsaLPgYqBlM": "sha256:6889c2002d8259aacc547add4cdfc4c0a0cf0622244906eee01594c82eac6094",
    "rkz_7hE4F9E": "sha256:7ce9b410029ba08cb8182b8c375d35b14052d9a9ec3842b95d86c40c7ece82b0",
    "tSexgfSCgT8": "sha256:002bd079aa2711741e43507da5b530df477002a28dd269e396a82528bc432e73",
}
RETIRED_PLAN_SHA256 = frozenset(
    {
        "sha256:972399dea800ebe8b1ed86dfe66ae46123c4c009cc1f2aefed187881540ff217",
        "sha256:ff518a567946a39729d3191cdc06e1257361fd3c8ed79f4f05a6018a410189de",
        "sha256:90539173533cd9bcebb38f61876ee805e09469b175229f8d8db7440867c21601",
        "sha256:d95be6c76df18c4371861e2525fd86716c89cf17e928395e0c4ddc880a57f72e",
    }
)
_CHAPTER = re.compile(r"^\s*(?:(?:[-*•‣◦⁃>]|\d+[.)])\s+)?[*_]*\d{1,4}:\d{2}(?::\d{2})?[*_]*\s+\S")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")


def digest_file(path: Path) -> str:
    with path.open("rb") as stream:
        return "sha256:" + hashlib.file_digest(stream, "sha256").hexdigest()


def chapter_stamp(second: int) -> str:
    if type(second) is not int or second < 0:
        raise ValueError("Invalid absolute chapter seconds")
    if second >= 3600:
        return f"{second // 3600}:{second % 3600 // 60:02d}:{second % 60:02d}"
    return f"{second // 60:02d}:{second % 60:02d}"


def _chapter_lines(text: str) -> tuple[str, ...]:
    return tuple(line.strip() for line in text.splitlines() if _CHAPTER.match(line))


def render_chapter_appendix(chapters: Any) -> str:
    if not isinstance(chapters, list) or not 3 <= len(chapters) <= 40:
        raise ValueError("Chapter release requires three to forty approved chapters")
    lines = []
    previous = -10
    for i, entry in enumerate(chapters):
        if not isinstance(entry, dict):
            raise ValueError("Invalid chapter entry")
        second = entry.get("second")
        heading = entry.get("heading")
        if (
            type(second) is not int
            or (i == 0 and second != 0)
            or second - previous < 10
            or entry.get("stamp") != chapter_stamp(second)
            or not isinstance(heading, str)
            or not 5 <= len(heading.strip()) <= 90
            or "\n" in heading
            or "\r" in heading
            or entry.get("semantic_boundary") != "APPROVED"
        ):
            raise ValueError("Invalid or unapproved semantic chapter boundary")
        previous = second
        lines.append(f"{chapter_stamp(second)} {heading.strip()}")
    return "\n\nТаймкоды:\n" + "\n".join(lines)


def require_review(review: dict[str, Any], review_path: Path, *, video_id: str, before: str, after: str) -> None:
    """Require an explicit, byte-bound editorial attestation, not self-hash alone."""
    if json.loads(review_path.read_text(encoding="utf-8-sig")) != review:
        raise ValueError("Chapter review differs from exact reviewed file")
    if (
        review.get("schema") != "lordgod-chapter-editorial-review-v2"
        or review.get("owner_channel_id") != LORD_GOD_OWNER_CHANNEL
        or review.get("video_id") != video_id
        or review.get("editorial_approval") != "APPROVED"
        or review.get("is_executable_plan") is not False
        or review.get("provider_writes") != 0
        or review.get("requires_fresh_youtube_api_preflight") is not True
        or review.get("recording_player_review_required") is not True
        or review.get("source_description_sha256") != sha256_text(before)
        or review.get("proposed_description_sha256") != sha256_text(after)
        or after != before + render_chapter_appendix(review.get("chapters"))
        or len(after.encode("utf-8")) > 5000
    ):
        raise ValueError("Chapter review is not approved for the exact target and description")
    approval = review.get("semantic_review")
    if not isinstance(approval, dict):
        raise ValueError("Missing semantic editorial review")
    reviewer = approval.get("reviewer")
    reviewed_at = approval.get("reviewed_at")
    if (
        not isinstance(reviewer, str)
        or not reviewer.strip()
        or not isinstance(reviewed_at, str)
        or approval.get("basis") not in {"exact_ru_caption_boundaries", "exact_ru_audio_boundaries"}
        or approval.get("recording_video_id") != video_id
        or approval.get("chapters_sha256") != canonical_sha256(review["chapters"])
        or approval.get("description_sha256") != sha256_text(after)
        or type(approval.get("boundary_count")) is not int
        or approval["boundary_count"] != len(review["chapters"])
        or approval.get("all_boundaries_reviewed") is not True
    ):
        raise ValueError("Semantic approval is incomplete or has drifted")
    try:
        date = datetime.fromisoformat(reviewed_at)
    except ValueError as exc:
        raise ValueError("Invalid semantic review timestamp") from exc
    if date.utcoffset() is None:
        raise ValueError("Semantic review requires an offset-aware timestamp")
    evidence = approval.get("evidence_file")
    evidence_hash = approval.get("evidence_sha256")
    if (
        not isinstance(evidence, str)
        or not evidence.strip()
        or not isinstance(evidence_hash, str)
        or not _DIGEST.fullmatch(evidence_hash)
    ):
        raise ValueError("Semantic review requires exact recording/caption evidence bytes")
    path = Path(evidence)
    if not path.is_absolute():
        path = review_path.parent / path
    if not path.is_file() or digest_file(path) != evidence_hash:
        raise ValueError("Semantic evidence is missing or changed")
    events = None
    if approval["basis"] == "exact_ru_caption_boundaries":
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
            raise ValueError("Expected original Russian JSON3 caption events")
        events = payload["events"]
    for i, chapter in enumerate(review["chapters"]):
        boundary = chapter.get("boundary_evidence")
        if not isinstance(boundary, dict):
            raise ValueError("Every chapter requires a reviewed boundary locator")
        start_ms = boundary.get("start_ms")
        note = boundary.get("note")
        cue = boundary.get("cue")
        if (
            type(start_ms) is not int
            or start_ms < 0
            or (i == 0 and start_ms > 60_000)
            or (i > 0 and start_ms // 1000 != chapter["second"])
            or not isinstance(note, str)
            or not note.strip()
            or not isinstance(cue, str)
            or not cue.strip()
        ):
            raise ValueError("Chapter boundary locator does not match reviewed seconds")
        if events is not None:
            index = boundary.get("event_index")
            if type(index) is not int or not 0 <= index < len(events):
                raise ValueError("Caption boundary event is missing")
            event = events[index]
            if not isinstance(event, dict) or event.get("tStartMs") != start_ms:
                raise ValueError("Caption boundary event does not match reviewed milliseconds")
            segments = event.get("segs")
            if not isinstance(segments, list) or not all(isinstance(s, dict) for s in segments):
                raise ValueError("Invalid original caption segments")
            text = " ".join("".join(str(s.get("utf8", "")) for s in segments).split())
            if " ".join(cue.split()).casefold() not in text.casefold():
                raise ValueError("Caption boundary cue is not in the cited original event")


def require_chapter_release(plan: dict[str, Any], *, execute: bool, confirm_review_sha256: str = "") -> None:
    """Block stale chapter effects and generic planner bypass before OAuth/API."""
    if not execute or plan.get("target_channel_id") != LORD_GOD_OWNER_CHANNEL:
        return
    if plan.get("plan_sha256") in RETIRED_PLAN_SHA256:
        raise ValueError("SUPERSEDED_DO_NOT_REPLAY: retired chapter plan")
    for op in plan["operations"]:
        video_id = op["video_id"]
        before = op["before_description"]
        after = op["after_description"]
        if RETIRED_EFFECTS.get(video_id) == sha256_text(after):
            raise ValueError("SUPERSEDED_DO_NOT_REPLAY: retired chapter effect")
        if _chapter_lines(before) == _chapter_lines(after):
            continue
        if plan.get("ruleset") != CHAPTER_RULESET or op.get("ruleset") != CHAPTER_RULESET:
            raise ValueError("New or changed chapters require the approved semantic chapter ruleset v2")
        review_name = plan.get("source_chapter_review")
        review_hash = plan.get("source_chapter_review_sha256")
        if (
            not isinstance(review_name, str)
            or not review_name
            or not isinstance(review_hash, str)
            or not _DIGEST.fullmatch(review_hash)
            or confirm_review_sha256 != review_hash
        ):
            raise ValueError("Chapter execution requires independent --confirm-chapter-review-sha256")
        review_path = Path(review_name)
        if not review_path.is_absolute() or not review_path.is_file() or digest_file(review_path) != review_hash:
            raise ValueError("Approved chapter review file is missing or changed")
        review = json.loads(review_path.read_text(encoding="utf-8-sig"))
        if not isinstance(review, dict):
            raise ValueError("Invalid chapter review object")
        require_review(review, review_path, video_id=video_id, before=before, after=after)
