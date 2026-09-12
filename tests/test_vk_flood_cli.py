from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from typer.testing import CliRunner

import video_channel_manager.cli.vk as vk_cli
from video_channel_manager.cli.vk import vk_app
from video_channel_manager.platforms.vk.flood_control import VkFloodControlGate
from video_channel_manager.platforms.vk.models import VkAccessToken
from video_channel_manager.platforms.vk.store import VkTokenStore

runner = CliRunner()


def test_flood_cli_uses_credential_scope_across_equivalent_aliases(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    store = VkTokenStore(tmp_path)
    shared = VkAccessToken(access_token="shared-token", user_id=42)
    store.save_token("default", shared)
    store.save_token("legendary-poet", shared)
    VkFloodControlGate(tmp_path, "legendary-poet").record("wall.get")
    VkFloodControlGate(tmp_path, "default").record("apps.get")

    monkeypatch.setattr(vk_cli, "get_settings", lambda: SimpleNamespace(data_dir=tmp_path))

    status = runner.invoke(vk_app, ["flood-status", "--account", "default"])

    assert status.exit_code == 0, status.output
    assert "wall.get" in status.output
    assert "apps.get" in status.output
    assert "Provider calls: 0" in status.output

    reset = runner.invoke(
        vk_app,
        ["flood-reset-all", "--account", "default", "--confirm-code", "9"],
    )

    assert reset.exit_code == 0, reset.output
    assert "Provider calls: 0" in reset.output
    assert "apps.get" in reset.output
    assert "wall.get" in reset.output
    for alias in ("default", "legendary-poet"):
        assert VkFloodControlGate(tmp_path, alias).list_open() == ()


def test_flood_reset_cannot_clear_final_global_quarantine_entry(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    store = VkTokenStore(tmp_path)
    store.save_token("legendary-poet", VkAccessToken(access_token="shared-token", user_id=42))
    VkFloodControlGate(tmp_path, "legendary-poet").record("wall.get")
    monkeypatch.setattr(vk_cli, "get_settings", lambda: SimpleNamespace(data_dir=tmp_path))

    result = runner.invoke(
        vk_app,
        ["flood-reset", "--account", "legendary-poet", "--method", "wall.get", "--confirm-code", "9"],
    )

    assert result.exit_code == 2, result.output
    assert "flood-reset-all" in result.output
    assert VkFloodControlGate(tmp_path, "legendary-poet").get("wall.get") is not None


def test_flood_reset_can_clear_one_forensic_entry_while_global_quarantine_remains(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    store = VkTokenStore(tmp_path)
    store.save_token("legendary-poet", VkAccessToken(access_token="shared-token", user_id=42))
    gate = VkFloodControlGate(tmp_path, "legendary-poet")
    gate.record("wall.get")
    gate.record("apps.get")
    monkeypatch.setattr(vk_cli, "get_settings", lambda: SimpleNamespace(data_dir=tmp_path))

    result = runner.invoke(
        vk_app,
        ["flood-reset", "--account", "legendary-poet", "--method", "apps.get", "--confirm-code", "9"],
    )

    assert result.exit_code == 0, result.output
    assert "calls: 0." in result.output
    assert gate.get("apps.get") is None
    assert gate.get("wall.get") is not None
