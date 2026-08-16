from __future__ import annotations

from typer.testing import CliRunner

from video_channel_manager.cli.vk import vk_app


def test_milovi_323_continue_cli_is_preview_only() -> None:
    result = CliRunner().invoke(vk_app, ["milovi-323-continue", "--help"])

    assert result.exit_code == 0
    assert "--promotion-spec" in result.stdout
    assert "--promotion-journal" in result.stdout
    assert "--confirm-journal-init" in result.stdout
    assert "--execute" not in result.stdout
    assert "execute zero writes" in result.stdout
