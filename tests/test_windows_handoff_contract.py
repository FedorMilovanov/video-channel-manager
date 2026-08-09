from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / ".github" / "copilot-instructions.md"
OPERATIONS_INDEX = ROOT / "docs" / "operations" / "README.md"


def test_windows_handoff_contract_is_fail_closed_and_scoped() -> None:
    text = HANDOFF.read_text(encoding="utf-8")
    required = (
        "`AGENTS.md` is the repository operating contract",
        "never authorizes provider writes",
        r"C:\Users\Fedor\Projects\video-channel-manager",
        r"C:\Users\Fedor\Downloads",
        r"C:\Users\Fedor\Projects\video-channel-manager\operator-output",
        '$ErrorActionPreference = "Stop"',
        "-LiteralPath",
        "Test-Path -LiteralPath",
        "$PSScriptRoot",
        "require exactly one match",
        "LastWriteTime",
        "evidence level",
        "exact `project_key`",
        "provider-effect state",
        "exact repository-owned entrypoint",
        "smallest non-mutating probe",
        "another ZIP/version family",
        "UTF-8 with BOM",
    )
    for invariant in required:
        assert invariant in text

    for duplicated_or_unsafe in (
        "provider_writes_authorized=true",
        "automatic_execution=true",
        "select the newest ZIP",
        "rerun the retired executor",
        "Historical Wave",
        "Current production code baseline",
    ):
        assert duplicated_or_unsafe not in text


def test_operations_index_preserves_historical_wave14_evidence() -> None:
    text = OPERATIONS_INDEX.read_text(encoding="utf-8")
    required = (
        "Waves 0–7 — completed",
        "Waves 8A–8F — completed",
        "Wave 9 read-only contract — completed",
        "Package A / Waves 9A–10 — completed",
        "Wave 11 — completed",
        "Wave 12 — completed",
        "Wave 12A / #118 — completed",
        "Wave 12B / #122 — completed",
        "Wave 12C / #126 — completed",
        "Wave 13 / #127 — completed",
        "Wave 14 / #130 — completed",
        "PR #131",
        "31000834701",
        "801 passed, 1 xfailed",
        "451 files already formatted",
        "one shared user access token",
        "never selects a project",
        "OAuth alias `fedor-milovanov`",
        "OAuth alias `legendary-poet`",
        "#31 — long-form reconciliation",
        "#32 — Shorts/Clips reconciliation",
        "#119 — Shorts/Clips reconciliation",
        "#38 — shared VK native Clip/ordinary-video provider-mode",
        "#123 — YouTube playlist mutation design",
        "Do not group #32/#38 as Legendary Poet",
        "Every tracked JSON file must parse",
        "Local Markdown links must resolve",
        "Provider writes remain unauthorized",
        "Closed issues and historical packages must not be reopened as execution authority",
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
        "Actual fresh live provider reconciliation: pending",
        "status: `requires_reconciliation`",
        "#123 — deferred YouTube playlist mutation contract",
        "safe playlist operations",
        "editorial CI run #669",
    ):
        assert claim not in text
