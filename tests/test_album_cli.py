from pathlib import Path

from typer.testing import CliRunner

import video_channel_manager.cli.album as album_cli
from video_channel_manager.cli.app import app
from video_channel_manager.config.settings import AppSettings

runner = CliRunner()


def test_album_command_is_registered() -> None:
    result = runner.invoke(app, ["album", "--help"])

    assert result.exit_code == 0
    assert "init" in result.stdout
    assert "add-youtube" in result.stdout
    assert "add-local" in result.stdout
    assert "acquire" in result.stdout
    assert "probe" in result.stdout
    assert "timing" in result.stdout
    assert "artwork-plan" in result.stdout
    assert "render" in result.stdout
    assert "verify" in result.stdout
    assert "package" in result.stdout


def test_cli_initializes_seven_tracks_and_accepts_pending_bonus(tmp_path: Path, monkeypatch) -> None:
    settings = AppSettings(data_dir=tmp_path)
    monkeypatch.setattr(album_cli, "get_settings", lambda: settings)

    init_result = runner.invoke(
        app,
        [
            "album",
            "init",
            "--project",
            "legendary-poet",
            "--album",
            "black-man",
            "--tracks",
            "7",
            "--title",
            "Сергей Есенин — Чёрный человек",
        ],
    )
    assert init_result.exit_code == 0, init_result.stdout

    youtube_result = runner.invoke(
        app,
        [
            "album",
            "add-youtube",
            "--album",
            "black-man",
            "--track",
            "1",
            "--video-id",
            "8ULM0GD_HdU",
            "--title",
            "Чёрный человек — Version 1",
        ],
    )
    assert youtube_result.exit_code == 0, youtube_result.stdout

    pending_path = tmp_path / "future" / "version-7.wav"
    local_result = runner.invoke(
        app,
        [
            "album",
            "add-local",
            "--album",
            "black-man",
            "--track",
            "7",
            "--path",
            str(pending_path),
            "--title",
            "Чёрный человек — Bonus Track",
        ],
    )
    assert local_result.exit_code == 0, local_result.stdout
    assert "pending_local_master" in local_result.stdout

    status_result = runner.invoke(app, ["album", "status", "--album", "black-man"])
    assert status_result.exit_code == 0, status_result.stdout
    assert "8ULM0GD_HdU" in status_result.stdout
    assert "pending_local_master" in status_result.stdout
