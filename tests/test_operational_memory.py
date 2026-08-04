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


def test_current_state_preserves_completed_wave8_and_read_only_wave9() -> None:
    text = (OPERATIONS_DIR / "current-state.md").read_text(encoding="utf-8")
    required_facts = (
        "WAVE_8_COMPLETED_WAVE_9_READ_ONLY_RECONCILIATION_ACTIVE",
        "dc3b25fdbbdb7d87e34f0f52e29fc9e3856190ae",
        "30950259625",
        "744 passed, 1 xfailed",
        "self_tested",
        "video-manager.catalog-identity-evidence",
        "wave-8c-v1",
        "video-manager.media-artifact-evidence",
        "wave-8d-v1",
        "video-manager.vk-thumbnail-evidence",
        "wave-8e-v1",
        "video-manager.operation-integration-evidence",
        "wave-8f-v1",
        "comparison snapshots/digest",
        "WavePlan source/self/operation-set digests",
        "expected remote delta",
        "planned`, `uploaded`, `verified`, `duplicate`, `failed`, and `requires_attention",
        "build_operation_integration_evidence",
        "OperationIntegrationEvidence",
        "provider_writes` is structurally `0",
        "Wave 9A — Lord God reconciliation",
        "Wave 9B — Legendary Poet reconciliation",
        "do not create a write plan",
        "do not perform provider writes during Wave 9 read-only reconciliation",
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
        "b9c0268be62ea8fb9281cc9a551ebc5621dfdd4bfeb22a9d8f4b50707baa33ed",
        "data\\vk-upload\\verified-longform-26",
        "BLOCKED_PENDING_FRESH_READ_ONLY_WALL_AUDIT_AND_LOCAL_LEDGER_RECONCILIATION",
        "56 exact YouTube Shorts",
        "41 exact pairs",
        "15 confirmed missing",
        "REVIEWED_MANIFEST_PREPARED / UPLOAD_COMPLETION_NOT_PROVEN",
        "SEPARATE_EXPERIMENTAL_SYSTEM",
    )
    for fact in required_facts:
        assert fact in text


def test_wave8_supported_contract_files_exist() -> None:
    required = (
        ROOT / "src/video_channel_manager/application/cross_platform/models.py",
        ROOT / "src/video_channel_manager/application/catalog_identity.py",
        ROOT / "src/video_channel_manager/local_media/artifact.py",
        ROOT / "src/video_channel_manager/platforms/vk/upload_media.py",
        ROOT / "src/video_channel_manager/platforms/vk/thumbnail_lifecycle.py",
        ROOT / "src/video_channel_manager/wave_engine/integration.py",
        ROOT / "tests/test_wave8_integration_evidence.py",
        ROOT / "tests/test_wave8_integration_public_boundary.py",
    )
    for path in required:
        assert path.is_file()

    integration = required[5].read_text(encoding="utf-8")
    assert 'INTEGRATION_SCHEMA: Literal["video-manager.operation-integration-evidence"]' in integration
    assert 'INTEGRATION_RULESET: Literal["wave-8f-v1"]' in integration
    assert 'evidence_level: Literal["self_tested"]' in integration
    assert "provider_writes: Literal[0]" in integration
    assert "build_operation_integration_evidence" in integration
    assert "calculate_integration_totals" in integration
    assert "REQUIRES_ATTENTION" in integration


def test_audit_register_tracks_completed_wave8_and_active_read_only_wave9() -> None:
    payload = json.loads((OPERATIONS_DIR / "audit-register-v2-2026-08-04.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "2.6"
    assert payload["wave_8e_state_sync_head"] == "bc267504258e07e8bb68ca4760b0b9beb2571b6d"
    assert payload["wave_8f_code_head"] == "dc3b25fdbbdb7d87e34f0f52e29fc9e3856190ae"
    assert payload["wave_8f_ci_run"] == 30950259625
    assert payload["program_state"] == "WAVE_8_COMPLETED_WAVE_9_READ_ONLY_RECONCILIATION_ACTIVE_NO_PROVIDER_WRITES"
    assert payload["wave_8_evidence_level"] == "self_tested"
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
    ):
        assert findings[finding_id]["status"] == "fixed"
    assert findings["STAGE-001"]["status"] == "covered_and_preserved"
    assert findings["LIVE-LORD-001"]["status"] == "requires_reconciliation"
    assert findings["LIVE-POET-001"]["status"] == "requires_reconciliation"
    assert findings["AUDIO-001"]["status"] == "separate_system"
    for wave in ("8a", "8b", "8c", "8d", "8e", "8f"):
        assert payload[f"provider_writes_during_wave_{wave}"] == 0
    assert payload["provider_writes_during_state_sync"] == 0
