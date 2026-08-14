from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

import video_channel_manager.platforms.vk.milovi_issue323_live_resume as resume
from video_channel_manager.platforms.vk.milovi_rollout_sources import ROLL_OUT_IDS
from video_channel_manager.platforms.vk.upload_lifecycle import UploadRecoveryRequired
from video_channel_manager.platforms.vk.wall_safety import build_wall_snapshot

PUBLISH_DATES = [
    1786723200,
    1786809600,
    1786896000,
    1786982400,
    1787068800,
    1787155200,
    1787241600,
]


def _wall_item(index: int, *, post_id: int | None = None, text: str | None = None) -> dict[str, Any]:
    return {
        "owner_id": -68859909,
        "id": (468 + index) if post_id is None else post_id,
        "date": PUBLISH_DATES[index],
        "text": text if text is not None else f"legacy wall {index}",
        "attachments": [
            {
                "type": "video",
                "video": {
                    "owner_id": -68859909,
                    "id": 456239225 + index,
                    "type": "short_video",
                },
            }
        ],
    }


def _journal() -> dict[str, Any]:
    items: dict[str, Any] = {}
    for index, source_id in enumerate(ROLL_OUT_IDS[:7]):
        items[source_id] = {
            "status": "wall_verified",
            "clip_remote_id": f"-68859909_{456239225 + index}",
            "wall_remote_id": f"-68859909_{468 + index}",
            "publish_date": PUBLISH_DATES[index],
        }
    for source_id in ROLL_OUT_IDS[7:]:
        items[source_id] = {"status": "pending"}
    return {"items": items}


def _historical_before():
    return build_wall_snapshot(
        community_id=68859909,
        published_items=[],
        postponed_items=[_wall_item(index) for index in range(7)],
        published_pages=1,
        postponed_pages=1,
        complete=True,
        captured_at=datetime(2026, 8, 13, 18, 0, tzinfo=UTC),
    )


def _record() -> dict[str, Any]:
    before = _historical_before()
    after_sha = "sha256:wall-475-side-effect"
    return {
        "source_video_id": resume.ISSUE323_EIGHTH_SOURCE_ID,
        "wall_safety": {
            "before_snapshot_sha256": before.snapshot_sha256,
            "before_captured_at": before.captured_at,
            "before_published_pages": before.published_pages,
            "before_postponed_pages": before.postponed_pages,
            "after_snapshot_sha256": after_sha,
            "delta": {
                "status": "changed",
                "created": [resume.ISSUE323_RECONCILED_WALL_VIEW],
                "removed": [],
                "changed": [],
                "before_sha256": before.snapshot_sha256,
                "after_sha256": after_sha,
                "reasons": [],
            },
        },
    }


def _current_with_successor(
    *,
    successor_id: int = 476,
    successor_text: str | None = None,
    second_successor_id: int | None = None,
):
    published = [_wall_item(0, post_id=successor_id, text=successor_text)]
    if second_successor_id is not None:
        published.append(_wall_item(0, post_id=second_successor_id, text=successor_text))
    return build_wall_snapshot(
        community_id=68859909,
        published_items=published,
        postponed_items=[_wall_item(index) for index in range(1, 7)],
        published_pages=1,
        postponed_pages=1,
        complete=True,
        captured_at=datetime(2026, 8, 14, 18, 0, tzinfo=UTC),
    )


class _ExactWallReader:
    def __init__(self, post: dict[str, Any] | None) -> None:
        self.post = post
        self.calls: list[tuple[int, int]] = []

    def read_post(self, *, community_id: int, post_id: int) -> dict[str, Any] | None:
        self.calls.append((community_id, post_id))
        return self.post


def _tombstone(*, owner_id: int = -68859909, post_id: int = 468, date: int = PUBLISH_DATES[0]):
    return {
        "owner_id": owner_id,
        "id": post_id,
        "date": date,
        "is_deleted": True,
    }


def test_due_postponed_tombstone_rekeys_unique_published_successor_for_historical_sha() -> None:
    reader = _ExactWallReader(_tombstone())
    current = _current_with_successor()

    effective, exact_ids = resume._supplement_due_prior_wall_readbacks(
        reader,
        current,
        journal=_journal(),
        source_id=resume.ISSUE323_EIGHTH_SOURCE_ID,
        now_epoch=PUBLISH_DATES[0] + 3600,
    )

    assert reader.calls == [(68859909, 468)]
    assert exact_ids == ("-68859909_468",)
    assert all(post.post_id != 476 for post in effective.posts)
    canonical = next(post for post in effective.posts if post.post_id == 468)
    assert canonical.surface.value == "published"
    assert canonical.publish_date == PUBLISH_DATES[0]
    assert canonical.attachments == ("video-68859909_456239225",)

    historical = resume._resume_wall_baseline(
        _record(),
        effective,
        journal=_journal(),
        now_epoch=PUBLISH_DATES[0] + 3600,
    )
    assert historical.snapshot_sha256 == _historical_before().snapshot_sha256


