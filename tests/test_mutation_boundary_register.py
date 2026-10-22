from __future__ import annotations

import ast
import importlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTER_PATH = ROOT / "docs" / "operations" / "mutation-boundary-register.json"
PROVIDER_COMMAND = re.compile(r"python -m [\w.]+ (send-once|send|apply-outcome|apply)\b")
PROVIDER_DISPATCH_VERBS = {"send", "send-once"}
CONCURRENCY_GROUP = re.compile(r"^\s*group:\s*(?P<group>[A-Za-z0-9._${}-]+)", re.MULTILINE)
STATE_REF = re.compile(r"STATE_BRANCH:\s*(?P<ref>state/[A-Za-z0-9._-]+)")
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
# Optional, explicitly typed extension: a boundary may document one narrow
# recovery path for a provider outcome that provably had no effect. It never
# relaxes retry_policy; the invariants below keep that separation enforced.
OPTIONAL_BOUNDARY_FIELDS = {"known_rejection_recovery"}
REQUIRED_KNOWN_REJECTION_RECOVERY_FIELDS = {
    "reopen_from_stage",
    "required_last_transition_to",
    "required_reason",
    "requires_absent_evidence",
    "requires_present_evidence",
    "archive_field",
    "reverify_media_before_reservation",
    "automatic_retry",
    "authority",
    "owning_callable",
}
REQUIRED_HIGH_RISK_STAGES = {"before_dispatch", "after_dispatch_before_response"}
_SAFE_DYNAMIC_VK_CALLS = {
    (
        "src/video_channel_manager/platforms/vk/client.py",
        "VkApiClient._list_offset",
    ),
}
_SAFE_VK_EXACT_READ_METHODS = {
    "groups.isMember",
    "utils.resolveScreenName",
}
# Telegram uses POST for reads as well, so the HTTP verb says nothing about mutation.
# A mutation is an API method dispatched through `telegram_transport._api_call` with an
# explicit literal `mutation=True`; the flag is what the reader and the scanner both trust,
# which is why a missing or computed flag is a violation rather than an unknown.
TELEGRAM_REQUIRED_FAULT_STAGES = {"before_dispatch", "after_dispatch_before_response", "after_response_before_commit"}

# Instagram: the Graph adapter dispatches every effect through one private `_request`, so a write
# is a POST/PUT/PATCH/DELETE with a literal `resource`. The resumable binary upload talks to
# rupload.facebook.com, not the Graph API, and therefore has its own single dispatch point.
INSTAGRAM_MUTATION_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
INSTAGRAM_PACKAGE_PREFIX = "src/video_channel_manager/instagram/"
_INSTAGRAM_REVIEWED_DIRECT_HTTP = {
    "InstagramProviderClient._request",
    "InstagramResumableProviderClient._dispatch_binary_upload",
}
_INSTAGRAM_DIRECT_WRITE_MARKER = "instagram_api:POST:resumable-binary-upload"
# YouTube release: every effect goes through `_mutation_request`, which classifies the request as
# AMBIGUOUS_MUTATION and forwards a resource that is only a parameter there. The static inventory
# therefore reads the call sites, exactly as it does for Telegram's `_api_call`.
YOUTUBE_RELEASE_PROVIDER_FILE = "src/video_channel_manager/youtube_release_provider.py"
_YOUTUBE_RELEASE_REVIEWED_HTTP = {
    "YouTubeReleaseProvider._safe_request",
    "YouTubeReleaseProvider._mutation_request",
    # A chunked-resumable status probe: PUT with `Content-Length: 0`, no body, classified
    # SAFE_READ. It is the only direct verb outside the two helpers and a test asserts the body.
    "YouTubeReleaseProvider.query_upload_status",
}
_DIRECT_HTTP_VERBS = {"get", "post", "put", "patch", "delete", "request"}


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


