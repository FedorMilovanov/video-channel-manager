from __future__ import annotations

import sys
from typing import Any

import pytest

import video_channel_manager.telegram_github_quality_gate as quality_gate
from video_channel_manager.telegram_github_quality_gate import (
    require_current_main_ref,
    require_successful_quality_run,
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


class _FakeTime:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


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


def test_quality_gate_waits_for_exact_sha_success(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_time = _FakeTime()
    run_reads = 0

    def fake_github_json(url: str, *, token: str) -> dict[str, Any]:
        nonlocal run_reads
        assert token == "token"
        if "/git/ref/heads/main" in url:
            return _main_ref()
        run_reads += 1
        if run_reads == 1:
            return {"workflow_runs": []}
        return {"workflow_runs": [_run(id=777)]}

    monkeypatch.setattr(quality_gate, "_safe_github_json", fake_github_json)
    monkeypatch.setattr(quality_gate, "time", fake_time)

    selected = require_successful_quality_run(
        api_url="https://api.github.test",
        repository="owner/repo",
        token="token",
        workflow_file=WORKFLOW,
        head_sha=SHA,
        wait_seconds=30,
        poll_seconds=10,
    )

    assert selected["id"] == 777
    assert run_reads == 2
    assert fake_time.sleeps == [10]


def test_quality_gate_reproves_main_while_waiting(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_time = _FakeTime()
    main_reads = 0

    def fake_github_json(url: str, *, token: str) -> dict[str, Any]:
        nonlocal main_reads
        if "/git/ref/heads/main" in url:
            main_reads += 1
            return _main_ref() if main_reads == 1 else _main_ref("2" * 40)
        return {"workflow_runs": []}

    monkeypatch.setattr(quality_gate, "_safe_github_json", fake_github_json)
    monkeypatch.setattr(quality_gate, "time", fake_time)

    with pytest.raises(ValueError, match="no longer the current main commit"):
        require_successful_quality_run(
            api_url="https://api.github.test",
            repository="owner/repo",
            token="token",
            workflow_file=WORKFLOW,
            head_sha=SHA,
            wait_seconds=30,
            poll_seconds=10,
        )

    assert main_reads == 2
    assert fake_time.sleeps == [10]


def test_quality_gate_wait_times_out_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_time = _FakeTime()
    run_reads = 0

    def fake_github_json(url: str, *, token: str) -> dict[str, Any]:
        nonlocal run_reads
        if "/git/ref/heads/main" in url:
            return _main_ref()
        run_reads += 1
        return {"workflow_runs": []}

    monkeypatch.setattr(quality_gate, "_safe_github_json", fake_github_json)
    monkeypatch.setattr(quality_gate, "time", fake_time)

    with pytest.raises(ValueError, match="exact current main SHA"):
        require_successful_quality_run(
            api_url="https://api.github.test",
            repository="owner/repo",
            token="token",
            workflow_file=WORKFLOW,
            head_sha=SHA,
            wait_seconds=5,
            poll_seconds=10,
        )

    assert run_reads == 2
    assert fake_time.sleeps == [5]


@pytest.mark.parametrize(("event_name", "expected_wait"), [("schedule", 420.0), ("workflow_dispatch", 0.0)])
def test_cli_uses_bounded_wait_only_for_scheduled_execution(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    event_name: str,
    expected_wait: float,
) -> None:
    captured: dict[str, Any] = {}

    def fake_require(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return _run(id=888)

    monkeypatch.setenv("GITHUB_API_URL", "https://api.github.test")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GH_TOKEN", "token")
    monkeypatch.setenv("GITHUB_EVENT_NAME", event_name)
    monkeypatch.setattr(quality_gate, "require_successful_quality_run", fake_require)
    monkeypatch.setattr(sys, "argv", ["quality-gate", "--workflow", WORKFLOW, "--sha", SHA])

    assert quality_gate.main() == 0
    assert captured["wait_seconds"] == expected_wait
    assert '"quality_proven": true' in capsys.readouterr().out
