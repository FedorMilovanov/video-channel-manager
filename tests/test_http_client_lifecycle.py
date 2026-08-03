from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import httpx
import pytest

import video_channel_manager.platforms.http as http_lifecycle_module
from video_channel_manager.platforms.http import HttpClientOwner
from video_channel_manager.platforms.vk.client import VkApiClient
from video_channel_manager.platforms.vk.models import VkAccessToken
from video_channel_manager.platforms.vk.store import VkTokenStore
from video_channel_manager.platforms.vk.thumbnails import VkThumbnailWriter
from video_channel_manager.platforms.vk.writer import VkVideoWriter
from video_channel_manager.platforms.youtube.client import YouTubeApiClient
from video_channel_manager.platforms.youtube.oauth import InstalledOAuthFlow
from video_channel_manager.platforms.youtube.writer import YouTubeDescriptionWriter

ROOT = Path(__file__).resolve().parents[1]


class RecordingHttpClient:
    def __init__(self) -> None:
        self.post_count = 0
        self.close_count = 0

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        del kwargs
        self.post_count += 1
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={"response": [{"id": 42, "first_name": "Test", "last_name": "User"}]},
        )

    def close(self) -> None:
        self.close_count += 1


def _token_store(tmp_path: Path) -> VkTokenStore:
    store = VkTokenStore(tmp_path)
    store.save_token("default", VkAccessToken(access_token="access", user_id=42))
    return store


def test_vk_reader_creates_one_client_and_reuses_it_for_multiple_calls(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    created: list[RecordingHttpClient] = []

    def client_factory(**kwargs: Any) -> RecordingHttpClient:
        assert kwargs["timeout"] == 45.0
        assert kwargs["follow_redirects"] is True
        client = RecordingHttpClient()
        created.append(client)
        return client

    monkeypatch.setattr(http_lifecycle_module.httpx, "Client", client_factory)
    client = VkApiClient(
        token_store=_token_store(tmp_path),
        account_alias="default",
        api_base_url="https://example.test/method",
    )

    assert client.owns_http_client is True
    assert client.get_current_user().user_id == 42
    assert client.get_current_user().user_id == 42
    assert len(created) == 1
    assert created[0].post_count == 2

    client.close()
    client.close()
    assert created[0].close_count == 1


def test_provider_never_closes_an_injected_client(tmp_path: Path) -> None:
    external = RecordingHttpClient()
    client = VkApiClient(
        token_store=_token_store(tmp_path),
        account_alias="default",
        http_client=external,  # type: ignore[arg-type]
        api_base_url="https://example.test/method",
    )

    assert client.owns_http_client is False
    assert client.get_current_user().user_id == 42
    client.close()
    assert external.close_count == 0


def test_owned_client_closes_on_context_exit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    owned = RecordingHttpClient()
    monkeypatch.setattr(http_lifecycle_module.httpx, "Client", lambda **_: owned)

    with VkApiClient(
        token_store=_token_store(tmp_path),
        account_alias="default",
        api_base_url="https://example.test/method",
    ) as client:
        assert client.get_current_user().user_id == 42

    assert owned.close_count == 1


def test_provider_clients_share_the_lifecycle_contract() -> None:
    for provider_class in (
        VkApiClient,
        VkVideoWriter,
        VkThumbnailWriter,
        YouTubeApiClient,
        YouTubeDescriptionWriter,
        InstalledOAuthFlow,
    ):
        assert issubclass(provider_class, HttpClientOwner)


def test_provider_request_methods_do_not_construct_per_call_clients() -> None:
    offenders: list[str] = []
    for relative_path in (
        "src/video_channel_manager/platforms/vk/client.py",
        "src/video_channel_manager/platforms/vk/writer.py",
        "src/video_channel_manager/platforms/vk/thumbnails.py",
        "src/video_channel_manager/platforms/youtube/client.py",
        "src/video_channel_manager/platforms/youtube/writer.py",
        "src/video_channel_manager/platforms/youtube/oauth.py",
    ):
        path = ROOT / relative_path
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if not isinstance(node.func.value, ast.Name):
                continue
            if node.func.value.id == "httpx" and node.func.attr == "Client":
                offenders.append(f"{relative_path}:{node.lineno}")
    assert offenders == []
