from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "milovi-telegram-bootstrap-activation-package.yml"


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_activation_package_is_manual_current_main_and_read_only() -> None:
    text = _text()
    assert "workflow_dispatch:" in text
    assert "schedule:" not in text
    assert "push:" not in text
    assert "pull_request:" not in text
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "github.ref == 'refs/heads/main'" in text
    assert "persist-credentials: false" in text
    assert "provider_writes_authorized') is not False" in text


def test_activation_package_discovers_only_exact_reviewed_milovi_target() -> None:
    text = _text()
    assert "PROFILE_PATH: content/telegram/channels/milovi-cake.json" in text
    assert "EXPECTED_CHAT_ID: -1002215328390" in text
    assert "EXPECTED_BOT_ID: 8716602202" in text
    assert "EXPECTED_BOT_USERNAME: preaching_mp3_bot" in text
    assert "MILOVI_CAKE_TELEGRAM_BOT_TOKEN: ${{ secrets.LORDCHRIST_TELEGRAM_BOT_TOKEN }}" in text
    assert "telegram_channel_cli discover-target" in text
    assert "telegram_target_binding_cli" in text


def test_activation_package_builds_then_binds_but_never_authorizes_release() -> None:
    text = _text()
    assert "milovi_telegram_bootstrap build-release" in text
    assert "telegram_release_binding_cli" in text
    assert "--expected-unbound-candidate-sha256" in text
    assert "bootstrap-unbound.json" in text
    assert "bootstrap-bound-unauthorized.json" in text
    assert "release_authorized') is not False" in text
    assert "reviewed_candidate_sha256" in text
    assert "unbound_candidate_sha256" in text
    assert "bound_candidate_sha256" in text
    assert "target_binding_sha256" in text
    assert "telegram_release_review_cli" not in text
    assert "authorize_release_candidate" not in text


def test_activation_package_has_no_provider_or_state_mutation_path() -> None:
    text = _text()
    for forbidden in (
        "sendMessage",
        "sendPhoto",
        "sendPoll",
        "dispatch-provider",
        "telegram_multichannel_cli prepare",
        "telegram_multichannel_cli record-outcome",
        "state/milovi-cake-telegram",
        "git commit",
        "git push",
        "provider_writes_authorized=true",
    ):
        assert forbidden not in text
    assert "provider_write_performed" in text
    assert "read_only_target_discovery_only" in text


def test_activation_package_is_ephemeral_and_preserves_exact_ten_items() -> None:
    text = _text()
    assert "bootstrap_items': 10" in text
    assert "len(candidate.get('items') or []) != 10" in text
    assert "unbound.get('items') != bound.get('items')" in text
    assert "milovi-bootstrap-activation-package-${{ github.sha }}" in text
    assert "retention-days: 7" in text
