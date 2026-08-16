from __future__ import annotations

from rich.text import Text
from typer.testing import CliRunner

from video_channel_manager.cli.vk import vk_app


def test_milovi_323_continue_cli_is_preview_only() -> None:
    result = CliRunner().invoke(vk_app, ["milovi-323-continue", "--help"])
    plain = Text.from_ansi(result.stdout).plain

    assert result.exit_code == 0
    assert "--promotion-spec" in plain
    assert "--promotion-journal" in plain
    assert "--confirm-journal-init" in plain
    assert "--confirm-preflight-digest" in plain
    assert "--execute" not in plain
    assert "execute zero provider writes" in plain
