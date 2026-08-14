from video_channel_manager.platforms.vk.milovi_issue323_upload_wall_reconcile import (
    ISSUE323_UPLOAD_WALL_RECOVERY_SOURCES,
)
from video_channel_manager.platforms.vk.milovi_rollout_sources import ROLL_OUT_IDS


def test_remaining_upload_wall_delete_authority_is_exactly_sources_9_through_12() -> None:
    assert ISSUE323_UPLOAD_WALL_RECOVERY_SOURCES == frozenset(ROLL_OUT_IDS[8:])
    assert ROLL_OUT_IDS[7] not in ISSUE323_UPLOAD_WALL_RECOVERY_SOURCES
