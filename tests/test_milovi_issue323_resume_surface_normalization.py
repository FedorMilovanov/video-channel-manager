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


def _wall_item(index: int, *, text: str | None = None) -> dict[str, Any]:
    return {
        "owner_id": -68859909,
        "id": 468 + index,
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


def _historical_before(*, first_already_published: bool = False):
    published = [_wall_item(0)] if first_already_published else []
    postponed_start = 1 if first_already_published else 0
    return build_wall_snapshot(
        community_id=68859909,
        published_items=published,
        postponed_items=[_wall_item(index) for index in range(postponed_start, 7)],
        published_pages=1,
        postponed_pages=1,
        complete=True,
        captured_at=datetime(2026, 8, 13, 18, 0, tzinfo=UTC),
    )


def _record(*, first_already_published: bool = False) -> dict[str, Any]:
    before = _historical_before(first_already_published=first_already_published)
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


def _current_after_first_publication(*, first_text: str | None = None, extra: dict[str, Any] | None = None):
    published = [_wall_item(0, text=first_text)]
    if extra is not None:
        published.append(extra)
    return build_wall_snapshot(
        community_id=68859909,
        published_items=published,
        postponed_items=[_wall_item(index) for index in range(1, 7)],
        published_pages=1,
        postponed_pages=1,
        complete=True,
        captured_at=datetime(2026, 8, 14, 18, 0, tzinfo=UTC),
    )


def _current_missing_first_publication():
    return build_wall_snapshot(
        community_id=68859909,
        published_items=[],
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


def test_eighth_resume_reverses_only_due_transition_needed_for_exact_historical_sha() -> None:
    normalized = resume._resume_wall_baseline(
        _record(),
        _current_after_first_publication(),
        journal=_journal(),
        now_epoch=PUBLISH_DATES[0] + 3600,
    )

    assert normalized.snapshot_sha256 == _historical_before().snapshot_sha256
    assert normalized.captured_at == _historical_before().captured_at
    first = next(post for post in normalized.posts if post.post_id == 468)
    assert first.surface.value == "postponed"


def test_solver_keeps_published_surface_when_it_was_already_published_in_historical_baseline() -> None:
    normalized = resume._resume_wall_baseline(
        _record(first_already_published=True),
        _current_after_first_publication(),
        journal=_journal(),
        now_epoch=PUBLISH_DATES[0] + 3600,
    )

    assert normalized.snapshot_sha256 == _historical_before(first_already_published=True).snapshot_sha256
    first = next(post for post in normalized.posts if post.post_id == 468)
    assert first.surface.value == "published"


def test_due_prior_wall_omitted_by_bulk_snapshot_is_recovered_by_exact_readback() -> None:
    reader = _ExactWallReader(_wall_item(0))

    effective, exact_ids = resume._supplement_due_prior_wall_readbacks(
        reader,
        _current_missing_first_publication(),
        journal=_journal(),
        source_id=resume.ISSUE323_EIGHTH_SOURCE_ID,
        now_epoch=PUBLISH_DATES[0] + 3600,
    )

    assert reader.calls == [(68859909, 468)]
    assert exact_ids == ("-68859909_468",)
    recovered = next(post for post in effective.posts if post.post_id == 468)
    assert recovered.surface.value == "published"

    normalized = resume._resume_wall_baseline(
        _record(),
        effective,
        journal=_journal(),
        now_epoch=PUBLISH_DATES[0] + 3600,
    )
    assert normalized.snapshot_sha256 == _historical_before().snapshot_sha256


def test_exact_readback_does_not_treat_missing_or_deleted_prior_wall_as_projection() -> None:
    reader = _ExactWallReader(None)

    with pytest.raises(UploadRecoveryRequired, match="disappeared during exact readback"):
        resume._supplement_due_prior_wall_readbacks(
            reader,
            _current_missing_first_publication(),
            journal=_journal(),
            source_id=resume.ISSUE323_EIGHTH_SOURCE_ID,
            now_epoch=PUBLISH_DATES[0] + 3600,
        )

    tombstone = _wall_item(0)
    tombstone["is_deleted"] = True
    reader = _ExactWallReader(tombstone)
    with pytest.raises(UploadRecoveryRequired, match="disappeared during exact readback"):
        resume._supplement_due_prior_wall_readbacks(
            reader,
            _current_missing_first_publication(),
            journal=_journal(),
            source_id=resume.ISSUE323_EIGHTH_SOURCE_ID,
            now_epoch=PUBLISH_DATES[0] + 3600,
        )


def test_exact_readback_requires_exact_prior_clip_binding() -> None:
    changed = _wall_item(0)
    changed["attachments"][0]["video"]["id"] = 999
    reader = _ExactWallReader(changed)

    with pytest.raises(UploadRecoveryRequired, match="changed Clip binding"):
        resume._supplement_due_prior_wall_readbacks(
            reader,
            _current_missing_first_publication(),
            journal=_journal(),
            source_id=resume.ISSUE323_EIGHTH_SOURCE_ID,
            now_epoch=PUBLISH_DATES[0] + 3600,
        )


def test_exact_readback_never_backfills_a_future_missing_post() -> None:
    current = build_wall_snapshot(
        community_id=68859909,
        published_items=[_wall_item(0)],
        postponed_items=[_wall_item(index) for index in range(2, 7)],
        published_pages=1,
        postponed_pages=1,
        complete=True,
        captured_at=datetime(2026, 8, 14, 18, 0, tzinfo=UTC),
    )
    reader = _ExactWallReader(_wall_item(1))

    with pytest.raises(UploadRecoveryRequired, match="before its frozen slot"):
        resume._supplement_due_prior_wall_readbacks(
            reader,
            current,
            journal=_journal(),
            source_id=resume.ISSUE323_EIGHTH_SOURCE_ID,
            now_epoch=PUBLISH_DATES[0] + 3600,
        )
    assert reader.calls == []


def test_surface_normalization_rejects_prior_post_published_before_its_slot() -> None:
    with pytest.raises(UploadRecoveryRequired, match="published before its slot"):
        resume._resume_wall_baseline(
            _record(),
            _current_after_first_publication(),
            journal=_journal(),
            now_epoch=PUBLISH_DATES[0] - 3600,
        )


def test_surface_normalization_does_not_hide_text_drift() -> None:
    with pytest.raises(resume.MiloviTokenRolloutBlocked, match="cannot be reduced"):
        resume._resume_wall_baseline(
            _record(),
            _current_after_first_publication(first_text="changed text"),
            journal=_journal(),
            now_epoch=PUBLISH_DATES[0] + 3600,
        )


def test_surface_normalization_does_not_hide_unexpected_extra_post() -> None:
    extra = {
        "owner_id": -68859909,
        "id": 999,
        "date": PUBLISH_DATES[0],
        "text": "unexpected",
        "attachments": [],
    }
    with pytest.raises(resume.MiloviTokenRolloutBlocked, match="cannot be reduced"):
        resume._resume_wall_baseline(
            _record(),
            _current_after_first_publication(extra=extra),
            journal=_journal(),
            now_epoch=PUBLISH_DATES[0] + 3600,
        )


def test_surface_normalization_requires_all_prior_wall_verified_bindings() -> None:
    journal = _journal()
    journal["items"][ROLL_OUT_IDS[3]]["status"] = "pending"

    with pytest.raises(UploadRecoveryRequired, match="not durably wall_verified"):
        resume._resume_wall_baseline(
            _record(),
            _current_after_first_publication(),
            journal=journal,
            now_epoch=PUBLISH_DATES[0] + 3600,
        )
