"""`python -m video_channel_manager` must reach the same CLI as the `video-manager` script.

`src/video_channel_manager/__main__.py` is three lines and had 0% coverage: nothing proved that the
module entrypoint dispatches to `cli.app.run`, and nothing proved that importing the module (as
opposed to running it) stays side-effect free. Both are cheap to pin down and both are the kind of
thing that breaks silently in a refactor.

The dispatch is observed by replacing `run` before the shim is executed, so no CLI command runs and
no provider is contacted.
"""

from __future__ import annotations

import runpy
import subprocess
import sys
from pathlib import Path

import pytest

from video_channel_manager.cli import app as cli_app

ROOT = Path(__file__).resolve().parents[1]


def test_module_entrypoint_dispatches_to_the_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(cli_app, "run", lambda: calls.append("run"))

    runpy.run_module("video_channel_manager.__main__", run_name="__main__")

    assert calls == ["run"]


def test_importing_the_entrypoint_module_runs_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(cli_app, "run", lambda: calls.append("run"))

    runpy.run_module("video_channel_manager.__main__", run_name="video_channel_manager.__main__")

    assert calls == []


def test_the_module_entrypoint_prints_help_without_touching_providers() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "video_channel_manager", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Usage" in completed.stdout
    assert completed.stderr == ""
