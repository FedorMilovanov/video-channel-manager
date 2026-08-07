from __future__ import annotations

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPOSITORY_ROOT / ".github/workflows/svodka-telegram-preflight.yml"


def test_svodka_discovery_reuses_shared_bot_credentials_without_provider_mutation() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "- discover" in workflow
    assert "secrets.SVODKA_TELEGRAM_BOT_TOKEN || secrets.LORDCHRIST_TELEGRAM_BOT_TOKEN" in workflow
    assert "vars.SVODKA_TELEGRAM_BOT_ID || vars.LORDCHRIST_TELEGRAM_BOT_ID" in workflow
    assert "vars.SVODKA_TELEGRAM_BOT_USERNAME || vars.LORDCHRIST_TELEGRAM_BOT_USERNAME" in workflow
    assert "discover-target" in workflow
    assert "svodka-target-discovery.json" in workflow
    assert "sendMessage" not in workflow
    assert "sendPoll" not in workflow
    assert "schedule:" not in workflow


def test_pinned_preflight_still_requires_exact_numeric_svodka_chat_id() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "SVODKA_TELEGRAM_CHAT_ID: ${{ vars.SVODKA_TELEGRAM_CHAT_ID }}" in workflow
    assert "--expected-chat-id \"$SVODKA_TELEGRAM_CHAT_ID\"" in workflow
    assert "SVODKA_TELEGRAM_CHAT_ID must be negative" in workflow
