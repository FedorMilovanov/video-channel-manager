"""The completed Charnock QC operation stays owner-only and read-only."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/lordchrist-charnock-qc-reissue.yml"


def _source() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_manual_single_page_read_only_dispatch() -> None:
    text = _source()
    assert "workflow_dispatch:" in text
    for event in ("schedule:", "push:", "pull_request:", "repository_dispatch:"):
        assert event not in text
    for page in ("'01b'", "'02'", "'07'", "'13'"):
        assert page in text
    assert "default: dry-run" in text
    assert "          - reconcile" in text
    assert "          - execute" not in text
    assert '"$MODE" == "execute"' not in text
    assert '"$MODE" == "reconcile"' in text
    assert "run-name: charnock-qc-readonly-" in text


def test_owner_main_and_exact_head_gate_are_preserved() -> None:
    text = _source()
    assert "github.actor == 'FedorMilovanov'" in text
    assert "github.repository == 'FedorMilovanov/video-channel-manager'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert '"$GITHUB_RUN_ATTEMPT" == "1"' in text
    assert 'gh api "repos/$GITHUB_REPOSITORY/commits/main" --jq .sha' in text


def test_no_edit_secrets_provider_mutation_or_write_permissions() -> None:
    text = _source()
    for forbidden in (
        "LORDCHRIST_TELEGRAPH_ACCESS_TOKEN",
        "LORDCHRIST_TELEGRAM_BOT_TOKEN",
        "sendMessage",
        "createPage",
        "editPage",
        "--execute",
        "--confirm",
        "contents: write",
        "actions: write",
    ):
        assert forbidden not in text
    assert "cancel-in-progress: false" in text
    assert "persist-credentials: false" in text
    assert "contents: read" in text


def test_retirement_registry_prohibits_only_the_consumed_edit_mode() -> None:
    registry = json.loads((ROOT / "docs/operations/retirement-registry-v1.json").read_text(encoding="utf-8"))
    entries = {entry["id"]: entry for entry in registry["retired_families"]}
    retired = entries["lordchrist-charnock-qc-page-edit-20261121"]
    assert retired["kind"] == "repository_provider_mutation_mode"
    assert retired["status"] == "retired_non_executable"
    assert retired["execution_prohibited"] is True
    assert retired["issues"] == [997]
    assert "read-only comparison only" in retired["replacement"]
    assert "old SHAs and external copies are not stopped" in retired["reason"]
    assert registry["provider_writes_authorized"] is False


def test_one_read_only_receipt_uploaded_even_when_comparison_fails() -> None:
    text = _source()
    assert "python -m scripts.charnock_telegraph_qc_reissue" in text
    assert "--reconcile" in text
    assert "--media-base-url" in text
    assert "--receipt-dir" in text
    assert "set -euo pipefail" in text
    assert 'if [[ "$MODE" == "reconcile" ]]' in text
    assert "if ! python -m scripts.charnock_telegraph_qc_reissue" in text
    assert "find" in text and "wc -l" in text and "-eq 1" in text
    assert "if: always() && inputs.mode == 'reconcile'" in text
    assert "actions/upload-artifact" in text
    assert "charnock-qc-readonly-result-${REVIEWED_PAGE}" in text
    assert "charnock-qc-reissue-receipt-${{ inputs.page }}" in text
