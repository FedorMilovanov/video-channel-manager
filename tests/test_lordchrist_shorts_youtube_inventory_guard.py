from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from video_channel_manager.platforms.youtube.client import YouTubeApiClient, YouTubeApiError
from video_channel_manager.platforms.youtube.models import InstalledClientConfig, OAuthToken
from video_channel_manager.platforms.youtube.store import TokenStore


def test_owner_upload_inventory_fails_closed_when_videos_list_omits_an_upload_id(tmp_path: Path) -> None:
    store = TokenStore(tmp_path)
    store.save_token(
        "default",
        OAuthToken(
            access_token="access",
            refresh_token="refresh",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        ),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        resource = request.url.path.rsplit("/", 1)[-1]
        params = request.url.params
        if resource == "channels":
            return httpx.Response(
                200,
                json={"items": [{"id": "UC1", "contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]},
            )
        if resource == "playlistItems" and params.get("playlistId") == "UU1":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {"contentDetails": {"videoId": "VID1"}},
                        {"contentDetails": {"videoId": "VID2"}},
                    ]
                },
            )
        if resource == "videos":
            assert params.get("id") == "VID1,VID2"
            assert "fileDetails" in params.get("part", "")
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "VID1",
                            "snippet": {"title": "Only one returned", "publishedAt": "2026-08-20T10:00:00Z"},
                            "contentDetails": {"duration": "PT1M"},
                            "status": {"privacyStatus": "public"},
                            "fileDetails": {
                                "durationMs": "60000",
                                "creationTime": "2026-08-20T09:00:00Z",
                                "videoStreams": [{"widthPixels": 1080, "heightPixels": 1920}],
                            },
                        }
                    ]
                },
            )
        raise AssertionError(request.url)

    client = YouTubeApiClient(
        client_config=InstalledClientConfig(client_id="id", client_secret="secret"),
        token_store=store,
        account_alias="default",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        api_base_url="https://example.test/youtube/v3",
    )

    with pytest.raises(YouTubeApiError, match=r"omitted upload IDs.*VID2"):
        client.list_videos("UC1")
