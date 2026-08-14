from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

import video_channel_manager.platforms.vk.milovi_issue323_upload_wall_reconcile as upload_reconcile
from video_channel_manager.platforms.vk.milovi_issue323_live_resume import _historical_issue323_wall_view
from video_channel_manager.platforms.vk.milovi_rollout_sources import ROLL_OUT_IDS
from video_channel_manager.platforms.vk.milovi_token_clip_rollout import MiloviTokenRolloutBlocked
from video_channel_manager.platforms.vk.upload_lifecycle import UploadRecoveryRequired, UploadStage
from video_channel_manager.platforms.vk.wall_safety import VkWallSnapshot, build_wall_snapshot

COMMUNITY_ID = 68859909
OWNER_ID = -68859909
SOURCE9 = ROLL_OUT_IDS[8]
SOURCE9_CLIP_ID = 456239233
AUTO_POST_ID = 478
AUTO_POST_DATE = 1786735800
WALL_BINDINGS = (
    (ROLL_OUT_IDS[0], 468, 456239225, 1786723200),
    (ROLL_OUT_IDS[1], 469, 456239226, 1786809600),
    (ROLL_OUT_IDS[2], 470, 456239227, 1786896000),
    (ROLL_OUT_IDS[3], 471, 456239228, 1786982400),
    (ROLL_OUT_IDS[4], 472, 456239229, 1787068800),
    (ROLL_OUT_IDS[5], 473, 456239230, 1787155200),
    (ROLL_OUT_IDS[6], 474, 456239231, 1787241600),
    (ROLL_OUT_IDS[7], 477, 456239232, 1787328000),
)


def _wall_item(
    post_id: int,
    clip_id: int,
    publish_date: int,
    *,
    text: str | None = None,
    extra_photo_id: int | None = None,
    second_video_id: int | None = None,
) -> dict[str, Any]:
    attachments: list[dict[str, Any]] = [
        {
            "type": "video",
            "video": {"owner_id": OWNER_ID, "id": clip_id, "type": "short_video"},
        }
    ]
    if second_video_id is not None:
        attachments.append(
            {
                "type": "video",
                "video": {"owner_id": OWNER_ID, "id": second_video_id, "type": "short_video"},
            }
        )
    if extra_photo_id is not None:
        attachments.append(
            {
                "type": "photo",
                "photo": {"owner_id": OWNER_ID, "id": extra_photo_id},
            }
        )
    return {
        "owner_id": OWNER_ID,
        "id": post_id,
        "date": publish_date,
        "text": text if text is not None else f"legacy wall {post_id}",
        "attachments": attachments,
    }


def _journal() -> dict[str, Any]:
    items: dict[str, dict[str, Any]] = {source_id: {"status": "pending"} for source_id in ROLL_OUT_IDS}
    for source_id, post_id, clip_id, publish_date in WALL_BINDINGS:
        items[source_id] = {
            "status": "wall_verified",
            "wall_remote_id": f"{OWNER_ID}_{post_id}",
            "clip_remote_id": f"{OWNER_ID}_{clip_id}",
            "publish_date": publish_date,
        }
    return {"items": items}


def _snapshot(
    *,
    capture_epoch: int,
    wall468_surface: str,
    wall468_text: str | None = None,
    wall468_clip_id: int = 456239225,
    wall468_extra_photo_id: int | None = None,
    wall468_second_video_id: int | None = None,
    unrelated: bool = False,
) -> VkWallSnapshot:
    published: list[dict[str, Any]] = []
    postponed: list[dict[str, Any]] = []
    for _source_id, post_id, clip_id, publish_date in WALL_BINDINGS:
        item = _wall_item(post_id, clip_id, publish_date)
        if post_id == 468:
            item = _wall_item(
                post_id,
                wall468_clip_id,
                publish_date,
                text=wall468_text,
                extra_photo_id=wall468_extra_photo_id,
                second_video_id=wall468_second_video_id,
            )
            (published if wall468_surface == "published" else postponed).append(item)
        else:
            postponed.append(item)
    if unrelated:
        published.append(_wall_item(999, 456239999, capture_epoch - 60, text="unrelated drift"))
    return build_wall_snapshot(
        community_id=COMMUNITY_ID,
        published_items=published,
        postponed_items=postponed,
        published_pages=1,
        postponed_pages=1,
        complete=True,
        captured_at=datetime.fromtimestamp(capture_epoch, UTC),
    )


