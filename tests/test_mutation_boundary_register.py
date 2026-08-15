from __future__ import annotations

import ast
import importlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTER_PATH = ROOT / "docs" / "operations" / "mutation-boundary-register.json"
REQUIRED_BOUNDARY_FIELDS = {
    "boundary_id",
    "risk",
    "provider",
    "language",
    "source_file",
    "module",
    "callable",
    "scanner_marker",
    "mutation_class",
    "intent_evidence",
    "dispatch_evidence",
    "response_evidence",
    "postflight_evidence",
    "reconciliation_identity",
    "retry_policy",
    "unknown_status",
    "attempt_limit",
    "required_fault_stages",
    "owning_tests",
}
REQUIRED_HIGH_RISK_STAGES = {"before_dispatch", "after_dispatch_before_response"}
_SAFE_VK_API_METHODS = {
    "groups.get",
    "groups.getById",
    "users.get",
    "video.get",
    "video.getAlbums",
    "video.getAlbumsByVideo",
    "wall.get",
    "wall.getById",
}
_SAFE_DYNAMIC_VK_CALLS = {
    (
        "src/video_channel_manager/platforms/vk/client.py",
        "VkApiClient._list_offset",
    ),
}


def _load_register() -> dict[str, Any]:
    payload = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _call_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _constant_string(node: ast.expr | None) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _keyword(call: ast.Call, name: str) -> ast.expr | None:
    for item in call.keywords:
        if item.arg == name:
            return item.value
    return None


def _is_true(node: ast.expr | None) -> bool:
    return isinstance(node, ast.Constant) and node.value is True


def _attribute_owner_name(node: ast.expr) -> str | None:
    if not isinstance(node, ast.Attribute):
        return None
    value = node.value
    return value.id if isinstance(value, ast.Name) else None


