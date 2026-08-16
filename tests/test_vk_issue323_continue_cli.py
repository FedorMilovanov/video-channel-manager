from __future__ import annotations

from rich.text import Text
from typer.testing import CliRunner

from video_channel_manager.cli.vk import vk_app


def test_milovi_323_continue_cli_requires_digest_bound_provider_confirmation() -> None:
    result = CliRunner().invoke(vk_app, ["milovi-323-continue", "--help"])
    plain = Text.from_ansi(result.stdout).plain
    normalized = " ".join(plain.split())

    assert result.exit_code == 0
    assert "--promotion-spec" in normalized
    assert "--promotion-journal" in normalized
    assert "--confirm-journal-init" in normalized
    assert "--confirm-preflight-digest" in normalized
    assert "--confirm-provider-dispatch" in normalized
    assert "--execute" not in normalized
    assert "Advance one digest-bound Issue #323 continuation step" in normalized
