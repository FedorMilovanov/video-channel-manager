from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from video_channel_manager.editorial.milovi_instagram_transfer_preview import (
    MiloviInstagramPreviewError,
    build_milovi_instagram_preview,
)

CHANNEL = "UCMDnxfGZiBqcDzgUV1zjFpw"
ID = "d48QLgOuiTs"
OTHER = "4PAEjymOOFs"


def make_inputs() -> dict:
    source = {
        "schema": "milovi-cake-instagram-source-review-v1",
        "project_key": "milovi-cake",
        "source_channel_id": CHANNEL,
        "provider_writes_authorized": False,
        "target_inventory_reconciled": False,
        "exact_instagram_account_id": None,
        "source_count": 2,
        "rows": [
            {
                "project_key": "milovi-cake",
                "youtube_video_id": i,
                "source_channel_id": CHANNEL,
                "publish_authorized": False,
                "instagram_presence": "UNVERIFIED",
                "historical_vk_transfer_gate": "MEDIA_RECONCILIATION_REQUIRED",
            }
            for i in (ID, OTHER)
        ],
    }
    metadata = {
        "project_key": "milovi-cake",
        "channel_expected": CHANNEL,
        "provider_mutations": 0,
        "results": [
            {
                "id": i,
                "status": "READ_OK",
                "channel_id": CHANNEL,
                "availability": "public",
                "title": "Торт на заказ",
                "duration_seconds": 35,
            }
            for i in (ID, OTHER)
        ],
    }
    captions = {
        "project_key": "milovi-cake",
        "approved_for_publication": False,
        "instagram_account_id": None,
        "caption_count": 2,
        "entries": [
            {
                "youtube_video_id": i,
                "caption": f"Торт от Milovi Cake #{i}",
                "approved": False,
                "duplicate_check": "unverified",
                "source_video_rights": "unverified",
            }
            for i in (ID, OTHER)
        ],
    }
    draft_slots = {
        "project_key": "milovi-cake",
        "provider_writes_authorized": False,
        "slots": [
            {
                "youtube_video_id": ID,
                "slot_local": "2026-11-10T19:00:00",
                "slot_status": "DRAFT_NOT_ARMED",
                "provider_writes_authorized": False,
                "target_instagram_presence": "UNVERIFIED",
            },
            {
                "youtube_video_id": OTHER,
                "slot_local": "2026-11-12T19:00:00",
                "slot_status": "DRAFT_NOT_ARMED",
                "provider_writes_authorized": False,
                "target_instagram_presence": "UNVERIFIED",
            },
        ],
    }
    holds = {
        "schema": "milovi-cake-instagram-scope-holds-v1",
        "project_key": "milovi-cake",
        "provider_writes_authorized": False,
        "entry_count": 1,
        "entries": [{"youtube_video_id": OTHER, "status": "manual_review", "reason": "character_flag"}],
    }
    return {
        "source_inventory": source,
        "youtube_metadata": metadata,
        "captions": captions,
        "draft_slots": draft_slots,
        "hold_registry": holds,
        "input_sha256": {"source": "sha256:" + sha256(b"source").hexdigest()},
    }


def build(inputs: dict) -> dict:
    return build_milovi_instagram_preview(**inputs)


def test_two_slots_provider_impossible_and_stable() -> None:
    inputs = make_inputs()
    result = build(inputs)
    assert result == build(deepcopy(inputs))
    assert result["project_key"] == "milovi-cake"
    assert result["status"] == "provider-inert"
    assert result["provider_effect"] == "impossible"
    assert result["provider_writes_authorized"] is False
    assert result["schedule_armed"] is False
    assert result["candidate_count"] == 2
    assert result["publish_ready_count"] == 0
    assert result["scope_hold_count"] == 1
    assert all(row["status"] == "hold" and not row["scheduled"] for row in result["rows"])
    assert result["rows"][0]["source_key"] == "milovi-cake-yt-d48QLgOuiTs-reel-v1"
    assert "manual_review" in result["rows"][1]["hold_reasons"]
    assert result["rows"][0]["caption_sha256"].startswith("sha256:")
    assert all(row["instagram_media_id"] is None for row in result["rows"])


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("source_inventory", "project_key"), "legendary-poet"),
        (("youtube_metadata", "channel_expected"), "UC-78ys2S3cQ3lpqgXfo-SvQ"),
        (("source_inventory", "exact_instagram_account_id"), "17841435926122104"),
        (("source_inventory", "target_inventory_reconciled"), True),
        (("source_inventory", "provider_writes_authorized"), True),
        (("draft_slots", "provider_writes_authorized"), True),
        (("captions", "approved_for_publication"), True),
        (("hold_registry", "provider_writes_authorized"), True),
        (("draft_slots", "slots", 0, "slot_status"), "ARMED"),
        (("draft_slots", "slots", 0, "slot_local"), "2026-11-11T19:00:00"),
        (("draft_slots", "slots", 1, "slot_local"), "2026-11-10T19:00:00"),
        (("youtube_metadata", "results", 0, "channel_id"), "WRONG_CHANNEL"),
        (("youtube_metadata", "results", 0, "status"), "PROBE_FAILED"),
        (("captions", "entries", 0, "approved"), True),
        (("captions", "entries", 0, "duplicate_check"), "absent"),
        (("captions", "entries", 0, "source_video_rights"), "cleared"),
    ],
)
def test_unverified_or_cross_project_input_is_refused(path: tuple, value: object) -> None:
    data = make_inputs()
    cursor = data
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = value
    with pytest.raises(MiloviInstagramPreviewError):
        build(data)


def test_duplicate_sources_or_missing_metadata_rejected() -> None:
    data = make_inputs()
    data["youtube_metadata"]["results"].append(deepcopy(data["youtube_metadata"]["results"][0]))
    with pytest.raises(MiloviInstagramPreviewError, match="duplicate"):
        build(data)
    data = make_inputs()
    data["youtube_metadata"]["results"].pop()
    with pytest.raises(MiloviInstagramPreviewError, match="different source IDs"):
        build(data)


def test_hold_registry_must_use_known_source_and_valid_status() -> None:
    data = make_inputs()
    data["hold_registry"]["entries"][0]["youtube_video_id"] = "UnknownID01"
    with pytest.raises(MiloviInstagramPreviewError, match="unknown source"):
        build(data)
    data = make_inputs()
    data["hold_registry"]["entries"][0]["status"] = "approved"
    with pytest.raises(MiloviInstagramPreviewError, match="stoplist status"):
        build(data)


def test_repository_review_registry_contains_provisional_holds_only() -> None:
    path = Path(__file__).resolve().parents[1] / "content" / "instagram" / "milovi-cake-scope-holds-v1.json"
    registry = json.loads(path.read_text(encoding="utf-8"))
    assert registry["project_key"] == "milovi-cake"
    assert registry["youtube_channel_id"] == CHANNEL
    assert registry["provider_writes_authorized"] is False
    assert registry["entry_count"] == len(registry["entries"]) == 26
    assert sum(r["status"] == "scope_excluded" for r in registry["entries"]) == 7
    assert sum(r["status"] == "manual_review" for r in registry["entries"]) == 19
    assert len({r["youtube_video_id"] for r in registry["entries"]}) == 26
    assert not {ID, OTHER} & {r["youtube_video_id"] for r in registry["entries"]}
