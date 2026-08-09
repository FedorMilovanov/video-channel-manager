from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "docs" / "operations" / "audit-register-v6-2026-08-05.json"
WAVE14_REGISTER = ROOT / "docs" / "operations" / "audit-register-v7-2026-08-05.json"
CURRENT_STATE = ROOT / "docs" / "operations" / "current-state.md"
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


def test_wave14_history_is_immutable_without_polluting_live_entrypoints() -> None:
    wave14 = json.loads(WAVE14_REGISTER.read_text(encoding="utf-8"))
    assert (
        wave14["program_state"]
        == "WAVES_0_14_COMPLETED_REPOSITORY_POLISHED_OPERATIONAL_GRAPH_CLOSED_NO_PROVIDER_WRITES"
    )
    assert wave14["wave_14_repository_polish"] == {
        "issue": 130,
        "pull_request": 131,
        "exact_head": "80f701b6926a5a9c788b99c69634b54d63ed1862",
        "merge": "626f83c6e5c068d7faa8b6d14163b42916faa769",
        "ci_run": 31000834701,
        "pytest": "801 passed, 1 xfailed",
        "coverage": "78% across 14306 statements",
        "ruff_correctness": "green",
        "ruff_format": "451 files already formatted",
        "mypy": "145 source files",
        "dependency_audit": "no known vulnerabilities",
        "powershell_environments_green": 3,
        "changed_files": 7,
        "runtime_provider_code_files_changed": 0,
        "production_runtime_behavior_changed": False,
        "test_clock_determinism_fixed": True,
    }

    live = CURRENT_STATE.read_text(encoding="utf-8") + "\n" + AGENTS.read_text(encoding="utf-8")
    assert wave14["program_state"] not in live
    assert "No operational continuation is pending" not in live
    assert "main@626f83c6e5c068d7faa8b6d14163b42916faa769" not in live


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
