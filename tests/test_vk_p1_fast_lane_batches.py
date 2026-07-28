from __future__ import annotations

import json
from pathlib import Path


_FAST_LANE = Path("content/policies/vk-p1-fast-lane-batches-20260728.json")
_FINAL_MEGAWAVE = Path("content/policies/vk-p1-final-megawave-policy-20260728.json")
_RETIRED_MEGAWAVE = Path("content/policies/vk-p1-megawave-policy-20260728.json")


def test_fast_lane_is_one_final_megawave() -> None:
    payload = json.loads(_FAST_LANE.read_text(encoding="utf-8"))
    megawave = payload["megawave"]

    assert payload["mode"] == "single_final_megawave"
    assert "descriptions-only waves" in payload["rule"]
    assert megawave["decision_set_id"] == "p1-final-all-in-one-20260728"
    assert megawave["policy"] == str(_FINAL_MEGAWAVE).replace("\\", "/")
    assert megawave["target_count"] == 42
    assert megawave["description_updates"] == 42
    assert megawave["title_updates"] == 3
    assert megawave["album_title_updates"] == 3
    assert megawave["membership_additions"] == 32
    assert megawave["total_operations"] == 77
    assert megawave["user_handoffs"] == 1
    assert megawave["wrapper"] == "scripts/Invoke-VkP1Megawave.ps1"


def test_final_megawave_policy_covers_each_remaining_target_once() -> None:
    payload = json.loads(_FINAL_MEGAWAVE.read_text(encoding="utf-8"))
    targets = [item["video_id"] for item in payload["targets"]]

    assert payload["decision_set_id"] == "p1-final-all-in-one-20260728"
    assert len(targets) == 42
    assert len(set(targets)) == 42

    fast_lane = json.loads(_FAST_LANE.read_text(encoding="utf-8"))
    completed = {video_id for group in fast_lane["completed"].values() for video_id in group}
    assert completed.isdisjoint(targets)


def test_old_descriptions_only_megawave_is_retired() -> None:
    payload = json.loads(_RETIRED_MEGAWAVE.read_text(encoding="utf-8"))

    assert payload["status"] == "retired"
    assert payload["approved_decision_set"] == "p1-final-all-in-one-20260728"
    assert payload["superseded_by"] == str(_FINAL_MEGAWAVE).replace("\\", "/")
