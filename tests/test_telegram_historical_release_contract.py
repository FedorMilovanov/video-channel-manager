from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_PATH = ROOT / "content/telegram/lordchrist/historical-editorial/v1/production-release-2026-09-cycle-01.json"


def test_historical_release_uses_durable_successor_binding_only() -> None:
    release = json.loads(RELEASE_PATH.read_text(encoding="utf-8"))

    assert "successor_cycle_verified" not in release
    assert release["replenishment_guard_remaining"] == 1
