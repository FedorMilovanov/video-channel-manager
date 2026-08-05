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
        "docs/operations/audit-register-v4-2026-08-05.json",
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
    broken = [target for target in local_targets if not (index_path.parent / target).resolve().is_file()]
    assert broken == []


def test_current_state_records_completed_wave12b_without_live_completion() -> None:
    text = (OPERATIONS_DIR / "current-state.md").read_text(encoding="utf-8")
    required = (
        "WAVES_0_12B_ENGINEERING_GOVERNANCE_COMPLETED",
        "main@38296d07f8b6e948a6c5c4846bb66bf116bcfb72",
        "ffd275e9173db5a46bdde85f318dfa08ca83adb3",
        "30988821430",
        "789 passed, 1 xfailed",
        "self_tested_credential_and_issue_graph_governance",
        "audit-register-v4-2026-08-05.json",
        "audit-register-v3-2026-08-05.json",
        "Actual fresh live provider reconciliation: pending",
        "one shared **user access token**",
        "it is not a project selector",
        "#31 — Lord God long-form reconciliation",
        "#32 — Lord God Shorts/Clips reconciliation",
        "#119 — Legendary Poet Shorts/Clips reconciliation",
        "#38 — shared provider-mode/final-type contract",
        "OAuth alias `fedor-milovanov`",
        "OAuth alias `legendary-poet`",
        "Issue #32 is not a Legendary Poet owner",
        "#33 — Lord God video catalog/publication gate",
        "VK Audio/MP3 and Legendary Poet are excluded",
        "#123 — deferred YouTube playlist mutation contract",
        "SEPARATE_EXPERIMENTAL_SYSTEM",
    )
    for fact in required:
        assert fact in text

    for claim in (
        "Actual fresh live provider reconciliation: completed",
        "Owner issues: #32 and #38",
        "#32/#38 — pending fresh Legendary Poet reconciliation",
        "#37 is an active operational owner",
    ):
        assert claim not in text


def test_agent_instructions_preserve_wave12b_project_and_credential_boundaries() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    required = (
        "main@38296d07f8b6e948a6c5c4846bb66bf116bcfb72",
        "PR #124",
        "30988821430",
        "789 passed, 1 xfailed",
        "one shared user access token",
        "it is not a project selector",
        "Using `fedor-milovanov` for #31/#32 does not imply a second VK token",
        "Package A output never authorizes a provider mutation by itself",
        "PowerShell orchestrates one repository-owned implementation",
        "#31 — `lord-god-strength` long-form reconciliation",
        "#32 — `lord-god-strength` Shorts/Clips reconciliation",
        "#119 — `legendary-poet` Shorts/Clips reconciliation",
        "#38 — shared VK native Clip/ordinary-video provider-mode",
        "Do not group #32/#38 as Legendary Poet ownership",
        "#123 — deferred YouTube playlist-mutation contract",
        "VK Audio browser/internal-web work remains",
        "filter=moder",
        "filter=admin",
        "LastWriteTime",
        "$PSScriptRoot",
    )
    for fact in required:
        assert fact in text

    assert "#37 — independent exact reviewed cleanup" not in text


def test_wave12a_predecessor_overlay_remains_valid_and_fail_closed() -> None:
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
    assert payload["wave_12a_status"] == "completed"
    assert payload["provider_queries_during_wave_12a"] == 0
    assert payload["provider_writes_during_wave_12a"] == 0
    assert payload["write_plans_created_during_wave_12a"] == 0
    assert payload["live_counts_are_fresh"] is False
    assert payload["mutation_authorized"] is False
    assert payload["automatic_execution"] is False


def test_wave11_predecessor_register_remains_valid_and_fail_closed() -> None:
    register_path = OPERATIONS_DIR / "audit-register-v2-2026-08-04.json"
    payload = json.loads(register_path.read_text(encoding="utf-8"))
    assert payload["schema_name"] == "video-manager.audit-register-v2"
    assert payload["schema_version"] == "2.9"
    assert payload["wave_11_code_head"] == "eeab53b779e5ea4af5d3dcc08d79e41812739e04"
    assert payload["wave_11_ci_run"] == 30967195938
    assert payload["wave_11_evidence_level"] == "self_tested_source_bound_governance"
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


def test_operational_contract_and_memory_sources_exist() -> None:
    required = (
        ROOT / "src/video_channel_manager/tools/operational_package_acceptance.py",
        OPERATIONS_DIR / "operational-package-acceptance.md",
        OPERATIONS_DIR / "retirement-registry-v1.json",
        ROOT / "docs/history/operational-attempts/lord-god-sermon-month-2026-08-05/SOURCE-METADATA.json",
        ROOT / ".github/copilot-instructions.md",
        OPERATIONS_DIR / "project-memory-changelog.d/2026-08-05-wave-12a.md",
        OPERATIONS_DIR / "project-memory-changelog.d/2026-08-05-wave-12b.md",
        OPERATIONS_DIR / "milestone-and-credential-reconciliation-2026-08-05.md",
    )
    for path in required:
        assert path.is_file()

    source = required[0].read_text(encoding="utf-8")
    assert "provider_writes_authorized: Literal[False]" in source
    assert "automatic_execution: Literal[False]" in source
    assert "PROJECT_IDENTITIES" in source
