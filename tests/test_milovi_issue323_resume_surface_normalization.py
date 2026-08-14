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


def test_eighth_resume_accepts_only_due_prior_postponed_to_published_transition() -> None:
    normalized = resume._resume_wall_baseline(
        _record(),
        _current_after_first_publication(),
        journal=_journal(),
        now_epoch=PUBLISH_DATES[0] + 3600,
    )

    assert normalized.snapshot_sha256 == _historical_before().snapshot_sha256
    assert normalized.captured_at == _historical_before().captured_at


def test_surface_normalization_rejects_prior_post_published_before_its_slot() -> None:
    with pytest.raises(UploadRecoveryRequired, match="published before its slot"):
        resume._resume_wall_baseline(
            _record(),
            _current_after_first_publication(),
            journal=_journal(),
            now_epoch=PUBLISH_DATES[0] - 3600,
        )


def test_surface_normalization_does_not_hide_text_drift() -> None:
    with pytest.raises(resume.MiloviTokenRolloutBlocked, match="pre-upload baseline"):
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
    with pytest.raises(resume.MiloviTokenRolloutBlocked, match="pre-upload baseline"):
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
