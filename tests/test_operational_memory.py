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


def test_current_state_preserves_program_and_project_identity() -> None:
    text = (OPERATIONS_DIR / "current-state.md").read_text(encoding="utf-8")
    required_facts = (
        "WAVE_8C_COMPLETED_WAVE_8D_ACTIVE",
        "ee7766a651cd55a0f51bd3cd5acfbe3f29bfbaed",
        "30940734221",
        "694 passed, 1 xfailed",
        "wave-8b-v1",
        "video-manager.catalog-identity-evidence",
        "wave-8c-v1",
        "Cross-platform comparison schema is `3.0`",
        "VK catalog plan version is 3",
        "exact target album ID",
        "duplicate_canonical_target_title",
        "unreviewed_existing_candidate",
        "Conflict decisions create no album operation",
        "exact target video ID sets",
        "Wave 8D — authoritative media and cache evidence",
        "authoritative final path",
        "structured ffprobe evidence",
        "directory glob fallback",
        "MP4 alone does not prove H.264/AAC",
        "scripts/operator/Invoke-VideoManager.ps1",
        "15 supported mutation boundaries",
        "25/25",
        "unknown_requires_reconciliation",
        "file_selected` is not `upload_completed",
        "PowerShell boundaries explicitly test zero, one, and many",
        "A URL-shaped value is not an upload ticket",
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
        "verified missing: `26`",
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


def test_audit_register_tracks_wave_8c_and_active_media_findings() -> None:
    payload = json.loads((OPERATIONS_DIR / "audit-register-v2-2026-08-04.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "2.3"
    assert payload["wave_8c_code_head"] == "ee7766a651cd55a0f51bd3cd5acfbe3f29bfbaed"
    assert payload["wave_8c_ci_run"] == 30940734221
    assert payload["program_state"] == "WAVE_8C_COMPLETED_WAVE_8D_ACTIVE_NO_PROVIDER_WRITES"
    assert payload["source_line_count"] == 7046

    source = next(item for item in payload["sources"] if item["name"] == "Вставленный текст(276).txt")
    assert source == {
        "name": "Вставленный текст(276).txt",
        "lines": 515,
        "sha256": "e62d428a31e3f167cce298a37936b132c023e61b5b8edee7b4f80e26c57e434a",
    }

    findings = {item["id"]: item for item in payload["findings"]}
    assert findings["MATCH-001"]["status"] == "fixed"
    assert findings["IDENTITY-001"]["status"] == "fixed"
    assert findings["IDENTITY-002"]["status"] == "fixed"
    assert findings["URL-001"]["status"] == "fixed"
    assert findings["ALBUM-001"]["status"] == "fixed"
    assert findings["CATALOG-001"]["status"] == "fixed"
    assert findings["CATALOG-002"]["status"] == "fixed"
    assert findings["CATALOG-003"]["status"] == "fixed"
    assert findings["MEDIA-001"]["status"] == "active"
    assert findings["MEDIA-002"]["status"] == "active"
    assert findings["MEDIA-003"]["status"] == "active"
    assert findings["OPS-SCOPE-001"]["status"] == "policy_recorded"
    assert findings["UPLOAD-TICKET-001"]["status"] == "policy_recorded"
    assert payload["provider_writes_during_wave_8a"] == 0
    assert payload["provider_writes_during_wave_8b"] == 0
    assert payload["provider_writes_during_wave_8c"] == 0
    assert payload["provider_writes_during_state_sync"] == 0
