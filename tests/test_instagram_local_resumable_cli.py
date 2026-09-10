from __future__ import annotations

import re

from typer.testing import CliRunner

from video_channel_manager.cli.instagram_production import instagram_production_app


_ANSI_CSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _plain(output: str) -> str:
    return _ANSI_CSI.sub("", output)


def test_publish_local_is_exposed_in_production_help() -> None:
    result = CliRunner().invoke(instagram_production_app, ["--help"])
    assert result.exit_code == 0, result.output
    assert "publish-local" in _plain(result.output)


def test_publish_local_help_exposes_explicit_write_gate() -> None:
    result = CliRunner().invoke(instagram_production_app, ["publish-local", "--help"])
    assert result.exit_code == 0, result.output
    output = _plain(result.output)
    assert "--publication-key" in output
    assert "--execute" in output
    assert "--share-to-feed" in output
