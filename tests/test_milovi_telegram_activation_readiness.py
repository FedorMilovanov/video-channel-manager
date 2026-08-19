from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
READINESS = ROOT / "content/telegram/milovi-cake/live/activation-readiness-2026-08-16.json"
PROFILE = ROOT / "content/telegram/channels/milovi-cake.json"
QUEUE = ROOT / "content/telegram/milovi-cake/queues/bootstrap-first-screen-queue-2026-08.json"
TARGET_BINDING = ROOT / "content/telegram/channels/milovi-cake-target-binding.json"
AUTHORIZED_RELEASE = ROOT / "content/telegram/milovi-cake/bootstrap-authorized-release-2026-08.json"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_historical_readiness_snapshot_stays_inert_while_current_canary_activation_is_explicit() -> None:
    readiness = _load(READINESS)
    profile = _load(PROFILE)
    queue = _load(QUEUE)
    binding = _load(TARGET_BINDING)
    release = _load(AUTHORIZED_RELEASE)

    assert readiness["schema_name"] == "video-channel-manager.milovi-telegram-activation-readiness"
    assert readiness["snapshot_date"] == "2026-08-16"
    assert readiness["status"] == "blocked_before_live_activation"
    assert readiness["provider_access_performed"] is False
    assert readiness["public_write_performed"] is False

    assert profile["provider_writes_authorized"] is True
    assert queue["execution_authorized"] is False
    assert queue["provider_mutation_allowed"] is False
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
    assert release["items"][2]["payload"]["media_sha256"] == (
        "sha256:8bb0956e44084265d7a3a14ce01f96eb1e4a9c327c780448de34e068f6cf6f10"
    )

    queue_ref = readiness["queue"]
    assert isinstance(queue_ref, dict)
    assert queue_ref["path"] == "content/telegram/milovi-cake/queues/bootstrap-first-screen-queue-2026-08.json"
    assert queue_ref["queue_id"] == queue["queue_id"] == "milovi-first-screen-2026-08-17"
    assert queue_ref["first_publication_id"] == queue["items"][0]["publication_id"] == "milovi-bootstrap-001"
    assert queue_ref["last_publication_id"] == queue["items"][-1]["publication_id"] == "milovi-bootstrap-010"


def test_historical_readiness_preserves_pre_activation_gate_order() -> None:
    readiness = _load(READINESS)
    blockers = readiness["current_blockers"]
    assert isinstance(blockers, list)
    assert [blocker["gate"] for blocker in blockers] == [
        "profile_write_gate",
        "fresh_target_binding",
        "authorized_release",
        "durable_state_ledger",
        "fresh_release_manual_canary",
    ]
    assert [blocker["state"] for blocker in blockers] == [
        "blocked",
        "missing",
        "missing",
        "missing",
        "not_verified",
    ]

    order = readiness["activation_order"]
    assert isinstance(order, list)
    joined = "\n".join(str(item) for item in order)
    assert joined.index("fresh exact target binding") < joined.index("exact authorized release")
    assert joined.index("exact authorized release") < joined.index("initialize isolated durable ledger")
    assert joined.index("initialize isolated durable ledger") < joined.index(
        "enable the Milovi profile provider write gate"
    )


def test_readiness_preserves_historical_canary_and_editorial_no_go_rules() -> None:
    readiness = _load(READINESS)
    guards = readiness["non_negotiable_guards"]
    assert isinstance(guards, list)
    joined = "\n".join(str(item) for item in guards)
    assert "31918457764" in joined
    assert "milovi-cake-canary-001-live-2026-08-16" in joined
    assert "deleted historical canary payload" in joined
    assert "historical canary as the fresh release canary" in joined
    assert "night" in joined
    assert "blind-retry" in joined
    assert "Milovi School" in joined
    assert "French-cuisine linkage" in joined
