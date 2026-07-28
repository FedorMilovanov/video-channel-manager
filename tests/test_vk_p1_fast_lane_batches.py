from __future__ import annotations

import json
from pathlib import Path


_FAST_LANE = Path("content/policies/vk-p1-fast-lane-batches-20260728.json")
_MEGAWAVE = Path("content/policies/vk-p1-megawave-policy-20260728.json")


def test_fast_lane_is_one_megawave() -> None:
    payload = json.loads(_FAST_LANE.read_text(encoding="utf-8"))
    megawave = payload["megawave"]

    assert payload["mode"] == "single_megawave"
    assert "Author batches" in payload["rule"]
    assert megawave["target_count"] == 42
    assert megawave["unique_description_count"] == 37
    assert megawave["user_handoffs"] == 1
    assert megawave["wrapper"] == "scripts/Invoke-VkP1Megawave.ps1"


def test_megawave_policy_covers_each_remaining_target_once() -> None:
    payload = json.loads(_MEGAWAVE.read_text(encoding="utf-8"))
    targets = [item["video_id"] for item in payload["targets"]]

    assert payload["mode"] == "single_megawave"
    assert payload["target_count"] == 42
    assert payload["expected_research_units"] == 37
    assert len(targets) == 42
    assert len(set(targets)) == 42

    fast_lane = json.loads(_FAST_LANE.read_text(encoding="utf-8"))
    completed = {video_id for group in fast_lane["completed"].values() for video_id in group}
    assert completed.isdisjoint(targets)
