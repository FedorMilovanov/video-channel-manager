from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from video_channel_manager.cli.app import app
from video_channel_manager.platforms.vk import milovi_issue323_finalize as finalizer

runner = CliRunner()
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def test_milovi_323_finalize_calls_guarded_finalizer_with_exact_paths(monkeypatch: Any, tmp_path: Path) -> None:
    output = tmp_path / "finalizer.json"
    rollout_output = tmp_path / "rollout.json"
    journal = tmp_path / "journal.json"
    finalizer_journal = tmp_path / "finalizer-journal.json"
    schedule = tmp_path / "schedule.json"
    work_dir = tmp_path / "work"
    observed: dict[str, Any] = {}

    def fake_run(**kwargs: Any) -> dict[str, Any]:
        observed.update(kwargs)
        return {"status": "final_verified", "browser_used": False}

    monkeypatch.setattr(finalizer, "run_issue_323_finalizer", fake_run)

    result = runner.invoke(
        app,
        [
            "vk",
            "milovi-323-finalize",
            "--execute",
            finalizer.EXECUTION_CONFIRMATION,
            "--output",
            str(output),
            "--rollout-output",
            str(rollout_output),
            "--journal",
            str(journal),
            "--finalizer-journal",
            str(finalizer_journal),
            "--schedule",
            str(schedule),
            "--work-dir",
            str(work_dir),
            "--verify-timeout",
            "600",
        ],
    )

    assert result.exit_code == 0, result.output
    assert observed == {
        "confirmation": finalizer.EXECUTION_CONFIRMATION,
        "output_path": output,
        "rollout_output_path": rollout_output,
        "journal_path": journal,
        "finalizer_journal_path": finalizer_journal,
        "schedule_path": schedule,
        "work_dir": work_dir,
        "verify_timeout_seconds": 600,
    }
    assert "final_verified" in result.output
    assert "browser=False" in result.output


def test_milovi_323_finalize_help_exposes_explicit_write_confirmation() -> None:
    result = runner.invoke(app, ["vk", "milovi-323-finalize", "--help"])
    plain_help = _ANSI_ESCAPE.sub("", result.output)

    assert result.exit_code == 0, result.output
    assert "--execute" in plain_help
    assert "--journal" in plain_help
    assert "--finalizer-journal" in plain_help
    assert "--schedule" in plain_help
    assert "--work-dir" in plain_help
    assert "--verify-timeout" in plain_help


def test_milovi_323_finalize_fails_closed(monkeypatch: Any, tmp_path: Path) -> None:
    def blocked(**_kwargs: Any) -> dict[str, Any]:
        raise finalizer.MiloviFinalizerBlocked("exact live state conflict")

    monkeypatch.setattr(finalizer, "run_issue_323_finalizer", blocked)

    result = runner.invoke(
        app,
        [
            "vk",
            "milovi-323-finalize",
            "--execute",
            finalizer.EXECUTION_CONFIRMATION,
            "--output",
            str(tmp_path / "finalizer.json"),
        ],
    )

    assert result.exit_code == 3
    assert "STOP: MiloviFinalizerBlocked: exact live state conflict" in result.output
