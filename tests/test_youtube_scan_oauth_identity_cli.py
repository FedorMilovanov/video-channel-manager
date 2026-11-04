"""Owner YouTube read-only scan must never misbind a channel or leak raw tracebacks."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

import video_channel_manager.cli.youtube as youtube_cli
from video_channel_manager.cli.app import app
from video_channel_manager.platforms.youtube.oauth import OAuthFlowError

RUNNER = CliRunner()
POET = "UC-78ys2S3cQ3lpqgXfo-SvQ"
LORD_GOD = "UCeSJsC6go2c9pdJCuUI1BYA"


def _client(channels: list[str], *, error: Exception | None = None) -> SimpleNamespace:
    def read_channels() -> list[SimpleNamespace]:
        if error is not None:
            raise error
        return [SimpleNamespace(ref=SimpleNamespace(remote_id=channel)) for channel in channels]

    return SimpleNamespace(list_my_channels=read_channels)


def _install(monkeypatch, tmp_path: Path, client: SimpleNamespace) -> None:
    monkeypatch.setattr(youtube_cli, "get_settings", lambda: SimpleNamespace(data_dir=tmp_path))
    monkeypatch.setattr(youtube_cli, "_components", lambda account, secret=None: (None, None, client))


def test_scan_catches_failed_oauth_refresh_without_traceback_or_output(tmp_path: Path, monkeypatch) -> None:
    error = OAuthFlowError("Google OAuth token.refresh returned HTTP 400 [kind=permanent_http attempts=1]")
    _install(monkeypatch, tmp_path, _client([], error=error))
    output = tmp_path / "scan.json"
    result = RUNNER.invoke(
        app,
        ["youtube", "scan", "--account", "legendary-poet", "--channel", POET, "--output", str(output)],
    )
    assert result.exit_code == 2, (result.stdout, result.exception)
    assert "YouTube scan failed" in result.stdout
    assert "HTTP 400" in result.stdout
    assert "Traceback" not in result.stdout
    assert not output.exists()


def test_channel_listing_catches_failed_oauth_refresh(tmp_path: Path, monkeypatch) -> None:
    error = OAuthFlowError("Google OAuth token.refresh returned HTTP 400 [kind=permanent_http attempts=1]")
    _install(monkeypatch, tmp_path, _client([], error=error))
    result = RUNNER.invoke(app, ["youtube", "channels", "--account", "legendary-poet"])
    assert result.exit_code == 2
    assert "Cannot read YouTube channels" in result.stdout
    assert "HTTP 400" in result.stdout
    assert "Traceback" not in result.stdout


def test_explicit_channel_not_owned_by_authenticated_alias_is_refused_before_inventory(
    tmp_path: Path, monkeypatch
) -> None:
    _install(monkeypatch, tmp_path, _client([LORD_GOD]))
    inventory_called = []

    class NoInventory:
        def __init__(self, *args, **kwargs) -> None:
            inventory_called.append(True)

    monkeypatch.setattr(youtube_cli, "YouTubeInventoryService", NoInventory)
    output = tmp_path / "mismatched.json"
    result = RUNNER.invoke(
        app,
        ["youtube", "scan", "--account", "legendary-poet", "--channel", POET, "--output", str(output)],
    )
    assert result.exit_code == 2, (result.stdout, result.exception)
    assert "Requested --channel does not belong" in result.stdout
    assert "Traceback" not in result.stdout
    assert not inventory_called
    assert not output.exists()


def test_exact_channel_on_multi_channel_alias_still_exports_readonly_package(tmp_path: Path, monkeypatch) -> None:
    _install(monkeypatch, tmp_path, _client([LORD_GOD, POET]))
    inspected: list[str] = []

    class Package:
        videos: list = []
        collections: list = []
        memberships: list = []

        def model_dump_json(self, *, indent: int) -> str:
            return json.dumps({"schema_name": "test-audit-package", "channel_id": inspected[-1]}, indent=indent)

    class Inventory:
        def __init__(self, client) -> None:
            assert client is not None

        def build_audit_package(self, channel_id: str) -> Package:
            inspected.append(channel_id)
            return Package()

    monkeypatch.setattr(youtube_cli, "YouTubeInventoryService", Inventory)
    path = tmp_path / "poet.json"
    result = RUNNER.invoke(
        app,
        ["youtube", "scan", "--account", "legendary-poet", "--channel", POET, "--output", str(path)],
    )
    assert result.exit_code == 0, (result.stdout, result.exception)
    assert inspected == [POET]
    assert json.loads(path.read_text(encoding="utf-8"))["channel_id"] == POET
