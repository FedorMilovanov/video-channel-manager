from __future__ import annotations

from pathlib import Path

from video_channel_manager.svodka_approval_cli import (
    load_svodka_release_approval,
    materialize_svodka_approved_release,
)
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_release import load_release
from video_channel_manager.telegram_target_binding import load_target_binding

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LEDGER_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/svodka-ledger-init.yml"
CANARY_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/svodka-canary.yml"
CUSTOM_EMOJI_CANARY_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/svodka-custom-emoji-capability-canary.yml"
NATIVE_RICH_CANARY_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/svodka-native-rich-message-canary.yml"
RICH_PRODUCTION_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/svodka-rich-production.yml"
SKIP_EXPIRED_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/svodka-skip-expired.yml"
SCHEDULED_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/svodka-scheduled-publisher.yml"
RECONCILE_SKIPPED_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/svodka-reconcile-skipped-send.yml"
RECONCILE_OUTCOME_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/svodka-reconcile-provider-outcome.yml"
PROFILE_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka.json"
BINDING_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka-target-binding.json"
QUEUE_PATH = REPOSITORY_ROOT / "content/telegram/svodka/draft-14-posts-2026-08.json"
APPROVAL_PATH = REPOSITORY_ROOT / "content/telegram/svodka/release-approval-2026-08.json"

RELEASE_STATE_WRITER_WORKFLOWS = (
    LEDGER_WORKFLOW,
    SKIP_EXPIRED_WORKFLOW,
    CANARY_WORKFLOW,
    SCHEDULED_WORKFLOW,
    RECONCILE_SKIPPED_WORKFLOW,
    RECONCILE_OUTCOME_WORKFLOW,
)
STATE_WRITER_WORKFLOWS = RELEASE_STATE_WRITER_WORKFLOWS + (
    CUSTOM_EMOJI_CANARY_WORKFLOW,
    NATIVE_RICH_CANARY_WORKFLOW,
    RICH_PRODUCTION_WORKFLOW,
)


