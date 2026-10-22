from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTECTED = ROOT / "docs" / "operations" / "protected-evidence-refs.json"
AGENTS = ROOT / "AGENTS.md"

# Ref shapes the repository actually uses. `refs/heads/main` is the execution baseline and
# needs no protection; every other bound ref must be declared protected.
BASELINE_REFS = frozenset({"main", "refs/heads/main"})
READONLY_TEST_VALUES = frozenset({"other", "feature", "refs/heads/other", "refs/heads/feature"})

REF_PATTERN = re.compile(
    r"(?:refs/heads/)?(?:state|agent|feat|fix|feature|lane|ops|probe|research|docs)/[A-Za-z0-9._-]+"
)
PY_CONSTANT = re.compile(r"^(?P<name>[A-Z][A-Z0-9_]*(?:_REF|_BRANCH))\s*=\s*\"(?P<value>[^\"]+)\"", re.MULTILINE)
JSON_BINDING_KEY = re.compile(r"\"(?:artifact_ref|evidence_branch|state_branch|branch)\"\s*:\s*\"(?P<value>[^\"]+)\"")
WORKFLOW_REF = re.compile(r"^(?P<name>[A-Z_]+):\s*(?P<value>state/[A-Za-z0-9._-]+)$", re.MULTILINE)


def _protected() -> dict[str, dict[str, object]]:
    payload = json.loads(PROTECTED.read_text(encoding="utf-8"))
    return {str(entry["ref"]): entry for entry in payload["refs"]}


def _python_bindings() -> dict[str, str]:
    """Module-level `*_REF` / `*_BRANCH` constants in runtime code."""

    found: dict[str, str] = {}
    for base in ("src", "scripts"):
        for path in (ROOT / base).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            for match in PY_CONSTANT.finditer(path.read_text(encoding="utf-8")):
                found[f"{path.relative_to(ROOT)}::{match.group('name')}"] = match.group("value")
    return found


def _workflow_bindings() -> dict[str, str]:
    found: dict[str, str] = {}
    for path in (ROOT / ".github" / "workflows").glob("*.yml"):
        text = path.read_text(encoding="utf-8")
        for match in WORKFLOW_REF.finditer(text):
            found[f"{path.name}::{match.group('name')}"] = match.group("value")
        for match in re.finditer(r"^\s+ref:\s*(?P<value>state/[A-Za-z0-9._-]+)$", text, re.MULTILINE):
            found[f"{path.name}::checkout_ref:{match.group('value')}"] = match.group("value")
    return found


def _json_bindings() -> dict[str, str]:
    found: dict[str, str] = {}
    for path in (ROOT / "content").rglob("*.json"):
        for match in JSON_BINDING_KEY.finditer(path.read_text(encoding="utf-8")):
            found[f"{path.relative_to(ROOT)}::{match.group('value')}"] = match.group("value")
    return found


def test_protected_evidence_inventory_is_structurally_valid() -> None:
    protected = _protected()

    assert protected, "the inventory must not be empty"
    allowed_roles = {"durable_state", "content_addressed_evidence"}

    for ref, entry in protected.items():
        assert REF_PATTERN.fullmatch(ref), ref
        assert entry["role"] in allowed_roles, ref
        assert str(entry["why"]).strip(), ref

        if entry["tip_is_stable"] is True:
            # An immutable ref must be restorable by SHA alone.
            assert re.fullmatch(r"[0-9a-f]{40}", str(entry["tip_commit"])), ref
            assert str(entry["tip_commit"]) in str(entry["restore"]), ref
            assert ref in str(entry["restore"]), ref
        else:
            # A moving ref cannot promise an exact tip; it must say so instead.
            assert entry["role"] == "durable_state", ref
            assert "tip_commit" not in entry, ref


def test_state_refs_are_declared_durable_and_not_immutable() -> None:
    protected = _protected()
    state_refs = {ref: entry for ref, entry in protected.items() if ref.startswith("state/")}

    assert set(state_refs) == {
        "state/lordchrist-telegram",
        "state/milovi-cake-telegram",
        "state/svodka-telegram",
    }
    assert all(entry["role"] == "durable_state" for entry in state_refs.values())
    assert all(entry["tip_is_stable"] is False for entry in state_refs.values())


def test_every_runtime_ref_binding_is_protected() -> None:
    """The binding is the contract: a ref named by code must be declared protected.

    This is the check that was missing on 2026-10-21, when a bound evidence ref was
    deleted as a duplicate and 20 references in `main` went dangling.
    """

    protected = _protected()
    unbound: list[str] = []

    for source, value in {
        **_python_bindings(),
        **_workflow_bindings(),
        **_json_bindings(),
    }.items():
        if value in BASELINE_REFS or value in READONLY_TEST_VALUES:
            continue
        if value not in protected:
            unbound.append(f"{source} -> {value}")

    assert unbound == [], unbound


def test_runtime_code_never_binds_a_ref_by_prefix_alone() -> None:
    """A prefix such as `agent/milovi-video-accepted` would silently accept a new ref."""

    for source, value in _python_bindings().items():
        if value in BASELINE_REFS:
            continue
        assert REF_PATTERN.fullmatch(value), source


def test_deletion_ledger_rows_are_restorable_records() -> None:
    """The ledger is the only way back to a deleted ref, so its rows must be usable."""

    ledger = (ROOT / "docs" / "operations" / "branch-hygiene-2026-10-21-deletion-ledger.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\|\s*`([^`]+)`\s*\|\s*`([^`]+)`", ledger, re.MULTILINE)

    assert rows, "the ledger must record what was deleted"
    refs = [ref for ref, _ in rows]
    assert len(refs) == len(set(refs)), "a ref listed twice makes the count meaningless"

    for ref, sha in rows:
        assert re.fullmatch(r"[0-9a-f]{40}", sha), (ref, sha)
        assert not ref.startswith("state/"), ref
        assert ref != "main", ref


def test_branch_policy_documents_the_protected_inventory() -> None:
    """An unread policy file protects nothing, so the policy must name it."""

    agents = AGENTS.read_text(encoding="utf-8")

    assert "docs/operations/protected-evidence-refs.json" in agents
    assert "content-addressed evidence" in agents.casefold()
    assert "Byte-identical duplication is **not** a sufficient reason" in agents
    # The three classes must stay distinguishable at the policy level.
    for phrase in ("Durable state refs", "Content-addressed evidence refs", "Ephemeral work branches"):
        assert phrase in agents, phrase
