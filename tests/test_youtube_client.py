from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from video_channel_manager.platforms.youtube.client import YouTubeApiClient
from video_channel_manager.platforms.youtube.models import InstalledClientConfig, OAuthToken
from video_channel_manager.platforms.youtube.service import YouTubeInventoryService
from video_channel_manager.platforms.youtube.store import TokenStore


def _client(tmp_path: Path) -> YouTubeApiClient:
    store = TokenStore(tmp_path)
    store.save_token(
        "default",
        OAuthToken(
            access_token="access",
            refresh_token="refresh",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        ),
    )
    config = InstalledClientConfig(client_id="id", client_secret="secret")

    def handler(request: httpx.Request) -> httpx.Response:
        resource = request.url.path.rsplit("/", 1)[-1]
        params = request.url.params
        if resource == "channels" and params.get("mine") == "true":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "UC1",
                            "snippet": {"title": "Legendary Poet", "description": "Channel"},
                            "contentDetails": {"relatedPlaylists": {"uploads": "UU1"}},
                            "statistics": {"videoCount": "1"},
                            "status": {"privacyStatus": "public"},
                        }
                    ]
                },
            )
        if resource == "channels":
            return httpx.Response(
                200,
                json={"items": [{"id": "UC1", "contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]},
            )
        if resource == "playlistItems" and params.get("playlistId") == "UU1":
            return httpx.Response(200, json={"items": [{"contentDetails": {"videoId": "VID1"}}]})
        if resource == "videos":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "VID1",
                            "snippet": {
                                "title": "Poem",
                                "description": "Description",
                                "publishedAt": "2026-01-02T03:04:05Z",
                                "tags": ["poetry"],
                                "thumbnails": {"high": {"url": "https://img/high.jpg"}},
                            },
                            "contentDetails": {"duration": "PT4M18S"},
                            "status": {"privacyStatus": "public"},
                        }
                    ]
                },
            )
        if resource == "playlists":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "PL1",
                            "snippet": {"channelId": "UC1", "title": "Esenin", "description": "Author"},
                            "status": {"privacyStatus": "public"},
                            "contentDetails": {"itemCount": 1},
                        }
                    ]
                },
            )
        if resource == "playlistItems" and params.get("playlistId") == "PL1":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "PLI1",
                            "snippet": {"position": 0},
                            "contentDetails": {"videoId": "VID1"},
                        }
                    ]
                },
            )
        return httpx.Response(404, json={"error": {"message": "unexpected request"}})

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    return YouTubeApiClient(
        client_config=config,
        token_store=store,
        account_alias="default",
        http_client=http_client,
        api_base_url="https://example.test/youtube/v3",
    )


def test_complete_inventory_package(tmp_path: Path) -> None:
    client = _client(tmp_path)
    package = YouTubeInventoryService(client).build_audit_package("UC1")
    assert package.channel.title == "Legendary Poet"
    assert len(package.videos) == 1
    assert package.videos[0].duration_seconds == 258
    assert package.videos[0].revision.startswith("sha256:")
    assert len(package.collections) == 1
    assert len(package.memberships) == 1
    assert package.memberships[0].membership_id == "PLI1"
    assert package.metadata["read_only"] is True


def test_safe_read_retries_transient_http_and_reports_attempts(tmp_path: Path) -> None:
    store = TokenStore(tmp_path)
    store.save_token(
        "default",
        OAuthToken(
            access_token="access",
            refresh_token="refresh",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        ),
    )
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, text="temporary")
        return httpx.Response(200, json={"items": []})

    from video_channel_manager.platforms.http import RetryPolicy

    client = YouTubeApiClient(
        client_config=InstalledClientConfig(client_id="id", client_secret="secret"),
        token_store=store,
        account_alias="default",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        api_base_url="https://example.test/youtube/v3",
        retry_policy=RetryPolicy(max_attempts=2, base_delay_seconds=0.25, jitter_seconds=0.0),
        sleep=sleeps.append,
    )

    assert client._get("channels", params={"part": "snippet", "mine": "true"}) == {"items": []}
    assert calls == 2
    assert sleeps == [0.25]


def test_uploads_playlist_id_is_cached_for_client_lifecycle(tmp_path: Path) -> None:
    store = TokenStore(tmp_path)
    store.save_token(
        "default",
        OAuthToken(
            access_token="access",
            refresh_token="refresh",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        ),
    )
    channel_lookups = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal channel_lookups
        resource = request.url.path.rsplit("/", 1)[-1]
        if resource == "channels":
            channel_lookups += 1
            return httpx.Response(
                200,
                json={"items": [{"id": "UC1", "contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]},
            )
        if resource == "playlistItems":
            return httpx.Response(200, json={"items": []})
        raise AssertionError(request.url)

    client = YouTubeApiClient(
        client_config=InstalledClientConfig(client_id="id", client_secret="secret"),
        token_store=store,
        account_alias="default",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        api_base_url="https://example.test/youtube/v3",
    )

    assert client.list_videos("UC1") == []
    assert client.list_videos("UC1") == []
    assert channel_lookups == 1
