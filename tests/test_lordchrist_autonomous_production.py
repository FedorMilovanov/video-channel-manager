from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from video_channel_manager.telegram_presentation import load_presentation_policy
from video_channel_manager.telegram_schedule import decide_scheduled_slot, load_production_schedule

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "content/telegram/lordchrist/production-schedule.json"
POLICY_PATH = ROOT / "content/telegram/lordchrist/presentation-policy.json"
WORKFLOW_PATH = ROOT / ".github/workflows/lordchrist-telegram-poster.yml"
EXPECTED_DIGEST = "sha256:43518f50844b92230dd3854c363e86f0075347e31ed266f0ecad9c92b48d1b20"
EXPECTED_CHAT_ID = -1001295216957
EXPECTED_BOT_ID = 8716602202
EXPECTED_BOT_USERNAME = "preaching_mp3_bot"


def test_autonomous_production_config_is_explicit_release_bound_and_slot_gated() -> None:
    config = load_production_schedule(CONFIG_PATH)
    policy = load_presentation_policy(POLICY_PATH)

    assert config.schema_name == "video-channel-manager.telegram-production-schedule"
    assert config.schema_version == 3
    assert config.project_key == "lord-god-strength"
    assert config.channel_username == "@lordchrist"
    assert config.chat_id == EXPECTED_CHAT_ID
    assert config.bot_id == EXPECTED_BOT_ID
    assert config.bot_username == EXPECTED_BOT_USERNAME
    assert config.enabled is True
    assert config.not_before_moscow_date == date(2026, 8, 8)
    assert config.timezone == "Europe/Moscow"
    assert config.slots["morning"].time == "09:17"
    assert config.slots["morning"].cron == "17 9 * * *"
    assert config.slots["morning"].iso_weekdays == (1, 2, 3, 4, 5, 6, 7)
    assert config.slots["morning"].max_lateness_minutes == 120
    assert config.slots["evening"].time == "21:17"
    assert config.slots["evening"].cron == "17 21 * * 2,5,0"
    assert config.slots["evening"].iso_weekdays == (2, 5, 7)
    assert config.slots["evening"].max_lateness_minutes == 120
    assert config.max_verified_per_slot == 1
    assert config.max_verified_per_day == 2
    assert config.backfill_policy == "none"
    assert config.queue_digest == EXPECTED_DIGEST
    assert config.presentation_policy_id == policy.policy_id
    assert config.presentation_policy_sha256 == policy.digest


def test_schedule_decision_has_daily_morning_and_only_tuesday_friday_sunday_evening() -> None:
    config = load_production_schedule(CONFIG_PATH)

    monday = datetime(2026, 9, 7, 6, 17, tzinfo=UTC)  # 09:17 Moscow
    tuesday_evening = datetime(2026, 9, 8, 18, 17, tzinfo=UTC)  # 21:17 Moscow
    friday_evening = datetime(2026, 9, 11, 18, 17, tzinfo=UTC)
    sunday_evening = datetime(2026, 9, 13, 18, 17, tzinfo=UTC)
    monday_evening = datetime(2026, 9, 7, 18, 17, tzinfo=UTC)

    assert decide_scheduled_slot(config, event_schedule="17 9 * * *", now=monday).slot == "morning"
    assert decide_scheduled_slot(config, event_schedule="17 21 * * 2,5,0", now=tuesday_evening).slot == "evening"
    assert decide_scheduled_slot(config, event_schedule="17 21 * * 2,5,0", now=friday_evening).slot == "evening"
    assert decide_scheduled_slot(config, event_schedule="17 21 * * 2,5,0", now=sunday_evening).slot == "evening"
    monday_result = decide_scheduled_slot(config, event_schedule="17 21 * * 2,5,0", now=monday_evening)
    assert monday_result.active is False
    assert monday_result.slot is None


def test_schedule_decision_rejects_premature_and_stale_runs_without_backfill() -> None:
    config = load_production_schedule(CONFIG_PATH)

    before_morning = datetime(2026, 9, 8, 6, 16, 59, tzinfo=UTC)  # 09:16:59 Moscow
    morning_deadline = datetime(2026, 9, 8, 8, 17, tzinfo=UTC)  # 11:17 Moscow
    fresh_delayed_evening = datetime(2026, 9, 8, 19, 16, 59, tzinfo=UTC)  # 22:16:59 Moscow

    premature = decide_scheduled_slot(config, event_schedule="17 9 * * *", now=before_morning)
    stale = decide_scheduled_slot(config, event_schedule="17 9 * * *", now=morning_deadline)
    delayed = decide_scheduled_slot(config, event_schedule="17 21 * * 2,5,0", now=fresh_delayed_evening)

    assert premature.active is False
    assert premature.reason == "morning slot is not due yet"
    assert stale.active is False
    assert stale.reason == "morning slot is too stale for safe publication"
    assert delayed.active is True
    assert delayed.slot == "evening"


def test_workflow_uses_version_controlled_slot_gate_and_exact_release_identity() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "PRODUCTION_CONFIG_PATH: content/telegram/lordchrist/production-schedule.json" in workflow
    assert "scheduled_slot=$scheduled_slot" in workflow
    assert "decide_scheduled_slot" in workflow
    assert "require_release_binding" in workflow
    assert "--scheduled-slot \"${{ steps.intent.outputs.scheduled_slot }}\"" in workflow
    assert "production schedule chat id does not match configured Telegram target" not in workflow
    assert "LORDCHRIST_SCHEDULE_ENABLED is not true." not in workflow
    assert 'cron: "17 9 * * *"' in workflow
    assert 'cron: "17 21 * * 2,5,0"' in workflow
    assert 'cron: "17 21 * * *"' not in workflow


def test_scheduled_gate_does_not_require_manual_posting_toggle() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    gate_start = workflow.index("      - name: Enforce publication gates")
    gate_end = workflow.index("      - name: Enable publication ledger writer")
    gate = workflow[gate_start:gate_end]

    scheduled_branch, manual_branch = gate.split("          else\n", 1)
    assert "LORDCHRIST_POSTING_ENABLED" not in scheduled_branch
    assert "LORDCHRIST_POSTING_ENABLED" in manual_branch
    assert "EXPECTED_SLOT" in scheduled_branch
    assert "Scheduled production slot" in scheduled_branch


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
