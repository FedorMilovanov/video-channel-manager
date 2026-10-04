from __future__ import annotations

import json
from pathlib import Path

import pytest

from video_channel_manager.telegram_presentation import load_presentation_policy
from video_channel_manager.telegram_quote_depth import DEPTH_QUEUE_DIGEST
from video_channel_manager.telegram_quote_runtime_activation import load_runtime_activation
from video_channel_manager.telegram_quote_source_audit import load_source_web_audit

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content/telegram/lordchrist"
ACTIVATION_PATH = CONTENT / "successor-depth-runtime-activation-v4.json"


def test_v4_runtime_activation_is_exact_provider_inert_15_45_checkpoint() -> None:
    activation = load_runtime_activation(ACTIVATION_PATH)
    policy = load_presentation_policy(CONTENT / "presentation-policy-v4.json")

    assert activation.release_id == "lordchrist-successor-depth-v2"
    assert activation.queue_digest == DEPTH_QUEUE_DIGEST
    assert activation.sealed_handoff_published_prefix == 14
    assert activation.required_published_prefix == 15
    assert activation.required_pending_suffix == 45
    assert activation.presentation_policy_id == policy.policy_id == "lordchrist-quote-v4"
    assert activation.presentation_policy_sha256 == policy.digest
    assert activation.provider_writes_authorized is False


def test_v4_runtime_activation_points_only_to_reviewed_migration_and_source_evidence() -> None:
    activation = load_runtime_activation(ACTIVATION_PATH)
    audit = load_source_web_audit(CONTENT / activation.source_web_audit)
    probe = json.loads((CONTENT / activation.source_live_probe).read_text(encoding="utf-8"))

    assert activation.presentation_migration == "successor-depth-presentation-migration-v1.json"
    assert audit.queue_digest == activation.queue_digest
    assert audit.future_sequences_reviewed == tuple(range(16, 61))
    assert audit.research_pages_reviewed == 99
    assert probe["queue_digest"] == activation.queue_digest
    assert probe["urls_attempted"] == audit.research_pages_reviewed == 99
    assert probe["schema_version"] == 2
    assert probe["classification_counts"]["retrieved"] == probe["urls_fetched_successfully"]
    assert probe["urls_fetched_successfully"] >= 50
    assert probe["urls_fetched_successfully"] + probe["fetch_failures"] == probe["urls_attempted"]
    assert probe["urls_attempted"] == len(probe["results"])
    outcomes = {entry["outcome"] for entry in probe["results"]}
    assert outcomes <= {
        "retrieved",
        "transport_failure",
        "bot_protection",
        "stale_url_relocated",
        "not_found",
        "insufficient_evidence",
    }


def test_runtime_activation_rejects_write_authorization_in_preflight_artifact(tmp_path: Path) -> None:
    payload = json.loads(ACTIVATION_PATH.read_text(encoding="utf-8"))
    payload["required_published_prefix"] = 16
    payload["required_pending_suffix"] = 45
    invalid = tmp_path / "invalid-runtime-activation.json"
    invalid.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="cover all 60"):
        load_runtime_activation(invalid)
