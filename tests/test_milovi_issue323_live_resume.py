from __future__ import annotations

import inspect

import pytest

import video_channel_manager.platforms.vk.milovi_issue323_live_resume as resume
from video_channel_manager.platforms.vk.upload_lifecycle import VkUploadReadiness


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


def test_live_resume_module_is_provider_inert_helper_only() -> None:
    source = inspect.getsource(resume)
    forbidden = (
        "run_issue_323_live_resume",
        "def main(",
        'if __name__ == "__main__"',
        "execute_upload_operation",
        "local_vk_write_lock",
        "VkWallWriter",
        "argparse",
    )
    assert [token for token in forbidden if token in source] == []
