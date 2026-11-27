"""Diagnostic uploads must not suppress quality checks or hide their failures."""

import subprocess
from pathlib import Path

import pytest

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


@pytest.mark.parametrize(
    "event,parents,changed,expected",
    [
        (
            "pull_request",
            "merge base head",
            b":100644 100644 a b M\0docs/youtube-description-rendering-standard.md\0",
            True,
        ),
        ("pull_request", "merge base head", b":100644 100644 a b M\0docs/operations/current-state.md\0", True),
        (
            "pull_request",
            "merge base head",
            b":100644 100644 a b M\0docs/operations/current-state.md\0:100644 100644 a b M\0docs/youtube-description-rendering-standard.md\0",
            True,
        ),
        ("push", "merge base head", b":100644 100644 a b M\0docs/operations/current-state.md\0", False),
        ("pull_request", "merge wrong head", b":100644 100644 a b M\0docs/operations/current-state.md\0", False),
        ("pull_request", "merge base wrong", b":100644 100644 a b M\0docs/operations/current-state.md\0", False),
        ("pull_request", "merge base", b":100644 100644 a b M\0docs/operations/current-state.md\0", False),
        ("pull_request", "merge base head", b":100644 100644 a b M\0src/runtime.py\0", False),
        (
            "pull_request",
            "merge base head",
            b":100644 100644 a b M\0docs/operations/current-state.md\0:100644 100644 a b M\0src/runtime.py\0",
            False,
        ),
        ("pull_request", "merge base head", b":100644 100644 a b M\0AGENTS.md\0", False),
        ("pull_request", "merge base head", b":000000 100644 a b A\0docs/operations/current-state.md\0", False),
        ("pull_request", "merge base head", b":100644 000000 a b D\0docs/operations/current-state.md\0", False),
        ("pull_request", "merge base head", b":100644 100644 a b M\0docs/other.md\0", False),
        ("pull_request", "merge base head", b":100644 100644 a b M\0.github/workflows/ci.yml\0", False),
        ("pull_request", "merge base head", b":100644 100644 a b M\0docs/operations/current-state.md", False),
        ("pull_request", "merge base head", b":100644 100755 a b M\0docs/operations/current-state.md\0", False),
        ("pull_request", "merge base head", b":100644 120000 a b T\0docs/operations/current-state.md\0", False),
        ("pull_request", "merge base head", b"", False),
        ("pull_request", "merge base head", None, False),
    ],
)
def test_early_scope_classifier_fails_closed(tmp_path, monkeypatch, event, parents, changed, expected) -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    step = next(s for s in workflow["jobs"]["fast-check"]["steps"] if s.get("id") == "scope")
    script = step["run"].split("python - <<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    output = tmp_path / "github-output"
    monkeypatch.setenv("EVENT_NAME", event)
    monkeypatch.setenv("PR_BASE_SHA", "base")
    monkeypatch.setenv("PR_HEAD_SHA", "head")
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))

    def git(args):
        if args[1] == "rev-list":
            return parents.encode()
        if changed is None:
            raise subprocess.CalledProcessError(1, args)
        return changed

    monkeypatch.setattr(subprocess, "check_output", git)
    exec(compile(script, "ci.yml:scope", "exec"), {})
    assert output.read_text(encoding="utf-8").strip() == f"docs_only={str(expected).lower()}"


def test_required_jobs_fail_on_early_failure_and_keep_main_matrix() -> None:
    jobs = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))["jobs"]
    early = jobs["fast-check"]
    assert early["outputs"]["docs_only"] == "${{ steps.scope.outputs.docs_only }}"
    assert early["steps"][-1]["run"] == "ruff check . --output-format=concise\nruff format --check .\n"
    assert jobs["quality"]["strategy"]["matrix"]["python-version"] == ["3.11", "3.12", "3.13"]
    for job_id in ("quality", "powershell-windows-51", "powershell-windows-7", "powershell-linux-7"):
        job = jobs[job_id]
        assert job["needs"] == "fast-check"
        assert job["if"] == "${{ !cancelled() }}"
        assert job["steps"][0] == {
            "name": "Require successful early check",
            "if": "needs.fast-check.result != 'success'",
            "run": "exit 1",
        }
        for step in job["steps"][2:]:
            assert "needs.fast-check.result == 'success'" in step["if"]
            assert "needs.fast-check.outputs.docs_only != 'true'" in step["if"]
            if job_id == "quality":
                assert "matrix.python-version == '3.11'" in step["if"]
