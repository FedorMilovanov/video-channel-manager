from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/svodka-native-rich-message-canary.yml"
REGISTRY = ROOT / "docs/operations/retirement-registry-v1.json"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_native_rich_canary_is_retired_and_not_executable() -> None:
    assert not WORKFLOW.exists()

    registry = _load(REGISTRY)
    retired = {
        item["id"]: item
        for item in registry["retired_families"]  # type: ignore[index]
    }
    item = retired["svodka-native-rich-message-canary-v1"]

    assert item["status"] == "retired_non_executable"
    assert item["execution_prohibited"] is True
    assert item["replacement"] is None
    assert item["issues"] == [537]
    assert item["historical_evidence"] == [
        "state/svodka-telegram:content/telegram/svodka/native-rich-message-canary.json",
        "github-actions:run/31441659164/attempt/1",
    ]
