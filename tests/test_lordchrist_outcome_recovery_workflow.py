from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/lordchrist-reconcile-provider-outcome.yml"
PUBLISHER = ROOT / ".github/workflows/lordchrist-telegram-poster.yml"


def test_lordchrist_outcome_recovery_is_manual_main_only_and_provider_free() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "schedule:" not in text
    assert "if: github.ref == 'refs/heads/main'" in text
    assert "actions: read" in text
    assert "contents: write" in text
    assert "group: lordchrist-telegram-publisher" in text
    assert "cancel-in-progress: false" in text
    assert "queue: max" in text
    assert "runs-on: ubuntu-24.04" in text
    assert "secrets." not in text
    assert "LORDCHRIST_TELEGRAM_BOT_TOKEN" not in text
    assert "sendMessage" not in text
    assert "telegram_cli \\\n            send" not in text


def test_recovery_requires_exact_confirmation_dispatch_and_archived_outcome() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "RECOVER-LORDCHRIST-OUTCOME:$SOURCE_RUN_ID:$SOURCE_RUN_ATTEMPT:$REQUESTED_PUBLICATION_ID:$REQUESTED_QUEUE_DIGEST" in text
    assert "verify-intent" in text
    assert "verify-rendered" in text
    assert "telegram_lordchrist_outcome_artifact" in text
    assert "telegram_lordchrist_outcome_cli" in text
    assert "outcome-recovery-proof.json" in text
    assert "provider-outcome.json" in text


def test_recovery_rechecks_intent_and_runtime_freshness_before_durable_commit() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    first_verify = text.index("Verify exact unresolved persisted dispatch evidence")
    download = text.index("Prove and download exact archived provider outcome")
    writer = text.index("Enable exact Lordchrist state writer")
    second_verify = text.index("Re-verify durable intent after writer checkout")
    apply = text.index("Apply archived outcome without provider access")
    persist = text.index("Persist exact recovered state and evidence")
    current_main = text.index("git ls-remote origin refs/heads/main", persist)
    commit = text.index("Recover Lordchrist provider outcome for run", persist)
    assert first_verify < download < writer < second_verify < apply < persist < current_main < commit
    assert '[[ "$current_main_sha" == "$GITHUB_SHA" ]]' in text


def test_publisher_and_recovery_share_the_exact_artifact_contract() -> None:
    publisher = PUBLISHER.read_text(encoding="utf-8")
    recovery = WORKFLOW.read_text(encoding="utf-8")
    assert "Archive exact Lordchrist provider outcome before state mutation" in publisher
    assert "lordchrist-provider-outcome-${{ github.run_id }}-${{ github.run_attempt }}" in publisher
    assert "lordchrist-outcome.json" in publisher
    assert "source_run_id" in recovery
    assert "source_run_attempt" in recovery
