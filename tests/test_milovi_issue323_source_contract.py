from __future__ import annotations

from video_channel_manager.platforms.vk.milovi_immediate_wall import MILOVI_SOURCE_ALLOWLIST
from video_channel_manager.platforms.vk.milovi_rollout_sources import (
    ROLL_OUT_IDS,
    SOURCE_SNAPSHOT_ID,
    build_description,
    build_wall_message,
)


def test_issue323_reviewed_source_allowlist_is_exact() -> None:
    assert len(ROLL_OUT_IDS) == 12
    assert frozenset(ROLL_OUT_IDS) == MILOVI_SOURCE_ALLOWLIST
    assert ROLL_OUT_IDS[0] == "d48QLgOuiTs"
    assert "SiluLt5Bz1c" not in ROLL_OUT_IDS
    assert SOURCE_SNAPSHOT_ID == "milovi-cake-issue-323-reviewed-public106-final-d48-a8841ece-v1"


def test_source_description_and_wall_copy_keep_exact_source_marker() -> None:
    source_id = "d48QLgOuiTs"
    description = build_description("Торт", source_id)
    wall_message = build_wall_message("Торт", source_id)

    assert description.endswith(f"https://www.youtube.com/shorts/{source_id}")
    assert wall_message.count(f"https://www.youtube.com/shorts/{source_id}") == 1
    assert "https://milovicake.ru/" in wall_message
