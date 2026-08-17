from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_root_agent_contract_preserves_hardened_resi_rules() -> None:
    agents = text("AGENTS.md")

    for required in (
        "video-manager resi watch",
        "resi watch --background",
        "PID proves startup only",
        "target-page scoped",
        "--require-single-audio",
        "must not auto-dispatch a multi-gigabyte FULL download",
        "Russian-labelled page/player proves routing only",
    ):
        assert required in agents


def test_windows_handoff_contract_preserves_unattended_resi_rules() -> None:
    instructions = text(".github/copilot-instructions.md")

    for required in (
        "resi watch --background",
        "detached child owns keep-awake",
        "PID proves startup only",
        "scoped to the exact target page",
        "--require-single-audio",
        "Do not recreate a hidden PowerShell/Python watcher pair",
    ):
        assert required in instructions


def test_grace_runbook_preserves_two_phase_language_and_download_gates() -> None:
    runbook = text("docs/operations/resi-grace-russian-live.md")

    for required in (
        "Never collapse 1–3 into claim 4",
        "--background",
        "startup grace check",
        "target page",
        "exactly one audio stream at sample time",
        "--require-single-audio",
        "immediately before a new remote FULL download",
        "watch -> sample -> explicit guarded handoff",
    ):
        assert required in runbook

    assert "watch -> automatic multi-GB download" in runbook