class _MutationCallsiteVisitor(ast.NodeVisitor):
    def __init__(self, source_file: str) -> None:
        self.source_file = source_file
        self.scope: list[str] = []
        self.callsites: list[tuple[str, str, str]] = []
        self.violations: list[tuple[str, str, str]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_Call(self, node: ast.Call) -> None:
        marker: str | None = None
        name = _call_name(node.func)
        callable_name = ".".join(self.scope) if self.scope else "<module>"
        callsite = (self.source_file, callable_name)
        if name == "_call":
            method = _constant_string(node.args[0]) if node.args else None
            if method is None:
                if callsite not in _SAFE_DYNAMIC_VK_CALLS:
                    self.violations.append(("vk_api:dynamic_or_missing_method", self.source_file, callable_name))
            elif method not in _SAFE_VK_API_METHODS:
                if _is_true(_keyword(node, "retry_transient")):
                    self.violations.append((f"vk_api:{method}:retry_transient", self.source_file, callable_name))
                else:
                    marker = f"vk_api:{method}"
        elif name == "_list_offset":
            method = _constant_string(node.args[0]) if node.args else None
            if method not in _SAFE_VK_API_METHODS:
                rendered_method = method if method is not None else "dynamic_or_missing_method"
                self.violations.append((f"vk_api:list_offset:{rendered_method}", self.source_file, callable_name))
        elif name == "execute_http_request":
            operation = _keyword(node, "operation")
            resource = _constant_string(_keyword(node, "resource"))
            if isinstance(operation, ast.Attribute) and operation.attr == "AMBIGUOUS_MUTATION" and resource:
                marker = f"http:{resource}"
        elif name == "_request" and len(node.args) >= 2 and _is_true(_keyword(node, "require_write")):
            method = _constant_string(node.args[0])
            resource = _constant_string(node.args[1])
            if method and resource:
                marker = f"youtube:{method}:{resource}"
        elif name == "execute" and _attribute_owner_name(node.func) == "adapter":
            marker = "wave:adapter.execute"
        elif name == "reconcile" and _attribute_owner_name(node.func) == "adapter":
            marker = "wave:adapter.reconcile"
        if marker is not None:
            self.callsites.append((marker, self.source_file, callable_name))
        self.generic_visit(node)


def _scan_python_mutation_callsites() -> list[tuple[str, str, str]]:
    callsites: list[tuple[str, str, str]] = []
    violations: list[tuple[str, str, str]] = []
    for path in sorted((ROOT / "src").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        visitor = _MutationCallsiteVisitor(path.relative_to(ROOT).as_posix())
        visitor.visit(tree)
        callsites.extend(visitor.callsites)
        violations.extend(visitor.violations)
    assert not violations, {"unscannable_direct_vk_calls": sorted(violations)}
    return callsites


def _scan_snippet(source: str) -> _MutationCallsiteVisitor:
    visitor = _MutationCallsiteVisitor("snippet.py")
    visitor.visit(ast.parse(source, filename="snippet.py"))
    return visitor


def test_vk_mutation_inventory_rejects_dynamic_direct_call() -> None:
    visitor = _scan_snippet("def mutate(writer, method):\n    writer._call(method, params={})\n")
    assert visitor.callsites == []
    assert visitor.violations == [("vk_api:dynamic_or_missing_method", "snippet.py", "mutate")]


def test_vk_mutation_inventory_rejects_transient_retry_on_mutation() -> None:
    visitor = _scan_snippet("def mutate(writer):\n    writer._call('wall.delete', params={}, retry_transient=True)\n")
    assert visitor.callsites == []
    assert visitor.violations == [("vk_api:wall.delete:retry_transient", "snippet.py", "mutate")]


def test_vk_read_inventory_rejects_dynamic_list_offset_dispatch() -> None:
    visitor = _scan_snippet("def read(client, method):\n    client._list_offset(method, params={}, page_size=100)\n")
    assert visitor.callsites == []
    assert visitor.violations == [("vk_api:list_offset:dynamic_or_missing_method", "snippet.py", "read")]


def test_register_schema_and_unique_boundaries() -> None:
    payload = _load_register()
    assert payload["schema_name"] == "video-channel-manager.mutation-boundary-register"
    assert payload["schema_version"] == 1
    assert payload["provider_writes_in_ci"] is False
    assert isinstance(payload["baseline_commit"], str) and len(payload["baseline_commit"]) == 40

    boundaries = payload["boundaries"]
    assert isinstance(boundaries, list) and boundaries
    boundary_ids = [item["boundary_id"] for item in boundaries]
    callsite_keys = [(item["scanner_marker"], item["source_file"], item["callable"]) for item in boundaries]
    assert len(boundary_ids) == len(set(boundary_ids))
    assert len(callsite_keys) == len(set(callsite_keys))
    for item in boundaries:
        assert set(item) == REQUIRED_BOUNDARY_FIELDS
        assert item["risk"] in {"P0", "P1"}
        assert item["language"] in {"python", "powershell"}
        assert item["unknown_status"] == "unknown_requires_reconciliation"
        assert type(item["attempt_limit"]) is int and item["attempt_limit"] == 1
        assert isinstance(item["required_fault_stages"], list) and item["required_fault_stages"]
        assert isinstance(item["owning_tests"], list) and item["owning_tests"]


def test_registered_callables_and_owning_tests_exist() -> None:
    for boundary in _load_register()["boundaries"]:
        source_path = ROOT / boundary["source_file"]
        assert source_path.is_file(), boundary["boundary_id"]
        source_text = source_path.read_text(encoding="utf-8")
        if boundary["language"] == "python":
            module = importlib.import_module(boundary["module"])
            target: object = module
            for component in boundary["callable"].split("."):
                target = getattr(target, component)
            assert callable(target), boundary["boundary_id"]
        else:
            assert f"function {boundary['callable']}" in source_text

        for relative_test_path in boundary["owning_tests"]:
            test_path = ROOT / relative_test_path
            assert test_path.is_file(), f"{boundary['boundary_id']}: {relative_test_path}"
            test_text = test_path.read_text(encoding="utf-8")
            if test_path.suffix == ".py":
                assert "def test_" in test_text
            else:
                assert "It " in test_text


def test_high_risk_boundaries_define_minimum_fault_stages() -> None:
    for boundary in _load_register()["boundaries"]:
        stages = set(boundary["required_fault_stages"])
        assert REQUIRED_HIGH_RISK_STAGES <= stages, boundary["boundary_id"]
        if boundary["risk"] == "P0":
            assert boundary["reconciliation_identity"].strip()
            assert boundary["postflight_evidence"].strip()


def test_ambiguous_boundaries_are_never_replayed() -> None:
    for boundary in _load_register()["boundaries"]:
        if boundary["mutation_class"] == "ambiguous_mutation":
            assert boundary["retry_policy"] == "never_replay", boundary["boundary_id"]
            assert boundary["attempt_limit"] == 1


def test_ast_mutation_inventory_matches_registered_python_markers() -> None:
    payload = _load_register()
    registered = Counter(
        (item["scanner_marker"], item["source_file"], item["callable"])
        for item in payload["boundaries"]
        if item["language"] == "python"
    )
    discovered = Counter(_scan_python_mutation_callsites())
    assert discovered == registered, {
        "unregistered": sorted((discovered - registered).elements()),
        "stale_registry_entries": sorted((registered - discovered).elements()),
    }


def test_powershell_process_boundary_is_registered() -> None:
    payload = _load_register()
    powershell_markers = {item["scanner_marker"] for item in payload["boundaries"] if item["language"] == "powershell"}
    assert powershell_markers == {"powershell:Invoke-VcmNativeProcess"}
