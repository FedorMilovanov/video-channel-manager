from __future__ import annotations

import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "content/telegram/lordchrist/production-schedule.json"
WORKFLOW_PATH = ROOT / ".github/workflows/lordchrist-telegram-poster.yml"
EXPECTED_DIGEST = "sha256:43518f50844b92230dd3854c363e86f0075347e31ed266f0ecad9c92b48d1b20"


def test_autonomous_production_config_is_explicit_and_future_gated() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    assert config["schema_name"] == "video-channel-manager.telegram-production-schedule"
    assert config["schema_version"] == 1
    assert config["project_key"] == "lord-god-strength"
    assert config["channel_username"] == "@lordchrist"
    assert config["enabled"] is True
    assert date.fromisoformat(config["not_before_moscow_date"]) == date(2026, 8, 8)
    assert config["timezone"] == "Europe/Moscow"
    assert config["primary_time"] == "09:17"
    assert config["catchup_time"] == "21:17"
    assert config["daily_verified_limit"] == 1
    assert config["queue_digest"] == EXPECTED_DIGEST


def test_workflow_uses_version_controlled_schedule_gate() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "PRODUCTION_CONFIG_PATH: content/telegram/lordchrist/production-schedule.json" in workflow
    assert "(github.event_name != 'schedule' || vars.LORDCHRIST_SCHEDULE_ENABLED == 'true')" not in workflow
    assert "scheduled_not_active_yet" in workflow
    assert "scheduled_execution" in workflow
    assert "LORDCHRIST_POSTING_ENABLED is not true." in workflow
    assert "Scheduled production config is not active." in workflow
    assert "LORDCHRIST_SCHEDULE_ENABLED is not true." not in workflow
    assert 'cron: "17 9 * * *"' in workflow
    assert 'cron: "17 21 * * *"' in workflow
