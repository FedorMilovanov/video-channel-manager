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
        "docs/operations/audit-register-v6-2026-08-05.json",
        "docs/operations/audit-register-v5-2026-08-05.json",
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


def test_current_state_records_completed_wave13_and_zero_active_graph() -> None:
    text = (OPERATIONS_DIR / "current-state.md").read_text(encoding="utf-8")
    required = (
        "WAVES_0_13_COMPLETED_OPERATIONAL_GRAPH_CLOSED_NO_PROVIDER_WRITES",
        "main@8d6a5ba243788e7b95b0e8a57eb02fb10eaf12ba",
        "731cc247a0c757c7103cd1ce5336adaf125d04d0",
        "30992600857",
        "792 passed, 1 xfailed",
        "audit-register-v6-2026-08-05.json",
        "audit-register-v5-2026-08-05.json",
        "No operational continuation is pending",
        "one shared **user access token**",
        "is not a project selector",
        "#31 — Lord God long-form reconciliation",
        "#32 — non-authoritative Lord God 108-item Shorts auto-upload scope",
        "#119 — Legendary Poet Shorts/Clips reconciliation",
        "#38 — shared VK native Clip/ordinary-video provider-mode",
        "OAuth alias `fedor-milovanov`",
        "OAuth alias `legendary-poet`",
        "Do not group #32/#38 as Legendary Poet",
        "#33 — broad Lord God catalog/editorial/postponed-wall continuation",
        "#99 — unproved Legendary Poet article-wall launcher continuation",
        "#123 — deferred YouTube playlist mutation scope",
        "SEPARATE_EXPERIMENTAL_SYSTEM",
        "Provider writes remain unauthorized",
    )
    for fact in required:
        assert fact in text

    for claim in (
        "Actual fresh live provider reconciliation: pending",
        "status: `requires_reconciliation`",
        "Correct active operational graph",
        "all 56 are native Clips",
        "#37 is an active operational owner",
    ):
        assert claim not in text


def test_agent_instructions_preserve_final_project_and_credential_boundaries() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    required = (
        "main@8d6a5ba243788e7b95b0e8a57eb02fb10eaf12ba",
        "PR #128",
        "30992600857",
        "792 passed, 1 xfailed",
        "one shared user access token",
        "it is not a project selector",
        "They do not imply separate VK tokens",
        "Package A output never authorizes a provider mutation by itself",
        "PowerShell orchestrates one repository-owned implementation",
        "#31 — exact Lord God 26-item long-form reconciliation",
        "#32 — Lord God non-authoritative 108-item Shorts auto-upload scope",
        "#119 — Legendary Poet Shorts/Clips reconciliation",
        "#38 — shared VK native Clip/ordinary-video final-type contract",
        "Do not group #32/#38 as Legendary Poet",
        "#123 — deferred YouTube playlist mutation scope",
        "VK Audio browser/internal-web work remains",
        "filter=moder",
        "filter=admin",
        "LastWriteTime",
        "$PSScriptRoot",
        "No operational continuation is pending",
    )
    for fact in required:
        assert fact in text

    for claim in (
        "#37 — independent exact reviewed cleanup",
        "active operational issues after completed-state merge: `1`",
        "automatic over-60-second native Clip publication is supported",
    ):
        assert claim not in text


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
        OPERATIONS_DIR / "final-operational-disposition-2026-08-05.md",
        OPERATIONS_DIR / "audit-register-v6-2026-08-05.json",
    )
    for path in required:
        assert path.is_file()

    source = required[0].read_text(encoding="utf-8")
    assert "provider_writes_authorized: Literal[False]" in source
    assert "automatic_execution: Literal[False]" in source
    assert "PROJECT_IDENTITIES" in source
