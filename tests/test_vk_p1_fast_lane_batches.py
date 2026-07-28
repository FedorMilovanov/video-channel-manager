from __future__ import annotations

import json
from pathlib import Path


_POLICY = Path("content/policies/vk-p1-fast-lane-batches-20260728.json")


def test_fast_lane_covers_remaining_p1_targets_once() -> None:
    payload = json.loads(_POLICY.read_text(encoding="utf-8"))
    batches = payload["batches"]
    targets = [target["video_id"] for batch in batches for target in batch["targets"]]

    assert payload["mode"] == "author_batches"
    assert [batch["target_count"] for batch in batches] == [7, 9, 10, 3, 4, 9]
    assert len(targets) == 42
    assert len(set(targets)) == 42
    assert all(batch["handoffs"] == 2 for batch in batches)

    completed = {
        video_id
        for group in payload["completed_or_in_flight"].values()
        for video_id in group
    }
    assert completed.isdisjoint(targets)


def test_fast_lane_forbids_one_video_waves_after_cloud() -> None:
    payload = json.loads(_POLICY.read_text(encoding="utf-8"))

    assert "do not create one-video correction waves" in payload["rule"]
    assert payload["batches"][0]["batch_id"] == "p1-fast-pushkin-remaining-20260728"
    assert payload["batches"][0]["target_count"] == 7
