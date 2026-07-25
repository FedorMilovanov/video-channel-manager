from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from video_channel_manager.cli.app import app

runner = CliRunner()


def _example_path() -> Path:
    return Path(__file__).resolve().parents[1] / "content" / "editorial" / "examples" / "tyutchev-night-sea.json"


def test_content_preview_youtube_and_vk() -> None:
    youtube = runner.invoke(
        app,
        ["content", "preview", "--platform", "youtube", "--surface", "comment", "--input", str(_example_path())],
    )
    assert youtube.exit_code == 0, youtube.stdout
    assert "The Legendary Poet" in youtube.stdout

    vk = runner.invoke(
        app,
        ["content", "preview", "--platform", "vk", "--surface", "video_description", "--input", str(_example_path())],
    )
    assert vk.exit_code == 0, vk.stdout
    assert "Сообщество проекта VK: https://vk.com/thelegendarypoet" in vk.stdout
    assert "*Сообщество" not in vk.stdout


def test_content_validate_command() -> None:
    result = runner.invoke(app, ["content", "validate", "--input", str(_example_path())])
    assert result.exit_code == 0, result.stdout
    assert "Validated 1 editorial content record" in result.stdout
