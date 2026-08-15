from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

import video_channel_manager.platforms.vk.milovi_issue323_live_resume as resume
from video_channel_manager.platforms.vk.milovi_rollout_sources import ROLL_OUT_IDS
from video_channel_manager.platforms.vk.wall_safety import build_wall_snapshot

OWNER_ID = -68859909
SOURCE9 = ROLL_OUT_IDS[8]
PUBLISH_DATES = [
    1786723200,
    1786809600,
    1786896000,
    1786982400,
    1787068800,
    1787155200,
    1787241600,
    1787328000,
]
WALL_IDS = [468, 469, 470, 471, 472, 473, 474, 477]
CLIP_IDS = [456239225, 456239226, 456239227, 456239228, 456239229, 456239230, 456239231, 456239232]
SUCCESSOR_ID = 476
CAPTURE_EPOCH = PUBLISH_DATES[0] + 3 * 3600
CANARY_CAPTURE_TEXT = (
    "Романтичный Торт с Бантом от #Milovi_Cake #ТортыНаЗаказ #Cake #Shorts #CakeDecorating\n\n"
    "🌐 https://milovicake.ru/\n"
    "Источник: https://www.youtube.com/shorts/d48QLgOuiTs"
)
CANARY_LIVE_HISTORICAL_TEXT = (
    "Романтичный Торт с Бантом от #Milovi_Cake #ТортыНаЗаказСПб #Cake #Shorts #CakeDecorating\n\n"
    "🌐 https://milovicake.ru/"
)


def _wall_item(
    index: int,
    *,
    post_id: int | None = None,
    extra_photo_id: int | None = None,
    text: str | None = None,
) -> dict[str, Any]:
    attachments: list[dict[str, Any]] = [
        {
            "type": "video",
            "video": {"owner_id": OWNER_ID, "id": CLIP_IDS[index], "type": "short_video"},
        }
    ]
    if extra_photo_id is not None:
        attachments.append({"type": "photo", "photo": {"owner_id": OWNER_ID, "id": extra_photo_id}})
    return {
        "owner_id": OWNER_ID,
        "id": WALL_IDS[index] if post_id is None else post_id,
        "date": PUBLISH_DATES[index],
        "text": f"prior wall {index}" if text is None else text,
        "attachments": attachments,
    }


def _journal() -> dict[str, Any]:
    items: dict[str, dict[str, Any]] = {}
    for index, source_id in enumerate(ROLL_OUT_IDS[:8]):
        items[source_id] = {
            "status": "wall_verified",
            "clip_remote_id": f"{OWNER_ID}_{CLIP_IDS[index]}",
            "wall_remote_id": f"{OWNER_ID}_{WALL_IDS[index]}",
            "publish_date": PUBLISH_DATES[index],
        }
    for source_id in ROLL_OUT_IDS[8:]:
        items[source_id] = {"status": "pending"}
    return {"items": items}


def _snapshot(
    *,
    first_post_id: int,
    captured_epoch: int,
    extra_photo_id: int | None = None,
    first_text: str | None = None,
):
    return build_wall_snapshot(
        community_id=68859909,
        published_items=[_wall_item(0, post_id=first_post_id, extra_photo_id=extra_photo_id, text=first_text)],
        postponed_items=[_wall_item(index) for index in range(1, 8)],
        published_pages=1,
        postponed_pages=1,
        complete=True,
        captured_at=datetime.fromtimestamp(captured_epoch, UTC),
    )


def _record(before) -> dict[str, Any]:
    return {
        "source_video_id": SOURCE9,
        "wall_safety": {
            "before_snapshot_sha256": before.snapshot_sha256,
            "before_captured_at": before.captured_at,
            "before_published_pages": before.published_pages,
            "before_postponed_pages": before.postponed_pages,
        },
    }


class _OldIdTombstoneReader:
    def __init__(self) -> None:
        self.calls: list[tuple[int, int]] = []

    def read_post(self, *, community_id: int, post_id: int) -> dict[str, Any] | None:
        self.calls.append((community_id, post_id))
        assert post_id == 468
        return {
            "owner_id": OWNER_ID,
            "id": 468,
            "date": PUBLISH_DATES[0],
            "is_deleted": True,
        }


def _prove_current_successor(current):
    reader = _OldIdTombstoneReader()
    effective, exact_ids = resume._supplement_due_prior_wall_readbacks(
        reader,
        current,
        journal=_journal(),
        source_id=SOURCE9,
        now_epoch=CAPTURE_EPOCH + 3600,
    )
    assert reader.calls == [(68859909, 468)]
    assert exact_ids == (f"{OWNER_ID}_468",)
    assert any(post.post_id == SUCCESSOR_ID for post in effective.posts)
    assert all(post.post_id != 468 for post in effective.posts)
    return effective


