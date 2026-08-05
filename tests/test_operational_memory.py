from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPERATIONS_DIR = ROOT / "docs" / "operations"


def test_agent_instructions_reference_existing_sources_of_truth() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    required_sources = (
        "docs/operations/master-audit-marathon-v2-2026-08-04.md",
        "docs/operations/audit-register-v3-2026-08-05.json",
        "docs/operations/audit-register-v2-2026-08-04.json",
        "docs/operations/current-state.md",
        "docs/operations/automation-backlog.md",
        ".github/copilot-instructions.md",
        "docs/operations/operational-artifact-standard.md",
        "docs/operations/operational-package-acceptance.md",
        "docs/operations/retirement-registry-v1.json",
    )
    for relative_path in required_sources:
        assert relative_path in text
        assert (ROOT / relative_path).is_file()


def test_operations_index_has_no_broken_local_markdown_links() -> None:
    index_path = OPERATIONS_DIR / "README.md"
    text = index_path.read_text(encoding="utf-8")
    local_targets = re.findall(r"\[[^]]+\]\(([^)]+\.md)\)", text)
    assert local_targets
    broken = [
        target
        for target in local_targets
        if not (index_path.parent / target).resolve().is_file()
    ]
    assert broken == []


def test_current_state_records_completed_wave12a_without_live_completion() -> None:
    text = (OPERATIONS_DIR / "current-state.md").read_text(encoding="utf-8")
    required = (
        "WAVES_0_12A_ENGINEERING_GOVERNANCE_COMPLETED",
        "main@30c1ec11040034f6d3ed2492afe1bc7c029db1d0",
        "98b4f3df7dd25918398d3544ee81d2b04a0aa21b",
        "30971070928",
        "785 passed, 1 xfailed",
        "self_tested_project_bound_governance",
        "audit-register-v3-2026-08-05.json",
        "739146b63cfb3207a6b8d2d7a12698b3e54c28dd",
        "python -m video_channel_manager.tools.operational_package_acceptance",
        "editorial_prepared",
        "preview_validated",
        "self_tested",
        "canary_verified",
        "batch_verified",
        "provider_writes_authorized=false",
        "automatic_execution=false",
        "groups.get(filter=moder, extended=1, count=1000, offset=0)",
        "filter=admin",
        "operator_transcript_reported",
        "FINAL_OK — 30/30",
        "-60805374_12482",
        "-60805374_12511",
        "2fd8cbd46e5b39b2baa0b4adcebba3cbfc6e57e445cddd5a8d16dbb5795bfb1d",
        "Actual fresh live provider reconciliation: pending",
        "BLOCKED_PENDING_FRESH_READ_ONLY_WALL_AUDIT_AND_LOCAL_LEDGER_RECONCILIATION",
        "REVIEWED_MANIFEST_PREPARED / UPLOAD_COMPLETION_NOT_PROVEN",
        "KobOzfBqzic",
        "BXZeRiEOHmQ",
        "SEPARATE_EXPERIMENTAL_SYSTEM",
        "LastWriteTime",
        "$PSScriptRoot",
        "#31 — Lord God long-form reconciliation",
        "#32 — Lord God Shorts/Clips reconciliation",
        "#119 — Legendary Poet Shorts/Clips reconciliation",
        "#38 — shared provider-mode/final-type contract",
        "Issue #32 is not a Legendary Poet owner",
        "#33 — Lord God video catalog/publication gate",
        "VK Audio/MP3 and Legendary Poet are excluded",
    )
    for fact in required:
        assert fact in text
    assert "independently `batch_verified`" in text
    assert "Actual fresh live provider reconciliation: completed" not in text
    assert "Owner issues: #32 and #38" not in text


def test_agent_instructions_preserve_project_bound_read_only_owners() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    required = (
        "main@30c1ec11040034f6d3ed2492afe1bc7c029db1d0",
        "Package A PR #110",
        "Wave 11 operational-package truth",
        "Wave 12 deterministic Windows handoffs",
        "Wave 12A project-bound ownership correction",
        "30971070928",
        "785 passed, 1 xfailed",
        "self_tested_project_bound_governance",
        "editorial_prepared",
        "preview_validated",
        "canary_verified",
        "batch_verified",
        "filter=moder",
        "filter=admin",
        "operator_transcript_reported",
        "Package A output never authorizes a provider mutation by itself",
        "PowerShell orchestrates one repository-owned implementation",
        "LastWriteTime",
        "newest ZIP",
        "exact absolute paths",
        "$PSScriptRoot",
        "#31 — `lord-god-strength` long-form reconciliation",
        "#32 — `lord-god-strength` Shorts/Clips reconciliation",
        "#119 — `legendary-poet` Shorts/Clips reconciliation",
        "#38 — shared VK native Clip/ordinary-video provider-mode",
        "Do not group #32/#38 as Legendary Poet ownership",
        "OAuth alias `fedor-milovanov`",
        "OAuth alias `legendary-poet`",
        "VK Audio browser/internal-web work remains",
    )
    for fact in required:
        assert fact in text


