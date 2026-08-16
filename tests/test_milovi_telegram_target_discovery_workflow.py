from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "milovi-telegram-target-discovery.yml"


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_milovi_target_discovery_is_manual_read_only_and_main_only() -> None:
    text = _text()
    assert "workflow_dispatch:" in text
    assert "schedule:" not in text
    assert "push:" not in text
    assert "pull_request:" not in text
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "github.ref == 'refs/heads/main'" in text
    assert "persist-credentials: false" in text


def test_milovi_target_discovery_uses_exact_reviewed_identity() -> None:
    text = _text()
    assert "PROFILE_PATH: content/telegram/channels/milovi-cake.json" in text
    assert "EXPECTED_CHAT_ID: -1002215328390" in text
    assert "EXPECTED_BOT_ID: 8716602202" in text
    assert "EXPECTED_BOT_USERNAME: preaching_mp3_bot" in text
    assert "provider_writes_authorized') is not False" in text
    assert '--expected-bot-id "$EXPECTED_BOT_ID"' in text
    assert '--expected-bot-username "$EXPECTED_BOT_USERNAME"' in text


def test_milovi_target_discovery_reuses_shared_bot_secret_but_never_sends() -> None:
    text = _text()
    assert "MILOVI_CAKE_TELEGRAM_BOT_TOKEN: ${{ secrets.LORDCHRIST_TELEGRAM_BOT_TOKEN }}" in text
    assert "discover-target" in text
    assert "telegram_target_binding_cli" in text
    assert "provider_write_performed" in text
    for forbidden in (
        "sendMessage",
        "sendPhoto",
        "sendPoll",
        "dispatch-provider",
        "telegram_multichannel_cli prepare",
        "telegram_multichannel_cli record-outcome",
    ):
        assert forbidden not in text


def test_milovi_target_discovery_only_uploads_ephemeral_candidate_artifact() -> None:
    text = _text()
    assert "milovi-cake-target-binding-${{ github.sha }}" in text
    assert ".runtime/milovi-cake-generic-target-proof.json" in text
    assert ".runtime/milovi-cake-target-binding.json" in text
    assert "retention-days: 7" in text
    assert "git commit" not in text
    assert "git push" not in text
