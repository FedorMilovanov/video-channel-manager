from __future__ import annotations

from pathlib import Path

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_release import load_release
from video_channel_manager.telegram_target_binding import load_target_binding

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LEDGER_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/svodka-ledger-init.yml"
CANARY_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/svodka-canary.yml"
SKIP_EXPIRED_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/svodka-skip-expired.yml"
SCHEDULED_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/svodka-scheduled-publisher.yml"
PROFILE_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka.json"
BINDING_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka-target-binding.json"
APPROVED_RELEASE = REPOSITORY_ROOT / "content/telegram/svodka/approved-release-2026-08.json"


def test_ledger_initialization_is_manual_exact_and_provider_free() -> None:
    profile = load_channel_profile(PROFILE_PATH)
    workflow = LEDGER_WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "schedule:" not in workflow
    assert "INITIALIZE:$REQUESTED_DIGEST" in workflow
    assert "approved-release-2026-08.json" in workflow
    assert "release.release_authorized" in workflow
    assert "state/svodka-telegram" in workflow
    assert f"group: {profile.concurrency_group}" in workflow
    assert "initialize-ledger" in workflow
    assert "sendMessage" not in workflow
    assert "sendPoll" not in workflow
    assert "send-once" not in workflow
    assert "secrets." not in workflow


def test_canary_is_one_exact_fresh_manual_dispatch_with_durable_intent_first() -> None:
    profile = load_channel_profile(PROFILE_PATH)
    workflow = CANARY_WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "schedule:" not in workflow
    assert "CANARY:$REQUESTED_PUBLICATION_ID:$REQUESTED_DIGEST" in workflow
    assert "actions: read" in workflow
    assert "Require current-main exact-SHA Svodka quality proof" in workflow
    assert "telegram_github_quality_gate" in workflow
    assert '--sha "$GITHUB_SHA"' in workflow
    assert "MAX_PUBLICATION_LAG_MINUTES: 120" in workflow
    assert "Require fresh strict-next canary window" in workflow
    assert "telegram_publication_freshness next" in workflow
    assert '--ledger "$LEDGER_PATH"' in workflow
    assert '--publication-id "$REQUESTED_PUBLICATION_ID"' in workflow
    assert "profile.provider_writes_authorized" in workflow
    assert "release.release_authorized" in workflow
    assert "approved-release-2026-08.json" in workflow
    assert "Fresh read-only target preflight" in workflow
    assert workflow.index("Require current-main exact-SHA Svodka quality proof") < workflow.index(
        "Fresh read-only target preflight"
    )
    assert workflow.index("Require fresh strict-next canary window") < workflow.index("Fresh read-only target preflight")
    assert "Persist intent before Telegram mutation" in workflow
    assert "Re-prove current-main quality immediately before Telegram mutation" in workflow
    assert "send-once" in workflow
    persist_index = workflow.index("Persist intent before Telegram mutation")
    reproof_index = workflow.index("Re-prove current-main quality immediately before Telegram mutation")
    send_index = workflow.index("Send exactly one canary payload")
    assert persist_index < reproof_index < send_index
    assert "apply-outcome" in workflow
    assert "if: always()" not in workflow
    assert "!cancelled()" in workflow
    assert "initialize-ledger" not in workflow
    assert "state/svodka-telegram" in workflow
    assert f"group: {profile.concurrency_group}" in workflow


def test_stale_slot_recovery_is_manual_state_only_and_current_main_proven() -> None:
    profile = load_channel_profile(PROFILE_PATH)
    workflow = SKIP_EXPIRED_WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "schedule:" not in workflow
    assert "SKIP-EXPIRED:$REQUESTED_DIGEST" in workflow
    assert "skip-expired" in workflow
    assert "actions: read" in workflow
    assert "telegram_github_quality_gate" in workflow
    assert '--sha "$GITHUB_SHA"' in workflow
    assert workflow.index("telegram_github_quality_gate") < workflow.index(
        'git -C "$STATE_DIR" commit -m "Skip expired Svodka publication windows [skip ci]"'
    )
    assert "state/svodka-telegram" in workflow
    assert f"group: {profile.concurrency_group}" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "sendMessage" not in workflow
    assert "sendPoll" not in workflow
    assert "send-once" not in workflow
    assert "secrets." not in workflow


def test_scheduler_mutation_is_cron_only_quality_proven_and_freshness_bounded() -> None:
    profile = load_channel_profile(PROFILE_PATH)
    workflow = SCHEDULED_WORKFLOW.read_text(encoding="utf-8")

    assert "schedule:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "if: github.event_name == 'schedule' && github.ref == 'refs/heads/main'" in workflow
    assert "actions: read" in workflow
    assert "Require current-main exact-SHA Svodka quality proof" in workflow
    assert "telegram_github_quality_gate" in workflow
    assert '--sha "$GITHUB_SHA"' in workflow
    assert "MAX_PUBLICATION_LAG_MINUTES: 120" in workflow
    assert "Check strict-next publication freshness" in workflow
    assert "telegram_publication_freshness next" in workflow
    assert "steps.freshness.outputs.fresh == 'true'" in workflow
    assert workflow.index("Require current-main exact-SHA Svodka quality proof") < workflow.index(
        "Fresh read-only target preflight"
    )
    assert workflow.index("Check strict-next publication freshness") < workflow.index("Fresh read-only target preflight")
    assert "Persist scheduled intent before Telegram mutation" in workflow
    assert "Re-prove current-main quality immediately before Telegram mutation" in workflow
    persist_index = workflow.index("Persist scheduled intent before Telegram mutation")
    reproof_index = workflow.index("Re-prove current-main quality immediately before Telegram mutation")
    send_index = workflow.index("Send exactly one scheduled payload")
    assert persist_index < reproof_index < send_index
    assert f"group: {profile.concurrency_group}" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "send-once" in workflow


def test_all_svodka_state_writers_share_profile_concurrency_group() -> None:
    profile = load_channel_profile(PROFILE_PATH)
    expected = f"group: {profile.concurrency_group}"

    for workflow_path in (LEDGER_WORKFLOW, SKIP_EXPIRED_WORKFLOW, CANARY_WORKFLOW, SCHEDULED_WORKFLOW):
        workflow = workflow_path.read_text(encoding="utf-8")
        assert expected in workflow, workflow_path.name
        assert "cancel-in-progress: false" in workflow, workflow_path.name


def test_committed_live_release_if_present_is_exact_and_authorized() -> None:
    if not APPROVED_RELEASE.exists():
        return

    profile = load_channel_profile(PROFILE_PATH)
    binding = load_target_binding(BINDING_PATH, profile)
    release = load_release(APPROVED_RELEASE)

    assert release.release_authorized is True
    assert release.reviewed_candidate_sha256 is not None
    assert release.project_key == profile.project_key
    assert release.channel_username == profile.channel_username
    assert release.profile_sha256 == profile.digest
    assert release.target_binding_sha256 == binding.digest
    assert release.chat_id == binding.chat_id
    assert release.bot_id == binding.bot_id
    assert release.bot_username == binding.bot_username
