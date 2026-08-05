from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPERATIONS = ROOT / "docs" / "operations"
INCIDENT = ROOT / "docs" / "history" / "operational-attempts" / "lord-god-sermon-month-2026-08-05"


def test_operational_acceptance_contract_preserves_truth_levels_and_zero_authority() -> None:
    text = (OPERATIONS / "operational-package-acceptance.md").read_text(encoding="utf-8")
    required = (
        "editorial_prepared",
        "preview_validated",
        "self_tested",
        "canary_verified",
        "batch_verified",
        "provider_write_bundle",
        "provider_writes_authorized=false",
        "automatic_execution=false",
        "scripts/operator/Invoke-VideoManager.ps1",
        "groups.get(filter=moder, extended=1)",
        "filter=admin",
        "per_operation_results_required=true",
        "unknown_outcome_requires_reconciliation=true",
        "operator_transcript_reported",
        "Do not rerun v1, v2, or v3",
    )
    for fact in required:
        assert fact in text


def test_sermon_month_incident_archive_is_source_bound_and_non_executable() -> None:
    metadata = json.loads((INCIDENT / "SOURCE-METADATA.json").read_text(encoding="utf-8"))
    assert metadata["schema_name"] == "video-manager.historical-incident-source"
    assert metadata["archive_id"] == "lord-god-sermon-month-2026-08-05"
    assert metadata["source"] == {
        "filename": "Вставленный текст(290).txt",
        "sha256": "2fd8cbd46e5b39b2baa0b4adcebba3cbfc6e57e445cddd5a8d16dbb5795bfb1d",
        "bytes": 16765,
        "splitlines_count": 366,
        "file_service_line_count": 367,
        "kind": "operator_chat_transcript",
    }
    assert metadata["evidence"]["v3_batch_outcome"] == "operator_transcript_reported"
    assert metadata["evidence"]["independently_verified_provider_state"] is False
    assert metadata["reported_v3_outcome"]["scheduled_operations"] == 30
    assert metadata["reported_v3_outcome"]["first_post_id"] == "-60805374_12482"
    assert metadata["reported_v3_outcome"]["last_post_id"] == "-60805374_12511"
    assert metadata["reported_v3_outcome"]["rerun_prohibited"] is True
    assert metadata["execution_authority"] is False
    assert metadata["provider_writes_authorized"] is False

    expected = {
        "README.md",
        "TIMELINE.md",
        "LESSONS.md",
        "REPRESENTATIVE-SNIPPETS.md",
        "SOURCE-METADATA.json",
    }
    assert {path.name for path in INCIDENT.iterdir() if path.is_file()} == expected
    assert {path.suffix for path in INCIDENT.iterdir() if path.is_file()} <= {".md", ".json"}


def test_incident_lessons_prohibit_parallel_publishers_and_stdout_only_success() -> None:
    lessons = (INCIDENT / "LESSONS.md").read_text(encoding="utf-8")
    snippets = (INCIDENT / "REPRESENTATIVE-SNIPPETS.md").read_text(encoding="utf-8")
    required_lessons = (
        "PowerShell orchestrates one repository-owned CLI",
        "Downloads-only executors are never a supported adapter",
        "groups.get(filter=moder, extended=1)",
        "FINAL_OK — 30/30",
        "every operation owns a durable result",
        "unknown_requires_reconciliation",
        "Do not rerun",
    )
    combined = lessons + snippets
    for fact in required_lessons:
        assert fact in combined


def test_operational_documentation_indexes_wave11_contract_and_incident() -> None:
    operations_index = (OPERATIONS / "README.md").read_text(encoding="utf-8")
    history_index = (ROOT / "docs" / "history" / "operational-attempts" / "README.md").read_text(encoding="utf-8")
    standard = (OPERATIONS / "operational-artifact-standard.md").read_text(encoding="utf-8")

    assert "operational-package-acceptance.md" in operations_index
    assert "lord-god-sermon-month-2026-08-05/" in history_index
    assert "video_channel_manager.tools.operational_package_acceptance" in standard
    assert "provider_writes_authorized=false" in standard
