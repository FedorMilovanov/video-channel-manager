from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "telegram" / "milovi-cake"
WORKFLOWS = ROOT / ".github" / "workflows"
PUBLICATION_ID = "milovi-feed-20260819-001"
TRANSPORT_SHA256 = "sha256:d40b185ab813a46d29b66aa0da6f9300a13cad2bac0baf0ba71f1cd8e36a50a1"
CAPTION_SHA256 = "sha256:e4549b91102cad61a94f2faadc0100de23716c54e48d27552e21b92eb71cf918"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_exact_one_item_release_is_provider_inert_and_attempt_bounded() -> None:
    candidate = _json(CONTENT / "next-publication-candidate-2026-08-19.json")
    release = _json(CONTENT / "releases" / "milovi-feed-20260819-001-review.json")
    state = _json(CONTENT / "releases" / "milovi-feed-20260819-001-state-contract.json")

    assert candidate["publication_id"] == release["publication_id"] == state["publication_id"] == PUBLICATION_ID
    assert candidate["execution_authorized"] is False
    assert release["release_authorized"] is False
    assert release["execution_authorized"] is False
    assert state["execution_authorized"] is False
    assert release["provider_mutation_allowed"] is False
    assert state["provider_mutation_allowed"] is False
    assert release["execution_contract"]["max_provider_attempts"] == 1
    assert release["execution_contract"]["blind_mutation_retries"] == 0
    assert release["execution_contract"]["publish_exactly_one_item"] is True
    assert release["execution_contract"]["second_item_allowed"] is False
    assert state["execution_transition_rules"]["second_publication_forbidden"] is True


def test_exact_candidate_transport_target_and_schedule_are_locked() -> None:
    candidate = _json(CONTENT / "next-publication-candidate-2026-08-19.json")
    release = _json(CONTENT / "releases" / "milovi-feed-20260819-001-review.json")
    state = _json(CONTENT / "releases" / "milovi-feed-20260819-001-state-contract.json")
    binding = _json(ROOT / "content" / "telegram" / "channels" / "milovi-cake-target-binding.json")

    assert candidate["media"]["media_id"] == "p03"
    assert candidate["media"]["transport_byte_size"] == 391620
    assert candidate["media"]["transport_sha256"] == TRANSPORT_SHA256
    assert candidate["caption_sha256"] == CAPTION_SHA256
    assert candidate["scheduled_at"] == "2026-08-19T10:30:00+03:00"
    assert candidate["timezone"] == "Europe/Moscow"
    assert release["allowed_execution_window"] == {"start_local": "09:00:00", "end_local": "21:00:00"}
    assert binding["chat_id"] == release["target"]["chat_id"] == state["identity_lock"]["chat_id"] == -1002215328390
    assert binding["bot_id"] == release["target"]["bot_id"] == state["identity_lock"]["bot_id"] == 8716602202
    assert binding["bot_username"].casefold() == "preaching_mp3_bot"


def test_provider_inert_preparation_creates_no_intent_or_effect() -> None:
    release = _json(CONTENT / "releases" / "milovi-feed-20260819-001-review.json")
    state = _json(CONTENT / "releases" / "milovi-feed-20260819-001-state-contract.json")

    assert release["preparation_evidence"]["durable_publication_id_found"] is False
    assert release["preparation_evidence"]["durable_intent_found"] is False
    assert release["preparation_evidence"]["durable_provider_effect_found"] is False
    assert state["initial_state"]["provider_effect"] == "impossible"
    assert state["initial_state"]["intent_id"] is None
    assert state["initial_state"]["provider_attempt_count"] == 0
    assert state["preparation_rules"]["create_execution_intent_during_provider_inert_preparation"] is False
    assert state["preparation_rules"]["write_state_branch_during_provider_inert_preparation"] is False


def test_controller_is_workflow_run_current_main_and_has_no_cron_or_telegram_secret() -> None:
    controller = (WORKFLOWS / "milovi-feed-20260819-001-controller.yml").read_text(encoding="utf-8")

    assert "workflow_run:" in controller
    assert "ref: main" in controller
    assert "schedule:" not in controller
    assert "cron:" not in controller
    assert "secrets." not in controller
    assert "MILOVI_CAKE_TELEGRAM_BOT_TOKEN" not in controller
    assert "sendPhoto" not in controller
    assert 'provider_write_performed": False' in controller
    assert "fresh_exact_human_execution_authorization_missing" in controller


def test_new_exact_workflows_do_not_reference_historical_bootstrap_publications() -> None:
    paths = [
        WORKFLOWS / "milovi-feed-20260819-001-quality.yml",
        WORKFLOWS / "milovi-feed-20260819-001-media-proof.yml",
        WORKFLOWS / "milovi-feed-20260819-001-controller.yml",
        CONTENT / "releases" / "milovi-feed-20260819-001-review.json",
        CONTENT / "releases" / "milovi-feed-20260819-001-state-contract.json",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert "milovi-bootstrap-004" not in combined
    assert "milovi-bootstrap-005" not in combined
    assert "milovi-canary-20260818-002" not in combined
