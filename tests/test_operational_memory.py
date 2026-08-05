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
        "docs/operations/audit-register-v2-2026-08-04.json",
        "docs/operations/current-state.md",
        "docs/operations/automation-backlog.md",
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


def test_current_state_records_wave11_without_claiming_live_or_batch_completion() -> None:
    text = (OPERATIONS_DIR / "current-state.md").read_text(encoding="utf-8")
    required = (
        "WAVE_11_OPERATIONAL_PACKAGE_TRUTH_COMPLETED_LIVE_RECONCILIATION_PENDING_NO_PROVIDER_WRITES",
        "eeab53b779e5ea4af5d3dcc08d79e41812739e04",
        "30967195938",
        "782 passed, 1 xfailed",
        "self_tested_source_bound_governance",
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
        "Вставленный текст(290).txt",
        "2fd8cbd46e5b39b2baa0b4adcebba3cbfc6e57e445cddd5a8d16dbb5795bfb1d",
        "Actual fresh Wave 9A/9B live provider reconciliation: pending",
        "BLOCKED_PENDING_FRESH_READ_ONLY_WALL_AUDIT_AND_LOCAL_LEDGER_RECONCILIATION",
        "REVIEWED_MANIFEST_PREPARED / UPLOAD_COMPLETION_NOT_PROVEN",
        "KobOzfBqzic",
        "BXZeRiEOHmQ",
        "SEPARATE_EXPERIMENTAL_SYSTEM",
    )
    for fact in required:
        assert fact in text
    assert "independently `batch_verified`" in text
    assert "Actual fresh Wave 9A/9B live provider reconciliation: completed" not in text


def test_agent_instructions_preserve_wave11_and_read_only_boundaries() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    required = (
        "main@eeab53b779e5ea4af5d3dcc08d79e41812739e04",
        "Package A PR #110",
        "Package A state sync PR #111",
        "Wave 11 PR #113",
        "782 passed, 1 xfailed",
        "editorial_prepared",
        "preview_validated",
        "canary_verified",
        "batch_verified",
        "filter=moder",
        "filter=admin",
        "Do not rerun it",
        "operator_transcript_reported",
        "Package A output never authorizes a provider mutation by itself",
        "PowerShell must not become a second provider implementation",
    )
    for fact in required:
        assert fact in text


def test_wave11_machine_register_is_valid_and_fail_closed() -> None:
    payload = json.loads(
        (OPERATIONS_DIR / "audit-register-v2-2026-08-04.json").read_text(encoding="utf-8")
    )
    assert payload["schema_name"] == "video-manager.audit-register-v2"
    assert payload["schema_version"] == "2.9"
    assert payload["wave_11_code_head"] == "eeab53b779e5ea4af5d3dcc08d79e41812739e04"
    assert payload["wave_11_ci_run"] == 30967195938
    assert payload["wave_11_evidence_level"] == "self_tested_source_bound_governance"
    assert payload["program_state"] == (
        "WAVE_11_OPERATIONAL_PACKAGE_TRUTH_COMPLETED_LIVE_RECONCILIATION_PENDING_NO_PROVIDER_WRITES"
    )
    assert payload["live_wave_9a_9b_reconciliation"] == (
        "pending_exact_local_ledgers_and_fresh_bounded_provider_snapshots"
    )
    assert payload["source_line_count"] == 7413
    assert len(payload["sources"]) == 8
    transcript = next(item for item in payload["sources"] if item["name"] == "Вставленный текст(290).txt")
    assert transcript == {
        "name": "Вставленный текст(290).txt",
        "lines": 367,
        "sha256": "2fd8cbd46e5b39b2baa0b4adcebba3cbfc6e57e445cddd5a8d16dbb5795bfb1d",
        "evidence_level": "operator_transcript_reported",
    }
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
    assert payload["provider_queries_during_wave_11"] == 0
    assert payload["provider_writes_during_wave_11"] == 0
    assert payload["write_plans_created_during_wave_11"] == 0
    assert payload["provider_writes_during_state_sync"] == 0


def test_wave11_contract_and_history_sources_exist() -> None:
    required = (
        ROOT / "src/video_channel_manager/tools/operational_package_acceptance.py",
        OPERATIONS_DIR / "operational-package-acceptance.md",
        OPERATIONS_DIR / "retirement-registry-v1.json",
        ROOT
        / "docs/history/operational-attempts/lord-god-sermon-month-2026-08-05/SOURCE-METADATA.json",
    )
    for path in required:
        assert path.is_file()
    source = required[0].read_text(encoding="utf-8")
    assert "provider_writes_authorized: Literal[False]" in source
    assert "automatic_execution: Literal[False]" in source
    assert "PROJECT_IDENTITIES" in source