def _wall_safety(before: VkWallSnapshot) -> dict[str, Any]:
    return {
        "before_captured_at": before.captured_at,
        "before_snapshot_sha256": before.snapshot_sha256,
        "before_published_pages": before.published_pages,
        "before_postponed_pages": before.postponed_pages,
    }


def test_capture_after_slot_restores_video_only_historical_projection() -> None:
    capture_epoch = WALL_BINDINGS[0][3] + 3600
    before = _snapshot(capture_epoch=capture_epoch, wall468_surface="published")
    current = _snapshot(
        capture_epoch=capture_epoch + 7200,
        wall468_surface="published",
        wall468_extra_photo_id=9001,
    )

    historical, reversed_ids = _historical_issue323_wall_view(
        current,
        wall_safety=_wall_safety(before),
        journal=_journal(),
        source_id=SOURCE9,
        now_epoch=capture_epoch + 7200,
    )

    assert historical.snapshot_sha256 == before.snapshot_sha256
    assert reversed_ids == ()
    wall468 = next(post for post in historical.posts if post.post_id == 468)
    assert wall468.attachments == (f"video{OWNER_ID}_456239225",)


def test_historical_projection_does_not_forgive_text_drift() -> None:
    capture_epoch = WALL_BINDINGS[0][3] + 3600
    before = _snapshot(capture_epoch=capture_epoch, wall468_surface="published")
    current = _snapshot(
        capture_epoch=capture_epoch + 7200,
        wall468_surface="published",
        wall468_text="changed text",
        wall468_extra_photo_id=9001,
    )

    with pytest.raises(MiloviTokenRolloutBlocked, match="pre-upload baseline"):
        _historical_issue323_wall_view(
            current,
            wall_safety=_wall_safety(before),
            journal=_journal(),
            source_id=SOURCE9,
            now_epoch=capture_epoch + 7200,
        )


def test_historical_projection_does_not_forgive_unrelated_wall_drift() -> None:
    capture_epoch = WALL_BINDINGS[0][3] + 3600
    before = _snapshot(capture_epoch=capture_epoch, wall468_surface="published")
    current = _snapshot(
        capture_epoch=capture_epoch + 7200,
        wall468_surface="published",
        wall468_extra_photo_id=9001,
        unrelated=True,
    )

    with pytest.raises(MiloviTokenRolloutBlocked, match="pre-upload baseline"):
        _historical_issue323_wall_view(
            current,
            wall_safety=_wall_safety(before),
            journal=_journal(),
            source_id=SOURCE9,
            now_epoch=capture_epoch + 7200,
        )


@pytest.mark.parametrize(
    ("clip_id", "second_video_id", "message"),
    [
        (999, None, "changed Clip binding"),
        (456239225, 456239998, "exactly one video"),
    ],
)
def test_historical_projection_keeps_exact_video_identity(
    clip_id: int,
    second_video_id: int | None,
    message: str,
) -> None:
    capture_epoch = WALL_BINDINGS[0][3] + 3600
    before = _snapshot(capture_epoch=capture_epoch, wall468_surface="published")
    current = _snapshot(
        capture_epoch=capture_epoch + 7200,
        wall468_surface="published",
        wall468_clip_id=clip_id,
        wall468_second_video_id=second_video_id,
    )

    with pytest.raises(UploadRecoveryRequired, match=message):
        _historical_issue323_wall_view(
            current,
            wall_safety=_wall_safety(before),
            journal=_journal(),
            source_id=SOURCE9,
            now_epoch=capture_epoch + 7200,
        )


