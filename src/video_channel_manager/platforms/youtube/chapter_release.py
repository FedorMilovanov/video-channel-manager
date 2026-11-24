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


PANORAMA_PLAYLIST = "PLu2Bhoh2caiVnr044VEc_MLE_8nGHcVmL"


def load_panorama_owner_evidence(
    owner_file: Path, playlist_file: Path, source_file: Path, *, video_id: str
) -> dict[str, Any]:
    """Validate the exact provider response plus immutable series/source identity.

    A receipt is historical evidence, never fresh write authority or a quota grant.
    """
    owner, playlist, sources = (
        json.loads(p.read_text(encoding="utf-8-sig")) for p in (owner_file, playlist_file, source_file)
    )
    if not all(isinstance(v, dict) for v in (owner, playlist, sources)):
        raise ValueError("Expected exact Panorama evidence objects")
    raw = owner.get("raw")
    if not isinstance(raw, dict):
        raise ValueError("Missing complete owner response")
    snippet, status, details, locales = (raw.get(k) for k in ("snippet", "status", "contentDetails", "localizations"))
    if (
        not isinstance(snippet, dict)
        or not isinstance(status, dict)
        or not isinstance(details, dict)
        or not isinstance(locales, dict)
    ):
        raise ValueError("Incomplete owner metadata/localization response")
    before = snippet.get("description")
    title = snippet.get("title")
    revision = canonical_sha256(raw)
    if (
        owner.get("schema") != "panorama-exact-owner-one-probe-v1"
        or owner.get("status") != "OWNER_READ_SUCCESS"
        or owner.get("read_only") is not True
        or owner.get("provider_writes") != 0
        or owner.get("api_read_operations") != 1
        or owner.get("video_id") != video_id
        or owner.get("owner_channel_id_expected") != LORD_GOD_OWNER_CHANNEL
        or owner.get("owner_channel_id") != LORD_GOD_OWNER_CHANNEL
        or raw.get("id") != video_id
        or snippet.get("channelId") != LORD_GOD_OWNER_CHANNEL
        or status.get("privacyStatus") != "public"
        or snippet.get("defaultLanguage") != "ru"
        or snippet.get("defaultAudioLanguage") != "ru"
        or not isinstance(snippet.get("tags"), list)
        or not all(isinstance(t, str) for t in snippet["tags"])
        or not isinstance(snippet.get("categoryId"), str)
        or not isinstance(title, str)
        or not title.strip()
        or owner.get("title") != title
        or not isinstance(before, str)
        or not before.strip()
        or _chapter_lines(before)
        or owner.get("description_sha256") != sha256_text(before)
        or owner.get("revision") != revision
        or owner.get("locale_keys") != sorted(locales)
        or not all(
            isinstance(v, dict) and isinstance(v.get("title"), str) and isinstance(v.get("description"), str)
            for v in locales.values()
        )
    ):
        raise ValueError("Exact owner receipt identity, revision, chapter state or metadata mismatch")
    duration = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", str(details.get("duration", "")))
    if not duration:
        raise ValueError("Missing exact provider duration")
    seconds = sum(int(v or 0) * m for v, m in zip(duration.groups(), (3600, 60, 1), strict=True))
    if seconds < 30:
        raise ValueError("Invalid provider duration")
    members = playlist.get("memberships")
    items = sources.get("items")
    if (
        playlist.get("schema") != "panorama-current-owner-playlist-v1"
        or playlist.get("playlist_id") != PANORAMA_PLAYLIST
        or playlist.get("owner_channel_id") != LORD_GOD_OWNER_CHANNEL
        or not isinstance(members, list)
        or len(members) != 68
        or not all(isinstance(m, dict) for m in members)
        or {m.get("position") for m in members} != set(range(68))
        or len({m.get("video_id") for m in members}) != 68
        or any(m.get("video_owner") != LORD_GOD_OWNER_CHANNEL for m in members)
        or sources.get("schema") != "panorama-68-exact-original-sources-verified-v1"
        or sources.get("catalogue") != "https://www.slovo.org/resursy/serii/panorama-biblii/"
        or not isinstance(items, list)
        or len(items) != 68
        or not all(isinstance(m, dict) for m in items)
        or {m.get("number") for m in items} != set(range(1, 69))
    ):
        raise ValueError("Frozen Panorama playlist/source register is incomplete or foreign")
    member = next((m for m in members if m.get("video_id") == video_id), None)
    if member is None or member.get("video_title") != title:
        raise ValueError("Video is absent from the frozen series or title changed")
    episode = member["position"] + 1
    source = next(m for m in items if m["number"] == episode)
    original = source.get("url")
    urls = set(re.findall(r"https?://[^\s<>\"'«»]+", before))
    if (
        source.get("ok") is not True
        or not isinstance(original, str)
        or not original.startswith("https://www.slovo.org/resursy/propovedi/")
        or original not in urls
        or f"https://www.youtube.com/playlist?list={PANORAMA_PLAYLIST}" not in urls
    ):
        raise ValueError("Exact primary source or series playlist is missing from the owner description")
    return {
        "description": before,
        "title": title,
        "revision": revision,
        "duration_seconds": seconds,
        "episode": episode,
        "original": original,
    }


def require_panorama_owner_evidence(plan: dict[str, Any], review: dict[str, Any]) -> None:
    if plan.get("source_scope") != "exact-panorama-owner-v1":
        raise ValueError("Expected exact Panorama owner scope")
    paths = []
    for name, digest in (
        ("source_owner_receipt", "source_audit_sha256"),
        ("source_playlist_receipt", "source_playlist_sha256"),
        ("source_original_register", "source_original_register_sha256"),
    ):
        value = plan.get(name)
        if not isinstance(value, str):
            raise ValueError("Missing exact owner/source artifact path")
        path = Path(value)
        if not path.is_absolute() or not path.is_file() or digest_file(path) != plan.get(digest):
            raise ValueError("Exact owner/source artifact missing or changed")
        paths.append(path)
    op = plan["operations"][0]
    proof = load_panorama_owner_evidence(*paths, video_id=op["video_id"])
    if (
        plan["checked_video_ids"] != [op["video_id"]]
        or len(plan["operations"]) != 1
        or plan["unresolved"]
        or op["before_description"] != proof["description"]
        or op["title"] != proof["title"]
        or op["expected_revision"] != proof["revision"]
        or review.get("original") != proof["original"]
        or review.get("episode") != proof["episode"]
        or review["chapters"][-1]["second"] > proof["duration_seconds"] - 10
    ):
        raise ValueError("Plan does not match the exact owner/source receipt")


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
        if plan.get("source_scope") == "exact-panorama-owner-v1":
            require_panorama_owner_evidence(plan, review)
