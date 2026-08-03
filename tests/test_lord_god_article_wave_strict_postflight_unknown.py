from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lord_god_article_wave_v3 import link_cards_hardened_entry as entry  # noqa: E402


def test_network_failure_persists_unknown_before_raising(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    policy, contract = entry.core.load_hardened_policy(ROOT)
    expectations: dict[str, dict[str, str]] = {
        str(operation["operation_id"]): {
            "title": str(operation["title"]),
            "description": (
                "Проверенное полное описание карточки длиной более сорока символов."
            ),
        }
        for operation in policy["operations"]
    }
    result: dict[str, Any] = {"status": "completed", "operations": []}
    monkeypatch.setattr(
        entry,
        "wall_snapshot",
        lambda client: (_ for _ in ()).throw(RuntimeError("VK read timeout")),
    )

    with pytest.raises(RuntimeError, match="postflight outcome is unknown"):
        entry.verify_strict_postflight(
            mode="canary",
            policy=policy,
            contract=contract,
            expectations=expectations,
            read_client=object(),
            journal=entry.core.fresh_journal(policy, contract),
            output_dir=tmp_path,
            result=result,
        )

    path = tmp_path / "link-card-canary-result.json"
    assert path.is_file()
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["status"] == "strict_postflight_unknown"
    assert written["description_match_mode"] == entry.DESCRIPTION_MATCH_MODE
    assert "VK read timeout" in written["strict_postflight_error"]
