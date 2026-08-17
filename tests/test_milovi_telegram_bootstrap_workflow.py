from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/milovi-telegram-bootstrap-publisher.yml"
MEDIA_PROOF_WORKFLOW = ROOT / ".github/workflows/milovi-telegram-bootstrap-media-proof.yml"
PROFILE = ROOT / "content/telegram/channels/milovi-cake.json"
TARGET_BINDING = ROOT / "content/telegram/channels/milovi-cake-target-binding.json"
AUTHORIZED_RELEASE = ROOT / "content/telegram/milovi-cake/bootstrap-authorized-release-2026-08.json"


def test_scheduler_cron_and_concurrency_match_frozen_moscow_slots() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'cron: "30 7 * * *"' in text
    assert 'cron: "0 17 * * *"' in text
    assert "group: milovi-cake-telegram-publisher" in text
    assert "cancel-in-progress: false" in text
    assert "MAX_PUBLICATION_LAG_MINUTES: 120" in text


def test_manual_canary_requires_exact_frozen_publication_identity() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "publication_id:" in text
    assert "PUBLISH:@MiloviCake:<publication_id>" in text
    assert "manual_publication_id_not_frozen" in text
    assert 'expected_confirm = f"PUBLISH:@MiloviCake:{manual_publication_id}"' in text
    assert "manual_confirmation_missing_or_mismatched" in text
    assert '--publication-id "$MANUAL_PUBLICATION_ID"' in text
    assert "--mode manual" in text
    assert "--mode scheduled" in text


def test_activation_gate_precedes_any_telegram_secret_or_provider_access() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    activation = text.index("Resolve fail-closed activation and daylight gate")
    first_secret = text.index("LORDCHRIST_TELEGRAM_BOT_TOKEN")
    first_preflight = text.index("Fresh exact target preflight")
    assert activation < first_secret
    assert activation < first_preflight
    assert "profile_write_gate_disabled" in text
    assert "authorized_release_missing" in text
    assert "target_binding_missing" in text
    assert "outside_09_00_21_00_moscow_window" in text


def test_authorization_requires_real_pinned_target_binding_digest() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "BINDING_PATH: content/telegram/channels/milovi-cake-target-binding.json" in text
    assert "load_target_binding" in text
    assert "authorized.target_binding_sha256 != binding.digest" in text
    assert "authorized.chat_id != binding.chat_id" in text
    assert "authorized.bot_id != binding.bot_id" in text
    assert "authorized_release_target_binding_drift" in text


def test_current_main_quality_proofs_run_before_state_or_telegram_access() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    quality = text.index("Require current-main exact bootstrap quality proofs")
    state = text.index("Check out isolated durable Milovi state branch")
    preflight = text.index("Fresh exact target preflight")
    assert quality < state < preflight
    assert "milovi-telegram-bootstrap-quality.yml" in text
    assert "milovi-telegram-bootstrap-media-proof.yml" in text
    assert '--sha "$GITHUB_SHA"' in text


def test_exact_media_proof_runs_on_every_main_revision() -> None:
    text = MEDIA_PROOF_WORKFLOW.read_text(encoding="utf-8")
    assert "push:\n    branches:\n      - main" in text
    assert "workflow_dispatch:" in text
    assert "provider_write_performed" in text


def test_missing_state_branch_is_a_fail_closed_non_provider_condition() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    checkout = text.index("Check out isolated durable Milovi state branch")
    ledger = text.index("Require existing exact publication ledger")
    preflight = text.index("Fresh exact target preflight")
    checkout_block = text[checkout:ledger]
    assert "continue-on-error: true" in checkout_block
    assert "state_branch_or_ledger_missing" in text
    assert checkout < ledger < preflight


def test_scheduled_provider_access_is_hard_stopped_after_single_manual_canary_intent() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    canary = text.index("Resolve release canary gate before Telegram access")
    freshness = text.index("Require fresh exact strict-next slot before Telegram access")
    preflight = text.index("Fresh exact target preflight")
    assert canary < freshness < preflight
    assert 'envelope.dispatch_mode == "manual"' in text
    assert "prior_manual_intents" in text
    assert "manual_canary_intent_already_recorded_hard_stop" in text
    assert "single_canary_gate_blocks_scheduler_until_separate_rollout_authorization" in text
    assert "No Telegram access was attempted" in text


def test_scheduler_persists_no_catch_up_and_intent_barriers_before_send() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    stale_skip = text.index("Skip stale predecessors before any Telegram access")
    canary = text.index("Resolve release canary gate before Telegram access")
    freshness = text.index("Require fresh exact strict-next slot before Telegram access")
    preflight = text.index("Fresh exact target preflight")
    prepare = text.index("Prepare one durable exact strict-next intent")
    persist = text.index("Persist intent and target proof before provider mutation")
    materialize = text.index("Materialize exact reviewed photo bytes when required")
    send = text.index("Send exactly once through generic Telegram runtime")
    outcome = text.index("Apply provider outcome and persist final state")
    assert stale_skip < canary < freshness < preflight < prepare < persist < materialize < send < outcome
    assert "no catch-up send will be made" in text
    assert "durable intent remains non-replayable" in text
    assert "blind replay is blocked" in text


def test_current_branch_contains_exact_reviewed_one_canary_activation() -> None:
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    binding = json.loads(TARGET_BINDING.read_text(encoding="utf-8"))
    release = json.loads(AUTHORIZED_RELEASE.read_text(encoding="utf-8"))

    assert profile["provider_writes_authorized"] is True
    assert binding["provider_write_performed"] is False
    assert binding["chat_id"] == -1002215328390
    assert binding["bot_id"] == 8716602202
    assert release["release_authorized"] is True
    assert release["reviewed_candidate_sha256"] == (
        "sha256:d2d574e7480d6e5d76c9e5fad15bc00cdd0af04703d0039059f7705a828cf9dc"
    )
    assert release["target_binding_sha256"] == (
        "sha256:741a8b4b54d785976236c6f15ed5d82cc9ad46aeb96a80cf372f22c421ba047c"
    )
    assert release["items"][2]["publication_id"] == "milovi-bootstrap-003"
    assert release["items"][2]["payload"]["provider_payload_sha256"] == (
        "sha256:8c4efbd9817af78086f00947623f4d642144d1a387288cc2bb61bbce2a0fa88a"
    )


def test_deleted_historical_canary_is_not_a_scheduler_identity() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "milovi-cake-canary-001" not in text
    assert "31918457764" not in text
    assert "milovi-cake-canary-001-live-2026-08-16" not in text