def test_due_postponed_missing_exact_object_can_use_unique_published_successor() -> None:
    reader = _ExactWallReader(None)

    effective, exact_ids = resume._supplement_due_prior_wall_readbacks(
        reader,
        _current_with_successor(),
        journal=_journal(),
        source_id=resume.ISSUE323_EIGHTH_SOURCE_ID,
        now_epoch=PUBLISH_DATES[0] + 3600,
    )

    assert exact_ids == ("-68859909_468",)
    historical = resume._resume_wall_baseline(
        _record(),
        effective,
        journal=_journal(),
        now_epoch=PUBLISH_DATES[0] + 3600,
    )
    assert historical.snapshot_sha256 == _historical_before().snapshot_sha256


def test_published_successor_text_drift_still_fails_exact_historical_sha() -> None:
    effective, _exact_ids = resume._supplement_due_prior_wall_readbacks(
        _ExactWallReader(_tombstone()),
        _current_with_successor(successor_text="changed after publication"),
        journal=_journal(),
        source_id=resume.ISSUE323_EIGHTH_SOURCE_ID,
        now_epoch=PUBLISH_DATES[0] + 3600,
    )

    with pytest.raises(resume.MiloviTokenRolloutBlocked, match="cannot be reduced"):
        resume._resume_wall_baseline(
            _record(),
            effective,
            journal=_journal(),
            now_epoch=PUBLISH_DATES[0] + 3600,
        )


def test_multiple_published_successors_are_ambiguous() -> None:
    with pytest.raises(UploadRecoveryRequired, match="published successor is ambiguous"):
        resume._supplement_due_prior_wall_readbacks(
            _ExactWallReader(_tombstone()),
            _current_with_successor(second_successor_id=477),
            journal=_journal(),
            source_id=resume.ISSUE323_EIGHTH_SOURCE_ID,
            now_epoch=PUBLISH_DATES[0] + 3600,
        )


def test_wrong_tombstone_identity_blocks_before_successor_rekey() -> None:
    with pytest.raises(UploadRecoveryRequired, match="tombstone changed identity"):
        resume._supplement_due_prior_wall_readbacks(
            _ExactWallReader(_tombstone(post_id=999)),
            _current_with_successor(),
            journal=_journal(),
            source_id=resume.ISSUE323_EIGHTH_SOURCE_ID,
            now_epoch=PUBLISH_DATES[0] + 3600,
        )


def test_successor_must_keep_exact_clip_binding() -> None:
    current = _current_with_successor()
    first = next(post for post in current.posts if post.post_id == 476)
    wrong = first.__class__(
        owner_id=first.owner_id,
        post_id=first.post_id,
        surface=first.surface,
        publish_date=first.publish_date,
        text_sha256=first.text_sha256,
        attachments=("video-68859909_999",),
    )
    current = current.__class__(
        community_id=current.community_id,
        captured_at=current.captured_at,
        complete=current.complete,
        published_pages=current.published_pages,
        postponed_pages=current.postponed_pages,
        posts=tuple(wrong if post.post_id == 476 else post for post in current.posts),
    )

    with pytest.raises(UploadRecoveryRequired, match="no published successor exists"):
        resume._supplement_due_prior_wall_readbacks(
            _ExactWallReader(_tombstone()),
            current,
            journal=_journal(),
            source_id=resume.ISSUE323_EIGHTH_SOURCE_ID,
            now_epoch=PUBLISH_DATES[0] + 3600,
        )


def test_successor_cannot_reuse_another_journaled_postponed_id() -> None:
    with pytest.raises(UploadRecoveryRequired, match="collides with another journaled ID"):
        resume._supplement_due_prior_wall_readbacks(
            _ExactWallReader(_tombstone()),
            _current_with_successor(successor_id=469),
            journal=_journal(),
            source_id=resume.ISSUE323_EIGHTH_SOURCE_ID,
            now_epoch=PUBLISH_DATES[0] + 3600,
        )
