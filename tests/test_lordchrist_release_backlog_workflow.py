"""Read-only guarantees for the daily @lordchrist backlog report workflow."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/lordchrist-release-backlog.yml"


def _source() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_read_only_and_scheduled() -> None:
    text = _source()
    assert "schedule:" in text
    assert "workflow_dispatch:" in text
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "persist-credentials: false" in text
    for forbidden in ("secrets.", "sendMessage", "editPage", "createPage", "PUBLISH:"):
        assert forbidden not in text


def test_reports_from_the_real_queue_and_durable_ledger() -> None:
    text = _source()
    assert "python scripts/lordchrist_telegraph_backlog.py" in text
    assert "--ledger-ref refs/remotes/origin/state/lordchrist-telegram" in text
    assert "git fetch --depth=1 origin" in text
    assert "$GITHUB_STEP_SUMMARY" in text
    assert "::notice title=lordchrist-release-backlog::" in text
    assert "actions/upload-artifact@" in text
