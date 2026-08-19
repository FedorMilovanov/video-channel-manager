from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLISHER = ROOT / ".github" / "workflows" / "milovi-telegram-feed-publisher.yml"
STATE_BRANCH = "state/milovi-cake-telegram"


def _text() -> str:
    return PUBLISHER.read_text(encoding="utf-8")


def test_permanent_feed_control_plane_is_manual_main_only_and_serialized() -> None:
    text = _text()
    trigger = text.split("permissions:", 1)[0]

    assert "workflow_dispatch:" in trigger
    assert "schedule:" not in trigger
    assert "cron:" not in trigger
    assert "push:" not in trigger
    assert "pull_request:" not in trigger
    assert "if: github.ref == 'refs/heads/main'" in text
    assert "group: milovi-cake-telegram-publisher" in text
    assert "cancel-in-progress: false" in text
    assert f"STATE_BRANCH: {STATE_BRANCH}" in text


def test_state_initialization_is_explicit_exact_and_provider_free() -> None:
    text = _text()

    assert "- initialize-state" in text
    assert '[[ "$CONFIRM" == "INITIALIZE:@MiloviCake:$PUBLICATION_ID" ]]' in text
    assert "--require-release-authorized" in text
    assert "python -m video_channel_manager.milovi_telegram_feed state-init" in text
    assert "if: inputs.operation == 'initialize-state'" in text

    gate = text.index("Resolve exact bundle paths and authority gate")
    quality = text.index("Require exact current-main feed quality before state/provider path")
    checkout = text.index("Check out isolated durable Milovi feed state")
    init = text.index("Initialize exact release state and channel-wide duplicate guard")
    preflight = text.index("Fresh exact target preflight")
    assert gate < quality < checkout < init < preflight


def test_publish_requires_separate_execution_authority_and_existing_state() -> None:
    text = _text()

    assert '[[ "$CONFIRM" == "PUBLISH:@MiloviCake:$PUBLICATION_ID" ]]' in text
    assert "--require-execution-authorized" in text
    assert "Require exact initialized publishable state before Telegram access" in text
    assert "--require-publishable" in text
    assert "refusing to auto-register publication during dispatch" not in text

    authority = text.index("--require-execution-authorized")
    state_check = text.index("Require exact initialized publishable state before Telegram access")
    preflight = text.index("Fresh exact target preflight")
    secret = text.index("MILOVI_CAKE_TELEGRAM_BOT_TOKEN")
    assert authority < state_check < preflight < secret


def test_provider_steps_are_publish_only_and_exact_target_bound() -> None:
    text = _text()

    assert "--expected-chat-id -1002215328390" in text
    assert "--expected-bot-id 8716602202" in text
    assert "--expected-bot-username preaching_mp3_bot" in text

    preflight = text.index("- name: Fresh exact target preflight")
    prepare = text.index("- name: Prepare exactly one durable feed intent")
    persist = text.index("- name: Persist exact intent in release ledger and channel-wide index before mutation")
    reprove = text.index("- name: Re-prove exact current main and quality immediately before mutation")
    send = text.index("- name: Send exactly once through the canonical generic Telegram runtime")
    outcome = text.index("- name: Apply exact outcome and persist terminal or blocking state")
    assert preflight < prepare < persist < reprove < send < outcome

    for step in (preflight, prepare, persist, reprove, send, outcome):
        block = text[step : text.find("\n      - name:", step + 1) if text.find("\n      - name:", step + 1) != -1 else None]
        assert "if: inputs.operation == 'publish'" in block or "inputs.operation == 'publish' && always()" in block


def test_publish_never_auto_initializes_missing_state_or_blindly_retries() -> None:
    text = _text()

    assert text.count("python -m video_channel_manager.milovi_telegram_feed state-init") == 1
    assert "A `publish` operation never auto-initializes missing state" not in text
    assert text.count("telegram_multichannel_cli send-once") == 1
    assert "blind replay is blocked" in text
    assert "this intent is non-replayable" in text
