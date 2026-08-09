from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from video_channel_manager.platforms.youtube.client import YouTubeApiClient, YouTubeApiError
from video_channel_manager.platforms.youtube.models import InstalledClientConfig, OAuthToken
from video_channel_manager.platforms.youtube.store import TokenStore


def _client(tmp_path: Path, handler) -> YouTubeApiClient:
    store = TokenStore(tmp_path)
    store.save_token(
        "legendary-poet",
        OAuthToken(
            access_token="access",
            refresh_token="refresh",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        ),
    )
    return YouTubeApiClient(
        client_config=InstalledClientConfig(client_id="id", client_secret="secret"),
        token_store=store,
        account_alias="legendary-poet",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        api_base_url="https://example.test/youtube/v3",
    )


def test_get_video_reads_one_exact_id_and_preserves_remote_channel(tmp_path: Path) -> None:
    seen_ids: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_ids.append(str(request.url.params.get("id")))
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "VID1",
                        "snippet": {
                            "channelId": "UC-78ys2S3cQ3lpqgXfo-SvQ",
                            "title": "Exact target",
                            "description": "Description",
                            "publishedAt": "2026-08-09T12:00:00Z",
                            "tags": ["one", "two"],
                        },
                        "contentDetails": {"duration": "PT1M2S"},
                        "status": {"privacyStatus": "public"},
                    }
                ]
            },
        )

    client = _client(tmp_path, handler)
    record = client.get_video("VID1")
    assert seen_ids == ["VID1"]
    assert record.ref.remote_id == "VID1"
    assert record.ref.channel_id == "UC-78ys2S3cQ3lpqgXfo-SvQ"
    assert record.duration_seconds == 62
    assert record.privacy_status == "public"
    assert record.revision.startswith("sha256:")


def test_get_video_rejects_empty_or_ambiguous_provider_result(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json={"items": []})

    client = _client(tmp_path, handler)
    with pytest.raises(YouTubeApiError, match="not found or inaccessible"):
        client.get_video("VID1")
    with pytest.raises(YouTubeApiError, match="cannot be blank"):
        client.get_video("   ")
