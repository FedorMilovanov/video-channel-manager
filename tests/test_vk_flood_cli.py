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

    monkeypatch.setattr(vk_cli, "get_settings", lambda: SimpleNamespace(data_dir=tmp_path))

    status = runner.invoke(vk_app, ["flood-status", "--account", "default"])

    assert status.exit_code == 0, status.output
    assert "wall.get" in status.output
    assert "Provider calls: 0" in status.output

    reset = runner.invoke(
        vk_app,
        ["flood-reset", "--account", "default", "--method", "wall.get", "--confirm-code", "9"],
    )

    assert reset.exit_code == 0, reset.output
    assert "Provider calls: 0" in reset.output
    assert VkFloodControlGate(tmp_path, "default").get("wall.get") is None
    assert VkFloodControlGate(tmp_path, "legendary-poet").get("wall.get") is None


def test_community_probe_is_single_attempt_read_only(monkeypatch: Any, tmp_path: Path) -> None:
    store = VkTokenStore(tmp_path)
    store.save_token(
        "legendary-poet", VkAccessToken(access_token="shared-token", user_id=42, scopes=["groups", "wall"])
    )
    observed: dict[str, Any] = {}

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            observed["max_attempts"] = kwargs["max_attempts"]
            observed["account_alias"] = kwargs["account_alias"]

        def get_community(self, community: int) -> object:
            observed["community"] = community
            return object()

        def close(self) -> None:
            observed["closed"] = True

    monkeypatch.setattr(
        vk_cli,
        "get_settings",
        lambda: SimpleNamespace(data_dir=tmp_path, vk_api_version="5.199"),
    )
    monkeypatch.setattr(vk_cli, "VkApiClient", FakeClient)

    result = runner.invoke(
        vk_app,
        ["community-probe", "--account", "legendary-poet", "--community", "60805374"],
    )

    assert result.exit_code == 0, result.output
    assert observed == {
        "max_attempts": 1,
        "account_alias": "legendary-poet",
        "community": 60805374,
        "closed": True,
    }
    assert "Provider calls: 1" in result.output
    assert "Provider writes: 0" in result.output


def test_wall_probe_is_single_attempt_read_only(monkeypatch: Any, tmp_path: Path) -> None:
    store = VkTokenStore(tmp_path)
    store.save_token(
        "legendary-poet", VkAccessToken(access_token="shared-token", user_id=42, scopes=["groups", "wall"])
    )
    observed: dict[str, Any] = {}

    class FakeWriter:
        def __init__(self, **kwargs: Any) -> None:
            observed["max_attempts"] = kwargs["max_attempts"]
            observed["account_alias"] = kwargs["account_alias"]

        def assert_token_scopes(self, *scopes: str) -> None:
            observed["scopes"] = scopes

        def probe_wall_get(self, *, community_id: int) -> tuple[list[dict[str, Any]], int]:
            observed["community_id"] = community_id
            return ([{"owner_id": -community_id}], 3137)

        def close(self) -> None:
            observed["closed"] = True

    monkeypatch.setattr(
        vk_cli,
        "get_settings",
        lambda: SimpleNamespace(data_dir=tmp_path, vk_api_version="5.199"),
    )
    monkeypatch.setattr(vk_cli, "VkWallWriter", FakeWriter)

    result = runner.invoke(
        vk_app,
        ["wall-probe", "--account", "legendary-poet", "--community", "60805374"],
    )

    assert result.exit_code == 0, result.output
    assert observed == {
        "max_attempts": 1,
        "account_alias": "legendary-poet",
        "scopes": ("wall",),
        "community_id": 60805374,
        "closed": True,
    }
    assert "Provider calls: 1" in result.output
    assert "Provider writes: 0" in result.output
