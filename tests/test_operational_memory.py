from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPERATIONS_DIR = ROOT / "docs" / "operations"


def test_agent_instructions_reference_existing_sources_of_truth() -> None:
    agents_path = ROOT / "AGENTS.md"
    assert agents_path.is_file()
    text = agents_path.read_text(encoding="utf-8")
    required_sources = (
        "docs/operations/master-audit-marathon-v2-2026-08-04.md",
        "docs/operations/audit-register-v2-2026-08-04.json",
        "docs/operations/current-state.md",
        "docs/operations/2026-07-31-youtube-vk-transfer-postmortem.md",
        "docs/operations/operational-artifact-standard.md",
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


def test_current_state_preserves_completed_wave9_contract_and_pending_live_reconciliation() -> None:
    text = (OPERATIONS_DIR / "current-state.md").read_text(encoding="utf-8")
    required_facts = (
        "WAVE_9_READ_ONLY_RECONCILIATION_CONTRACT_COMPLETED_LIVE_RECONCILIATION_PENDING_NO_PROVIDER_WRITES",
        "604b962a9936ab173e41602bd9ab10b2dfaa9e59",
        "30954499845",
        "761 passed, 1 xfailed",
        "read_only_contract_self_tested",
        "Actual fresh Wave 9A/9B provider reconciliation: pending",
        "Provider queries during Wave 9 contract implementation and CI: `0`",
        "Provider writes during Wave 9 contract implementation and CI: `0`",
        "Write plans created during Wave 9 contract implementation and CI: `0`",
        "video-manager.read-only-reconciliation-evidence",
        "wave-9-v1",
        "build_read_only_reconciliation_evidence",
        "ReadOnlyReconciliationEvidence",
        "BoundedSourceSnapshot",
        "BoundedTargetSnapshot",
        "LocalReconciliationRecord",
        "RemoteReconciliationObservation",
        "present",
        "duplicate",
        "missing",
        "unknown",
        "requires_attention",
        "provider_writes` is structurally `0",
        "write_plan_created` is structurally `false",
        "future_write_authorized=false",
        "do not create a write plan",
        "Do not perform provider writes during Wave 9 live read-only reconciliation",
        "scripts/operator/Invoke-VideoManager.ps1",
        "15 supported mutation boundaries",
        "25/25",
        "unknown_requires_reconciliation",
        "file_selected` is not `upload_completed",
        "PowerShell boundaries explicitly test zero, one, and many",
        "a URL-shaped value is not an upload ticket",
        "designed, self-tested, canary-verified, and batch-verified",
        "UCeSJsC6go2c9pdJCuUI1BYA",
        "UC-78ys2S3cQ3lpqgXfo-SvQ",
        "60805374",
        "-60805374",
        "235216998",
        "-235216998",
        "confirmed_deleted=403",
        "run=completed",
        "KobOzfBqzic",
        "s512Opa8Eu4",
        "-60805374_456241938",
        "previously verified missing: `26`",
        "23 confirmed",
        "4wmCcHMcP90",
        "Vs__dbIlVqU",
        "84puu6MnLZs",
        "b9c0268be62ea8fb9281cc9a551ebc5621dfdd4bfeb22a9d8f4b50707baa33ed",
        "data\\vk-upload\\verified-longform-26",
        "BLOCKED_PENDING_FRESH_READ_ONLY_WALL_AUDIT_AND_LOCAL_LEDGER_RECONCILIATION",
        "56 exact YouTube Shorts",
        "41 exact pairs",
        "15 confirmed missing",
        "REVIEWED_MANIFEST_PREPARED / UPLOAD_COMPLETION_NOT_PROVEN",
        "regression fixtures, not fresh provider snapshots",
        "SEPARATE_EXPERIMENTAL_SYSTEM",
    )
    for fact in required_facts:
        assert fact in text


def test_wave8_and_wave9_supported_contract_files_exist() -> None:
    required = (
        ROOT / "src/video_channel_manager/application/cross_platform/models.py",
        ROOT / "src/video_channel_manager/application/catalog_identity.py",
        ROOT / "src/video_channel_manager/local_media/artifact.py",
        ROOT / "src/video_channel_manager/platforms/vk/upload_media.py",
        ROOT / "src/video_channel_manager/platforms/vk/thumbnail_lifecycle.py",
        ROOT / "src/video_channel_manager/wave_engine/integration.py",
        ROOT / "src/video_channel_manager/wave_engine/reconciliation.py",
        ROOT / "tests/test_wave8_integration_evidence.py",
        ROOT / "tests/test_wave8_integration_public_boundary.py",
        ROOT / "tests/test_wave9_read_only_reconciliation.py",
        ROOT / "tests/test_wave9_reconciliation_public_boundary.py",
    )
    for path in required:
        assert path.is_file()

    integration = required[5].read_text(encoding="utf-8")
    assert 'INTEGRATION_SCHEMA: Literal["video-manager.operation-integration-evidence"]' in integration
    assert 'INTEGRATION_RULESET: Literal["wave-8f-v1"]' in integration
    assert 'evidence_level: Literal["self_tested"]' in integration
    assert "provider_writes: Literal[0]" in integration
    assert "build_operation_integration_evidence" in integration
    assert "REQUIRES_ATTENTION" in integration

    reconciliation = required[6].read_text(encoding="utf-8")
    assert 'RECONCILIATION_SCHEMA: Literal["video-manager.read-only-reconciliation-evidence"]' in reconciliation
    assert 'RECONCILIATION_RULESET: Literal["wave-9-v1"]' in reconciliation
    assert 'evidence_level: Literal["read_only_reconciliation"]' in reconciliation
    assert "provider_writes: Literal[0]" in reconciliation
    assert "write_plan_created: Literal[False]" in reconciliation
    assert "future_write_authorized: Literal[False]" in reconciliation
    assert "build_read_only_reconciliation_evidence" in reconciliation
    assert "ReconciliationState.PRESENT" in reconciliation
    assert "ReconciliationState.DUPLICATE" in reconciliation
    assert "ReconciliationState.MISSING" in reconciliation
    assert "ReconciliationState.UNKNOWN" in reconciliation
    assert "ReconciliationState.REQUIRES_ATTENTION" in reconciliation


def test_audit_register_tracks_completed_wave9_contract_and_pending_live_reconciliation() -> None:
    payload = json.loads((OPERATIONS_DIR / "audit-register-v2-2026-08-04.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "2.7"
    assert payload["wave_8e_state_sync_head"] == "bc267504258e07e8bb68ca4760b0b9beb2571b6d"
    assert payload["wave_8f_code_head"] == "dc3b25fdbbdb7d87e34f0f52e29fc9e3856190ae"
    assert payload["wave_8f_ci_run"] == 30950259625
    assert payload["wave_9_contract_code_head"] == "604b962a9936ab173e41602bd9ab10b2dfaa9e59"
    assert payload["wave_9_contract_ci_run"] == 30954499845
    assert (
        payload["program_state"]
        == "WAVE_9_READ_ONLY_RECONCILIATION_CONTRACT_COMPLETED_LIVE_RECONCILIATION_PENDING_NO_PROVIDER_WRITES"
    )
    assert payload["wave_8_evidence_level"] == "self_tested"
    assert payload["wave_9_contract_evidence_level"] == "read_only_contract_self_tested"
    assert payload["wave_9_live_reconciliation_status"] == (
        "pending_fresh_bounded_provider_snapshots_and_local_ledgers"
    )
    assert payload["wave_9_contract_schema"] == "video-manager.read-only-reconciliation-evidence"
    assert payload["wave_9_contract_ruleset"] == "wave-9-v1"
    assert payload["source_line_count"] == 7046

    source = next(item for item in payload["sources"] if item["name"] == "Вставленный текст(276).txt")
    assert source == {
        "name": "Вставленный текст(276).txt",
        "lines": 515,
        "sha256": "e62d428a31e3f167cce298a37936b132c023e61b5b8edee7b4f80e26c57e434a",
    }

    findings = {item["id"]: item for item in payload["findings"]}
    for finding_id in (
        "MATCH-001",
        "MATCH-002",
        "MATCH-003",
        "IDENTITY-001",
        "IDENTITY-002",
        "URL-001",
        "ALBUM-001",
        "CATALOG-001",
        "CATALOG-002",
        "CATALOG-003",
        "MEDIA-001",
        "MEDIA-002",
        "MEDIA-003",
        "THUMB-001",
        "OPS-SCOPE-001",
        "RECON-001",
    ):
        assert findings[finding_id]["status"] == "fixed"
    assert findings["STAGE-001"]["status"] == "covered_and_preserved"
    assert findings["LIVE-LORD-001"]["status"] == "requires_reconciliation"
    assert findings["LIVE-POET-001"]["status"] == "requires_reconciliation"
    assert findings["AUDIO-001"]["status"] == "separate_system"

    for wave in ("8a", "8b", "8c", "8d", "8e", "8f"):
        assert payload[f"provider_writes_during_wave_{wave}"] == 0
    assert payload["provider_queries_during_wave_9_contract"] == 0
    assert payload["provider_writes_during_wave_9_contract"] == 0
    assert payload["write_plans_created_during_wave_9_contract"] == 0
    assert payload["provider_writes_during_wave_9_state_sync"] == 0
    assert payload["provider_writes_during_state_sync"] == 0