def _module_string_constants(tree: ast.Module) -> dict[str, str]:
    constants: dict[str, str] = {}
    for statement in tree.body:
        target: ast.expr | None = None
        value: ast.expr | None = None
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target = statement.targets[0]
            value = statement.value
        elif isinstance(statement, ast.AnnAssign):
            target = statement.target
            value = statement.value
        if isinstance(target, ast.Name) and isinstance(value, ast.Constant) and isinstance(value.value, str):
            constants[target.id] = value.value
    return constants


def _constant_string(node: ast.expr | None, constants: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    return None


def _vk_method_is_read_only(method: str) -> bool:
    if method in _SAFE_VK_EXACT_READ_METHODS:
        return True
    _separator, _dot, action = method.rpartition(".")
    return bool(action) and (action.startswith("get") or action.startswith("search"))


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
    def __init__(self, source_file: str, *, constants: dict[str, str] | None = None) -> None:
        self.source_file = source_file
        self.constants = constants or {}
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
            method = _constant_string(node.args[0], self.constants) if node.args else None
            if method is None:
                if callsite not in _SAFE_DYNAMIC_VK_CALLS:
                    self.violations.append(("vk_api:dynamic_or_missing_method", self.source_file, callable_name))
            elif _vk_method_is_read_only(method):
                pass
            elif _is_true(_keyword(node, "retry_transient")):
                self.violations.append((f"vk_api:{method}:retry_transient", self.source_file, callable_name))
            else:
                marker = f"vk_api:{method}"
        elif name == "_list_offset":
            method = _constant_string(node.args[0], self.constants) if node.args else None
            if method is None or not _vk_method_is_read_only(method):
                rendered_method = method if method is not None else "dynamic_or_missing_method"
                self.violations.append((f"vk_api:list_offset:{rendered_method}", self.source_file, callable_name))
        elif name == "_api_call":
            mutation = _keyword(node, "mutation")
            method = _constant_string(_keyword(node, "method"), self.constants)
            if not isinstance(mutation, ast.Constant) or not isinstance(mutation.value, bool):
                self.violations.append(
                    ("telegram_api:mutation_flag_missing_or_dynamic", self.source_file, callable_name)
                )
            elif mutation.value is True:
                if method is None:
                    self.violations.append(("telegram_api:dynamic_or_missing_method", self.source_file, callable_name))
                else:
                    marker = f"telegram_api:{method}"
        elif name == "execute_http_request":
            operation = _keyword(node, "operation")
            resource = _constant_string(_keyword(node, "resource"), self.constants)
            if isinstance(operation, ast.Attribute) and operation.attr == "AMBIGUOUS_MUTATION" and resource:
                marker = f"http:{resource}"
        elif name == "_request" and len(node.args) >= 2 and _is_true(_keyword(node, "require_write")):
            method = _constant_string(node.args[0], self.constants)
            resource = _constant_string(node.args[1], self.constants)
            if method and resource:
                marker = f"youtube:{method}:{resource}"
        elif name == "_request" and self.scope and self.scope[0] in {
            "InstagramProviderClient",
            "InstagramResumableProviderClient",
        }:
            method = _constant_string(node.args[0], self.constants) if node.args else None
            if method is None:
                self.violations.append(("instagram_api:dynamic_or_missing_method", self.source_file, callable_name))
            elif method.upper() in INSTAGRAM_MUTATION_METHODS:
                resource = _constant_string(_keyword(node, "resource"), self.constants)
                if resource is None:
                    self.violations.append(
                        ("instagram_api:resource_missing_or_dynamic", self.source_file, callable_name)
                    )
                else:
                    marker = f"instagram_api:{method.upper()}:{resource}"
        elif name == "_mutation_request":
            method = _constant_string(node.args[0], self.constants) if node.args else None
            resource = _constant_string(_keyword(node, "resource"), self.constants)
            if method is None:
                self.violations.append(
                    ("youtube_release_api:dynamic_or_missing_method", self.source_file, callable_name)
                )
            elif resource is None:
                self.violations.append(
                    ("youtube_release_api:resource_missing_or_dynamic", self.source_file, callable_name)
                )
            else:
                marker = f"youtube_release_api:{method.upper()}:{resource}"
        elif (
            name in _DIRECT_HTTP_VERBS
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr in {"_client", "_media_client", "_http_client"}
            and node.func.value.value.__class__ is ast.Name
            and node.func.value.value.id == "self"
        ):
            if self.source_file.startswith(INSTAGRAM_PACKAGE_PREFIX):
                if callable_name not in _INSTAGRAM_REVIEWED_DIRECT_HTTP:
                    self.violations.append(
                        (f"instagram_api:unclassified_direct_write:{name}", self.source_file, callable_name)
                    )
                else:
                    for known_callable, known_marker in (
                        ("InstagramResumableProviderClient._dispatch_binary_upload", _INSTAGRAM_DIRECT_WRITE_MARKER),
                    ):
                        if callable_name == known_callable:
                            marker = known_marker
            elif self.source_file == YOUTUBE_RELEASE_PROVIDER_FILE and callable_name not in _YOUTUBE_RELEASE_REVIEWED_HTTP:
                self.violations.append(
                    (f"youtube_release_api:unclassified_direct_write:{name}", self.source_file, callable_name)
                )
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
        visitor = _MutationCallsiteVisitor(
            path.relative_to(ROOT).as_posix(),
            constants=_module_string_constants(tree),
        )
        visitor.visit(tree)
        callsites.extend(visitor.callsites)
        violations.extend(visitor.violations)
    assert not violations, {"unscannable_direct_vk_calls": sorted(violations)}
    return callsites


def _scan_snippet(source: str, *, source_file: str = "snippet.py") -> _MutationCallsiteVisitor:
    tree = ast.parse(source, filename=source_file)
    visitor = _MutationCallsiteVisitor(source_file, constants=_module_string_constants(tree))
    visitor.visit(tree)
    return visitor


def test_vk_mutation_inventory_rejects_dynamic_direct_call() -> None:
    visitor = _scan_snippet("def mutate(writer, method):\n    writer._call(method, params={})\n")
    assert visitor.callsites == []
    assert visitor.violations == [("vk_api:dynamic_or_missing_method", "snippet.py", "mutate")]


def test_vk_mutation_inventory_rejects_transient_retry_on_mutation() -> None:
    visitor = _scan_snippet("def mutate(writer):\n    writer._call('wall.delete', params={}, retry_transient=True)\n")
    assert visitor.callsites == []
    assert visitor.violations == [("vk_api:wall.delete:retry_transient", "snippet.py", "mutate")]


def test_vk_read_inventory_accepts_literal_retryable_getter() -> None:
    visitor = _scan_snippet(
        "def read(client):\n    client._call('video.getThumbUploadUrl', params={}, retry_transient=True)\n"
    )
    assert visitor.callsites == []
    assert visitor.violations == []


def test_vk_read_inventory_resolves_module_level_method_constant() -> None:
    visitor = _scan_snippet(
        "METHOD = 'shortVideo.getOwnerVideos'\ndef read(client):\n    client._call(METHOD, params={})\n"
    )
    assert visitor.callsites == []
    assert visitor.violations == []


def test_vk_read_inventory_rejects_dynamic_list_offset_dispatch() -> None:
    visitor = _scan_snippet("def read(client, method):\n    client._list_offset(method, params={}, page_size=100)\n")
    assert visitor.callsites == []
    assert visitor.violations == [("vk_api:list_offset:dynamic_or_missing_method", "snippet.py", "read")]


def test_telegram_mutation_inventory_requires_the_explicit_flag() -> None:
    visitor = _scan_snippet("def send(client):\n    _api_call(client, api_base='b', token='t', method='sendMessage')\n")
    assert visitor.callsites == []
    assert visitor.violations == [("telegram_api:mutation_flag_missing_or_dynamic", "snippet.py", "send")]


def test_telegram_mutation_inventory_rejects_dynamic_method() -> None:
    visitor = _scan_snippet(
        "def send(client, method):\n    _api_call(client, api_base='b', token='t', method=method, mutation=True)\n"
    )
    assert visitor.callsites == []
    assert visitor.violations == [("telegram_api:dynamic_or_missing_method", "snippet.py", "send")]


def test_telegram_read_is_not_a_mutation_callsite() -> None:
    visitor = _scan_snippet(
        "def read(client):\n    _api_call(client, api_base='b', token='t', method='getMe', mutation=False)\n"
    )
    assert visitor.callsites == []
    assert visitor.violations == []


def test_telegram_literal_mutation_is_discovered_by_method() -> None:
    visitor = _scan_snippet(
        "def send(client):\n    _api_call(client, api_base='b', token='t', method='sendPhoto', mutation=True)\n"
    )
    assert visitor.callsites == [("telegram_api:sendPhoto", "snippet.py", "send")]
    assert visitor.violations == []


def test_register_schema_and_unique_boundaries() -> None:
    payload = _load_register()
    assert payload["schema_name"] == "video-channel-manager.mutation-boundary-register"
    assert payload["schema_version"] == 1
    # The old header claimed `provider_writes_in_ci: false`. The repository's own scheduled
    # publishers write to Telegram, so that claim was false and hid which workflows may write.
    # It is replaced by an exact inventory that a test can check (below).
    assert "provider_writes_in_ci" not in payload
    assert payload["provider_writes_in_quality_ci"] is False
    assert isinstance(payload["baseline_commit"], str) and len(payload["baseline_commit"]) == 40

    boundaries = payload["boundaries"]
    assert isinstance(boundaries, list) and boundaries
    boundary_ids = [item["boundary_id"] for item in boundaries]
    callsite_keys = [(item["scanner_marker"], item["source_file"], item["callable"]) for item in boundaries]
    assert len(boundary_ids) == len(set(boundary_ids))
    assert len(callsite_keys) == len(set(callsite_keys))
    for item in boundaries:
        assert REQUIRED_BOUNDARY_FIELDS <= set(item) <= REQUIRED_BOUNDARY_FIELDS | OPTIONAL_BOUNDARY_FIELDS
        assert set(item) - REQUIRED_BOUNDARY_FIELDS <= OPTIONAL_BOUNDARY_FIELDS
        assert item["risk"] in {"P0", "P1"}
        assert item["language"] in {"python", "powershell"}
        assert item["unknown_status"] == "unknown_requires_reconciliation"
        assert type(item["attempt_limit"]) is int and item["attempt_limit"] == 1
        assert isinstance(item["required_fault_stages"], list) and item["required_fault_stages"]
        assert isinstance(item["owning_tests"], list) and item["owning_tests"]


def test_provider_write_workflows_are_an_exact_declared_inventory() -> None:
    """Which CI workflows may reach a provider is a claim; this makes it checkable.

    Telegram uses POST for reads as well, so the inventory is built from the command that can
    dispatch a publication (`send` / `send-once`), not from the HTTP verb. State-only `apply`
    and `apply-outcome` commands are deliberately excluded: they mutate the durable state ref,
    not the provider.
    """

    payload = _load_register()
    declared = [str(item).replace("\\", "/") for item in payload["provider_write_workflows"]]
    assert len(declared) == len(set(declared))
    assert declared

    discovered: dict[str, list[str]] = {}
    for path in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        verbs = {match.group(1) for match in PROVIDER_COMMAND.finditer(text)} & PROVIDER_DISPATCH_VERBS
        if verbs:
            discovered[path.relative_to(ROOT).as_posix()] = sorted(verbs)

    assert set(discovered) == set(declared), {
        "undeclared_provider_writers": sorted(set(discovered) - set(declared)),
        "declared_but_never_dispatches": sorted(set(declared) - set(discovered)),
    }

    for relative in declared:
        path = ROOT / relative
        assert path.is_file(), relative
        text = path.read_text(encoding="utf-8")
        assert "secrets." in text, relative
        assert "schedule:" in text or "workflow_dispatch:" in text, relative
        name = path.name
        assert "quality" not in name and "preflight" not in name and name != "ci.yml", relative


def test_declared_provider_writers_share_one_serialising_group_per_state_ref() -> None:
    """One durable state namespace must have exactly one serialising concurrency group.

    Two workflows may write the same channel, but only if they are serialised by the same
    `group` with `cancel-in-progress: false`; two different groups over one state ref would be
    two writers racing on the same ledger.
    """

    payload = _load_register()
    by_state_ref: dict[str, set[str]] = {}

    for relative in payload["provider_write_workflows"]:
        text = (ROOT / str(relative)).read_text(encoding="utf-8")
        groups = {match.group("group").split("$")[0].rstrip("-") for match in CONCURRENCY_GROUP.finditer(text)}
        state_refs = {match.group("ref") for match in STATE_REF.finditer(text)}
        assert len(groups) == 1, {relative: sorted(groups)}
        assert state_refs, relative
        assert "cancel-in-progress: false" in text, relative
        for state_ref in state_refs:
            by_state_ref.setdefault(state_ref, set()).update(groups)

    for state_ref, groups in by_state_ref.items():
        assert len(groups) == 1, {state_ref: sorted(groups)}


def test_telegram_boundaries_prove_all_three_mutation_stages() -> None:
    telegram = [item for item in _load_register()["boundaries"] if item["scanner_marker"].startswith("telegram_api:")]

    assert telegram, "the live Telegram writers must be registered"
    for boundary in telegram:
        assert set(boundary["required_fault_stages"]) == TELEGRAM_REQUIRED_FAULT_STAGES, boundary["boundary_id"]
        assert boundary["mutation_class"] == "ambiguous_mutation", boundary["boundary_id"]
        assert boundary["retry_policy"] == "never_replay", boundary["boundary_id"]


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


def test_known_rejection_recovery_is_typed_and_never_relaxes_retry_policy() -> None:
    """A documented no-effect recovery must stay narrower than an automatic retry."""

    from video_channel_manager.platforms.vk.upload_lifecycle import (
        UploadStage,
        reopen_known_rejection,
    )

    documented = [boundary for boundary in _load_register()["boundaries"] if "known_rejection_recovery" in boundary]
    assert [item["boundary_id"] for item in documented] == ["vk.video.upload.reserve"]

    boundary = documented[0]
    assert boundary["retry_policy"] == "never_replay"
    assert boundary["attempt_limit"] == 1

    recovery = boundary["known_rejection_recovery"]
    assert set(recovery) == REQUIRED_KNOWN_REJECTION_RECOVERY_FIELDS
    assert recovery["reopen_from_stage"] == UploadStage.REJECTED.value
    assert recovery["required_last_transition_to"] == UploadStage.REJECTED.value
    assert recovery["required_reason"] == "reservation_rejected"
    assert recovery["archive_field"] == "known_rejections"
    assert recovery["reverify_media_before_reservation"] is True
    # No automatic retry: only a later, separately invoked Wave may reopen.
    assert recovery["automatic_retry"] is False
    assert recovery["authority"] == "later_separately_invoked_wave"
    assert recovery["owning_callable"].endswith(".reopen_known_rejection")
    assert callable(reopen_known_rejection)
    assert isinstance(recovery["requires_absent_evidence"], list) and recovery["requires_absent_evidence"]
    assert isinstance(recovery["requires_present_evidence"], list) and recovery["requires_present_evidence"]
    assert set(recovery["requires_absent_evidence"]).isdisjoint(recovery["requires_present_evidence"])


def test_rejected_stage_has_exactly_one_documented_successor() -> None:
    """The only edge out of REJECTED is the audited known-rejection reopen."""

    from video_channel_manager.platforms.vk.upload_lifecycle import UploadStage, _ALLOWED_TRANSITIONS

    assert _ALLOWED_TRANSITIONS[UploadStage.REJECTED] == frozenset({UploadStage.PLANNED})


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


def test_instagram_write_without_a_resource_is_a_violation() -> None:
    """A Graph write that does not name its resource cannot be inventoried, so it is refused."""

    visitor = _scan_snippet(
        "class InstagramProviderClient:\n"
        "    def create(self):\n"
        "        return self._request('POST', 'account/media', data={})\n"
    )
    assert visitor.callsites == []
    assert visitor.violations == [
        ("instagram_api:resource_missing_or_dynamic", "snippet.py", "InstagramProviderClient.create")
    ]


def test_instagram_read_needs_no_resource() -> None:
    visitor = _scan_snippet(
        "class InstagramProviderClient:\n"
        "    def status(self):\n"
        "        return self._request('GET', 'container-1', params={})\n"
    )
    assert visitor.callsites == []
    assert visitor.violations == []


def test_instagram_classified_write_is_discovered_by_method_and_resource() -> None:
    visitor = _scan_snippet(
        "class InstagramProviderClient:\n"
        "    def publish(self, container):\n"
        "        return self._request('POST', 'account/media_publish', data={}, resource='media_publish')\n"
    )
    assert visitor.callsites == [
        ("instagram_api:POST:media_publish", "snippet.py", "InstagramProviderClient.publish")
    ]
    assert visitor.violations == []


def test_instagram_direct_provider_write_outside_the_reviewed_points_is_a_violation() -> None:
    """The binary upload is the only direct verb the package may use, in one named method."""

    visitor = _scan_snippet(
        "class InstagramProviderClient:\n"
        "    def leak(self):\n"
        "        return self._client.post('https://rupload.facebook.com/x', content=b'bytes')\n",
        source_file="src/video_channel_manager/instagram/production.py",
    )
    assert visitor.callsites == []
    assert visitor.violations == [
        ("instagram_api:unclassified_direct_write:post", "src/video_channel_manager/instagram/production.py", "InstagramProviderClient.leak")
    ]


def test_instagram_binary_upload_dispatch_point_is_registered() -> None:
    visitor = _scan_snippet(
        "class InstagramResumableProviderClient:\n"
        "    def _dispatch_binary_upload(self, target, body):\n"
        "        return self._client.post(target, content=body)\n",
        source_file="src/video_channel_manager/instagram/local_resumable.py",
    )
    assert visitor.callsites == [
        (
            "instagram_api:POST:resumable-binary-upload",
            "src/video_channel_manager/instagram/local_resumable.py",
            "InstagramResumableProviderClient._dispatch_binary_upload",
        )
    ]
    assert visitor.violations == []


def test_youtube_release_write_with_a_dynamic_resource_is_a_violation() -> None:
    visitor = _scan_snippet(
        "class YouTubeReleaseProvider:\n"
        "    def mutate(self, resource):\n"
        "        return self._mutation_request('POST', 'https://api/videos', resource=resource)\n"
    )
    assert visitor.callsites == []
    assert visitor.violations == [
        ("youtube_release_api:resource_missing_or_dynamic", "snippet.py", "YouTubeReleaseProvider.mutate")
    ]


def test_youtube_release_direct_write_outside_the_reviewed_methods_is_a_violation() -> None:
    visitor = _scan_snippet(
        "class YouTubeReleaseProvider:\n"
        "    def leak(self):\n"
        "        return self._http_client.delete('https://api/videos')\n",
        source_file="src/video_channel_manager/youtube_release_provider.py",
    )
    assert visitor.callsites == []
    assert visitor.violations == [
        (
            "youtube_release_api:unclassified_direct_write:delete",
            "src/video_channel_manager/youtube_release_provider.py",
            "YouTubeReleaseProvider.leak",
        )
    ]


def test_youtube_release_classified_write_is_discovered_by_method_and_resource() -> None:
    visitor = _scan_snippet(
        "class YouTubeReleaseProvider:\n"
        "    def thumbnail(self, video):\n"
        "        return self._mutation_request('POST', 'https://upload/thumbnails/set', resource='thumbnails.set')\n"
    )
    assert visitor.callsites == [("youtube_release_api:POST:thumbnails.set", "snippet.py", "YouTubeReleaseProvider.thumbnail")]
    assert visitor.violations == []
