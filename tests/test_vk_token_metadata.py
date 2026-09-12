from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

import video_channel_manager.cli.vk as vk_cli
from video_channel_manager.cli.vk import vk_app
from video_channel_manager.platforms.vk.client import VkApiClient, VkApiError
from video_channel_manager.platforms.vk.models import (
    VkAccessToken,
    VkUserIdentity,
    known_user_scopes_from_permission_mask,
)
from video_channel_manager.platforms.vk.store import VkTokenStore
from video_channel_manager.platforms.vk.writer import VkVideoWriter, VkWriteError

runner = CliRunner()
_FULL_MASK = 16 | 8192 | 262144


def test_raw_vk_token_does_not_claim_unverified_permissions() -> None:
    token = VkAccessToken.from_text("secret-token")

    assert token.scopes == []
    assert token.permission_mask is None
    assert known_user_scopes_from_permission_mask(_FULL_MASK) == ["video", "wall", "groups"]


def test_vk_client_reads_and_validates_app_permission_mask(tmp_path: Path) -> None:
    store = VkTokenStore(tmp_path)
    store.save_token("legendary-poet", VkAccessToken(access_token="secret"))

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": _FULL_MASK})

    client = VkApiClient(
        token_store=store,
        account_alias="legendary-poet",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        api_base_url="https://example.test/method",
    )

    assert client.get_app_permission_mask() == _FULL_MASK


def test_vk_client_rejects_invalid_app_permission_mask(tmp_path: Path) -> None:
    store = VkTokenStore(tmp_path)
    store.save_token("legendary-poet", VkAccessToken(access_token="secret"))
    client = VkApiClient(
        token_store=store,
        account_alias="legendary-poet",
        http_client=httpx.Client(
            transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={"response": True}))
        ),
        api_base_url="https://example.test/method",
    )

    with pytest.raises(VkApiError, match="invalid permission mask"):
        client.get_app_permission_mask()


def test_wall_call_requires_verified_wall_scope_before_network(tmp_path: Path) -> None:
    store = VkTokenStore(tmp_path)
    store.save_token(
        "legendary-poet",
        VkAccessToken(access_token="secret", scopes=["video"], permission_mask=16),
    )
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    writer = VkVideoWriter(
        token_store=store,
        account_alias="legendary-poet",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        api_base_url="https://example.test/method",
    )

    with pytest.raises(VkWriteError, match="wall") as captured:
        writer._call("wall.get", params={"owner_id": -1}, retry_transient=True)

    assert captured.value.code == 7
    assert captured.value.attempts == 0
    assert calls == 0


class _PermissionClient:
    def __init__(self, **_kwargs: Any) -> None:
        pass

    def get_app_permission_mask(self) -> int:
        return _FULL_MASK


def test_token_capabilities_syncs_equivalent_alias_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = VkTokenStore(tmp_path)
    stale = VkAccessToken(access_token="shared", scopes=["video"], permission_mask=16)
    store.save_token("default", stale.model_copy(deep=True))
    store.save_token("legendary-poet", stale.model_copy(deep=True))
    monkeypatch.setattr(vk_cli, "get_settings", lambda: SimpleNamespace(data_dir=tmp_path, vk_api_version="5.199"))
    monkeypatch.setattr(vk_cli, "VkApiClient", _PermissionClient)

    result = runner.invoke(
        vk_app,
        ["token-capabilities", "--account", "legendary-poet", "--sync-local"],
    )

    assert result.exit_code == 0, result.output
    assert "Provider writes: 0" in result.output
    for alias in ("default", "legendary-poet"):
        token = store.load_token(alias)
        assert token.permission_mask == _FULL_MASK
        assert token.scopes == ["video", "wall", "groups"]


class _LoginClient(_PermissionClient):
    def get_current_user(self) -> VkUserIdentity:
        return VkUserIdentity(user_id=42, display_name="Test User")

    def validate_video_access(self, user_id: int) -> None:
        assert user_id == 42

    def list_managed_communities(self) -> list[Any]:
        return []


def test_vk_login_persists_provider_verified_permission_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        vk_cli,
        "get_settings",
        lambda: SimpleNamespace(
            data_dir=tmp_path,
            vk_api_version="5.199",
            vk_access_token=None,
        ),
    )
    monkeypatch.setattr(vk_cli, "_read_token_input", lambda _path: VkAccessToken.from_text("secret"))
    monkeypatch.setattr(vk_cli, "VkApiClient", _LoginClient)

    result = runner.invoke(vk_app, ["login", "--account", "legendary-poet"])

    assert result.exit_code == 0, result.output
    token = VkTokenStore(tmp_path).load_token("legendary-poet")
    assert token.user_id == 42
    assert token.permission_mask == _FULL_MASK
    assert token.scopes == ["video", "wall", "groups"]
