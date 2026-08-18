from pathlib import Path


WORKFLOW = Path(".github/workflows/svodka-rich-reconcile-message-28.yml")


def test_reconciliation_persists_diagnostic_before_hard_stop_or_state_proof() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "continue-on-error: true" in workflow
    assert "Persist provider-free reconciliation diagnostic" in workflow
    assert "reconciliation-diagnostics/${{ github.run_id }}-${{ github.run_attempt }}.json" in workflow
    assert 'provider_access_performed": False' in workflow
    assert 'provider_write_performed": False' in workflow
    assert 'replay_performed": False' in workflow
    assert "Stop after durable diagnostic if reconciliation failed" in workflow

    reconcile = workflow.index("Reconcile archived message 28 without provider access")
    diagnostic = workflow.index("Persist provider-free reconciliation diagnostic")
    stop = workflow.index("Stop after durable diagnostic if reconciliation failed")
    persist = workflow.index("Persist only reconciled ledger and proof")
    assert reconcile < diagnostic < stop < persist


def test_reconciliation_diagnostic_workflow_still_has_no_telegram_surface() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "secrets." not in workflow
    assert "SVODKA_TELEGRAM_BOT_TOKEN" not in workflow
    assert "sendRichMessage" not in workflow
    assert "sendMessage" not in workflow
