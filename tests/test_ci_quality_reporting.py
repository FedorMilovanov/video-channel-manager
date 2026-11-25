"""Diagnostic uploads must not suppress quality checks or hide their failures."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_quality_gates_run_after_a_failed_test_report_upload() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    steps = workflow["jobs"]["quality"]["steps"]
    by_name = {step.get("name"): step for step in steps}
    upload = by_name["Upload test report"]
    coverage = by_name["Coverage ratchet gate"]
    enforce = by_name["Enforce quality gates"]

    assert steps.index(upload) < steps.index(coverage) < steps.index(enforce)
    assert upload["with"]["if-no-files-found"] == "error"
    assert not upload.get("continue-on-error", False)
    assert "always()" in coverage["if"]
    assert "matrix.python-version == '3.11'" in coverage["if"]
    assert "steps.tests.outcome == 'success'" in coverage["if"]
    assert "steps.tests.outcome == 'failure'" in coverage["if"]
    assert "always()" in enforce["if"]
    for gate in ("pip_audit", "ruff", "format", "mypy", "tests", "coverage_ratchet"):
        assert f"steps.{gate}.outcome == 'failure'" in enforce["if"]
    assert enforce["run"] == "exit 1"
