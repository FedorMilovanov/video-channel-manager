from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/milovi-telegram-follow-on-readiness.yml"


def test_follow_on_readiness_trigger_surface_is_retired() -> None:
    assert not WORKFLOW.exists()
