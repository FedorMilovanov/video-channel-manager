from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / ".github" / "copilot-instructions.md"
OPERATIONS_INDEX = ROOT / "docs" / "operations" / "README.md"


def test_windows_handoff_contract_is_fail_closed() -> None:
    text = HANDOFF.read_text(encoding="utf-8")
    required = (
        "supplement the repository-root `AGENTS.md`",
        "This file never authorizes provider writes",
        r"C:\Users\Fedor\Projects\video-channel-manager",
        r"C:\Users\Fedor\Downloads",
        '$ErrorActionPreference = "Stop"',
        "-LiteralPath",
        "Test-Path -LiteralPath",
        "$PSScriptRoot",
        "require exactly one match",
        "Never choose an artifact by `LastWriteTime`",
        "evidence level",
        "exact community ID and owner ID",
        "provider_writes_authorized=false",
        "automatic_execution=false",
        "must not become a second provider client",
        "generated external `executor.py`",
        "retirement-registry-v1.json",
        "never blind-retry an unknown outcome",
        "UTF-8 with BOM",
        "machine-readable output paths",
    )
    for invariant in required:
        assert invariant in text

    prohibited_claims = (
        "provider_writes_authorized=true",
        "automatic_execution=true",
        "select the newest ZIP",
        "rerun the retired executor",
    )
    for claim in prohibited_claims:
        assert claim not in text


def test_operations_index_records_post_wave11_sequence() -> None:
    text = OPERATIONS_INDEX.read_text(encoding="utf-8")
    required = (
        "Waves 8A–8F — completed",
        "Wave 9 read-only evidence contract — completed",
        "Package A",
        "Wave 11 — completed",
        "Wave 12 / issue #115",
        "Live reconciliation — pending",
        "#31",
        "#32/#38",
        "#33",
        "provider writes remain unauthorized",
    )
    for fact in required:
        assert fact in text

    stale_claims = (
        "Wave 8 / issue #86 — active core engineering",
        "Wave 10 — retirement and production governance",
    )
    for claim in stale_claims:
        assert claim not in text
