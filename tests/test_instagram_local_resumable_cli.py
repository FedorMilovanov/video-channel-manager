from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.main import get_command
from typer.testing import CliRunner

from video_channel_manager.cli.instagram_production import (
    _enforce_local_reel_size,
    instagram_production_app,
)
from video_channel_manager.instagram.production import InstagramProductionError


_ANSI_CSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _plain(output: str) -> str:
    return _ANSI_CSI.sub("", output)


def test_publish_local_is_exposed_in_production_help() -> None:
    result = CliRunner().invoke(instagram_production_app, ["--help"])
    assert result.exit_code == 0, result.output
    assert "publish-local" in _plain(result.output)


def test_publish_local_exposes_explicit_write_gate() -> None:
    command = get_command(instagram_production_app)
    publish_local = command.commands["publish-local"]
    options = {option for parameter in publish_local.params for option in getattr(parameter, "opts", ())}
    assert "--publication-key" in options
    assert "--execute" in options
    assert "--share-to-feed" in options


def test_publish_local_rejects_file_above_meta_one_gigabyte_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    video_path = tmp_path / "too-large.mp4"
    monkeypatch.setattr(Path, "stat", lambda self: SimpleNamespace(st_size=1_000_000_001))

    with pytest.raises(InstagramProductionError, match="at most 1000000000 bytes"):
        _enforce_local_reel_size(video_path)
