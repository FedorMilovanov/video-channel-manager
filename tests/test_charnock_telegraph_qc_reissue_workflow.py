"""Owner-only, manual-only exposure guards for the QC reissue workflow."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/lordchrist-charnock-qc-reissue.yml"


def _source() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_manual_single_page_dispatch_only() -> None:
    text = _source()
    assert "workflow_dispatch:" in text
    for event in ("schedule:", "push:", "pull_request:", "repository_dispatch:"):
        assert event not in text
    for page in ("'01b'", "'02'", "'07'", "'13'"):
        assert page in text
    assert "default: dry-run" in text
    assert "          - reconcile" in text
    assert '"$MODE" == "execute"' in text
    assert '"$MODE" == "reconcile"' in text
    assert "run-name: charnock-qc-reissue-" in text


def test_owner_main_and_explicit_confirmation_gate() -> None:
    text = _source()
    assert "github.actor == 'FedorMilovanov'" in text
    assert "github.repository == 'FedorMilovanov/video-channel-manager'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert "inputs.confirm == 'REISSUE_EXISTING_CHARNOCK_PAGE_ONCE'" in text
    assert '"$GITHUB_RUN_ATTEMPT" == "1"' in text
    assert 'gh api "repos/$GITHUB_REPOSITORY/commits/main" --jq .sha' in text


def test_no_page_creation_no_telegram_and_no_write_token() -> None:
    text = _source()
    assert "secrets.LORDCHRIST_TELEGRAPH_ACCESS_TOKEN" in text
    assert "secrets.LORDCHRIST_TELEGRAM_BOT_TOKEN" not in text
    assert "sendMessage" not in text
    assert "createPage" not in text
    assert "cancel-in-progress: false" in text
    assert "persist-credentials: false" in text
    assert "contents: read" in text
    assert "contents: write" not in text


def test_one_pinned_script_exactly_one_receipt_and_upload() -> None:
    text = _source()
    assert "python -m scripts.charnock_telegraph_qc_reissue" in text
    assert "--execute" in text
    assert "--confirm REISSUE_EXISTING_CHARNOCK_PAGE_ONCE" in text
    assert "--media-base-url" in text
    assert "--receipt-dir" in text
    assert 'if [[ "$MODE" == "execute" ]]' in text
    assert "find" in text and "wc -l" in text and "-eq 1" in text
    assert "actions/upload-artifact" in text
    assert "charnock-qc-reissue-result-${REVIEWED_PAGE}" in text
    assert "charnock-qc-reissue-receipt-${{ inputs.page }}" in text
    assert "::notice title=charnock-qc-reissue-" in text
