from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPERATIONS = ROOT / "docs" / "operations"
V9 = OPERATIONS / "audit-register-v9-2026-08-05.json"
V8 = OPERATIONS / "audit-register-v8-2026-08-05.json"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_v9_is_wave16_fail_closed_overlay() -> None:
    data = _load(V9)

    assert data["schema_name"] == "video-manager.audit-register-v9"
    assert data["schema_version"] == "9.0"
    assert data["predecessor_register"] == {
        "path": "docs/operations/audit-register-v8-2026-08-05.json",
        "blob_sha": "f45244b9be7bfa35402f42d20b533e413c176bc2",
        "schema_version": "8.0",
        "role": "immutable Wave 15 adaptive-agent and local-only MP3 foundation contract",
    }
    assert data["program_state"] == (
        "WAVES_0_16_COMPLETED_CI_RUNTIME_SQLITE_MP3_IDENTITY_HARDENED_OPERATIONAL_GRAPH_CLOSED_NO_PROVIDER_WRITES"
    )
    assert data["operational_dispositions_inherited_unchanged_from_v8"] is True
    assert data["active_operational_issues"] == []
    assert data["active_repository_backlog_after_state_sync_merge"] == []
    assert data["existing_remote_objects_untouched"] is True
    assert data["provider_queries_during_wave_16"] == 0
    assert data["provider_writes_during_wave_16"] == 0
    assert data["write_plans_created_during_wave_16"] == 0
    assert data["historical_executors_run_during_wave_16"] == 0
    assert data["browser_launches_during_wave_16"] == 0
    assert data["id3_writes_during_wave_16"] == 0
    assert data["mutation_authorized"] is False
    assert data["automatic_execution"] is False
    assert data["replay_authorized"] is False


def test_wave16_exact_proof_is_machine_readable() -> None:
    wave = _load(V9)["wave_16_ci_sqlite_mp3_identity_hardening"]  # type: ignore[index]

    assert wave == {
        "issue": 137,
        "pull_request": 138,
        "exact_head": "c495308430bce6e1b86343b6cd4e6ae3a302734b",
        "merge": "22ed56256df3388c23c9f785f1e02cca71fd8524",
        "ci_run": 31022560789,
        "pytest": "845 passed, 1 xfailed",
        "coverage": "79% across 14675 statements",
        "ruff_correctness": "green",
        "ruff_format": "464 files already formatted",
        "mypy": "147 source files",
        "dependency_audit": "no known vulnerabilities",
        "powershell_environments_green": 3,
        "changed_files": 9,
        "provider_adapter_files_changed": 0,
        "node20_deprecation_warning_present": False,
        "unclosed_sqlite_resource_warning_present": False,
        "production_provider_behavior_changed": False,
    }


def test_v9_records_ci_and_sqlite_lifetime_contracts() -> None:
    data = _load(V9)
    ci = data["ci_runtime_contract"]  # type: ignore[index]
    sqlite = data["sqlite_lifetime_contract"]  # type: ignore[index]

    assert ci["node_runtime_generation"] == 24
    assert ci["immutable_action_sha_required"] is True
    assert ci["checkout"].endswith("de0fac2e4500dabe0009e67214ff5f5447ce83dd")
    assert ci["setup_python"].endswith("a309ff8b426b58ec0e2a45f0f869d46889d02405")
    assert ci["upload_artifact"].endswith("043fb46d1a93c77aae656e7c1c64a875d1fc6a0a")
    assert sqlite == {
        "connections_explicitly_closed": True,
        "contextlib_closing_used": True,
        "unclosed_database_resource_warning_is_test_error": True,
        "package_a_remains_read_only": True,
    }


def test_v9_mp3_identity_hardening_remains_local_only() -> None:
    mp3 = _load(V9)["local_mp3_foundation"]  # type: ignore[index]

    assert mp3["support_level"] == "local_only_read_only_intake_and_manifest"
    assert mp3["manifest_schema_version"] == "1.1"
    assert mp3["provider_mutation_support"] is False
    assert mp3["metadata_ranked_canonical_selection"] is True
    assert mp3["source_id_sha256_conflict_fail_closed"] is True
    assert mp3["sha256_multiple_source_ids_fail_closed"] is True
    assert mp3["unique_deterministic_candidate_operation_ids"] is True
    assert mp3["thousand_track_ready_count"] == 1000
    assert mp3["thousand_track_chunk_count_at_25"] == 40
    for prohibited in (
        "id3_rewrite",
        "rename",
        "transcode",
        "browser_launch",
        "provider_access",
        "upload",
        "remote_metadata_edit",
        "playlist_mutation",
        "wall_publication",
    ):
        assert mp3[prohibited] is False


def test_human_entrypoints_report_wave16_and_no_active_backlog() -> None:
    texts = {
        "current_state": (OPERATIONS / "current-state.md").read_text(encoding="utf-8"),
        "backlog": (OPERATIONS / "automation-backlog.md").read_text(encoding="utf-8"),
        "operations_index": (OPERATIONS / "README.md").read_text(encoding="utf-8"),
        "agents": (ROOT / "AGENTS.md").read_text(encoding="utf-8"),
    }
    joined = "\n".join(texts.values())
    required = (
        "WAVES_0_16_COMPLETED_CI_RUNTIME_SQLITE_MP3_IDENTITY_HARDENED_OPERATIONAL_GRAPH_CLOSED_NO_PROVIDER_WRITES",
        "audit-register-v9-2026-08-05.json",
        "main@22ed56256df3388c23c9f785f1e02cca71fd8524",
        "PR #138",
        "31022560789",
        "845 passed, 1 xfailed",
        "464 files already formatted",
        "147 source files",
        "source_id_sha256_conflict",
        "sha256_multiple_source_ids",
        "Provider writes remain unauthorized",
        "No operational continuation is pending",
    )
    for phrase in required:
        assert phrase in joined

    assert "## Active backlog\n\nNone." in texts["backlog"]
    assert "provider_mutation_support: true" not in joined.casefold()
    assert "VK Audio writer is supported" not in joined


def test_v8_remains_immutable_wave15_contract() -> None:
    data = _load(V8)

    assert data["schema_name"] == "video-manager.audit-register-v8"
    assert data["schema_version"] == "8.0"
    assert data["program_state"] == (
        "WAVES_0_15_COMPLETED_ADAPTIVE_AGENT_REASONING_LOCAL_MP3_FOUNDATION_OPERATIONAL_GRAPH_CLOSED_NO_PROVIDER_WRITES"
    )
    assert data["provider_queries_during_wave_15"] == 0
    assert data["provider_writes_during_wave_15"] == 0
    assert data["write_plans_created_during_wave_15"] == 0
    assert data["mutation_authorized"] is False
