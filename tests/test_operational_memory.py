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


def test_current_state_preserves_verified_operational_identity() -> None:
    text = (OPERATIONS_DIR / "current-state.md").read_text(encoding="utf-8")

    required_facts = (
        "lord-god-strength",
        "UCeSJsC6go2c9pdJCuUI1BYA",
        "UC-78ys2S3cQ3lpqgXfo-SvQ",
        "60805374",
        "-60805374",
        "confirmed_deleted=403",
        "run=completed",
        "KobOzfBqzic",
        "s512Opa8Eu4",
        "-60805374_456241938",
        "verified missing: `26`",
        "b9c0268be62ea8fb9281cc9a551ebc5621dfdd4bfeb22a9d8f4b50707baa33ed",
        "data\\vk-upload\\verified-longform-26",
        "BLOCKED_PENDING_FRESH_READ_ONLY_WALL_AUDIT_AND_LOCAL_LEDGER_RECONCILIATION",
        "d85f7cf94b8ba0b30947291b3a08491239438843",
        "1a62779293a404e4654b6230644dfc78e9b20dc1",
        "c4c4d3233ec20b8f939343c5d667d8687d7ff040",
        "df956bbbf19af6652f8711f95fb4fecf272e9951",
        "30918639372",
        "a06a93e1ec16b4ddb0f578a92e47ce76b4ee78a5",
        "30925523584",
        "09babd9176049d8271c50b6f5e44b7b0fd10d39f",
        "30933582322",
        "664 passed, 1 xfailed",
        "WAVE_8A_COMPLETED_WAVE_8B_ACTIVE",
        "master-audit-marathon-v2-2026-08-04.md",
        "audit-register-v2-2026-08-04.json",
        "Wave 8 / issue #86",
        "scripts/operator/Invoke-VideoManager.ps1",
        "15 supported mutation boundaries",
        "25/25",
        "unknown_requires_reconciliation",
        "provider writes 0",
        "SEPARATE_EXPERIMENTAL_SYSTEM",
        "duplicate_exact_title",
        "exact_title_duration_mismatch",
        "non_unique_fallback",
        "exact field-by-field readback",
        "file_selected` is not `upload_completed",
        "PowerShell boundaries must explicitly test zero, one, and many",
        "A URL-shaped value is not an upload ticket",
        "designed, self-tested, canary-verified, and batch-verified",
    )

    for fact in required_facts:
        assert fact in text


def test_audit_register_tracks_wave_8a_and_new_source() -> None:
    payload = json.loads((OPERATIONS_DIR / "audit-register-v2-2026-08-04.json").read_text(encoding="utf-8"))

    assert payload["schema_version"] == "2.1"
    assert payload["wave_8a_code_head"] == "09babd9176049d8271c50b6f5e44b7b0fd10d39f"
    assert payload["wave_8a_ci_run"] == 30933582322
    assert payload["program_state"] == "WAVE_8A_COMPLETED_WAVE_8B_ACTIVE_NO_PROVIDER_WRITES"
    assert payload["source_line_count"] == 7046

    source = next(item for item in payload["sources"] if item["name"] == "Вставленный текст(276).txt")
    assert source == {
        "name": "Вставленный текст(276).txt",
        "lines": 515,
        "sha256": "e62d428a31e3f167cce298a37936b132c023e61b5b8edee7b4f80e26c57e434a",
    }

    findings = {item["id"]: item for item in payload["findings"]}
    assert findings["MATCH-001"]["status"] == "fixed"
    assert findings["MATCH-002"]["status"] == "fixed"
    assert findings["MATCH-003"]["status"] == "fixed"
    assert findings["IDENTITY-002"]["target_wave"] == "Wave-8B"
    assert findings["OPS-SCOPE-001"]["status"] == "policy_recorded"
    assert findings["UPLOAD-TICKET-001"]["status"] == "policy_recorded"
    assert payload["provider_writes_during_wave_8a"] == 0
    assert payload["provider_writes_during_state_sync"] == 0
