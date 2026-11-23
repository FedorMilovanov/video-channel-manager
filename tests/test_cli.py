from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import video_channel_manager.cli.app as cli_module

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


@pytest.mark.parametrize("fail", [False, True])
def test_db_init_closes_database_on_success_and_failure(monkeypatch, fail: bool) -> None:
    calls: list[str] = []

    class FakeDatabase:
        def __init__(self, url: str) -> None:
            assert url == "sqlite:///:memory:"

        def create_schema(self) -> None:
            calls.append("create")
            if fail:
                raise RuntimeError("schema failed")

        def close(self) -> None:
            calls.append("close")

    monkeypatch.setattr(cli_module, "Database", FakeDatabase)
    monkeypatch.setattr(
        cli_module,
        "get_settings",
        lambda: SimpleNamespace(database_url="sqlite:///:memory:", ensure_runtime_directories=lambda: None),
    )
    if fail:
        with pytest.raises(RuntimeError, match="schema failed"):
            cli_module.db_init()
    else:
        cli_module.db_init()
    assert calls == ["create", "close"]
