"""No module may sit in the package without a decision about who reaches it.

The package ships 23 modules that nothing calls: nothing under `src/` or `scripts/` imports them, they
are not console scripts, and no workflow, script or document names them. Each of them has one test
file that imports it, so the suite is confident about code that never runs in production.

`scripts/module_disposition.py` measures that set and `docs/operations/module-disposition.json` records
a disposition for each module, either `package_entrypoint` (with evidence that names the module),
`archived_canary` (deliberately kept, with evidence) or `pending_owner_decision` (no owner has decided
yet, with its owning tests recorded). This test requires the measured set and the register to match in
both directions: new unreachable code fails until someone writes a line about it, and a module that
becomes reachable has to leave the register. The scan deliberately ignores the two registers that list
every module by path, which would otherwise make the whole package look used.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from scripts import module_disposition as disposition

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "docs/operations/module-disposition.json"
STATUSES = {"package_entrypoint", "archived_canary", "pending_owner_decision"}
EVIDENCE_STATUSES = {"package_entrypoint", "archived_canary"}


def _register() -> dict[str, object]:
    return json.loads(REGISTER.read_text(encoding="utf-8"))


def _entries() -> list[dict[str, object]]:
    modules = _register()["modules"]
    assert isinstance(modules, list)
    return modules


def _statements(path: Path) -> int:
    return sum(1 for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))) if isinstance(node, ast.stmt))


def test_the_register_matches_the_modules_nothing_reaches() -> None:
    measured = set(disposition.unreachable_modules(ROOT))
    recorded = {str(entry["module"]) for entry in _entries()}

    assert recorded - measured == set(), (
        "these modules are registered as unreachable but something reaches them now; "
        f"delete their entries: {sorted(recorded - measured)}"
    )
    assert measured - recorded == set(), (
        "these modules are reachable from no production path and have no disposition; "
        f"add a reviewed entry to {REGISTER.relative_to(ROOT)}: {sorted(measured - recorded)}"
    )


def test_every_entry_declares_a_known_status_and_a_reason() -> None:
    for entry in _entries():
        module = entry["module"]
        assert entry["status"] in STATUSES, module
        note = entry["note"]
        assert isinstance(note, str) and len(note) >= 40, f"{module} needs a note that explains the disposition"
        assert isinstance(entry["statements"], int) and entry["statements"] > 0, module


def test_evidence_backed_entries_point_at_a_file_that_names_the_module() -> None:
    checked = 0
    for entry in _entries():
        if entry["status"] not in EVIDENCE_STATUSES:
            continue
        evidence = entry.get("evidence")
        assert isinstance(evidence, str) and evidence, f"{entry['module']} needs an evidence path"
        assert disposition.evidence_names_module(str(entry["module"]), evidence, ROOT), (
            f"{evidence} does not name {entry['module']}"
        )
        checked += 1
    assert checked >= 1, "at least the package entrypoint carries evidence"


def test_pending_entries_record_the_tests_that_keep_them_alive() -> None:
    pending = [entry for entry in _entries() if entry["status"] == "pending_owner_decision"]
    assert pending, "the register exists because these decisions are open"

    for entry in pending:
        owning = entry.get("owning_tests")
        assert isinstance(owning, list) and owning, f"{entry['module']} must name the tests that import it"
        for test_path in owning:
            path = ROOT / str(test_path)
            assert path.is_file(), f"{entry['module']}: {test_path} does not exist"
            stem = str(entry["module"]).rsplit(".", 1)[-1]
            assert stem in path.read_text(encoding="utf-8"), f"{test_path} does not mention {stem}"


def test_chronicled_statements_match_the_module() -> None:
    for entry in _entries():
        module = str(entry["module"])
        path = ROOT / "src" / (module.replace(".", "/") + ".py")
        assert path.is_file(), f"{module} is registered but missing on disk"
        assert _statements(path) == entry["statements"], (
            f"{module} changed size; update `statements` in the register so the debt stays countable"
        )


def test_the_scan_does_not_treat_the_registers_as_evidence() -> None:
    corpus = disposition.text_corpus(ROOT)

    for register in ("docs/operations/coverage-ratchet.json", "docs/operations/module-disposition.json"):
        assert register not in corpus


@pytest.mark.parametrize("module", ["video_channel_manager.__main__"])
def test_the_package_entrypoint_is_validated_by_running_it(module: str) -> None:
    assert disposition.invocation_exists(module, ROOT) is False
    assert disposition.evidence_names_module(module, "tests/test_package_entrypoint.py", ROOT)
