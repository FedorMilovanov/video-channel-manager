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
    "cross_project",
    "wrong_owner",
    "wrong_snapshot_or_policy",
    "duplicate_operation",
    "incomplete_or_duplicate_result",
    "interrupted_atomic_write_and_orphan_temp",
    "nonempty_journal",
    "historical_pre_dispatch_migration",
    "historical_post_dispatch_migration_block",
    "utf8_without_bom",
    "crlf_lf_canonical_digest",
    "unsupported_explicit_python",
    "operator_output_path_collision",
    "ci_apply_prohibition",
    "operator_unknown_mutation_classification",
    "operator_timeout_and_interrupted_child",
    "operator_concurrent_output_no_deadlock",
    "operator_missing_or_malformed_result",
    "operator_inconsistent_unknown_result",
    "vk_safe_read_bounded_retry",
    "youtube_comment_safe_read_bounded_retry",
    "youtube_description_safe_read_bounded_retry",
    "unknown_outcome_stops_later_operations",
    "visible_object_is_not_completion",
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


def _module_string_sequences(tree: ast.Module) -> dict[str, set[str]]:
    """Module-level tuples/lists of string literals, such as a table of parametrized resources."""

    sequences: dict[str, set[str]] = {}
    for statement in tree.body:
        target: ast.expr | None = None
        value: ast.expr | None = None
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target, value = statement.targets[0], statement.value
        elif isinstance(statement, ast.AnnAssign):
            target, value = statement.target, statement.value
        if not isinstance(target, ast.Name) or not isinstance(value, ast.List | ast.Tuple | ast.Set):
            continue
        items = {
            str(item.value) for item in value.elts if isinstance(item, ast.Constant) and isinstance(item.value, str)
        }
        if len(items) == len(value.elts) and items:
            sequences[target.id] = items
    return sequences


def _parametrization_ids(path: Path, function_name: str) -> set[str]:
    """Every case id a test function's parametrize markers can produce.

    A proof may name one parametrized case (`test_x[POST:media]`) instead of the whole function: a
    table-driven stage test proves several boundaries, and citing the exact case keeps the register
    specific. The id has to be produced by that function's own markers, so a renamed case or a
    dropped resource breaks CI. Both `pytest.param(..., id="...")` and `ids=[...]`/an id-less table
    of string values are resolved statically from this module's own literals.
    """

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    sequences = _module_string_sequences(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) or node.name != function_name:
            continue
        ids: set[str] = set()
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            for keyword in decorator.keywords:
                if keyword.arg != "ids":
                    continue
                if isinstance(keyword.value, ast.Constant):
                    ids.add(str(keyword.value.value))
                elif isinstance(keyword.value, ast.Name):
                    ids.update(sequences.get(keyword.value.id, set()))
            for argument in decorator.args:
                if isinstance(argument, ast.List | ast.Tuple):
                    declared_values: set[str] = set()
                    all_literal = True
                    for item in argument.elts:
                        if isinstance(item, ast.Constant) and isinstance(item.value, str):
                            declared_values.add(str(item.value))
                            continue
                        all_literal = False
                        if not isinstance(item, ast.Call):
                            continue
                        for keyword in item.keywords:
                            if keyword.arg == "id" and isinstance(keyword.value, ast.Constant):
                                ids.add(str(keyword.value.value))
                    if all_literal:
                        ids.update(declared_values)
                elif isinstance(argument, ast.Name):
                    ids.update(sequences.get(argument.id, set()))
        return ids
    return set()


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

    base_name, bracket, case_id = function_name.partition("[")
    if bracket:
        assert case_id.endswith("]"), test_id
        case_id = case_id[:-1]
        assert base_name in _pytest_functions(path), test_id
        assert case_id in _parametrization_ids(path, base_name), {
            "test_id": test_id,
            "declared_ids": sorted(_parametrization_ids(path, base_name)),
        }
    else:
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
