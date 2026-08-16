from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READINESS = ROOT / "content/telegram/milovi-cake/live/activation-readiness-2026-08-16.json"
PROFILE = ROOT / "content/telegram/channels/milovi-cake.json"
QUEUE = ROOT / "content/telegram/milovi-cake/queues/bootstrap-first-screen-queue-2026-08.json"
PUBLISHER = ROOT / ".github/workflows/milovi-telegram-bootstrap-publisher.yml"
TARGET_BINDING = ROOT / "content/telegram/channels/milovi-cake-target-binding.json"
AUTHORIZED_RELEASE = ROOT / "content/telegram/milovi-cake/bootstrap-authorized-release-2026-08.json"


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_readiness_snapshot_matches_merged_operational_queue_and_stays_inert() -> None:
    readiness = _load(READINESS)
    profile = _load(PROFILE)
    queue = _load(QUEUE)

    assert readiness["schema_name"] == "video-channel-manager.milovi-telegram-activation-readiness"
    assert readiness["status"] == "blocked_before_live_activation"
    assert readiness["provider_access_performed"] is False
    assert readiness["public_write_performed"] is False
    assert profile["provider_writes_authorized"] is False
    assert queue["execution_authorized"] is False
    assert queue["provider_mutation_allowed"] is False
    assert not TARGET_BINDING.exists()
    assert not AUTHORIZED_RELEASE.exists()

    queue_ref = readiness["queue"]
    assert isinstance(queue_ref, dict)
    assert queue_ref["path"] == "content/telegram/milovi-cake/queues/bootstrap-first-screen-queue-2026-08.json"
    assert queue_ref["queue_id"] == queue["queue_id"] == "milovi-first-screen-2026-08-17"
    assert queue_ref["first_publication_id"] == queue["items"][0]["publication_id"] == "milovi-bootstrap-001"
    assert queue_ref["first_planned_local"] == queue["items"][0]["planned_local"] == "2026-08-17T10:30:00+03:00"
    assert queue_ref["last_publication_id"] == queue["items"][-1]["publication_id"] == "milovi-bootstrap-010"
    assert queue_ref["last_planned_local"] == queue["items"][-1]["planned_local"] == "2026-08-21T20:00:00+03:00"


def test_readiness_lists_every_live_gate_before_manual_canary() -> None:
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
    assert joined.index("initialize isolated durable ledger") < joined.index("enable the Milovi profile provider write gate")
    assert joined.index("enable the Milovi profile provider write gate") < joined.index("milovi-bootstrap-001")


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


def test_publisher_still_uses_operational_queue_and_daylight_activation_gate() -> None:
    publisher = PUBLISHER.read_text(encoding="utf-8")
    assert "ROLLOUT_PATH: content/telegram/milovi-cake/queues/bootstrap-first-screen-queue-2026-08.json" in publisher
    assert "profile_write_gate_disabled" in publisher
    assert "outside_09_00_21_00_moscow_window" in publisher
    assert "target_binding_missing" in publisher
    assert "authorized_release_missing" in publisher
    assert "state_branch_or_ledger_missing" in publisher
    assert "waiting_for_release_manual_canary" in publisher
