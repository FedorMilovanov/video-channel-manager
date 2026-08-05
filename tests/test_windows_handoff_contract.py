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

    for claim in (
        "provider_writes_authorized=true",
        "automatic_execution=true",
        "select the newest ZIP",
        "rerun the retired executor",
    ):
        assert claim not in text


def test_operations_index_records_completed_wave12b_and_project_bound_graph() -> None:
    text = OPERATIONS_INDEX.read_text(encoding="utf-8")
    required = (
        "Waves 0–7, Audit A0, and Waves 8A–8F — completed",
        "Wave 9 and Package A / Waves 9A–10 — completed",
        "Wave 11 — completed",
        "Wave 12 — completed",
        "Wave 12A / #118 — completed",
        "Wave 12B / #122 — completed",
        "one shared user access token",
        "never selects a project",
        "`fedor-milovanov` → Lord God channel",
        "`legendary-poet` → Legendary Poet channel",
        "#31 — long-form reconciliation",
        "#32 — Shorts/Clips reconciliation",
        "#119 — Shorts/Clips reconciliation",
        "#38 — shared VK native Clip/ordinary-video provider-mode",
        "#123 — deferred YouTube playlist mutation contract",
        "Closed #2–#5 and #37 are not active owners",
        "Do not group #32/#38 as Legendary Poet",
        "never authorize writes",
    )
    for fact in required:
        assert fact in text

    for claim in (
        "Wave 8 / issue #86 — active core engineering",
        "Wave 10 — retirement and production governance",
        "Wave 12 / issue #115 — active repository governance",
        "Wave 12A / #118 — active correction",
        "issues #32/#38 own the Shorts/Clips surface",
        "#32/#38 — pending fresh Legendary Poet reconciliation",
        "#37 — independent exact reviewed cleanup only",
    ):
        assert claim not in text
