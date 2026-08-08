from __future__ import annotations

from pathlib import Path

from video_channel_manager.telegram_channel_profile import load_channel_profile

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/svodka-reconcile-skipped-send.yml"
PROFILE = ROOT / "content/telegram/channels/svodka.json"


def test_reconciliation_is_manual_main_only_and_provider_free() -> None:
    profile = load_channel_profile(PROFILE)
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "schedule:" not in workflow
    assert "if: github.ref == 'refs/heads/main'" in workflow
    assert f"group: {profile.concurrency_group}" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "actions: read" in workflow
    assert "contents: write" in workflow
    assert "secrets." not in workflow
    assert "sendMessage" not in workflow
    assert "sendPoll" not in workflow
    assert "send-once" not in workflow


def test_reconciliation_requires_completed_matching_github_run_and_exact_provenance() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "source_run_id" in workflow
    assert "source_run_attempt" in workflow
    assert "RECONCILE-SKIPPED:" in workflow
    assert "verify-intent" in workflow
    assert "/actions/runs/{run_id}" in workflow
    assert "/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100" in workflow
    assert 'run.get("status") != "completed"' in workflow
    assert 'workflow_path = workflow_path.split("@", 1)[0]' in workflow
    assert '".github/workflows/svodka-canary.yml": (' in workflow
    assert '"workflow_dispatch"' in workflow
    assert '".github/workflows/svodka-scheduled-publisher.yml": (' in workflow
    assert '"schedule"' in workflow
    assert 'run.get("event") != expected_event' in workflow
    assert 'persist_steps[0].get("conclusion") != "success"' in workflow
    assert 'send_steps[0].get("conclusion") != "skipped"' in workflow
    assert 'run.get("head_sha")' in workflow
    assert 'dispatch["github_sha"]' in workflow
    assert "provider send step is not proven skipped; reconciliation is forbidden" in workflow


def test_reconciliation_writes_confirmed_absent_outcome_only_after_proof() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    proof_index = workflow.index("Prove original provider send step never ran")
    resolution_index = workflow.index("Resolve only the proven no-effect intent")
    assert proof_index < resolution_index
    assert 'provider_effect="confirmed_absent"' in workflow
    assert "retryable=True" in workflow
    assert "apply-outcome" in workflow
    assert "reconciliation-proof.json" in workflow
    assert "outcome.json" in workflow
