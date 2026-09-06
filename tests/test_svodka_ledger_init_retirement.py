from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/svodka-ledger-init.yml"
REGISTRY = ROOT / "docs/operations/retirement-registry-v1.json"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_svodka_ledger_bootstrap_is_retired_and_not_executable() -> None:
    assert not WORKFLOW.exists()

    registry = _load(REGISTRY)
    retired = {
        item["id"]: item
        for item in registry["retired_families"]  # type: ignore[index]
    }
    item = retired["svodka-publication-ledger-bootstrap-v1"]

    assert item["status"] == "retired_non_executable"
    assert item["execution_prohibited"] is True
    assert item["replacement"] is None
    assert item["issues"] == [539]
    assert item["historical_evidence"] == [
        "state/svodka-telegram@b7c060099036c2faf061209178c03d5b46c2edcf:content/telegram/svodka/publication-ledger.json",
    ]
