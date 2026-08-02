from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE_CONTRACT = Path("content/policies/lord-god-article-wave-v3-source-contract.json")
BASE_POLICY = Path("content/policies/lord-god-article-wave-v3-202608.json")


@pytest.fixture(autouse=True)
def copy_article_source_contract_for_isolated_policy_test(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Complete the legacy isolated Plan fixture after it writes its base policy."""
    if request.node.name != "test_plan_branch_never_calls_execute_scope":
        return

    tmp_path = request.getfixturevalue("tmp_path")
    assert isinstance(tmp_path, Path)
    isolated_policy = tmp_path / BASE_POLICY
    isolated_contract = tmp_path / SOURCE_CONTRACT
    original_write_text = Path.write_text

    def write_text_and_contract(self: Path, *args: Any, **kwargs: Any) -> int:
        written = original_write_text(self, *args, **kwargs)
        if self == isolated_policy:
            shutil.copyfile(ROOT / SOURCE_CONTRACT, isolated_contract)
        return written

    monkeypatch.setattr(Path, "write_text", write_text_and_contract)
