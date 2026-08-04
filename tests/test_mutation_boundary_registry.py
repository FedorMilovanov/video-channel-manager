from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "docs" / "operations" / "mutation-boundaries.json"


def _registry() -> dict[str, Any]:
    payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _pytest_functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
    }


def _pester_titles(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    return set(re.findall(r'(?m)^\s*It\s+"([^"]+)"\s*\{', text))


def test_mutation_boundary_registry_has_complete_supported_surface() -> None:
    payload = _registry()

    assert payload["schema_name"] == "video-manager.mutation-boundary-registry"
    assert payload["schema_version"] == 1
    assert payload["policy_version"] == "wave7-risk-registry-v1"

    families = payload["families"]
    assert isinstance(families, list)
    assert families

    identifiers = [item["id"] for item in families]
    assert len(identifiers) == len(set(identifiers))

    required_components = {
        "vk_upload",
        "vk_wall",
        "youtube_comment",
        "youtube_description",
        "vk_description",
        "vk_thumbnail",
        "youtube_oauth",
        "shared_http",
        "wave_engine",
        "powershell_operator",
    }
    assert {item["component"] for item in families} >= required_components

    allowed_classes = {"ambiguous_mutation", "safe_read", "local_durable_commit", "local_process", "mixed"}
    for family in families:
        assert family["class"] in allowed_classes
        assert isinstance(family["replay"], str) and family["replay"].strip()
        assert isinstance(family["checkpoints"], list) and family["checkpoints"]
        assert len(family["checkpoints"]) == len(set(family["checkpoints"]))
        assert isinstance(family["evidence"], list) and len(family["evidence"]) >= 3
        assert isinstance(family["owners"], list) and family["owners"]

        module_path = ROOT / family["module"]
        assert module_path.is_file(), family["module"]
        module_text = module_path.read_text(encoding="utf-8")
        for checkpoint in family["checkpoints"]:
            assert checkpoint in module_text, f"{family['id']} missing runtime checkpoint {checkpoint!r}"

        for framework, relative_path, test_name in family["owners"]:
            owner_path = ROOT / relative_path
            assert owner_path.is_file(), relative_path
            if framework == "pytest":
                assert test_name in _pytest_functions(owner_path), f"missing pytest owner {relative_path}::{test_name}"
            elif framework == "pester":
                assert test_name in _pester_titles(owner_path), f"missing Pester owner {relative_path}::{test_name}"
            else:
                raise AssertionError(f"unsupported test framework: {framework}")


def test_every_upload_fault_hook_is_registered_exactly_once() -> None:
    payload = _registry()
    upload_family = next(item for item in payload["families"] if item["id"] == "vk.upload.lifecycle")
    registered = upload_family["checkpoints"]

    source_path = ROOT / upload_family["module"]
    source = source_path.read_text(encoding="utf-8")
    observed = re.findall(r'_fault\(fault_hook,\s*"([^"]+)"\)', source)

    assert observed
    assert len(observed) == len(set(observed))
    assert set(registered) == set(observed)


def test_ambiguous_mutations_never_claim_blind_retry_authority() -> None:
    payload = _registry()
    for family in payload["families"]:
        if family["class"] != "ambiguous_mutation":
            continue
        replay = family["replay"].casefold()
        assert "never" in replay or "prohibited" in replay
        assert "automatic_retry" not in replay
        assert "blind_retry" not in replay
