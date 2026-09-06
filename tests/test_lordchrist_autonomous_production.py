from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from video_channel_manager.telegram_presentation import load_presentation_policy

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "content/telegram/lordchrist/production-schedule.json"
POLICY_PATH = ROOT / "content/telegram/lordchrist/presentation-policy.json"
WORKFLOW_PATH = ROOT / ".github/workflows/lordchrist-telegram-poster.yml"
EXPECTED_DIGEST = "sha256:43518f50844b92230dd3854c363e86f0075347e31ed266f0ecad9c92b48d1b20"
EXPECTED_CHAT_ID = -1001295216957
EXPECTED_BOT_ID = 8716602202
EXPECTED_BOT_USERNAME = "preaching_mp3_bot"


def test_autonomous_production_config_is_explicit_release_bound_and_future_gated() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    policy = load_presentation_policy(POLICY_PATH)

    assert config["schema_name"] == "video-channel-manager.telegram-production-schedule"
    assert config["schema_version"] == 3
    assert config["project_key"] == "lord-god-strength"
    assert config["channel_username"] == "@lordchrist"
    assert config["chat_id"] == EXPECTED_CHAT_ID
    assert config["bot_id"] == EXPECTED_BOT_ID
    assert config["bot_username"] == EXPECTED_BOT_USERNAME
    assert config["enabled"] is True
    assert date.fromisoformat(config["not_before_moscow_date"]) == date(2026, 8, 8)
    assert config["timezone"] == "Europe/Moscow"
    assert config["max_publications_per_slot"] == 1
    assert config["slots"] == {
        "morning": {
            "time": "09:17",
            "weekdays": [
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
            ],
        },
        "evening": {
            "time": "21:17",
            "weekdays": ["tuesday", "friday", "sunday"],
        },
    }
    assert "primary_time" not in config
    assert "catchup_time" not in config
    assert "daily_verified_limit" not in config
    assert config["queue_digest"] == EXPECTED_DIGEST
    assert config["presentation_policy_id"] == policy.policy_id
    assert config["presentation_policy_sha256"] == policy.digest


def test_workflow_uses_version_controlled_schedule_gate_and_exact_release_identity() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "PRODUCTION_CONFIG_PATH: content/telegram/lordchrist/production-schedule.json" in workflow
    assert "(github.event_name != 'schedule' || vars.LORDCHRIST_SCHEDULE_ENABLED == 'true')" not in workflow
    assert "scheduled_not_active_yet" in workflow
    assert "scheduled_execution" in workflow
    assert "LORDCHRIST_POSTING_ENABLED is not true." in workflow
    assert "Scheduled production config is not active." in workflow
    assert "production schedule chat id does not match configured Telegram target" in workflow
    assert "production schedule bot id does not match configured Telegram bot" in workflow
    assert "production schedule presentation policy digest mismatch" in workflow
    assert "LORDCHRIST_SCHEDULE_ENABLED is not true." not in workflow
    assert 'cron: "17 9 * * *"' in workflow
    assert 'cron: "17 21 * * 0,2,5"' in workflow
    assert 'cron: "17 21 * * *"' not in workflow
    assert '"17 9 * * *": "morning"' in workflow
    assert '"17 21 * * 0,2,5": "evening"' in workflow
    assert "scheduled_moscow_date" in workflow
    assert "scheduled_slot" in workflow
    assert '--scheduled-moscow-date "${{ steps.intent.outputs.scheduled_moscow_date }}"' in workflow
    assert '--scheduled-slot "${{ steps.intent.outputs.scheduled_slot }}"' in workflow


def test_scheduled_gate_does_not_require_manual_posting_toggle() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    gate_start = workflow.index("      - name: Enforce publication gates")
    gate_end = workflow.index("      - name: Enable publication ledger writer")
    gate = workflow[gate_start:gate_end]

    scheduled_branch, manual_branch = gate.split("          else\n", 1)
    assert "LORDCHRIST_POSTING_ENABLED" not in scheduled_branch
    assert "LORDCHRIST_POSTING_ENABLED" in manual_branch
    assert "max_publications_per_slot" in scheduled_branch
    assert "daily_verified_limit" not in scheduled_branch


def test_send_step_bridges_only_a_valid_schedule_event_into_legacy_internal_gate() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    send_start = workflow.index("      - name: Send exactly one prepared message")
    send_end = workflow.index("      - name: Persist exact Telegram result")
    send_step = workflow[send_start:send_end]

    assert (
        "LORDCHRIST_POSTING_ENABLED: ${{ github.event_name == 'schedule' && 'true' || vars.LORDCHRIST_POSTING_ENABLED }}"
        in send_step
    )
    assert "LORDCHRIST_SCHEDULE_ENABLED: ${{ github.event_name == 'schedule' && 'true' || 'false' }}" in send_step
    assert workflow.count("LORDCHRIST_SCHEDULE_ENABLED: ${{ github.event_name == 'schedule'") == 1
    assert "if: steps.persist_intent.outputs.persisted == 'true'" in send_step
