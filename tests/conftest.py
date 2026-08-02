from __future__ import annotations

import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE_CONTRACT = Path(
    "content/policies/lord-god-article-wave-v3-source-contract.json"
)


@pytest.fixture(autouse=True)
def copy_article_source_contract_for_isolated_policy_test(
    request: pytest.FixtureRequest,
) -> None:
    """Keep the legacy isolated-repository Plan test complete after the new contract."""
    if request.node.name != "test_plan_branch_never_calls_execute_scope":
        return
    tmp_path = request.getfixturevalue("tmp_path")
    assert isinstance(tmp_path, Path)
    target = tmp_path / SOURCE_CONTRACT
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / SOURCE_CONTRACT, target)
