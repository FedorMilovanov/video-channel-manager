from __future__ import annotations

import video_channel_manager.platforms.vk.milovi_issue323_status_probe as status_probe
from video_channel_manager.platforms.vk.milovi_issue323_planner import plan_issue323_item


def test_status_has_no_parallel_safe_next_action_decision_tree() -> None:
    assert not hasattr(status_probe, "_safe_next_action")
    assert callable(plan_issue323_item)
