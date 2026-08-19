from __future__ import annotations

import json
from pathlib import Path

from video_channel_manager.milovi_telegram_feed import validate_bundle
from video_channel_manager.telegram_multichannel_release import load_release


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
    review = _json(CONTENT / "releases" / "milovi-feed-20260819-001-review.json")
    state = _json(CONTENT / "releases" / "milovi-feed-20260819-001-state-contract.json")
    runtime = load_release(CONTENT / "releases" / "milovi-feed-20260819-001-runtime.json")
    authority = _json(CONTENT / "releases" / "milovi-feed-20260819-001-execution-authority.json")

    assert candidate["publication_id"] == review["publication_id"] == state["publication_id"] == PUBLICATION_ID
    assert runtime.release_id == PUBLICATION_ID
    assert len(runtime.items) == 1
    assert runtime.items[0].publication_id == PUBLICATION_ID
    assert candidate["execution_authorized"] is False
    assert review["release_authorized"] is False
    assert runtime.release_authorized is False
    assert authority["execution_authorized"] is False
    assert authority["provider_mutation_allowed"] is False
    assert authority["historical_authorization_inherits"] is False
    assert authority["automation_is_execution_authority"] is False
    assert authority["max_provider_attempts"] == 1
    assert authority["blind_mutation_retries"] == 0
    assert review["execution_contract"]["max_provider_attempts"] == 1
    assert review["execution_contract"]["blind_mutation_retries"] == 0
    assert state["execution_transition_rules"]["second_publication_forbidden"] is True


def test_exact_candidate_transport_target_and_schedule_are_locked() -> None:
    candidate = _json(CONTENT / "next-publication-candidate-2026-08-19.json")
    runtime = load_release(CONTENT / "releases" / "milovi-feed-20260819-001-runtime.json")
    media = _json(CONTENT / "releases" / "milovi-feed-20260819-001-media.json")
    binding = _json(ROOT / "content" / "telegram" / "channels" / "milovi-cake-target-binding.json")
    payload = runtime.items[0].payload

    assert candidate["media"]["media_id"] == media["media_id"] == "p03"
    assert candidate["media"]["transport_byte_size"] == media["transport"]["byte_size"] == 391620
    assert candidate["media"]["transport_sha256"] == media["transport"]["sha256"] == TRANSPORT_SHA256
    assert candidate["caption_sha256"] == media["caption_sha256"] == CAPTION_SHA256
    assert candidate["scheduled_at"] == runtime.items[0].scheduled_at.isoformat()
    assert runtime.chat_id == binding["chat_id"] == -1002215328390
    assert runtime.bot_id == binding["bot_id"] == 8716602202
    assert runtime.bot_username == binding["bot_username"] == "preaching_mp3_bot"
    assert payload.provider_payload_sha256 == (
        "sha256:f0f09e0cd29c06eb3ab863b912da785184aca0f36e0861b01bcb48bd410b625c"
    )


def test_provider_inert_bundle_validates_without_state_or_provider_access() -> None:
    result = validate_bundle(PUBLICATION_ID)

    assert result["valid"] is True
    assert result["release_authorized"] is False
    assert result["execution_authorized"] is False
    assert result["provider_mutation_allowed"] is False
    assert result["provider_access_performed"] is False
    assert result["blockers"] == [
        "release_authorized=false",
        "execution_authorized=false",
        "provider_mutation_allowed=false",
    ]


def test_permanent_workflows_replace_oneoff_controller_surface() -> None:
    quality = (WORKFLOWS / "milovi-telegram-feed-quality.yml").read_text(encoding="utf-8")
    publisher = (WORKFLOWS / "milovi-telegram-feed-publisher.yml").read_text(encoding="utf-8")

    assert "push:" in quality
    assert "branches: [main]" in quality
    assert "schedule:" not in publisher
    assert "cron:" not in publisher
    assert "group: milovi-cake-telegram-publisher" in publisher
    assert "require-execution-authorized" in publisher
    assert "state/milovi-cake-telegram" in publisher
    assert "telegram_multichannel_cli prepare" in publisher
    assert "telegram_multichannel_cli send-once" in publisher
    assert publisher.index("telegram_multichannel_cli prepare") < publisher.index("telegram_multichannel_cli send-once")


def test_new_exact_bundle_does_not_reference_historical_bootstrap_publications() -> None:
    paths = [
        WORKFLOWS / "milovi-telegram-feed-quality.yml",
        WORKFLOWS / "milovi-telegram-feed-publisher.yml",
        CONTENT / "releases" / "milovi-feed-20260819-001-review.json",
        CONTENT / "releases" / "milovi-feed-20260819-001-state-contract.json",
        CONTENT / "releases" / "milovi-feed-20260819-001-runtime.json",
        CONTENT / "releases" / "milovi-feed-20260819-001-execution-authority.json",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert "milovi-bootstrap-004" not in combined
    assert "milovi-bootstrap-005" not in combined
    assert "milovi-canary-20260818-002" not in combined
