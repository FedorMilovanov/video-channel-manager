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


def test_current_state_records_completed_package_a_without_claiming_live_completion() -> None:
    text = (OPERATIONS_DIR / "current-state.md").read_text(encoding="utf-8")
    required_facts = (
        "PACKAGE_A_WAVE_9A_9B_WAVE_10_TOOLING_AND_GOVERNANCE_COMPLETED_LIVE_RECONCILIATION_PENDING_NO_PROVIDER_WRITES",
        "8f8b224f0386cf9f1ed89e0983e8af440e96cdd4",
        "30958445398",
        "773 passed, 1 xfailed",
        "read_only_package_self_tested",
        "video-manager-package-a reconcile",
        "video-manager-package-a verify-output",
        "video-manager.read-only-reconciliation-evidence",
        "wave-9-v1",
        "video-manager.recovery-decision-ledger",
        "wave-9b-v1",
        "video-manager.operator-board",
        "wave-10-v1",
        "Provider queries during Package A implementation and CI: `0`",
        "Provider writes during Package A implementation and CI: `0`",
        "Write plans created during Package A implementation and CI: `0`",
        "Actual fresh Wave 9A/9B live provider reconciliation: pending",
        "The output directory is evidence, not mutation authority",
        "BLOCKED_PENDING_FRESH_READ_ONLY_WALL_AUDIT_AND_LOCAL_LEDGER_RECONCILIATION",
        "REVIEWED_MANIFEST_PREPARED / UPLOAD_COMPLETION_NOT_PROVEN",
        "KobOzfBqzic",
        "s512Opa8Eu4",
        "-60805374_456241938",
        "b9c0268be62ea8fb9281cc9a551ebc5621dfdd4bfeb22a9d8f4b50707baa33ed",
        "BXZeRiEOHmQ",
        "-235216998_456239039",
        "56 exact YouTube Shorts",
        "41 exact retained pairs",
        "15 retained missing candidates",
        "UCeSJsC6go2c9pdJCuUI1BYA",
        "UC-78ys2S3cQ3lpqgXfo-SvQ",
        "60805374",
        "-60805374",
        "235216998",
        "-235216998",
        "SEPARATE_EXPERIMENTAL_SYSTEM",
    )
    for fact in required_facts:
        assert fact in text

    assert "Actual fresh Wave 9A/9B live provider reconciliation: completed" not in text
    assert "provider writes during Package A implementation and CI: `1`" not in text.lower()


def test_agent_instructions_preserve_package_a_read_only_boundary() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    required_facts = (
        "main@8f8b224f0386cf9f1ed89e0983e8af440e96cdd4",
        "Package A (Wave 9A + Wave 9B + Wave 10 tooling/governance)",
        "read_only_package_self_tested",
        "video-manager-package-a reconcile",
        "video-manager-package-a verify-output",
        "video-manager.recovery-decision-ledger",
        "video-manager.operator-board",
        "actual fresh Wave 9A/9B live reconciliation remains pending",
        "Package A output never authorizes a provider mutation by itself",
        "A dashboard or green status display is not mutation authorization",
    )
    for fact in required_facts:
        assert fact in text


def test_package_a_machine_register_is_valid_and_fail_closed() -> None:
    register_path = OPERATIONS_DIR / "audit-register-v2-2026-08-04.json"
    payload = json.loads(register_path.read_text(encoding="utf-8"))

    assert payload["schema_name"] == "video-manager.audit-register-v2"
    assert payload["schema_version"] == "2.8"
    assert payload["package_a_code_head"] == "8f8b224f0386cf9f1ed89e0983e8af440e96cdd4"
    assert payload["package_a_ci_run"] == 30958445398
    assert payload["program_state"] == (
        "PACKAGE_A_WAVE_9A_9B_WAVE_10_TOOLING_AND_GOVERNANCE_COMPLETED_LIVE_RECONCILIATION_PENDING_NO_PROVIDER_WRITES"
    )
    assert payload["package_a_evidence_level"] == "read_only_package_self_tested"
    assert payload["live_wave_9a_9b_reconciliation"] == (
        "pending_exact_local_ledgers_and_fresh_bounded_provider_snapshots"
    )
    assert payload["provider_queries_during_package_a"] == 0
    assert payload["provider_writes_during_package_a"] == 0
    assert payload["write_plans_created_during_package_a"] == 0
    assert payload["provider_writes_during_state_sync"] == 0
    assert payload["source_line_count"] == 7046

    assert len(payload["sources"]) == 7
    sources = {item["name"]: item for item in payload["sources"]}
    assert sources["Вставленный текст (4).txt"] == {
        "name": "Вставленный текст (4).txt",
        "lines": 1171,
        "sha256": "379b624e8743fb3d940ccc939f1f650bfd8967891dbc4869c1df1c6d56b878e0",
    }
    assert sources["Вставленный текст(276).txt"] == {
        "name": "Вставленный текст(276).txt",
        "lines": 515,
        "sha256": "e62d428a31e3f167cce298a37936b132c023e61b5b8edee7b4f80e26c57e434a",
    }

    findings = {item["id"]: item for item in payload["findings"]}
    for finding_id in (
        "TRUTH-001",
        "ADMIN-001",
        "ARCHIVE-001",
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
        "RECOVERY-001",
        "CONTROL-001",
        "GOV-001",
    ):
        assert findings[finding_id]["status"] == "fixed"

    assert findings["STAGE-001"]["status"] == "covered_and_preserved"
    assert findings["LIVE-LORD-001"]["status"] == "requires_reconciliation"
    assert findings["LIVE-POET-001"]["status"] == "requires_reconciliation"
    assert findings["AUDIO-001"]["status"] == "separate_system"


def test_wave9_and_package_a_public_contract_sources_exist() -> None:
    required = (
        ROOT / "src/video_channel_manager/wave_engine/reconciliation.py",
        ROOT / "src/video_channel_manager/wave_engine/__init__.py",
        ROOT / "pyproject.toml",
    )
    for path in required:
        assert path.is_file()

    reconciliation = required[0].read_text(encoding="utf-8")
    assert "video-manager.read-only-reconciliation-evidence" in reconciliation
    assert "wave-9-v1" in reconciliation
    assert "provider_writes" in reconciliation

    pyproject = required[2].read_text(encoding="utf-8")
    assert "video-manager-package-a" in pyproject
