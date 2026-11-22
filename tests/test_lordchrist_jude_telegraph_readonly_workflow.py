"""Prevent the Jude account probe from becoming a publication path."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/lordchrist-jude-telegraph-readonly.yml"


def test_manual_owner_main_only_and_no_state_write_permission() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    workflow = yaml.load(text, Loader=yaml.BaseLoader)
    assert set(workflow["on"]) == {"workflow_dispatch"}
    assert workflow["permissions"] == {"actions": "read", "contents": "read"}
    job = workflow["jobs"]["inspect"]
    assert "github.actor == 'FedorMilovanov'" in job["if"]
    assert "github.repository == 'FedorMilovanov/video-channel-manager'" in job["if"]
    assert "github.ref == 'refs/heads/main'" in job["if"]
    assert "persist-credentials: false" in text
    assert "state/lordchrist-telegram" in text
    assert "telegram_github_quality_gate" in text
    assert text.count("repos/$GITHUB_REPOSITORY/commits/main") >= 2
    assert "git ls-remote" in text
    assert "python -m video_channel_manager.lordchrist_jude_telegraph_readonly" in text
    assert "LORDCHRIST_TELEGRAPH_ACCESS_TOKEN" in text
    assert "::notice title=lordchrist-jude-account-read-only::" in text
    assert "contents: write" not in text
    assert "actions: write" not in text
    assert "LORDCHRIST_TELEGRAM_BOT_TOKEN" not in text
    assert "LORDCHRIST_TELEGRAPH_POSTING_ENABLED" not in text
    for forbidden in ("sendMessage", "createPage", "editPage", "git push", "schedule:"):
        assert forbidden not in text
