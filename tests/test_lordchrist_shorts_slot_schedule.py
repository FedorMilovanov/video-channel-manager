from __future__ import annotations

import json
from pathlib import Path

import pytest

from video_channel_manager.lordchrist_shorts import load_and_validate_editorial_schedule, load_policy

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "content/telegram/lordchrist/shorts-feed-policy.json"
SCHEDULE_PATH = ROOT / "content/telegram/lordchrist/production-schedule.json"


def test_shorts_reads_exact_slot_aware_editorial_schedule() -> None:
    policy = load_policy(POLICY_PATH)
    assert load_and_validate_editorial_schedule(SCHEDULE_PATH, policy) == ("09:17", "21:17")


def test_shorts_rejects_slot_aware_cadence_drift(tmp_path: Path) -> None:
    policy = load_policy(POLICY_PATH)
    payload = json.loads(SCHEDULE_PATH.read_text(encoding="utf-8"))
    payload["slots"]["evening"]["weekdays"] = ["monday", "friday", "sunday"]
    changed = tmp_path / "schedule.json"
    changed.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="evening weekdays differ from the reviewed cadence"):
        load_and_validate_editorial_schedule(changed, policy)


def test_shorts_keeps_historical_v2_schedule_readable(tmp_path: Path) -> None:
    policy = load_policy(POLICY_PATH)
    legacy = {
        "schema_name": "video-channel-manager.telegram-production-schedule",
        "schema_version": 2,
        "project_key": "lord-god-strength",
        "channel_username": "@lordchrist",
        "timezone": "Europe/Moscow",
        "primary_time": "09:17",
        "catchup_time": "21:17",
    }
    path = tmp_path / "legacy-schedule.json"
    path.write_text(json.dumps(legacy), encoding="utf-8")

    assert load_and_validate_editorial_schedule(path, policy) == ("09:17", "21:17")


def test_shorts_rejects_unknown_editorial_schedule_schema(tmp_path: Path) -> None:
    policy = load_policy(POLICY_PATH)
    payload = json.loads(SCHEDULE_PATH.read_text(encoding="utf-8"))
    payload["schema_version"] = 99
    path = tmp_path / "unknown-schedule.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported editorial schedule schema_version"):
        load_and_validate_editorial_schedule(path, policy)
