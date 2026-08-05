from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "docs" / "operations" / "audit-register-v6-2026-08-05.json"
CURRENT_STATE = ROOT / "docs" / "operations" / "current-state.md"
BACKLOG = ROOT / "docs" / "operations" / "automation-backlog.md"
OPERATIONS_INDEX = ROOT / "docs" / "operations" / "README.md"
AGENTS = ROOT / "AGENTS.md"


def _register() -> dict[str, object]:
    return json.loads(REGISTER.read_text(encoding="utf-8"))


def test_v6_is_final_fail_closed_machine_state() -> None:
    data = _register()

    assert data["schema_name"] == "video-manager.audit-register-v6"
    assert data["schema_version"] == "6.0"
    assert data["predecessor_register"] == {
        "path": "docs/operations/audit-register-v5-2026-08-05.json",
        "blob_sha": "dba0ab70288c045610313aa54c21ed16877e987b",
        "schema_version": "5.0",
        "role": "Wave 13 immutable evidence-backed disposition contract",
    }
    assert data["program_state"] == ("WAVES_0_13_COMPLETED_OPERATIONAL_GRAPH_CLOSED_NO_PROVIDER_WRITES")
    assert data["active_operational_issues"] == []
    assert data["open_issues_after_completed_state_merge"] == []
    assert data["open_pull_requests_after_completed_state_merge"] == []
    assert data["provider_queries_during_wave_13"] == 0
    assert data["provider_writes_during_wave_13"] == 0
    assert data["write_plans_created_during_wave_13"] == 0
    assert data["mutation_authorized"] is False
    assert data["automatic_execution"] is False
    assert data["replay_authorized"] is False
    assert data["existing_remote_objects_untouched"] is True


def test_actual_child_issue_dispositions_are_complete() -> None:
    data = _register()
    dispositions = {
        item["issue"]: item
        for item in data["closed_operational_issues"]  # type: ignore[index]
    }

    assert set(dispositions) == {31, 32, 33, 38, 99, 119, 123}

    for issue in (31, 38, 119):
        assert dispositions[issue]["state_reason"] == "completed"

    for issue in (32, 33, 99, 123):
        assert dispositions[issue]["state_reason"] == "not_planned"

    assert dispositions[119]["all_56_proven_native_clips"] is False
    assert dispositions[119]["no_blind_replay"] is True


def test_human_entrypoints_report_wave14_and_no_active_backlog() -> None:
    texts = {
        "current_state": CURRENT_STATE.read_text(encoding="utf-8"),
        "backlog": BACKLOG.read_text(encoding="utf-8"),
        "operations_index": OPERATIONS_INDEX.read_text(encoding="utf-8"),
        "agents": AGENTS.read_text(encoding="utf-8"),
    }

    required = (
        "WAVES_0_14_COMPLETED_REPOSITORY_POLISHED_OPERATIONAL_GRAPH_CLOSED_NO_PROVIDER_WRITES",
        "audit-register-v7-2026-08-05.json",
        "Provider writes remain unauthorized",
        "No operational continuation is pending",
        "one shared user access token",
        "OAuth alias `fedor-milovanov`",
        "OAuth alias `legendary-poet`",
        "Do not group #32/#38 as Legendary Poet",
    )
    joined = "\n".join(texts.values())
    for statement in required:
        assert statement in joined

    assert "## Active backlog\n\nNone." in texts["backlog"]
    assert "Actual fresh live provider reconciliation: pending." not in joined
    assert "status: `requires_reconciliation`" not in joined
    assert "#123 — deferred YouTube playlist mutation contract" not in joined


def test_permanent_unknown_is_not_promoted_or_replayed() -> None:
    data = _register()
    unknown = data["permanent_unknowns"][0]  # type: ignore[index]

    assert unknown == {
        "source_id": "M5hNecL_MsQ",
        "target_id": "-235216998_456239160",
        "observed_type": "video",
        "observed_is_draft": 1,
        "classification": "requires_attention_non_replayable_not_native_clip_success",
    }
    assert data["retired_undispatched_scope"] == {
        "legendary_poet_long_items": 6,
        "lord_god_non_authoritative_shorts_auto_upload": True,
        "article_wall_launcher_generations": True,
        "youtube_playlist_mutation_scope": True,
    }
