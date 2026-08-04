from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_REGISTER = ROOT / "docs" / "operations" / "mutation-boundary-register.json"
PROOF_REGISTER = ROOT / "docs" / "operations" / "mutation-fault-proof-register.json"
POWERSHELL_REGISTER = ROOT / "scripts" / "operator" / "powershell-wrappers.json"

REQUIRED_CROSS_CUTTING_SCENARIOS = {
    "truncated_or_malformed_json",
    "reordered_evidence",
    "stale_or_wrong_digest",
    "cross_project_or_wrong_owner",
    "wrong_snapshot_or_policy",
    "duplicate_operation",
    "incomplete_or_duplicate_result",
    "interrupted_atomic_write_and_orphan_temp",
    "nonempty_journal",
    "historical_pre_dispatch_migration",
    "historical_post_dispatch_migration_block",
}


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _pytest_functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith("test_")
    }


def _assert_exact_test_id(test_id: str, *, powershell_test_paths: set[str]) -> None:
    if "::It::" in test_id:
        relative_path, title = test_id.split("::It::", 1)
        assert relative_path in powershell_test_paths
        path = ROOT / relative_path
        assert path.is_file()
        assert title and title.strip() == title
        pattern = re.compile(rf'^\s*It\s+"{re.escape(title)}"\s*\{{', re.MULTILINE)
        assert pattern.search(path.read_text(encoding="utf-8")), test_id
        return

    relative_path, separator, function_name = test_id.partition("::")
    assert separator == "::" and function_name.startswith("test_")
    path = ROOT / relative_path
    assert path.is_file()
    assert function_name in _pytest_functions(path), test_id


def test_every_required_mutation_stage_has_an_exact_owned_fault_proof() -> None:
    boundary_register = _read_json(BOUNDARY_REGISTER)
    proof_register = _read_json(PROOF_REGISTER)
    powershell_register = _read_json(POWERSHELL_REGISTER)

    assert proof_register["schema_name"] == "video-manager.mutation-fault-proof-register"
    assert proof_register["schema_version"] == 1
    assert proof_register["boundary_register"] == BOUNDARY_REGISTER.relative_to(ROOT).as_posix()
    assert proof_register["aggregate_coverage_policy"] == "informational_only"
    assert proof_register["provider_writes_in_tests"] is False

    registered_boundaries = {item["boundary_id"]: item for item in boundary_register["boundaries"]}
    proof_boundaries = proof_register["boundaries"]
    proof_ids = [item["boundary_id"] for item in proof_boundaries]
    assert len(proof_ids) == len(set(proof_ids))
    assert set(proof_ids) == set(registered_boundaries)

    powershell_test_paths = {str(item["path"]).replace("\\", "/") for item in powershell_register["test_files"]}
    observed_proofs: set[tuple[str, tuple[str, ...], str]] = set()

    for proof_boundary in proof_boundaries:
        boundary_id = proof_boundary["boundary_id"]
        required_stages = set(registered_boundaries[boundary_id]["required_fault_stages"])
        assert required_stages
        covered_stages: set[str] = set()
        proofs = proof_boundary["proofs"]
        assert isinstance(proofs, list) and proofs

        for proof in proofs:
            stages = proof["stages"]
            test_id = proof["test_id"]
            claim = proof["claim"]
            assert isinstance(stages, list) and stages
            assert len(stages) == len(set(stages))
            assert set(stages) <= required_stages
            assert isinstance(test_id, str) and test_id.strip() == test_id
            assert isinstance(claim, str) and claim.strip() == claim and claim
            identity = (boundary_id, tuple(stages), test_id)
            assert identity not in observed_proofs
            observed_proofs.add(identity)
            covered_stages.update(stages)
            _assert_exact_test_id(test_id, powershell_test_paths=powershell_test_paths)

        assert covered_stages == required_stages, {
            "boundary_id": boundary_id,
            "missing": sorted(required_stages - covered_stages),
            "unexpected": sorted(covered_stages - required_stages),
        }


def test_cross_cutting_corruption_and_migration_proofs_are_complete_and_exact() -> None:
    proof_register = _read_json(PROOF_REGISTER)
    powershell_register = _read_json(POWERSHELL_REGISTER)
    powershell_test_paths = {str(item["path"]).replace("\\", "/") for item in powershell_register["test_files"]}

    proofs = proof_register["cross_cutting_proofs"]
    scenarios = [item["scenario"] for item in proofs]
    assert len(scenarios) == len(set(scenarios))
    assert set(scenarios) == REQUIRED_CROSS_CUTTING_SCENARIOS

    for proof in proofs:
        test_id = proof["test_id"]
        assert isinstance(test_id, str) and test_id.strip() == test_id
        _assert_exact_test_id(test_id, powershell_test_paths=powershell_test_paths)
