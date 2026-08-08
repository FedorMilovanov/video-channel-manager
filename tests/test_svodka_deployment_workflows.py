from __future__ import annotations

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LEDGER_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/svodka-ledger-init.yml"
CANARY_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/svodka-canary.yml"
APPROVED_RELEASE = REPOSITORY_ROOT / "content/telegram/svodka/approved-release-2026-08.json"


def test_ledger_initialization_is_manual_exact_and_provider_free() -> None:
    workflow = LEDGER_WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "schedule:" not in workflow
    assert "INITIALIZE:$REQUESTED_DIGEST" in workflow
    assert "approved-release-2026-08.json" in workflow
    assert "release.release_authorized" in workflow
    assert "state/svodka-telegram" in workflow
    assert "initialize-ledger" in workflow
    assert "sendMessage" not in workflow
    assert "sendPoll" not in workflow
    assert "send-once" not in workflow
    assert "secrets." not in workflow


def test_canary_is_one_exact_manual_dispatch_with_durable_intent_first() -> None:
    workflow = CANARY_WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "schedule:" not in workflow
    assert "CANARY:$REQUESTED_PUBLICATION_ID:$REQUESTED_DIGEST" in workflow
    assert "profile.provider_writes_authorized" in workflow
    assert "release.release_authorized" in workflow
    assert "approved-release-2026-08.json" in workflow
    assert "Fresh read-only target preflight" in workflow
    assert "Persist intent before Telegram mutation" in workflow
    assert "send-once" in workflow
    assert workflow.index("Persist intent before Telegram mutation") < workflow.index("send-once")
    assert "apply-outcome" in workflow
    assert "if: always()" not in workflow
    assert "!cancelled()" in workflow
    assert "initialize-ledger" not in workflow
    assert "state/svodka-telegram" in workflow


def test_live_release_is_not_committed_before_explicit_review() -> None:
    assert not APPROVED_RELEASE.exists()