def test_source9_capture_after_slot_can_already_contain_successor_id() -> None:
    before = _snapshot(first_post_id=SUCCESSOR_ID, captured_epoch=CAPTURE_EPOCH)
    current = _snapshot(first_post_id=SUCCESSOR_ID, captured_epoch=CAPTURE_EPOCH + 3600)
    effective = _prove_current_successor(current)

    historical = resume._resume_wall_baseline(
        _record(before),
        effective,
        journal=_journal(),
        successor_resolution_proven=True,
        now_epoch=CAPTURE_EPOCH + 3600,
    )

    assert historical.snapshot_sha256 == before.snapshot_sha256
    first = next(post for post in historical.posts if post.publish_date == PUBLISH_DATES[0])
    assert first.post_id == SUCCESSOR_ID
    assert first.surface.value == "published"


def test_source9_capture_after_slot_can_still_contain_old_published_id() -> None:
    before = _snapshot(first_post_id=468, captured_epoch=CAPTURE_EPOCH)
    current = _snapshot(first_post_id=SUCCESSOR_ID, captured_epoch=CAPTURE_EPOCH + 3600)
    effective = _prove_current_successor(current)

    historical = resume._resume_wall_baseline(
        _record(before),
        effective,
        journal=_journal(),
        successor_resolution_proven=True,
        now_epoch=CAPTURE_EPOCH + 3600,
    )

    assert historical.snapshot_sha256 == before.snapshot_sha256
    first = next(post for post in historical.posts if post.publish_date == PUBLISH_DATES[0])
    assert first.post_id == 468
    assert first.surface.value == "published"


def test_source9_successor_projection_can_be_removed_only_by_exact_historical_sha() -> None:
    before = _snapshot(first_post_id=SUCCESSOR_ID, captured_epoch=CAPTURE_EPOCH)
    current = _snapshot(
        first_post_id=SUCCESSOR_ID,
        captured_epoch=CAPTURE_EPOCH + 3600,
        extra_photo_id=9001,
    )
    effective = _prove_current_successor(current)

    historical = resume._resume_wall_baseline(
        _record(before),
        effective,
        journal=_journal(),
        successor_resolution_proven=True,
        now_epoch=CAPTURE_EPOCH + 3600,
    )

    assert historical.snapshot_sha256 == before.snapshot_sha256
    first = next(post for post in historical.posts if post.publish_date == PUBLISH_DATES[0])
    assert first.attachments == (f"video{OWNER_ID}_{CLIP_IDS[0]}",)


def test_source9_canary_text_projection_restores_capture_with_successor_id() -> None:
    before = _snapshot(
        first_post_id=SUCCESSOR_ID,
        captured_epoch=CAPTURE_EPOCH,
        first_text=CANARY_CAPTURE_TEXT,
    )
    current = _snapshot(
        first_post_id=SUCCESSOR_ID,
        captured_epoch=CAPTURE_EPOCH + 3600,
        first_text=CANARY_LIVE_HISTORICAL_TEXT,
    )
    current_sha = current.snapshot_sha256
    effective = _prove_current_successor(current)

    historical = resume._resume_wall_baseline(
        _record(before),
        effective,
        journal=_journal(),
        successor_resolution_proven=True,
        now_epoch=CAPTURE_EPOCH + 3600,
    )

    assert current.snapshot_sha256 == current_sha
    assert historical.snapshot_sha256 == before.snapshot_sha256
    first = next(post for post in historical.posts if post.publish_date == PUBLISH_DATES[0])
    assert first.post_id == SUCCESSOR_ID
    assert first.text_sha256 == resume.ISSUE323_CANARY_CAPTURE_TEXT_SHA256


def test_source9_canary_text_projection_restores_capture_with_old_published_id() -> None:
    before = _snapshot(
        first_post_id=468,
        captured_epoch=CAPTURE_EPOCH,
        first_text=CANARY_CAPTURE_TEXT,
    )
    current = _snapshot(
        first_post_id=SUCCESSOR_ID,
        captured_epoch=CAPTURE_EPOCH + 3600,
        first_text=CANARY_LIVE_HISTORICAL_TEXT,
    )
    effective = _prove_current_successor(current)

    historical = resume._resume_wall_baseline(
        _record(before),
        effective,
        journal=_journal(),
        successor_resolution_proven=True,
        now_epoch=CAPTURE_EPOCH + 3600,
    )

    assert historical.snapshot_sha256 == before.snapshot_sha256
    first = next(post for post in historical.posts if post.publish_date == PUBLISH_DATES[0])
    assert first.post_id == 468
    assert first.text_sha256 == resume.ISSUE323_CANARY_CAPTURE_TEXT_SHA256


def test_source9_canary_text_projection_rejects_near_miss() -> None:
    before = _snapshot(
        first_post_id=468,
        captured_epoch=CAPTURE_EPOCH,
        first_text=CANARY_CAPTURE_TEXT,
    )
    current = _snapshot(
        first_post_id=SUCCESSOR_ID,
        captured_epoch=CAPTURE_EPOCH + 3600,
        first_text=CANARY_LIVE_HISTORICAL_TEXT + "!",
    )
    effective = _prove_current_successor(current)

    with pytest.raises(resume.MiloviTokenRolloutBlocked, match="cannot be reduced"):
        resume._resume_wall_baseline(
            _record(before),
            effective,
            journal=_journal(),
            successor_resolution_proven=True,
            now_epoch=CAPTURE_EPOCH + 3600,
        )
