from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPERATIONS_DIR = ROOT / "docs" / "operations"


def test_agent_instructions_reference_existing_sources_of_truth() -> None:
    agents_path = ROOT / "AGENTS.md"
    assert agents_path.is_file()

    text = agents_path.read_text(encoding="utf-8")
    required_sources = (
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
        "WAVE_4_COMPLETED_WAVE_5_NEXT",
    )

    for fact in required_facts:
        assert fact in text
