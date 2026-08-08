from __future__ import annotations

import pytest

from video_channel_manager.telegram_github_quality_gate import (
    require_current_main_ref,
    select_successful_quality_run,
)

SHA = "1" * 40
WORKFLOW = "svodka-quality.yml"


def _run(**overrides):
    value = {
        "id": 100,
        "head_sha": SHA,
        "head_branch": "main",
        "status": "completed",
        "conclusion": "success",
        "event": "push",
        "path": ".github/workflows/svodka-quality.yml@main",
        "run_attempt": 1,
    }
    value.update(overrides)
    return value


def _main_ref(sha: str = SHA) -> dict[str, object]:
    return {
        "ref": "refs/heads/main",
        "object": {
            "type": "commit",
            "sha": sha,
        },
    }


def test_current_main_ref_accepts_exact_writer_sha() -> None:
    require_current_main_ref(_main_ref(), head_sha=SHA)


def test_current_main_ref_rejects_writer_sha_after_main_advances() -> None:
    with pytest.raises(ValueError, match="no longer the current main commit"):
        require_current_main_ref(_main_ref("2" * 40), head_sha=SHA)


def test_current_main_ref_rejects_wrong_reference() -> None:
    payload = _main_ref()
    payload["ref"] = "refs/heads/other"

    with pytest.raises(ValueError, match="wrong ref"):
        require_current_main_ref(payload, head_sha=SHA)


def test_quality_gate_accepts_only_completed_success_for_exact_main_sha() -> None:
    payload = {
        "workflow_runs": [
            _run(id=90, head_sha="2" * 40),
            _run(id=91, conclusion="failure"),
            _run(id=92, status="in_progress", conclusion=None),
            _run(id=93, head_branch="other"),
            _run(id=94, event="pull_request"),
            _run(id=95, path=".github/workflows/ci.yml@main"),
            _run(id=101),
        ]
    }

    selected = select_successful_quality_run(payload, workflow_file=WORKFLOW, head_sha=SHA)

    assert selected["id"] == 101


def test_quality_gate_normalizes_workflow_path_ref_suffix() -> None:
    payload = {"workflow_runs": [_run(id=101, path=".github/workflows/svodka-quality.yml@refs/heads/main")]}

    selected = select_successful_quality_run(payload, workflow_file=WORKFLOW, head_sha=SHA)

    assert selected["id"] == 101


def test_quality_gate_accepts_plain_workflow_path_fallback() -> None:
    payload = {"workflow_runs": [_run(id=101, path=".github/workflows/svodka-quality.yml")]}

    selected = select_successful_quality_run(payload, workflow_file=WORKFLOW, head_sha=SHA)

    assert selected["id"] == 101


def test_quality_gate_accepts_manual_full_quality_for_same_sha() -> None:
    payload = {"workflow_runs": [_run(id=102, event="workflow_dispatch")]}

    selected = select_successful_quality_run(payload, workflow_file=WORKFLOW, head_sha=SHA)

    assert selected["id"] == 102


def test_quality_gate_rejects_when_exact_sha_has_no_valid_success() -> None:
    payload = {"workflow_runs": [_run(head_sha="3" * 40), _run(conclusion="failure")]}

    with pytest.raises(ValueError, match="exact current main SHA"):
        select_successful_quality_run(payload, workflow_file=WORKFLOW, head_sha=SHA)
