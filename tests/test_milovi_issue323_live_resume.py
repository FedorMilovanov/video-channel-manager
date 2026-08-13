from __future__ import annotations

import inspect
from datetime import UTC, datetime
from pathlib import Path

import pytest

import video_channel_manager.platforms.vk.milovi_issue323_live_resume as resume
from video_channel_manager.platforms.vk.milovi_daily_postponed_wall import _schedule_payload, plan_daily_publish_slots
from video_channel_manager.platforms.vk.milovi_rollout_sources import ROLL_OUT_IDS, write_json_atomic
from video_channel_manager.platforms.vk.upload_lifecycle import VkUploadReadiness
from video_channel_manager.platforms.vk.wall_safety import build_wall_snapshot


def _readiness() -> VkUploadReadiness:
    return VkUploadReadiness(
        expected_title="Expected clip title",
        minimum_duration_seconds=30,
        allowed_types=("short_video",),
        require_playable=True,
    )


def _live_item(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "owner_id": -68859909,
        "id": 456239225,
        "title": "",
        "duration": 34,
        "type": "short_video",
        "processing": 1,
        "converting": 0,
        "can_watch": 1,
        "player": "https://vk.example/player",
        "description": "Источник: https://www.youtube.com/shorts/d48QLgOuiTs",
    }
    payload.update(overrides)
    return payload


def test_exact_live_canary_identity_and_confirmation_are_pinned() -> None:
    assert resume.EXPECTED_CANARY_REMOTE_ID == "-68859909_456239225"
    assert resume.EXECUTION_CONFIRMATION == "ISSUE_323_RESUME_LIVE_SHORT_VIDEO_AND_FINISH"


def test_playable_native_short_video_accepts_provider_processing_and_blank_title() -> None:
    assessment = resume._native_clip_assessment(
        _live_item(),
        expected_owner_id=-68859909,
        expected_video_id=456239225,
        readiness=_readiness(),
    )

    assert assessment.ready is True
    assert assessment.reasons == ()
    assert assessment.observed["readiness_mode"] == "playable_native_short_video"
    assert assessment.observed["provider_processing_flag_tolerated"] is True
    assert assessment.observed["blank_clip_title_tolerated"] is True


def test_lifecycle_view_preserves_raw_provider_shape_and_satisfies_shared_recheck() -> None:
    raw = _live_item()
    readiness = _readiness()
    assessment = resume._native_clip_assessment(
        raw,
        expected_owner_id=-68859909,
        expected_video_id=456239225,
        readiness=readiness,
    )

    view = resume._lifecycle_ready_view(raw, readiness=readiness, assessment=assessment)
    strict = resume.assess_vk_upload_readiness(
        view,
        expected_owner_id=-68859909,
        expected_video_id=456239225,
        readiness=readiness,
    )

    assert strict.ready is True
    assert raw["processing"] == 1
    assert raw["title"] == ""
    assert view["processing"] == 0
    assert view["title"] == readiness.expected_title


@pytest.mark.parametrize(
    "overrides",
    [
        {"type": "video", "processing": 0},
        {"duration": 5},
        {"can_watch": 0, "player": ""},
        {"converting": 1},
        {"owner_id": -1},
        {"id": 999},
        {"title": "Wrong non-empty title"},
    ],
)
def test_live_readiness_does_not_hide_material_provider_mismatches(overrides: dict[str, object]) -> None:
    assessment = resume._native_clip_assessment(
        _live_item(**overrides),
        expected_owner_id=-68859909,
        expected_video_id=456239225,
        readiness=_readiness(),
    )

    assert assessment.ready is False


class _WallReader:
    def capture_wall_snapshot(self, *, community_id: int, max_posts_per_surface: int):
        assert community_id == 68859909
        assert max_posts_per_surface == 10000
        return build_wall_snapshot(
            community_id=68859909,
            published_items=[],
            postponed_items=[],
            published_pages=1,
            postponed_pages=1,
            complete=True,
            captured_at=datetime(2026, 8, 13, 17, 2, tzinfo=UTC),
        )


def _no_wall_effect_journal() -> dict[str, object]:
    return {"items": {source_id: {"status": "pending"} for source_id in ROLL_OUT_IDS}}


def test_expired_frozen_schedule_rebases_before_first_wall_effect(tmp_path: Path) -> None:
    old_slots = plan_daily_publish_slots(
        existing_postponed_publish_dates=[],
        now=datetime(2026, 8, 13, 14, 0, tzinfo=UTC),
    )
    path = tmp_path / "schedule.json"
    write_json_atomic(path, _schedule_payload(old_slots))

    current = datetime(2026, 8, 13, 17, 2, tzinfo=UTC)
    rebased = resume._load_or_rebase_schedule(
        path,
        writer=_WallReader(),  # type: ignore[arg-type]
        journal=_no_wall_effect_journal(),
        now=current,
    )

    assert tuple(rebased) == ROLL_OUT_IDS
    assert min(rebased.values()) > current.astimezone(rebased[ROLL_OUT_IDS[0]].tzinfo)
    assert rebased[ROLL_OUT_IDS[0]].date().isoformat() == "2026-08-14"


def test_expired_schedule_never_rebases_after_wall_intent(tmp_path: Path) -> None:
    old_slots = plan_daily_publish_slots(
        existing_postponed_publish_dates=[],
        now=datetime(2026, 8, 13, 14, 0, tzinfo=UTC),
    )
    path = tmp_path / "schedule.json"
    write_json_atomic(path, _schedule_payload(old_slots))
    journal = _no_wall_effect_journal()
    items = journal["items"]
    assert isinstance(items, dict)
    items[ROLL_OUT_IDS[0]] = {"status": "wall_intent"}

    with pytest.raises(resume.MiloviTokenRolloutBlocked, match="automatic rebase is forbidden"):
        resume._load_or_rebase_schedule(
            path,
            writer=_WallReader(),  # type: ignore[arg-type]
            journal=journal,
            now=datetime(2026, 8, 13, 17, 2, tzinfo=UTC),
        )


def test_resume_loop_skips_durable_verified_children_before_fresh_clip_readback() -> None:
    source = inspect.getsource(resume.run_issue_323_live_resume)
    assert 'if status == "wall_verified":\n                    continue' in source
    assert 'if status == "clip_verified":' in source
    assert "Durable clip_verified item has no exact clip_remote_id" in source
    assert "_assert_live_clip(writer, asset, clip_id)" not in source


def test_resume_module_has_no_browser_dependency() -> None:
    source = inspect.getsource(resume).casefold()
    assert "playwright" not in source
    assert "yandex" not in source
    assert "chrome" not in source
