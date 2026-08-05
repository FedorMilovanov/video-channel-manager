from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPERATIONS = ROOT / "docs" / "operations"
V7 = OPERATIONS / "audit-register-v7-2026-08-05.json"
V6 = OPERATIONS / "audit-register-v6-2026-08-05.json"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_v7_is_wave14_fail_closed_overlay() -> None:
    data = _load(V7)

    assert data["schema_name"] == "video-manager.audit-register-v7"
    assert data["schema_version"] == "7.0"
    assert data["predecessor_register"] == {
        "path": "docs/operations/audit-register-v6-2026-08-05.json",
        "blob_sha": "bfbfec0150ecb5dbba3f24e3bb7d3b6dfd9c0bd3",
        "schema_version": "6.0",
        "role": "immutable Wave 13 completed operational-graph contract",
    }
    assert data["program_state"] == (
        "WAVES_0_14_COMPLETED_REPOSITORY_POLISHED_"
        "OPERATIONAL_GRAPH_CLOSED_NO_PROVIDER_WRITES"
    )
    assert data["operational_dispositions_inherited_unchanged_from_v6"] is True
    assert data["active_operational_issues"] == []
    assert data["active_repository_backlog_after_state_sync_merge"] == []
    assert data["open_issues_after_state_sync_merge"] == []
    assert data["open_pull_requests_after_state_sync_merge"] == []
    assert data["issue_130_closes_with_state_sync_merge"] is True
    assert data["existing_remote_objects_untouched"] is True
    assert data["provider_queries_during_wave_14"] == 0
    assert data["provider_writes_during_wave_14"] == 0
    assert data["write_plans_created_during_wave_14"] == 0
    assert data["historical_executors_run_during_wave_14"] == 0
    assert data["mutation_authorized"] is False
    assert data["automatic_execution"] is False
    assert data["replay_authorized"] is False


def test_wave14_exact_proof_and_scope_are_machine_readable() -> None:
    data = _load(V7)
    wave = data["wave_14_repository_polish"]  # type: ignore[index]

    assert wave == {
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


def test_integrity_contract_distinguishes_capability_from_authorization() -> None:
    data = _load(V7)
    integrity = data["repository_integrity_contract"]  # type: ignore[index]

    assert integrity == {
        "all_tracked_json_must_parse": True,
        "local_markdown_links_must_resolve": True,
        "code_examples_do_not_authorize_execution": True,
        "root_readme_exposes_no_write_boundary": True,
        "stale_initial_roadmap_removed": True,
        "stale_ci_and_playlist_next_step_claims_removed": True,
    }


def test_v6_remains_immutable_wave13_contract() -> None:
    data = _load(V6)

    assert data["schema_name"] == "video-manager.audit-register-v6"
    assert data["schema_version"] == "6.0"
    assert data["program_state"] == (
        "WAVES_0_13_COMPLETED_OPERATIONAL_GRAPH_CLOSED_NO_PROVIDER_WRITES"
    )
    assert data["provider_queries_during_wave_13"] == 0
    assert data["provider_writes_during_wave_13"] == 0
    assert data["write_plans_created_during_wave_13"] == 0
    assert data["mutation_authorized"] is False
