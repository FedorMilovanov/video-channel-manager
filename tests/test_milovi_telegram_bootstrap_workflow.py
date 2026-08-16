from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/milovi-telegram-bootstrap-publisher.yml"
PROFILE = ROOT / "content/telegram/channels/milovi-cake.json"
AUTHORIZED_RELEASE = ROOT / "content/telegram/milovi-cake/bootstrap-authorized-release-2026-08.json"


def test_scheduler_cron_and_concurrency_match_frozen_moscow_slots() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'cron: "30 7 * * *"' in text
    assert 'cron: "0 17 * * *"' in text
    assert "group: milovi-cake-telegram-publisher" in text
    assert "cancel-in-progress: false" in text
    assert "MAX_PUBLICATION_LAG_MINUTES: 120" in text


def test_activation_gate_precedes_any_telegram_secret_or_provider_access() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    activation = text.index("Resolve fail-closed activation and daylight gate")
    first_secret = text.index("LORDCHRIST_TELEGRAM_BOT_TOKEN")
    first_preflight = text.index("Fresh exact target preflight")
    assert activation < first_secret
    assert activation < first_preflight
    assert "profile_write_gate_disabled" in text
    assert "authorized_release_missing" in text
    assert "outside_09_00_21_00_moscow_window" in text


def test_scheduler_persists_no_catch_up_and_intent_barriers_before_send() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    stale_skip = text.index("Skip stale predecessors before any Telegram access")
    freshness = text.index("Require fresh strict-next slot before Telegram access")
    preflight = text.index("Fresh exact target preflight")
    prepare = text.index("Prepare one durable strict-next intent")
    persist = text.index("Persist intent and target proof before provider mutation")
    materialize = text.index("Materialize exact reviewed photo bytes when required")
    send = text.index("Send exactly once through generic Telegram runtime")
    outcome = text.index("Apply provider outcome and persist final state")
    assert stale_skip < freshness < preflight < prepare < persist < materialize < send < outcome
    assert "No catch-up send will be made" in text
    assert "durable intent remains non-replayable" in text
    assert "blind replay is blocked" in text


def test_current_branch_remains_provider_inert_without_authorized_release() -> None:
    profile = PROFILE.read_text(encoding="utf-8")
    assert '"provider_writes_authorized": false' in profile
    assert not AUTHORIZED_RELEASE.exists()


def test_deleted_historical_canary_is_not_a_scheduler_identity() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "milovi-cake-canary-001" not in text
    assert "31918457764" not in text
    assert "milovi-cake-canary-001-live-2026-08-16" not in text
