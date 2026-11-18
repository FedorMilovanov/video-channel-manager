"""Milovi Cake source-to-VK provider-inert evidence reconciliation.

Historical mappings are not current provider absence. This module never grants
an upload, native-Clip scheduling or VK wall-post operation.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from video_channel_manager.platforms.vk.milovi_final_review_queue import (
    ACCEPTED_GAP_ZIP_SHA256,
    ACCEPTED_SEQUENCE_ZIP_SHA256,
    _MANUAL_ADJUDICATIONS,
)

YOUTUBE_CHANNEL = "UCMDnxfGZiBqcDzgUV1zjFpw"
VK_OWNER = -68859909
VK_COMMUNITY = 68859909
STRONG = frozenset(
    {
        "VERIFIED_NATIVE_SEQUENCE",
        "VERIFIED_NATIVE_INDEPENDENT_1HZ",
        "VERIFIED_OLDER_60",
        "VERIFIED_NATIVE_FALLBACK",
        "VERIFIED_VK_ORDINARY",
    }
)
OPEN = frozenset(
    {
        "NOT_YET_PROVEN_PRESENT_REVIEW_UPLOAD",
        "WEAK_VIDEO_MATCH_INSPECT_EDIT",
        "LIKELY_EDIT_OR_LENGTH_MISMATCH_DO_NOT_UPLOAD",
    }
)
SOURCE_ID = re.compile(r"^[a-zA-Z0-9_-]{11}$")


class MiloviReviewEvidenceError(ValueError):
    """Refuse derived conclusions from wrong-owner, stale or contradictory evidence."""


def _items(payload: dict[str, Any], name: str) -> list[dict[str, Any]]:
    rows = payload.get(name)
    if not isinstance(rows, list) or any(not isinstance(x, dict) for x in rows):
        raise MiloviReviewEvidenceError(f"{name}: expected list of records")
    return rows


def _unique(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = row.get(key)
        if not isinstance(value, str) or not SOURCE_ID.fullmatch(value) or value in result:
            raise MiloviReviewEvidenceError(f"Invalid or duplicate {key}: {value!r}")
        result[value] = row
    return result


def build_source_review(
    *,
    youtube_owner: dict[str, Any],
    crosswalk: dict[str, Any],
    rights_terminal: dict[str, Any],
    accepted_manual: dict[str, Any],
    independent_visual: dict[str, Any],
    public_wall: dict[str, Any],
    additional_visual: dict[str, Any],
) -> dict[str, Any]:
    """Classify source IDs; NEVER issue a provider-write authorization.

    The public wall is evidence of presence, not a complete VK inventory.
    Absence cannot be established without owner-visible native/ordinary video,
    draft, scheduled, private and processing surfaces.
    """
    videos = _items(youtube_owner, "videos")
    indexed: dict[str, dict[str, Any]] = {}
    for video in videos:
        ref = video.get("ref") or {}
        if ref.get("channel_id") != YOUTUBE_CHANNEL:
            raise MiloviReviewEvidenceError("YouTube owner video channel mismatch")
        vid = ref.get("remote_id")
        if not isinstance(vid, str) or not SOURCE_ID.fullmatch(vid) or vid in indexed:
            raise MiloviReviewEvidenceError(f"Duplicate or invalid YouTube ID: {vid!r}")
        indexed[vid] = video
    if not indexed or not youtube_owner.get("generated_at"):
        raise MiloviReviewEvidenceError("Missing full YouTube owner scan")
    channel = youtube_owner.get("channel") or {}
    if (channel.get("ref") or {}).get("remote_id") != YOUTUBE_CHANNEL:
        raise MiloviReviewEvidenceError("Wrong YouTube owner channel")

    if (
        rights_terminal.get("owner_id") != VK_OWNER
        or rights_terminal.get("all_removed_ids_authoritatively_absent") is not True
    ):
        raise MiloviReviewEvidenceError("No exact VK owner rights deletion terminal")
    deleted_clips = set(rights_terminal.get("removed_native_ids") or [])
    deleted_posts = set(rights_terminal.get("removed_wall_posts") or [])
    if not deleted_clips or not deleted_posts or not all(type(x) is int for x in deleted_clips | deleted_posts):
        raise MiloviReviewEvidenceError("Missing authoritative rights tombstones")

    if (public_wall.get("community_id"), public_wall.get("owner_id")) != (VK_COMMUNITY, VK_OWNER) or public_wall.get(
        "public_wall_complete"
    ) is not True:
        raise MiloviReviewEvidenceError("Wrong or incomplete published VK wall")
    wall_map = public_wall.get("all_video_to_post_ids")
    if not isinstance(wall_map, dict) or not public_wall.get("captured_at_utc"):
        raise MiloviReviewEvidenceError("Public wall attachment evidence missing")
    if public_wall.get("duplicate_video_attachments_across_posts"):
        raise MiloviReviewEvidenceError("Duplicate exact VK attachments require review")

    def exact_published(vk_id: int) -> bool:
        posts = wall_map.get(f"{VK_OWNER}_{vk_id}", [])
        return type(vk_id) is int and isinstance(posts, list) and len(posts) == 1 and all(type(n) is int for n in posts)

    accepted_evidence = accepted_manual.get("input_evidence") or {}
    if (
        accepted_manual.get("project_key"),
        accepted_manual.get("youtube_channel_id"),
        accepted_manual.get("owner_id"),
    ) != ("milovi-cake", YOUTUBE_CHANNEL, VK_OWNER):
        raise MiloviReviewEvidenceError("Accepted manual adjudication identity mismatch")
    if (
        accepted_evidence.get("gap_zip_sha256") != ACCEPTED_GAP_ZIP_SHA256
        or accepted_evidence.get("sequence_zip_sha256") != ACCEPTED_SEQUENCE_ZIP_SHA256
    ):
        raise MiloviReviewEvidenceError("Manual frame adjudication is not the accepted ZIP pair")
    manual_pairs: dict[str, int] = {}
    for pair in _items(accepted_manual, "reviewed_sequence_pairs"):
        if pair.get("manual_decision") != "EXISTING_NATIVE_REPRESENTATION_OBSERVED":
            continue
        ref = pair.get("vk_remote_id")
        yid = pair.get("youtube_id")
        if not isinstance(ref, str) or not ref.startswith(f"{VK_OWNER}_") or not isinstance(yid, str):
            raise MiloviReviewEvidenceError("Manual pair malformed")
        vk_id = int(ref.partition("_")[2])
        spec = _MANUAL_ADJUDICATIONS.get(yid)
        if spec is None or spec["vk_remote_id"] != ref or spec["decision"] != pair["manual_decision"]:
            raise MiloviReviewEvidenceError("Manual pair is outside accepted reviewed scope")
        if pair.get("manual_confidence") != "high" or pair.get("upload_authorized") is not False:
            raise MiloviReviewEvidenceError("Manual matching confidence/write gate missing")
        if not exact_published(vk_id):
            raise MiloviReviewEvidenceError(f"Manual match {yid} not on fresh public wall")
        manual_pairs[yid] = vk_id

    probable_source_ids = {
        r["youtube_id"] for r in _items(crosswalk, "items") if r.get("scope") == "PROBABLE_PRESENT_DO_NOT_UPLOAD"
    }
    visual_pairs: dict[str, int] = {}
    for row in _items(independent_visual, "items"):
        if row.get("visual_verdict") != "MATCHING_SAME_VIDEO_CONTENT_AT_SIX_TIME_ALIGNED_MOMENTS":
            continue
        yid, vk_id = row.get("youtube_id"), row.get("vk_clip_id")
        if yid not in probable_source_ids:
            continue
        if not isinstance(yid, str) or not exact_published(vk_id):
            raise MiloviReviewEvidenceError("Six-frame pair not confirmed by fresh public wall")
        visual_pairs[yid] = vk_id

    extra = additional_visual.get("newly_high_confidence_present_short") or {}
    extra_yid = extra.get("youtube_id")
    extra_vk_id = extra.get("vk_best_match")
    if (
        extra_yid != "SiluLt5Bz1c"
        or extra_vk_id != 456239096
        or extra.get("vk_near_identical_existing_variant") != 456239082
        or extra.get("vk_1hz_same_position_dhash_distance_at_most_8_count", 0) < 21
        or extra.get("frame_pairs") != 30
        or not exact_published(extra_vk_id)
        or not exact_published(456239082)
    ):
        raise MiloviReviewEvidenceError("Extra timed-video proof missing, altered or not on live wall")
    extra_pairs = {extra_yid: extra_vk_id}

    if crosswalk.get("youtube_total") != len(_items(crosswalk, "items")) or crosswalk.get("youtube_total") != len(
        crosswalk["items"]
    ):
        raise MiloviReviewEvidenceError("Crosswalk cardinality invalid")
    entries = _unique(crosswalk["items"], "youtube_id")
    if not set(entries) <= set(indexed):
        raise MiloviReviewEvidenceError("Historical sources absent from current owner API")
    statuses: dict[str, dict[str, Any]] = {}
    for yid, row in entries.items():
        privacy = indexed[yid].get("privacy_status")
        scope = row.get("scope")
        vk_id = row.get("vk_id")
        state = "REVIEW_ONLY_NO_VK_OWNER_ABSENCE"
        identified_vk_id = None
        if vk_id in deleted_clips:
            state = "RETIRED_RIGHTS_NEVER_RESTORE"
        elif scope == "EXCLUDE_NAMED_CHARACTER_RIGHTS":
            state = "EXCLUDED_RIGHTS"
        elif scope == "EXCLUDE_NOT_CONFECTIONERY":
            state = "EXCLUDED_OFF_TOPIC"
        elif privacy != "public":
            state = "PRIVATE_OR_UNLISTED_HOLD"
        elif scope in STRONG:
            state = "HISTORICAL_VK_PRESENCE_PROTECT"
            identified_vk_id = vk_id
        elif yid in manual_pairs:
            state = "MANUAL_VK_PRESENCE_PROTECT"
            identified_vk_id = manual_pairs[yid]
        elif yid in visual_pairs:
            state = "SIXFRAME_VK_PRESENCE_PROTECT"
            identified_vk_id = visual_pairs[yid]
        elif yid in extra_pairs:
            state = "TIMED_VK_PRESENCE_PROTECT"
            identified_vk_id = extra_pairs[yid]
        elif scope not in OPEN:
            raise MiloviReviewEvidenceError(f"Unknown historical source scope: {scope!r}")
        statuses[yid] = {
            "youtube_id": yid,
            "privacy": privacy,
            "state": state,
            "verified_vk_video_id_if_known": identified_vk_id,
            "vk_current_complete_absence_proven": False,
            "upload_authorized": False,
            "postponed_create_authorized": False,
        }
    for yid in {**manual_pairs, **visual_pairs, **extra_pairs}:
        if yid not in statuses or statuses[yid]["state"] == "RETIRED_RIGHTS_NEVER_RESTORE":
            raise MiloviReviewEvidenceError(f"Invalid cross-source presence evidence for {yid}")
        if yid in extra_pairs and statuses[yid]["state"] != "TIMED_VK_PRESENCE_PROTECT":
            raise MiloviReviewEvidenceError("Extra match collides with higher authority status")

    counters = Counter(row["state"] for row in statuses.values())
    return {
        "schema": "milovi-source-gap-readonly-guard-v1",
        "project_key": "milovi-cake",
        "youtube_channel_id": YOUTUBE_CHANNEL,
        "vk_owner_id": VK_OWNER,
        "vk_community_id": VK_COMMUNITY,
        "youtube_owner_total": len(indexed),
        "historical_youtube_rows": len(statuses),
        "category_counts": dict(sorted(counters.items())),
        "sources": [statuses[k] for k in sorted(statuses)],
        "current_owner_vk_native_regular_private_processing_and_postponed_complete": False,
        "verified_missing_source_ids": [],
        "transfer_queue_created": False,
        "provider_writes": 0,
        "upload_authorized": False,
        "postponed_create_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only, rights-aware Milovi source gap gate")
    for name in (
        "youtube-owner",
        "crosswalk",
        "rights-terminal",
        "accepted-manual",
        "independent-visual",
        "public-wall",
        "additional-visual",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    paths = {
        name.replace("-", "_"): getattr(args, name.replace("-", "_"))
        for name in (
            "youtube-owner",
            "crosswalk",
            "rights-terminal",
            "accepted-manual",
            "independent-visual",
            "public-wall",
            "additional-visual",
        )
    }
    try:
        data = {key: json.loads(path.read_text(encoding="utf8")) for key, path in paths.items()}
        report = build_source_review(**data)
        if args.output.exists():
            raise MiloviReviewEvidenceError("Refusing to overwrite existing review evidence")
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
        print(
            json.dumps(
                {"output": str(args.output.resolve()), "categories": report["category_counts"], "provider_writes": 0}
            )
        )
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc), "provider_writes": 0}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
