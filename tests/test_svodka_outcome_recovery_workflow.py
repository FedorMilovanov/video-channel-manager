from __future__ import annotations

from pathlib import Path

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_github_outcome_artifact import PROVIDER_WORKFLOWS

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/svodka-reconcile-provider-outcome.yml"
CANARY_WORKFLOW = ROOT / ".github/workflows/svodka-canary.yml"
SCHEDULED_WORKFLOW = ROOT / ".github/workflows/svodka-scheduled-publisher.yml"
PROFILE = ROOT / "content/telegram/channels/svodka.json"


def test_archived_outcome_recovery_is_manual_main_only_and_provider_free() -> None:
    profile = load_channel_profile(PROFILE)
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "schedule:" not in workflow
    assert "if: github.ref == 'refs/heads/main'" in workflow
    assert "actions: read" in workflow
    assert "contents: write" in workflow
    assert f"group: {profile.concurrency_group}" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "secrets." not in workflow
    assert "sendMessage" not in workflow
    assert "sendPoll" not in workflow
    assert "send-once" not in workflow
    assert "SVODKA_TELEGRAM_BOT_TOKEN" not in workflow


def test_archived_outcome_recovery_requires_exact_source_run_artifact_and_dispatch() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert (
        "RECONCILE-OUTCOME:$SOURCE_RUN_ID:$SOURCE_RUN_ATTEMPT:$REQUESTED_PUBLICATION_ID:$REQUESTED_DIGEST" in workflow
    )
    assert "durable provider outcome already exists; archived-outcome recovery is forbidden" in workflow
    assert "verify-intent" in workflow
    assert "telegram_github_outcome_artifact prove" in workflow
    assert "telegram_github_outcome_artifact fetch" in workflow
    assert "telegram_github_outcome_artifact validate" in workflow
    assert "actions/download-artifact@" not in workflow
    assert '--proof "$PROOF_PATH"' in workflow
    assert '--outcome-output "$RECOVERED_OUTCOME_PATH"' in workflow
    assert "GH_TOKEN: ${{ github.token }}" in workflow
    assert "provider outcome artifact must contain exactly one file" in workflow
    assert "outcome-recovery-proof.json" in workflow


def test_provider_workflow_step_contract_matches_recovery_verifier() -> None:
    canary = CANARY_WORKFLOW.read_text(encoding="utf-8")
    scheduled = SCHEDULED_WORKFLOW.read_text(encoding="utf-8")

    contracts = {
        ".github/workflows/svodka-canary.yml": ("workflow_dispatch", canary),
        ".github/workflows/svodka-scheduled-publisher.yml": ("schedule", scheduled),
    }
    assert set(PROVIDER_WORKFLOWS) == set(contracts)
    for workflow_path, (expected_event, workflow) in contracts.items():
        contract = PROVIDER_WORKFLOWS[workflow_path]
        assert contract.event == expected_event
        assert contract.persist_step in workflow
        assert contract.send_step in workflow
        assert contract.archive_step in workflow
        assert contract.final_state_step in workflow


def test_archived_outcome_recovery_persists_only_after_provenance_without_current_quality_dependency() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    prove_index = workflow.index("Prove source run and archived outcome provenance")
    download_index = workflow.index("Download exact archived provider outcome")
    validate_index = workflow.index("Validate recovered outcome against persisted dispatch")
    apply_index = workflow.index("Apply archived outcome without provider access")
    persist_index = workflow.index("Persist recovered provider outcome state")
    current_main_index = workflow.index('git -C "$STATE_DIR" ls-remote origin refs/heads/main')
    commit_index = workflow.index("Recover archived Svodka provider outcome for run")

    assert prove_index < download_index < validate_index < apply_index < persist_index < current_main_index < commit_index
    assert '[[ "$current_main_sha" == "$GITHUB_SHA" ]]' in workflow
    assert "recovery runtime SHA is no longer current main" in workflow
    assert "telegram_github_quality_gate" not in workflow
    assert "apply-outcome" in workflow
    assert "validate-ledger" in workflow