def test_capture_before_slot_can_reverse_current_published_to_postponed() -> None:
    publish_date = WALL_BINDINGS[0][3]
    capture_epoch = publish_date - 3600
    before = _snapshot(capture_epoch=capture_epoch, wall468_surface="postponed")
    current = _snapshot(capture_epoch=publish_date + 3600, wall468_surface="published")

    historical, reversed_ids = _historical_issue323_wall_view(
        current,
        wall_safety=_wall_safety(before),
        journal=_journal(),
        source_id=SOURCE9,
        now_epoch=publish_date + 3600,
    )

    assert historical.snapshot_sha256 == before.snapshot_sha256
    assert reversed_ids == (f"{OWNER_ID}_468",)


def test_capture_after_slot_cannot_invent_historical_postponed_state() -> None:
    publish_date = WALL_BINDINGS[0][3]
    capture_epoch = publish_date + 3600
    inconsistent_before = _snapshot(capture_epoch=capture_epoch, wall468_surface="postponed")
    current = _snapshot(capture_epoch=capture_epoch + 3600, wall468_surface="published")

    with pytest.raises(MiloviTokenRolloutBlocked, match="pre-upload baseline"):
        _historical_issue323_wall_view(
            current,
            wall_safety=_wall_safety(inconsistent_before),
            journal=_journal(),
            source_id=SOURCE9,
            now_epoch=capture_epoch + 3600,
        )


def _upload_record_for_diagnostic(current: VkWallSnapshot) -> dict[str, Any]:
    before = current.captured_at
    return {
        "source_video_id": SOURCE9,
        "stage": UploadStage.UNKNOWN_REQUIRES_RECONCILIATION.value,
        "reservation": {
            "owner_id": OWNER_ID,
            "video_id": SOURCE9_CLIP_ID,
            "remote_id": f"{OWNER_ID}_{SOURCE9_CLIP_ID}",
            "upload_url": "journal-only",
        },
        "wall_safety": {
            "before_snapshot_sha256": "sha256:before",
            "before_captured_at": before,
            "after_snapshot_sha256": "sha256:after",
            "after_captured_at": before,
            "delta": {
                "status": "changed",
                "created": [f"published:{OWNER_ID}_{AUTO_POST_ID}"],
                "removed": [],
                "changed": [],
                "before_sha256": "sha256:before",
                "after_sha256": "sha256:after",
                "reasons": [],
            },
        },
    }


class _DiagnosticWriter:
    def read_post(self, *, community_id: int, post_id: int) -> dict[str, Any] | None:
        assert community_id == COMMUNITY_ID
        assert post_id == AUTO_POST_ID
        return _wall_item(AUTO_POST_ID, SOURCE9_CLIP_ID, AUTO_POST_DATE, text="")


def test_exact_candidate_reports_historical_baseline_rejection(monkeypatch: pytest.MonkeyPatch) -> None:
    current = build_wall_snapshot(
        community_id=COMMUNITY_ID,
        published_items=[],
        postponed_items=[],
        published_pages=1,
        postponed_pages=1,
        complete=True,
        captured_at=datetime.fromtimestamp(AUTO_POST_DATE, UTC),
    )
    record = _upload_record_for_diagnostic(current)
    monkeypatch.setattr(
        upload_reconcile,
        "_prove_historical_baseline",
        lambda **_kwargs: (_ for _ in ()).throw(MiloviTokenRolloutBlocked("specific historical drift")),
    )

    with pytest.raises(UploadRecoveryRequired, match="specific historical drift"):
        upload_reconcile._candidate_fingerprints(
            record=record,
            current=current,
            journal={"items": {source_id: {"status": "pending"} for source_id in ROLL_OUT_IDS}},
            source_id=SOURCE9,
            writer=_DiagnosticWriter(),  # type: ignore[arg-type]
            delta=record["wall_safety"]["delta"],
        )
