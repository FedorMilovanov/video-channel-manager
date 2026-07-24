from typer.testing import CliRunner

from video_channel_manager import __version__
from video_channel_manager.cli.app import app

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_schema_export(tmp_path) -> None:
    result = runner.invoke(app, ["schema", "export", "--output-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / "audit-package-v1.schema.json").exists()
    assert (tmp_path / "change-plan-v1.schema.json").exists()
