from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPERATIONS = ROOT / "docs" / "operations"
V8 = OPERATIONS / "audit-register-v8-2026-08-05.json"
V7 = OPERATIONS / "audit-register-v7-2026-08-05.json"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_v8_is_wave15_fail_closed_overlay() -> None:
    data = _load(V8)

    assert data["schema_name"] == "video-manager.audit-register-v8"
    assert data["schema_version"] == "8.0"
    assert data["predecessor_register"] == {
        "path": "docs/operations/audit-register-v7-2026-08-05.json",
        "blob_sha": "da3a29905eacc8233dfa969e857851de8b2cad8e",
        "schema_version": "7.0",
        "role": "immutable Wave 14 completed repository-polish contract",
    }
    assert data["program_state"] == (
        "WAVES_0_15_COMPLETED_ADAPTIVE_AGENT_REASONING_"
        "LOCAL_MP3_FOUNDATION_OPERATIONAL_GRAPH_CLOSED_NO_PROVIDER_WRITES"
    )
    assert data["operational_dispositions_inherited_unchanged_from_v7"] is True
    assert data["active_operational_issues"] == []
    assert data["active_repository_backlog_after_state_sync_merge"] == []
    assert data["existing_remote_objects_untouched"] is True
    assert data["provider_queries_during_wave_15"] == 0
    assert data["provider_writes_during_wave_15"] == 0
    assert data["write_plans_created_during_wave_15"] == 0
    assert data["historical_executors_run_during_wave_15"] == 0
    assert data["mutation_authorized"] is False
    assert data["automatic_execution"] is False
    assert data["replay_authorized"] is False


def test_wave15_exact_proof_is_machine_readable() -> None:
    wave = _load(V8)["wave_15_adaptive_agent_and_mp3_foundation"]  # type: ignore[index]

    assert wave == {
        "issue": 133,
        "pull_request": 134,
        "exact_head": "48baa13b0d08e27e5a1dfc8b30901524d3207148",
        "merge": "eb58c1ad238fde01d66c6630b16e244b1c6c2992",
        "ci_run": 31006136529,
        "pytest": "833 passed, 1 xfailed",
        "coverage": "79% across 14643 statements",
        "ruff_correctness": "green",
        "ruff_format": "461 files already formatted",
        "mypy": "147 source files",
        "dependency_audit": "no known vulnerabilities",
        "powershell_environments_green": 3,
        "changed_files": 12,
        "provider_adapter_files_changed": 0,
        "historical_mp3_browser_packages_executed": False,
        "production_provider_behavior_changed": False,
    }


def test_mp3_foundation_remains_strictly_local_only() -> None:
    mp3 = _load(V8)["local_mp3_foundation"]  # type: ignore[index]

    assert mp3["support_level"] == "local_only_read_only_intake_and_manifest"
    assert mp3["provider_mutation_support"] is False
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
    assert mp3["default_metadata_policy"] == "explicit_only"
    assert mp3["default_ready_chunk_size"] == 1


def test_human_entrypoints_report_wave15_and_no_active_backlog() -> None:
    texts = {
        "current_state": (OPERATIONS / "current-state.md").read_text(encoding="utf-8"),
        "backlog": (OPERATIONS / "automation-backlog.md").read_text(encoding="utf-8"),
        "operations_index": (OPERATIONS / "README.md").read_text(encoding="utf-8"),
        "agents": (ROOT / "AGENTS.md").read_text(encoding="utf-8"),
    }
    joined = "\n".join(texts.values())
    required = (
        "WAVES_0_15_COMPLETED_ADAPTIVE_AGENT_REASONING_LOCAL_MP3_FOUNDATION_OPERATIONAL_GRAPH_CLOSED_NO_PROVIDER_WRITES",
        "audit-register-v8-2026-08-05.json",
        "main@eb58c1ad238fde01d66c6630b16e244b1c6c2992",
        "PR #134",
        "31006136529",
        "833 passed, 1 xfailed",
        "461 files already formatted",
        "147 source files",
        "local_only_read_only_intake_and_manifest",
        "Provider writes remain unauthorized",
        "No operational continuation is pending",
    )
    for phrase in required:
        assert phrase in joined

    assert "## Active backlog\n\nNone." in texts["backlog"]
    assert "provider_mutation_support: true" not in joined.casefold()
    assert "VK Audio writer is supported" not in joined


def test_v7_remains_immutable_wave14_contract() -> None:
    data = _load(V7)

    assert data["schema_name"] == "video-manager.audit-register-v7"
    assert data["schema_version"] == "7.0"
    assert data["program_state"] == (
        "WAVES_0_14_COMPLETED_REPOSITORY_POLISHED_OPERATIONAL_GRAPH_CLOSED_NO_PROVIDER_WRITES"
    )
    assert data["provider_queries_during_wave_14"] == 0
    assert data["provider_writes_during_wave_14"] == 0
    assert data["write_plans_created_during_wave_14"] == 0
    assert data["mutation_authorized"] is False