def _workflow(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _assert_materialized_release_contract(workflow: str) -> None:
    assert "release-approval-2026-08.json" in workflow
    assert "video_channel_manager.svodka_approval_cli" in workflow
    assert '--approval "$APPROVAL_PATH"' in workflow
    assert "RELEASE_PATH: .runtime/svodka-approved-release.json" in workflow


def _assert_dual_current_main_quality(workflow: str) -> None:
    assert "svodka-quality.yml" in workflow
    assert "svodka-approved-release-quality.yml" in workflow
    assert '--sha "$GITHUB_SHA"' in workflow


def test_all_state_writers_share_lossless_serialization_contract() -> None:
    profile = load_channel_profile(PROFILE_PATH)
    expected_group = f"group: {profile.concurrency_group}"
    expected_names = {path.name for path in STATE_WRITER_WORKFLOWS}
    workflows_dir = REPOSITORY_ROOT / ".github/workflows"
    discovered = {path for path in workflows_dir.glob("*.yml") if expected_group in _workflow(path)}

    assert {path.name for path in discovered} == expected_names
    assert discovered == set(STATE_WRITER_WORKFLOWS)
    for path in discovered:
        workflow = _workflow(path)
        assert "cancel-in-progress: false" in workflow, path.name
        assert "queue: max" in workflow, path.name
        assert "runs-on: ubuntu-24.04" in workflow, path.name
    for path in RELEASE_STATE_WRITER_WORKFLOWS:
        _assert_materialized_release_contract(_workflow(path))


def test_custom_emoji_capability_canary_is_manual_serialized_and_release_independent() -> None:
    workflow = _workflow(CUSTOM_EMOJI_CANARY_WORKFLOW)

    assert "workflow_dispatch:" in workflow
    assert "schedule:" not in workflow
    assert "push:" not in workflow
    assert "CUSTOM-EMOJI-CANARY:@deep_info_life:ONE-POST" in workflow
    assert "group: svodka-telegram-publisher" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "queue: max" in workflow
    _assert_dual_current_main_quality(workflow)
    assert "release-approval-2026-08.json" not in workflow
    assert "svodka_approval_cli" not in workflow
    assert "Persist intent before Telegram mutation" in workflow
    assert "Archive exact canary outcome before durable-state mutation" in workflow
    assert "Persist exact canary outcome and block blind retry" in workflow
    assert "Refuse any second capability-canary attempt" in workflow
    assert "telegram_custom_emoji_canary send" in workflow
    assert "sendMessage" not in workflow
    assert "deleteMessage" not in workflow

    persist_index = workflow.index("Persist intent before Telegram mutation")
    reproof_index = workflow.index("Re-prove current-main quality immediately before Telegram mutation")
    send_index = workflow.index("Send exactly one visible custom-emoji capability post")
    archive_index = workflow.index("Archive exact canary outcome before durable-state mutation")
    apply_index = workflow.index("Persist exact canary outcome and block blind retry")
    assert persist_index < reproof_index < send_index < archive_index < apply_index


def test_native_rich_canary_is_manual_main_only_serialized_and_release_independent() -> None:
    workflow = _workflow(NATIVE_RICH_CANARY_WORKFLOW)

    assert "workflow_dispatch:" in workflow
    assert "schedule:" not in workflow
    assert "push:" not in workflow
    assert "RICH-CANARY:@deep_info_life:ONE-ARTICLE" in workflow
    assert "if: github.ref == 'refs/heads/main'" in workflow
    assert "group: svodka-telegram-publisher" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "queue: max" in workflow
    _assert_dual_current_main_quality(workflow)
    assert "release-approval-2026-08.json" not in workflow
    assert "publication-ledger.json" not in workflow
    assert "svodka_approval_cli" not in workflow
    assert "Refuse every second native Rich Message canary run" in workflow
    assert "Persist durable intent before any Telegram mutation" in workflow
    assert "Dispatch exactly one native sendRichMessage mutation" in workflow
    assert "Archive exact provider outcome before durable outcome" in workflow
    assert "Persist durable outcome and permanently block blind retry" in workflow
    assert "sendMessage" not in workflow
    assert "deleteMessage" not in workflow
    assert "editMessageText" not in workflow

    persist_index = workflow.index("Persist durable intent before any Telegram mutation")
    reproof_index = workflow.index("Re-prove exact current-main quality immediately before mutation")
    send_index = workflow.index("Dispatch exactly one native sendRichMessage mutation")
    archive_index = workflow.index("Archive exact provider outcome before durable outcome")
    apply_index = workflow.index("Persist durable outcome and permanently block blind retry")
    assert persist_index < reproof_index < send_index < archive_index < apply_index


def test_rich_production_is_serialized_release_specific_and_single_mutation() -> None:
    workflow = _workflow(RICH_PRODUCTION_WORKFLOW)

    assert "schedule:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "push:" not in workflow
    assert workflow.count("cron:") == 6
    assert 'cron: "30 16 11 8 *"' in workflow
    assert 'cron: "17 17 11 8 *"' in workflow
    assert 'cron: "30 7 12-18 8 *"' in workflow
    assert 'cron: "17 8 12-18 8 *"' in workflow
    assert 'cron: "30 16 12-17 8 *"' in workflow
    assert 'cron: "17 17 12-17 8 *"' in workflow
    assert "group: svodka-telegram-publisher" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "queue: max" in workflow
    _assert_dual_current_main_quality(workflow)
    assert "production-release-2026-08.json" in workflow
    assert "rich-production-ledger.json" in workflow
    assert "publication-ledger.json" not in workflow
    assert "release-approval-2026-08.json" not in workflow
    assert "svodka_approval_cli" not in workflow
    assert "Persist intent and evidence before Telegram mutation" in workflow
    assert "Re-fetch identical media bytes immediately before mutation" in workflow
    assert "Send exactly one native Rich Message" in workflow
    assert "svodka_rich_production send" in workflow
    assert "Archive exact provider outcome before ledger mutation" in workflow
    assert "Apply exact outcome and persist terminal state" in workflow
    assert "telegram_multichannel_cli send-once" not in workflow
    assert "/sendMessage" not in workflow

    persist_index = workflow.index("Persist intent and evidence before Telegram mutation")
    reproof_index = workflow.index("Re-prove quality immediately before mutation")
    media_recheck_index = workflow.index("Re-fetch identical media bytes immediately before mutation")
    send_index = workflow.index("Send exactly one native Rich Message")
    archive_index = workflow.index("Archive exact provider outcome before ledger mutation")
    apply_index = workflow.index("Apply exact outcome and persist terminal state")
    assert persist_index < reproof_index < media_recheck_index < send_index < archive_index < apply_index


def test_ledger_initialization_is_manual_exact_provider_free_and_dual_quality_proven() -> None:
    workflow = _workflow(LEDGER_WORKFLOW)

    assert "workflow_dispatch:" in workflow
    assert "schedule:" not in workflow
    assert "INITIALIZE:$REQUESTED_DIGEST" in workflow
    assert "release.release_authorized" in workflow
    assert "initialize-ledger" in workflow
    _assert_materialized_release_contract(workflow)
    _assert_dual_current_main_quality(workflow)
    initialize_index = workflow.index("initialize-ledger")
    reproof_index = workflow.index("telegram_github_quality_gate", initialize_index)
    commit_index = workflow.index('git -C "$STATE_DIR" commit -m "Initialize Svodka publication ledger [skip ci]"')
    assert initialize_index < reproof_index < commit_index
    assert "sendMessage" not in workflow
    assert "sendPoll" not in workflow
    assert "send-once" not in workflow
    assert "secrets." not in workflow


def test_canary_is_exact_fresh_manual_dispatch_with_durable_intent_first() -> None:
    workflow = _workflow(CANARY_WORKFLOW)

    assert "workflow_dispatch:" in workflow
    assert "schedule:" not in workflow
    assert "CANARY:$REQUESTED_PUBLICATION_ID:$REQUESTED_DIGEST" in workflow
    _assert_materialized_release_contract(workflow)
    _assert_dual_current_main_quality(workflow)
    assert "MAX_PUBLICATION_LAG_MINUTES: 120" in workflow
    assert "Require fresh strict-next canary window" in workflow
    assert "telegram_publication_freshness next" in workflow
    assert '--publication-id "$REQUESTED_PUBLICATION_ID"' in workflow
    assert "profile.provider_writes_authorized" in workflow
    assert "release.release_authorized" in workflow
    assert "Fresh read-only target preflight" in workflow
    assert "Persist intent before Telegram mutation" in workflow
    assert "Re-prove current-main quality immediately before Telegram mutation" in workflow
    assert "send-once" in workflow

    persist_index = workflow.index("Persist intent before Telegram mutation")
    reproof_index = workflow.index("Re-prove current-main quality immediately before Telegram mutation")
    send_index = workflow.index("Send exactly one canary payload")
    archive_index = workflow.index("Archive exact provider outcome before state mutation")
    apply_index = workflow.index("Apply and persist exact provider outcome")
    assert persist_index < reproof_index < send_index < archive_index < apply_index
    assert "svodka-provider-outcome-${{ github.run_id }}-${{ github.run_attempt }}" in workflow
    assert "if-no-files-found: error" in workflow
    assert "retention-days: 30" in workflow
    assert "include-hidden-files: true" in workflow
    assert "if: always()" not in workflow
    assert "!cancelled()" in workflow
    assert "initialize-ledger" not in workflow


def test_stale_slot_recovery_is_manual_state_only_and_dual_quality_proven() -> None:
    workflow = _workflow(SKIP_EXPIRED_WORKFLOW)

    assert "workflow_dispatch:" in workflow
    assert "schedule:" not in workflow
    assert "SKIP-EXPIRED:$REQUESTED_DIGEST" in workflow
    assert "skip-expired" in workflow
    _assert_materialized_release_contract(workflow)
    _assert_dual_current_main_quality(workflow)
    assert workflow.index("telegram_github_quality_gate") < workflow.index(
        'git -C "$STATE_DIR" commit -m "Skip expired Svodka publication windows [skip ci]"'
    )
    assert "sendMessage" not in workflow
    assert "sendPoll" not in workflow
    assert "send-once" not in workflow
    assert "secrets." not in workflow


def test_scheduler_is_canary_gated_freshness_bounded_and_covers_full_pilot() -> None:
    workflow = _workflow(SCHEDULED_WORKFLOW)

    assert workflow.count("cron:") == 4
    assert 'cron: "30 7 10-16 8 *"' in workflow
    assert 'cron: "17 8 10-16 8 *"' in workflow
    assert 'cron: "30 16 10-16 8 *"' in workflow
    assert 'cron: "17 17 10-16 8 *"' in workflow
    assert "if: github.event_name == 'schedule' && github.ref == 'refs/heads/main'" in workflow
    _assert_materialized_release_contract(workflow)
    _assert_dual_current_main_quality(workflow)
    assert "Require verified manual canary before scheduler activity" in workflow
    assert 'entry.dispatch_mode == "manual"' in workflow
    assert 'entry.provider_effect == "verified"' in workflow
    assert "steps.canary.outputs.ready == 'true'" in workflow
    assert "MAX_PUBLICATION_LAG_MINUTES: 120" in workflow
    assert "telegram_publication_freshness next" in workflow
    assert "steps.freshness.outputs.fresh == 'true'" in workflow

    canary_index = workflow.index("Require verified manual canary before scheduler activity")
    skip_index = workflow.index("Skip expired windows before any provider operation")
    freshness_index = workflow.index("Check strict-next publication freshness")
    preflight_index = workflow.index("Fresh read-only target preflight")
    persist_index = workflow.index("Persist scheduled intent before Telegram mutation")
    reproof_index = workflow.index("Re-prove current-main quality immediately before Telegram mutation")
    send_index = workflow.index("Send exactly one scheduled payload")
    archive_index = workflow.index("Archive exact provider outcome before state mutation")
    apply_index = workflow.index("Apply and persist exact scheduled provider outcome")
    assert canary_index < skip_index < freshness_index < preflight_index < persist_index < reproof_index < send_index
    assert send_index < archive_index < apply_index
    assert "send-once" in workflow


def test_skipped_send_reconciliation_is_provider_free_and_quality_proven() -> None:
    workflow = _workflow(RECONCILE_SKIPPED_WORKFLOW)

    assert "workflow_dispatch:" in workflow
    assert "schedule:" not in workflow
    assert "RECONCILE-SKIPPED:" in workflow
    _assert_materialized_release_contract(workflow)
    _assert_dual_current_main_quality(workflow)
    assert "provider send step is not proven skipped; reconciliation is forbidden" in workflow
    assert 'provider_effect="confirmed_absent"' in workflow
    assert "retryable=True" in workflow
    assert "sendMessage" not in workflow
    assert "sendPoll" not in workflow
    assert "send-once" not in workflow
    assert "secrets." not in workflow


def test_provider_outcome_reconciliation_requires_archived_exact_provider_evidence() -> None:
    workflow = _workflow(RECONCILE_OUTCOME_WORKFLOW)

    assert "workflow_dispatch:" in workflow
    assert "schedule:" not in workflow
    assert "RECONCILE-OUTCOME:" in workflow
    _assert_materialized_release_contract(workflow)
    _assert_dual_current_main_quality(workflow)
    assert "download-artifact" in workflow
    assert "telegram_github_outcome_artifact" in workflow
    assert "apply-outcome" in workflow
    assert "sendMessage" not in workflow
    assert "sendPoll" not in workflow
    assert "send-once" not in workflow
    assert "secrets." not in workflow


def test_svodka_release_approval_still_materializes_frozen_legacy_release() -> None:
    profile = load_channel_profile(PROFILE_PATH)
    binding = load_target_binding(BINDING_PATH, profile)
    approval = load_svodka_release_approval(APPROVAL_PATH)
    materialized = materialize_svodka_approved_release(
        profile=profile,
        binding=binding,
        approval=approval,
        queue_path=QUEUE_PATH,
    )
    release = load_release(materialized)

    assert release.release_id == "svodka-pilot-2026-08"
    assert release.digest == "sha256:959a42e914acedc6969550ba842a12d1a2b174c940497d8a98f4ab8e2e63cdce"
