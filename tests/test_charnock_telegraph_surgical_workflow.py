"""Owner-only, manual-only exposure guards for the Charnock in-place workflow."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/lordchrist-charnock-telegraph-inplace.yml"


def _source() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_only_manual_single_page_dispatch() -> None:
    text = _source()
    assert "workflow_dispatch:" in text
    assert "schedule:" not in text
    assert "push:" not in text
    assert "pull_request:" not in text
    assert "  - '03'" in text
    assert "  - history-01" in text
    assert "inputs.page == '03'" in text
    assert "inputs.page == 'history-01'" in text


def test_owner_main_and_explicit_confirmation_gate() -> None:
    text = _source()
    assert "github.actor == 'FedorMilovanov'" in text
    assert "github.repository == 'FedorMilovanov/video-channel-manager'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert "inputs.confirm == 'EDIT_EXISTING_CHARNOCK_PAGE_ONCE'" in text
    assert '"$GITHUB_RUN_ATTEMPT" == "1"' in text
    assert 'gh api "repos/$GITHUB_REPOSITORY/commits/main" --jq .sha' in text


def test_no_bot_credentials_or_channel_posts() -> None:
    text = _source()
    assert "secrets.LORDCHRIST_TELEGRAPH_ACCESS_TOKEN" in text
    assert "secrets.LORDCHRIST_TELEGRAM_BOT_TOKEN" not in text
    assert "sendMessage" not in text
    assert "createPage" not in text
    assert "cancel-in-progress: false" in text
    assert "persist-credentials: false" in text
    assert "contents: read" in text


def test_one_pinned_script_exactly_one_receipt() -> None:
    text = _source()
    assert "python -m scripts.charnock_telegraph_surgical_revision" in text
    assert "--execute" in text
    assert "--page" in text
    assert "--receipt-dir" in text
    assert "find" in text and "wc -l" in text
