from __future__ import annotations

import json

from datetime import UTC, date, datetime
from pathlib import Path

from video_channel_manager.telegram_presentation import load_presentation_policy
from video_channel_manager.telegram_schedule import (
    SLOT_LANES,
    decide_scheduled_slot,
    load_production_schedule,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "content/telegram/lordchrist/production-schedule.json"
POLICY_PATH = ROOT / "content/telegram/lordchrist/presentation-policy.json"
ACTIVATION_PATH = ROOT / "content/telegram/lordchrist/quote-v4-runtime-activation.json"
WORKFLOW_PATH = ROOT / ".github/workflows/lordchrist-telegram-poster.yml"
EXPECTED_DIGEST = "sha256:a3e5bd757b49996f5db27d46427ce3e6909ce1cf8146d41f6bd316081a2065dd"
EXPECTED_SUCCESSOR_DIGEST = "sha256:43518f50844b92230dd3854c363e86f0075347e31ed266f0ecad9c92b48d1b20"
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
    activation = json.loads(ACTIVATION_PATH.read_text(encoding="utf-8"))
    # Arming is not a free-standing flag: autonomous dispatch may only be enabled by the
    # same reviewed activation checkpoint that authorizes provider writes, and both must
    # bind the identical reviewed presentation policy.
    assert config.enabled is activation["provider_writes_authorized"]
    assert config.presentation_policy_sha256 == activation["presentation_policy_sha256"]
    assert activation["release_id"] == "lordchrist-puritan-spurgeon-v4"
    assert activation["queue_digest"] == config.queue_digest == EXPECTED_DIGEST
    note = config.activation_note.casefold()
    assert "v4" in note or "depth-v3" in note
    assert "10:00" in note
    assert config.not_before_moscow_date == date(2026, 8, 8)
    assert config.timezone == "Europe/Moscow"
    assert config.primary_time == "10:00"
    assert config.catchup_time == "21:00"
    assert config.slots["morning"].time == config.primary_time
    assert config.slots["morning"].cron == "0 7 * * *"
    assert config.slots["morning"].iso_weekdays == (1, 2, 3, 4, 5, 6, 7)
    assert config.slots["morning"].max_lateness_minutes == 660
    assert config.slots["evening"].time == config.catchup_time
    assert config.slots["evening"].cron == "0 18 * * 2,5,0"
    assert config.slots["evening"].iso_weekdays == (2, 5, 7)
    assert config.slots["evening"].max_lateness_minutes == 180
    assert config.max_verified_per_slot == 1
    assert config.max_verified_per_day == 2
    assert config.backfill_policy == "none"
    assert config.queue_digest == EXPECTED_DIGEST
    assert config.successor_queue_digest == EXPECTED_SUCCESSOR_DIGEST
    assert config.presentation_policy_id == policy.policy_id
    assert config.presentation_policy_sha256 == policy.digest


def test_disabled_depth_v2_schedule_fails_closed_before_slot_evaluation() -> None:
    config = load_production_schedule(CONFIG_PATH).model_copy(update={"enabled": False})
    decision = decide_scheduled_slot(
        config,
        event_schedule="0 7 * * *",
        now=datetime(2026, 9, 7, 7, 0, tzinfo=UTC),
    )

    assert decision.active is False
    assert decision.slot is None
    assert decision.reason == "production schedule disabled"


def test_armed_depth_v2_schedule_still_publishes_at_most_one_verified_post_per_slot() -> None:
    config = load_production_schedule(CONFIG_PATH)

    assert config.enabled is True
    assert config.max_verified_per_slot == 1
    assert config.max_verified_per_day == 2
    assert config.backfill_policy == "none"
    assert (
        decide_scheduled_slot(
            config,
            event_schedule="0 7 * * *",
            now=datetime(2026, 9, 7, 7, 0, tzinfo=UTC),
        ).slot
        == "morning"
    )


def test_schedule_decision_has_daily_morning_and_only_tuesday_friday_sunday_evening() -> None:
    config = load_production_schedule(CONFIG_PATH).model_copy(update={"enabled": True})

    monday = datetime(2026, 9, 7, 7, 0, tzinfo=UTC)  # 10:00 Moscow
    tuesday_evening = datetime(2026, 9, 8, 18, 17, tzinfo=UTC)  # 21:00 Moscow
    friday_evening = datetime(2026, 9, 11, 18, 0, tzinfo=UTC)
    sunday_evening = datetime(2026, 9, 13, 18, 0, tzinfo=UTC)
    monday_evening = datetime(2026, 9, 7, 18, 0, tzinfo=UTC)

    assert decide_scheduled_slot(config, event_schedule="0 7 * * *", now=monday).slot == "morning"
    assert decide_scheduled_slot(config, event_schedule="0 18 * * 2,5,0", now=tuesday_evening).slot == "evening"
    assert decide_scheduled_slot(config, event_schedule="0 18 * * 2,5,0", now=friday_evening).slot == "evening"
    assert decide_scheduled_slot(config, event_schedule="0 18 * * 2,5,0", now=sunday_evening).slot == "evening"
    monday_result = decide_scheduled_slot(config, event_schedule="0 18 * * 2,5,0", now=monday_evening)
    assert monday_result.active is False
    assert monday_result.slot is None


def test_schedule_decision_rejects_premature_and_stale_runs_without_backfill() -> None:
    config = load_production_schedule(CONFIG_PATH).model_copy(update={"enabled": True})

    before_morning = datetime(2026, 9, 8, 6, 59, 59, tzinfo=UTC)  # 09:59:59 Moscow
    fresh_delayed_morning = datetime(2026, 9, 8, 17, 59, 59, tzinfo=UTC)  # 20:59:59 Moscow
    morning_deadline = datetime(2026, 9, 8, 18, 0, tzinfo=UTC)  # 21:00 Moscow, lease expired
    fresh_delayed_evening = datetime(2026, 9, 8, 20, 59, 59, tzinfo=UTC)  # 23:59:59 MSK Tue, still Tue in MSK
    # The evening lease extends exactly to MSK midnight (21:00 UTC), at which point
    # the local date becomes Wed and the weekday gate rejects before the lateness
    # check runs; cron itself never fires on Wed/Fri/Sat UTC anyway, so there is no
    # "stale-evening" edge to publish from.
    post_lease_evening = datetime(2026, 9, 8, 21, 0, tzinfo=UTC)  # 00:00 MSK Wed -> weekday gate

    premature = decide_scheduled_slot(config, event_schedule="0 7 * * *", now=before_morning)
    delayed_morning = decide_scheduled_slot(config, event_schedule="0 7 * * *", now=fresh_delayed_morning)
    stale_morning = decide_scheduled_slot(config, event_schedule="0 7 * * *", now=morning_deadline)
    delayed_evening = decide_scheduled_slot(config, event_schedule="0 18 * * 2,5,0", now=fresh_delayed_evening)
    post_lease_evening_decision = decide_scheduled_slot(config, event_schedule="0 18 * * 2,5,0", now=post_lease_evening)

    assert premature.active is False
    assert premature.reason == "morning slot is not due yet"
    assert delayed_morning.active is True
    assert delayed_morning.slot == "morning"
    assert stale_morning.active is False
    assert stale_morning.reason == "morning slot is too stale for safe publication"
    assert delayed_evening.active is True
    assert delayed_evening.slot == "evening"
    assert post_lease_evening_decision.active is False
    # At MSK midnight we are on a non-evening weekday; cron never fires here anyway.
    assert "not eligible" in post_lease_evening_decision.reason or "too stale" in post_lease_evening_decision.reason


def test_workflow_uses_version_controlled_slot_gate_and_exact_release_identity() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "PRODUCTION_CONFIG_PATH: content/telegram/lordchrist/production-schedule.json" in workflow
    assert "scheduled_slot=$scheduled_slot" in workflow
    assert "decide_scheduled_slot" in workflow
    assert "require_release_binding" in workflow
    assert '--scheduled-slot "${{ steps.intent.outputs.scheduled_slot }}"' in workflow
    assert "production schedule chat id does not match configured Telegram target" not in workflow
    assert "LORDCHRIST_SCHEDULE_ENABLED is not true." not in workflow
    assert 'cron: "0 7 * * *"' in workflow
    assert 'cron: "0 18 * * 2,5,0"' in workflow
    assert 'cron: "17 16 * * 1,3,6"' in workflow
    # The previous UTC-as-Moscow expressions fired three hours past every
    # documented slot boundary and must never return.
    assert 'cron: "17 9 * * *"' not in workflow
    assert 'cron: "17 21 * * 2,5,0"' not in workflow
    assert 'cron: "17 19 * * 1,3,6"' not in workflow


def test_scheduled_gate_does_not_require_manual_posting_toggle() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    gate_start = workflow.index("      - name: Enforce publication gates")
    gate_end = workflow.index("      - name: Archive predecessor ledger before durable v4 initialization")
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


def test_v4_ledger_durable_initialization_is_execution_gated_and_after_current_main_proof() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    # After the v4 cutover the publisher reads directly from the strict-schema
    # 30-post queue; local ledger materialization (the old depth-v3 step) is no
    # longer needed because the ledger is initialized on the state branch in
    # one protected block that lives after the current-main CI proof.
    validate_start = workflow.index("      - name: Validate immutable queue and strict ledger")
    quality_start = workflow.index("      - name: Require current-main exact-SHA repository CI proof")
    target_start = workflow.index("      - name: Validate read-only target configuration")
    preflight_start = workflow.index("      - name: Read-only bot and channel preflight")
    gate_start = workflow.index("      - name: Enforce publication gates")
    discard_start = workflow.index("      - name: Archive predecessor ledger before durable v4 initialization")
    writer_start = workflow.index("      - name: Enable state writer for one-time v4 ledger initialization")
    durable_start = workflow.index("      - name: Persist initialized v4 ledger to state branch")
    publication_writer_start = workflow.index("      - name: Enable publication ledger writer")

    assert (
        validate_start
        < quality_start
        < target_start
        < preflight_start
        < gate_start
        < discard_start
        < writer_start
        < durable_start
        < publication_writer_start
    )

    writer_step = workflow[writer_start:durable_start]
    assert "steps.active_release.outputs.needs_ledger_initialization == 'true'" in writer_step
    assert "steps.intent.outputs.do_publish == 'true'" in writer_step
    assert "persist-credentials: true" in writer_step

    durable_step = workflow[durable_start:publication_writer_start]
    assert "steps.active_release.outputs.needs_ledger_initialization == 'true'" in durable_step
    assert "steps.intent.outputs.do_publish == 'true'" in durable_step
    assert "INITIALIZE_NEW_LORDCHRIST_LEDGER" in durable_step
    assert 'git -C "$STATE_DIR" push origin "HEAD:$STATE_BRANCH"' in durable_step
    assert "remote-v4-ledger.json" in durable_step
    # The v4 ledger must not exist before initialization (we just discarded any
    # stale file); otherwise a previously-sealed ledger would silently rebind.
    assert "refusing ambiguous initialization" in durable_step

    # History is never deleted: the predecessor ledger is archived under a
    # digest-named path inside the state snapshot and committed together with
    # the fresh v4 ledger.
    archive_step = workflow[discard_start:writer_start]
    assert 'mv -- "$LEDGER_PATH" "$STATE_DIR/$archive_relative"' in archive_step
    assert "publication-ledger-archive-${old_digest}.json" in archive_step
    assert 'git -C "$STATE_DIR" add -- "$LEDGER_ARCHIVE_RELATIVE_PATH"' in durable_step

    before_quality = workflow[:quality_start]
    assert "persist-credentials: true" not in before_quality
    assert "INITIALIZE_NEW_LORDCHRIST_LEDGER" not in before_quality


def test_midday_slot_is_the_tuesday_friday_rich_article_lane() -> None:
    """The 12:00 slot exists for the L2 article track and for nothing else.

    Pinning time, cron, weekdays and lease here means a later "small" edit to the
    schedule JSON cannot silently turn the article hour into a third quote hour.
    """

    config = load_production_schedule(CONFIG_PATH)
    midday = config.slots["midday"]

    assert midday.time == "12:00"
    assert midday.cron == "0 9 * * 2,5"
    assert midday.iso_weekdays == (2, 5)
    # 12:00 + 240 minutes = 16:00 Moscow: the lease must close before the 19:17
    # historical rich boundary, exactly as the evening lease closes before midnight.
    assert midday.max_lateness_minutes == 240
    assert SLOT_LANES["midday"] == "rich_article"
    assert SLOT_LANES["morning"] == SLOT_LANES["evening"] == "quote"


def test_quote_lane_never_spends_the_midday_slot() -> None:
    """A quote run on the midday cron is refused instead of publishing a card."""

    config = load_production_schedule(CONFIG_PATH).model_copy(update={"enabled": True})
    tuesday_noon = datetime(2026, 10, 27, 9, 0, tzinfo=UTC)  # 12:00 Moscow

    quote_run = decide_scheduled_slot(config, event_schedule="0 9 * * 2,5", now=tuesday_noon, lane="quote")
    assert quote_run.active is False
    assert quote_run.slot is None
    assert quote_run.reason == "midday slot carries the rich_article lane, not quote"

    article_run = decide_scheduled_slot(config, event_schedule="0 9 * * 2,5", now=tuesday_noon, lane="rich_article")
    assert article_run.active is True
    assert article_run.slot == "midday"

    # And the reverse direction: the article lane may not borrow a quote hour.
    monday_morning = datetime(2026, 10, 26, 7, 0, tzinfo=UTC)  # 10:00 Moscow
    borrowed = decide_scheduled_slot(config, event_schedule="0 7 * * *", now=monday_morning, lane="rich_article")
    assert borrowed.active is False
    assert borrowed.reason == "morning slot carries the quote lane, not rich_article"


def test_midday_slot_is_only_eligible_on_tuesday_and_friday() -> None:
    config = load_production_schedule(CONFIG_PATH).model_copy(update={"enabled": True})

    wednesday_noon = datetime(2026, 10, 28, 9, 0, tzinfo=UTC)
    friday_noon = datetime(2026, 10, 30, 9, 0, tzinfo=UTC)
    tuesday_late = datetime(2026, 10, 27, 13, 0, tzinfo=UTC)  # 16:00 Moscow, lease closed

    assert (
        decide_scheduled_slot(config, event_schedule="0 9 * * 2,5", now=wednesday_noon, lane="rich_article").active
        is False
    )
    assert (
        decide_scheduled_slot(config, event_schedule="0 9 * * 2,5", now=friday_noon, lane="rich_article").slot
        == "midday"
    )
    stale = decide_scheduled_slot(config, event_schedule="0 9 * * 2,5", now=tuesday_late, lane="rich_article")
    assert stale.active is False
    assert "too stale" in stale.reason


def test_poster_runs_the_quote_lane_only() -> None:
    """The workflow must ask for the quote lane, otherwise it would publish at 12:00."""

    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert 'lane="quote"' in workflow
    assert '"0 9 * * 2,5"' in workflow
