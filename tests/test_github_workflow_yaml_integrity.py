"""Prevent malformed GitHub Actions workflows from reaching main without CI detection."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from yaml.nodes import MappingNode, ScalarNode

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted(path for path in (REPO_ROOT / ".github" / "workflows").iterdir() if path.suffix in {".yml", ".yaml"})


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda path: path.name)
def test_each_github_workflow_is_valid_yaml(workflow: Path) -> None:
    """Parse exact workflow bytes, including inline run commands with YAML colons."""
    try:
        root = yaml.compose(workflow.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        pytest.fail(f"Invalid GitHub Actions YAML in {workflow.relative_to(REPO_ROOT)}: {exc}")
    assert isinstance(root, MappingNode), workflow.name
    keys = [key.value for key, _value in root.value if isinstance(key, ScalarNode)]
    assert "on" in keys and "jobs" in keys, workflow.name


def test_unquoted_pip_binary_selector_reproduces_the_original_yaml_error() -> None:
    invalid = "run: python -m pip install --only-binary=:all: -r requirements/telegram-publisher.txt\n"
    with pytest.raises(yaml.YAMLError):
        yaml.compose(invalid)
