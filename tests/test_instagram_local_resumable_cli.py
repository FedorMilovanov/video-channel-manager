from __future__ import annotations

from typer.testing import CliRunner

from video_channel_manager.cli.instagram_production import instagram_production_app


def test_publish_local_is_exposed_in_production_help() -> None:
    result = CliRunner().invoke(instagram_production_app, ["--help"])
    assert result.exit_code == 0, result.output
    assert "publish-local" in result.output


def test_publish_local_help_exposes_explicit_write_gate() -> None:
    result = CliRunner().invoke(instagram_production_app, ["publish-local", "--help"])
    assert result.exit_code == 0, result.output
    assert "--publication-key" in result.output
    assert "--execute" in result.output
    assert "--share-to-feed" in result.output
