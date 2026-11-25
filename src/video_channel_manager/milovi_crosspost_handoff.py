"""Provider-inert, exact-media Milovi Cake multi-platform transfer handoff.

This does NOT schedule or publish anything. The existing platform writers and
their independent provider receipts remain the sole source of truth.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

SOURCE_CHANNEL_ID = "UCMDnxfGZiBqcDzgUV1zjFpw"
IG_ACCOUNT_ID = "17841407843933779"
VK_COMMUNITY_ID = 68859909
TG_CHAT_ID = -1002215328390
FROZEN_INDEX_SHA256 = "19a211320f32e3c0f16c0aad1ed23db4b2bd89f100bbd22b8d1b801734aba5a4"

# These are workflow *boundaries*, never fictional remote publication statuses.
ROUTES: tuple[tuple[str, str, str], ...] = (
    ("youtube", "already_source", "Existing owner YouTube Short; do not upload again"),
    ("instagram", "existing_single_writer", "Only installed MILOVI-CAKE-Instagram-Reels may dispatch"),
    ("vk_clips", "hold_creator_reconciliation", "Check native Creator clips, all states, exact existing IDs"),
    ("telegram", "hold_fresh_release", "Requires fresh reviewed release, state ledger and send authority"),
    ("rutube", "hold_account_access", "Requires verified Milovi Rutube Studio or partner API access"),
    ("threads", "hold_oauth_https", "Requires exact Threads OAuth and approved public HTTPS video source"),
)


class HandoffError(ValueError):
    """Unsafe or inconsistent source binding."""


def _digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise HandoffError(f"Expected JSON object: {path.name}")
    return value


def build_handoff(
    index_path: Path,
    *,
    start_date: date,
    end_date: date,
    expected_index_sha256: str = FROZEN_INDEX_SHA256,
) -> dict[str, Any]:
    """Produce 6-route per-source operator handoff; no provider access or writes."""
    if start_date > end_date:
        raise HandoffError("Reversed requested date range")
    if not re.fullmatch(r"[a-f0-9]{64}", expected_index_sha256):
        raise HandoffError("Expected index digest must be SHA-256")
    if _digest_file(index_path) != expected_index_sha256:
        raise HandoffError("Frozen index SHA-256 differs; fail closed")
    index = _load_json(index_path)
    if (
        index.get("project_key") != "milovi-cake"
        or index.get("target_instagram_id") != IG_ACCOUNT_ID
        or index.get("meta_app_id") != "989716813600695"
    ):
        raise HandoffError("Index project/target/app mismatch")
    rows = index.get("rows")
    if not isinstance(rows, list) or not rows:
        raise HandoffError("Frozen index has no source rows")

    seen: set[str] = set()
    selected: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise HandoffError("Non-object source row")
        source_id = row.get("youtube_id")
        if not isinstance(source_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{11}", source_id):
            raise HandoffError("Invalid YouTube source identity")
        if source_id in seen:
            raise HandoffError(f"Duplicate source in frozen index: {source_id}")
        seen.add(source_id)
        slot = row.get("proposed_moscow_slot")
        if not isinstance(slot, str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT19:00:00", slot):
            raise HandoffError(f"Invalid exact Moscow slot for {source_id}")
        source_day = date.fromisoformat(slot[:10])
        if not (start_date <= source_day <= end_date):
            continue
        folder = Path(str(row["folder"]))
        video = folder / "ORIGINAL-MUSIC-REEL.mp4"
        manifest_path = folder / "exact-local-publish-manifest.json"
        approval_path = folder / "OWNER_DIRECTED_RISK_ACCEPTED.json"
        if _digest_file(manifest_path) != row.get("manifest_sha256"):
            raise HandoffError(f"Manifest digest mismatch: {source_id}")
        manifest = _load_json(manifest_path)
        ack = _load_json(approval_path)
        media_digest = _digest_file(video)
        if (
            manifest.get("publication_key") != row.get("publication_key")
            or manifest.get("account_id") != IG_ACCOUNT_ID
            or manifest.get("media_sha256") != f"sha256:{media_digest}"
            or media_digest != row.get("media_sha256")
            or manifest.get("media_size_bytes") != video.stat().st_size
        ):
            raise HandoffError(f"MP4/Instagram manifest mismatch: {source_id}")
        caption = manifest.get("caption")
        if not isinstance(caption, str) or (
            hashlib.sha256(caption.encode("utf-8")).hexdigest() != row.get("caption_sha256")
        ):
            raise HandoffError(f"Caption digest mismatch: {source_id}")
        if (
            ack.get("project_key") != "milovi-cake"
            or ack.get("instagram_id") != IG_ACCOUNT_ID
            or ack.get("publication_key") != row.get("publication_key")
            or ack.get("media_sha256") != manifest.get("media_sha256")
            or ack.get("owner_directed_repost") is not True
        ):
            raise HandoffError(f"Owner acknowledgement mismatch: {source_id}")
        routes = [
            {
                "platform": name,
                "logical_key": f"milovi-cake.{name}.yt-{source_id}.original-audio-v1",
                "state": state,
                "explanation": reason,
                "may_dispatch": False,
                "provider_receipt_verified": False,
            }
            for name, state, reason in ROUTES
        ]
        selected.append(
            {
                "youtube_id": source_id,
                "youtube_channel_id": SOURCE_CHANNEL_ID,
                "youtube_source_url": f"https://www.youtube.com/shorts/{source_id}",
                "title": row["title"],
                "candidate_moscow_slot": slot,
                "file": str(video),
                "file_sha256": media_digest,
                "file_bytes": video.stat().st_size,
                "caption": caption,
                "caption_sha256": row["caption_sha256"],
                "instagram_publication_key": row["publication_key"],
                "rights_independently_verified": bool(row.get("rights_verified")),
                "music_license_independently_verified": bool(ack.get("soundtrack_license_independently_verified")),
                "destinations": routes,
            }
        )

    selected.sort(key=lambda r: (r["candidate_moscow_slot"], r["youtube_id"]))
    return {
        "schema": "video-manager.milovi-crosspost-handoff-v1",
        "project_key": "milovi-cake",
        "source_index_sha256": expected_index_sha256,
        "window_start": start_date.isoformat(),
        "window_end": end_date.isoformat(),
        "timezone": "Europe/Moscow",
        "source_channel_id": SOURCE_CHANNEL_ID,
        "instagram_account_id": IG_ACCOUNT_ID,
        "vk_community_id": VK_COMMUNITY_ID,
        "telegram_chat_id": TG_CHAT_ID,
        "source_count": len(selected),
        "destination_count": len(selected) * len(ROUTES),
        "provider_access_performed": False,
        "provider_writes_performed": False,
        "new_schedules_armed": False,
        "candidates": selected,
    }
