from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/milovi-telegram-bootstrap-publisher.yml"


def test_milovi_publisher_allows_at_most_one_durable_manual_canary_intent() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert 'evidence_root = Path(os.environ["STATE_DIR"]) / "content/telegram/milovi-cake/dispatches"' in text
    assert "GenericDispatchEnvelope.model_validate_json" in text
    assert "envelope.release_digest == release.digest" in text
    assert 'envelope.dispatch_mode == "manual"' in text
    assert "prior_manual_intents.append(envelope.publication_id)" in text
    assert 'reason = "manual_canary_intent_already_recorded_hard_stop"' in text


def test_milovi_publisher_does_not_auto_roll_out_after_canary() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert 'reason = "single_canary_gate_blocks_scheduler_until_separate_rollout_authorization"' in text
    assert "ready = manual_event or verified_manual_canary" not in text
    assert "verified_release_manual_canary_present" not in text


def test_milovi_publisher_persists_intent_before_provider_send() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    persist_index = text.index("- name: Persist intent and target proof before provider mutation")
    send_index = text.index("- name: Send exactly once through generic Telegram runtime")
    assert persist_index < send_index