def test_wave12a_machine_state_is_project_bound_and_fail_closed() -> None:
    overlay_path = OPERATIONS_DIR / "audit-register-v3-2026-08-05.json"
    payload = json.loads(overlay_path.read_text(encoding="utf-8"))
    assert payload["schema_name"] == "video-manager.audit-register-v3"
    assert payload["schema_version"] == "3.2"
    assert payload["predecessor_register"] == {
        "path": "docs/operations/audit-register-v2-2026-08-04.json",
        "blob_sha": "739146b63cfb3207a6b8d2d7a12698b3e54c28dd",
        "schema_version": "2.9",
        "role": "complete historical finding and source ledger",
    }
    assert (ROOT / payload["predecessor_register"]["path"]).is_file()
    assert payload["verified_main"] == "30c1ec11040034f6d3ed2492afe1bc7c029db1d0"
    assert payload["wave_12a_code_head"] == (
        "30c1ec11040034f6d3ed2492afe1bc7c029db1d0"
    )
    assert payload["wave_12a_exact_head"] == (
        "98b4f3df7dd25918398d3544ee81d2b04a0aa21b"
    )
    assert payload["wave_12a_ci_run"] == 30971070928
    assert payload["wave_12a_evidence_level"] == (
        "self_tested_project_bound_governance"
    )
    assert payload["wave_12a_status"] == "completed"
    assert payload["program_state"] == (
        "WAVES_0_12A_ENGINEERING_GOVERNANCE_COMPLETED_"
        "LIVE_RECONCILIATION_PENDING_NO_PROVIDER_WRITES"
    )

    graph = {item["issue"]: item for item in payload["active_operational_graph"]}
    assert graph[31] == {
        "issue": 31,
        "project_key": "lord-god-strength",
        "oauth_alias": "fedor-milovanov",
        "youtube_channel_id": "UCeSJsC6go2c9pdJCuUI1BYA",
        "vk_community_id": 60805374,
        "vk_owner_id": -60805374,
        "scope": "fresh bounded read-only long-form reconciliation",
        "status": "requires_reconciliation",
    }
    assert graph[32]["project_key"] == "lord-god-strength"
    assert graph[32]["oauth_alias"] == "fedor-milovanov"
    assert graph[32]["vk_owner_id"] == -60805374
    assert graph[119]["project_key"] == "legendary-poet"
    assert graph[119]["oauth_alias"] == "legendary-poet"
    assert graph[119]["vk_owner_id"] == -235216998
    assert "project_key" not in graph[38]
    assert graph[38]["status"] == "primary_source_and_canary_contract_required"
    assert graph[33]["project_key"] == "lord-god-strength"
    assert graph[33]["status"] == "blocked_by_issues_31_and_32"
    assert graph[99]["project_key"] == "legendary-poet"

    findings = {
        item["id"]: item for item in payload["corrected_source_of_truth_findings"]
    }
    assert set(findings) == {
        "OWNER-ISSUE-001",
        "OWNER-ISSUE-002",
        "OWNER-ISSUE-003",
        "OWNER-ISSUE-004",
    }
    assert all(item["status"] == "fixed" for item in findings.values())

    controls = payload["wave_12_controls"]
    assert controls["self_contained_powershell_required"] is True
    assert controls["exact_absolute_paths_required"] is True
    assert controls["newest_zip_selection_prohibited"] is True
    assert controls["external_generated_provider_executor_prohibited"] is True
    assert controls["unknown_outcome_blind_retry_prohibited"] is True
    assert payload["provider_queries_during_wave_12a"] == 0
    assert payload["provider_writes_during_wave_12a"] == 0
    assert payload["write_plans_created_during_wave_12a"] == 0
    assert payload["provider_writes_during_wave_12a_state_sync"] == 0
    assert payload["live_counts_are_fresh"] is False
    assert payload["mutation_authorized"] is False
    assert payload["automatic_execution"] is False


def test_wave11_predecessor_register_remains_valid_and_fail_closed() -> None:
    register_path = OPERATIONS_DIR / "audit-register-v2-2026-08-04.json"
    payload = json.loads(register_path.read_text(encoding="utf-8"))
    assert payload["schema_name"] == "video-manager.audit-register-v2"
    assert payload["schema_version"] == "2.9"
    assert payload["wave_11_code_head"] == (
        "eeab53b779e5ea4af5d3dcc08d79e41812739e04"
    )
    assert payload["wave_11_ci_run"] == 30967195938
    assert payload["wave_11_evidence_level"] == (
        "self_tested_source_bound_governance"
    )
    assert payload["source_line_count"] == 7413
    assert len(payload["sources"]) == 8
    findings = {item["id"]: item for item in payload["findings"]}
    for finding_id in (
        "PACKAGE-TRUTH-001",
        "VK-PERMISSION-001",
        "HISTORY-002",
        "ARCHIVE-001",
        "RECOVERY-001",
        "CONTROL-001",
        "GOV-001",
    ):
        assert findings[finding_id]["status"] == "fixed"
    assert findings["LIVE-LORD-001"]["status"] == "requires_reconciliation"
    assert findings["LIVE-POET-001"]["status"] == "requires_reconciliation"
    assert findings["AUDIO-001"]["status"] == "separate_system"


def test_wave11_contract_and_history_sources_exist() -> None:
    required = (
        ROOT / "src/video_channel_manager/tools/operational_package_acceptance.py",
        OPERATIONS_DIR / "operational-package-acceptance.md",
        OPERATIONS_DIR / "retirement-registry-v1.json",
        ROOT
        / "docs/history/operational-attempts/"
        "lord-god-sermon-month-2026-08-05/SOURCE-METADATA.json",
        ROOT / ".github/copilot-instructions.md",
    )
    for path in required:
        assert path.is_file()
    source = required[0].read_text(encoding="utf-8")
    assert "provider_writes_authorized: Literal[False]" in source
    assert "automatic_execution: Literal[False]" in source
    assert "PROJECT_IDENTITIES" in source
