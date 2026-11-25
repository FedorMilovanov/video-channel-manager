"""Provider-impossible Milovi Cake Instagram transfer preview, issue #790.

This module never invokes Meta, uploads media, schedules jobs, or grants approval.
Its purpose is to fail closed until a project-bound account inventory and
individual clean-master/rights evidence can be reconciled by the canonical publisher.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

PROJECT_KEY = "milovi-cake"
YOUTUBE_CHANNEL_ID = "UCMDnxfGZiBqcDzgUV1zjFpw"
MOSCOW = ZoneInfo("Europe/Moscow")
MAX_CAPTION_LENGTH = 2200

COMMON_HOLDS = (
    "instagram_professional_account_unverified",
    "instagram_reels_inventory_unverified",
    "clean_master_and_media_qc_unverified",
    "media_and_audio_rights_unverified",
    "exact_youtube_media_cover_unverified",
    "provider_execution_not_authorized",
)


class MiloviInstagramPreviewError(ValueError):
    """Reject an incomplete or cross-project preview input."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise MiloviInstagramPreviewError(message)


def _source_ids(rows: list[dict[str, Any]], field: str, label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        _require(isinstance(row, dict), f"{label} row must be an object")
        source_id = row.get(field)
        if (
            not isinstance(source_id, str)
            or len(source_id) != 11
            or not all(c.isalnum() or c in "-_" for c in source_id)
        ):
            raise MiloviInstagramPreviewError(f"{label} has invalid YouTube source ID")
        _require(source_id not in result, f"{label} contains duplicate ID {source_id}")
        result[source_id] = row
    return result


def _read_json(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    try:
        document = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise MiloviInstagramPreviewError(f"invalid JSON: {path.name}") from exc
    _require(isinstance(document, dict), f"{path.name} must be an object")
    return document, "sha256:" + hashlib.sha256(raw).hexdigest()


def build_milovi_instagram_preview(
    *,
    source_inventory: Mapping[str, Any],
    youtube_metadata: Mapping[str, Any],
    captions: Mapping[str, Any],
    draft_slots: Mapping[str, Any],
    hold_registry: Mapping[str, Any],
    input_sha256: Mapping[str, str],
) -> dict[str, Any]:
    """Join five exact inputs; output only review candidates, never executable intent."""

    _require(source_inventory.get("schema") == "milovi-cake-instagram-source-review-v1", "unexpected source schema")
    _require(source_inventory.get("project_key") == PROJECT_KEY, "source project mismatch")
    _require(source_inventory.get("source_channel_id") == YOUTUBE_CHANNEL_ID, "source channel mismatch")
    _require(source_inventory.get("provider_writes_authorized") is False, "source writes must be disabled")
    _require(source_inventory.get("target_inventory_reconciled") is False, "cannot claim target inventory")
    _require(source_inventory.get("exact_instagram_account_id") is None, "unregistered account must remain absent")
    _require(youtube_metadata.get("project_key") == PROJECT_KEY, "metadata project mismatch")
    _require(youtube_metadata.get("channel_expected") == YOUTUBE_CHANNEL_ID, "metadata channel mismatch")
    _require(youtube_metadata.get("provider_mutations") == 0, "metadata must be read-only")
    _require(captions.get("project_key") == PROJECT_KEY, "caption project mismatch")
    _require(captions.get("approved_for_publication") is False, "captions cannot be approved")
    _require(captions.get("instagram_account_id") is None, "caption account binding not verified")
    _require(draft_slots.get("project_key") == PROJECT_KEY, "slots project mismatch")
    _require(draft_slots.get("provider_writes_authorized") is False, "slots must be provider-inert")
    _require(hold_registry.get("project_key") == PROJECT_KEY, "stoplist project mismatch")
    _require(hold_registry.get("schema") == "milovi-cake-instagram-scope-holds-v1", "stoplist schema mismatch")
    _require(hold_registry.get("provider_writes_authorized") is False, "stoplist must be provider-inert")

    sources = _source_ids(list(source_inventory.get("rows") or []), "youtube_video_id", "source inventory")
    metadata = _source_ids(list(youtube_metadata.get("results") or []), "id", "YouTube metadata")
    edited = _source_ids(list(captions.get("entries") or []), "youtube_video_id", "captions")
    slots_raw = list(draft_slots.get("slots") or [])
    slots = _source_ids(slots_raw, "youtube_video_id", "draft slots")
    _require(len(sources) == source_inventory.get("source_count"), "source_count mismatch")
    _require(len(edited) == captions.get("caption_count"), "caption_count mismatch")
    _require(bool(slots), "empty draft slots")
    _require(set(slots) == set(metadata) == set(edited), "slots, metadata and captions have different source IDs")

    flags = _source_ids(list(hold_registry.get("entries") or []), "youtube_video_id", "stoplist")
    _require(set(flags) <= set(sources), "stoplist contains unknown source ID")
    _require(len(flags) == hold_registry.get("entry_count"), "stoplist count mismatch")
    _require(
        all(f.get("status") in ("scope_excluded", "manual_review") for f in flags.values()), "invalid stoplist status"
    )

    rows: list[dict[str, Any]] = []
    previous_slot: datetime | None = None
    for slot in slots_raw:
        source_id = slot["youtube_video_id"]
        src = sources[source_id]
        meta = metadata[source_id]
        caption = edited[source_id]
        _require(src.get("project_key") == PROJECT_KEY, f"{source_id}: source row project mismatch")
        _require(src.get("source_channel_id") == YOUTUBE_CHANNEL_ID, f"{source_id}: source row channel mismatch")
        _require(src.get("publish_authorized") is False, f"{source_id}: source row cannot be approved")
        _require(src.get("instagram_presence") == "UNVERIFIED", f"{source_id}: Instagram presence not reconciled")
        _require(meta.get("status") == "READ_OK", f"{source_id}: source metadata unavailable")
        _require(meta.get("channel_id") == YOUTUBE_CHANNEL_ID, f"{source_id}: YouTube channel mismatch")
        _require(meta.get("availability") == "public", f"{source_id}: source is not public")
        duration = meta.get("duration_seconds")
        _require(isinstance(duration, int | float) and 3 <= duration <= 180, f"{source_id}: invalid Shorts duration")
        _require(slot.get("slot_status") == "DRAFT_NOT_ARMED", f"{source_id}: armed schedule not accepted")
        _require(slot.get("provider_writes_authorized") is False, f"{source_id}: slot writes not disabled")
        _require(slot.get("target_instagram_presence") == "UNVERIFIED", f"{source_id}: target state unverified")
        _require(caption.get("approved") is False, f"{source_id}: captions cannot be approved")
        _require(caption.get("duplicate_check") == "unverified", f"{source_id}: cannot claim Instagram absence")
        _require(caption.get("source_video_rights") == "unverified", f"{source_id}: rights not verified")
        text = caption.get("caption")
        if not isinstance(text, str) or not (0 < len(text) <= MAX_CAPTION_LENGTH):
            raise MiloviInstagramPreviewError(f"{source_id}: bad caption")
        _require(text.count("#") <= 5, f"{source_id}: more than five hashtags")
        try:
            when = datetime.fromisoformat(slot["slot_local"])
        except (TypeError, ValueError) as exc:
            raise MiloviInstagramPreviewError(f"{source_id}: invalid slot timestamp") from exc
        _require(when.tzinfo is None, f"{source_id}: slot must use local clock without offset")
        _require(
            when.weekday() in (1, 3, 5) and (when.hour, when.minute, when.second) == (19, 0, 0),
            f"{source_id}: only Tue/Thu/Sat 19:00 Moscow slots allowed",
        )
        aware = when.replace(tzinfo=MOSCOW)
        _require(
            previous_slot is None or (aware - previous_slot).total_seconds() >= 2 * 86400,
            f"{source_id}: slots must be ordered and at least 48h apart",
        )
        previous_slot = aware

        source_flags = flags.get(source_id, {})
        holds = list(COMMON_HOLDS)
        if source_flags:
            holds.append(source_flags["status"])
        if src.get("historical_vk_transfer_gate") in ("IP_HOLD_DO_NOT_TRANSFER", "TRADEMARK_REVIEW_REQUIRED"):
            holds.append("historical_vk_ip_or_brand_review")
        rows.append(
            {
                "source_key": f"milovi-cake-yt-{source_id}-reel-v1",
                "youtube_video_id": source_id,
                "youtube_channel_id": YOUTUBE_CHANNEL_ID,
                "source_title": meta["title"],
                "source_url": f"https://www.youtube.com/shorts/{source_id}",
                "duration_seconds": duration,
                "proposal_local": slot["slot_local"],
                "proposal_timezone": "Europe/Moscow",
                "status": "hold",
                "scheduled": False,
                "instagram_presence": "unverified",
                "instagram_media_id": None,
                "media_sha256": None,
                "cover_sha256": None,
                "caption_sha256": "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "caption": text,
                "hold_reasons": holds,
                "provider_writes_authorized": False,
            }
        )
    result = {
        "schema": "milovi-cake-instagram-staggered-preview-v1",
        "project_key": PROJECT_KEY,
        "youtube_channel_id": YOUTUBE_CHANNEL_ID,
        "instagram_account_id": None,
        "status": "provider-inert",
        "provider_writes_authorized": False,
        "provider_effect": "impossible",
        "schedule_armed": False,
        "confirmed_missing_in_instagram": 0,
        "publish_ready_count": 0,
        "candidate_count": len(rows),
        "scope_hold_count": sum(bool(flags.get(row["youtube_video_id"])) for row in rows),
        "input_sha256": dict(sorted(input_sha256.items())),
        "rows": rows,
    }
    return result


def preview_from_files(
    *, inventory: Path, metadata: Path, captions: Path, slots: Path, stoplist: Path
) -> dict[str, Any]:
    paths = {"inventory": inventory, "metadata": metadata, "captions": captions, "slots": slots, "stoplist": stoplist}
    parsed = {key: _read_json(path) for key, path in paths.items()}
    return build_milovi_instagram_preview(
        source_inventory=parsed["inventory"][0],
        youtube_metadata=parsed["metadata"][0],
        captions=parsed["captions"][0],
        draft_slots=parsed["slots"][0],
        hold_registry=parsed["stoplist"][0],
        input_sha256={key: value[1] for key, value in parsed.items()},
    )
