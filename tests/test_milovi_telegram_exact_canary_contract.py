from __future__ import annotations

import json
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LEGACY_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/telegram-milovi-exact-canary.yml"
LEGACY_RUNTIME = REPOSITORY_ROOT / "src/video_channel_manager/milovi_telegram_live_canary.py"
LEGACY_AUTHORIZATION = REPOSITORY_ROOT / "content/telegram/milovi-cake/live/canary-authorization.json"
LEGACY_DISCOVERY = REPOSITORY_ROOT / ".github/workflows/telegram-milovi-target-discovery.yml"
CANONICAL_PUBLISHER = REPOSITORY_ROOT / ".github/workflows/milovi-telegram-bootstrap-publisher.yml"
CANONICAL_DISCOVERY = REPOSITORY_ROOT / ".github/workflows/milovi-telegram-target-discovery.yml"
REVIEW_READY = REPOSITORY_ROOT / ".github/workflows/milovi-telegram-bootstrap-review-ready.yml"
HISTORICAL_STATE = REPOSITORY_ROOT / "content/telegram/milovi-cake/live/canary-dispatch-state.json"
RETIREMENT_REGISTRY = REPOSITORY_ROOT / "docs/operations/retirement-registry-v1.json"


def test_legacy_milovi_provider_authority_is_removed_from_executable_tree() -> None:
    assert not LEGACY_WORKFLOW.exists()
    assert not LEGACY_RUNTIME.exists()
    assert not LEGACY_AUTHORIZATION.exists()
    assert not LEGACY_DISCOVERY.exists()


def test_canonical_milovi_publisher_and_discovery_remain_the_supported_paths() -> None:
    publisher = CANONICAL_PUBLISHER.read_text(encoding="utf-8")
    discovery = CANONICAL_DISCOVERY.read_text(encoding="utf-8")

    assert "group: milovi-cake-telegram-publisher" in publisher
    assert "provider_writes_authorized" in publisher
    assert "-1002215328390" in publisher
    assert "8716602202" in publisher

    assert "Milovi Cake Telegram target discovery" in discovery
    assert "EXPECTED_CHAT_ID: -1002215328390" in discovery
    assert "EXPECTED_BOT_ID: 8716602202" in discovery
    assert "provider_writes_authorized" in discovery


def test_review_ready_accepts_only_legitimate_activation_package_events_without_weakening_identity_gates() -> None:
    workflow = REVIEW_READY.read_text(encoding="utf-8")

    assert "source_event not in {'push', 'workflow_dispatch'}" in workflow
    assert 'git merge-base --is-ancestor "$EXPECTED_MAIN_SHA" "$GITHUB_SHA"' in workflow
    assert "Milovi-critical files changed after source package revision" in workflow
    assert "run.get('head_branch') != 'main' or run.get('head_sha') != expected_sha" in workflow
    assert "run.get('path') != '.github/workflows/milovi-telegram-bootstrap-activation-package.yml'" in workflow
    assert "run.get('status') != 'completed' or run.get('conclusion') != 'success'" in workflow
    assert "int(run.get('run_attempt') or 0) != 1" in workflow
    assert "len(matches) != 1" in workflow
    assert "artifact.get('expired') is not False" in workflow
    assert "source_artifact_digest" in workflow


def test_historical_verified_canary_outcome_remains_inert_evidence() -> None:
    state = json.loads(HISTORICAL_STATE.read_text(encoding="utf-8"))

    assert state["status"] == "verified"
    assert state["provider_effect"] == "verified"
    assert state["message_id"] == 25
    assert state["message_url"] == "https://t.me/MiloviCake/25"
    assert state["automatic_replay_allowed"] is False


def test_retirement_registry_prohibits_reactivation_of_both_legacy_milovi_paths() -> None:
    registry = json.loads(RETIREMENT_REGISTRY.read_text(encoding="utf-8"))
    entries = {entry["id"]: entry for entry in registry["retired_families"]}

    canary = entries["milovi-telegram-exact-canary-legacy"]
    assert canary["status"] == "retired_non_executable"
    assert canary["execution_prohibited"] is True
    assert canary["replacement"] == ".github/workflows/milovi-telegram-bootstrap-publisher.yml"
    assert 353 in canary["issues"]

    discovery = entries["milovi-telegram-target-discovery-legacy"]
    assert discovery["status"] == "retired_non_executable"
    assert discovery["execution_prohibited"] is True
    assert discovery["replacement"] == ".github/workflows/milovi-telegram-target-discovery.yml"
    assert 353 in discovery["issues"]

    assert registry["provider_writes_authorized"] is False
