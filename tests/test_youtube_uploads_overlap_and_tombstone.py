"""Owner-only YouTube inventory must distinguish page overlap from real conflicts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from video_channel_manager.platforms.youtube.client import YouTubeApiClient, YouTubeApiError
from video_channel_manager.platforms.youtube.models import InstalledClientConfig, OAuthToken
from video_channel_manager.platforms.youtube.store import TokenStore


def _live_item(video_id: str, item_id: str) -> dict:
    return {"id": item_id, "contentDetails": {"videoId": video_id}}


def _deleted_item(video_id: str, item_id: str, *, exact: bool = True) -> dict:
    return {
        "id": item_id,
        "contentDetails": {"videoId": video_id},
        "snippet": {
            "title": "Deleted video",
            "description": "This video is unavailable." if exact else "temporarily unavailable",
        },
        "status": {"privacyStatus": "privacyStatusUnspecified"},
    }


def _setup(tmp_path: Path, pages: dict[str, dict], returned_ids: set[str]) -> tuple[YouTubeApiClient, list[str]]:
    store = TokenStore(tmp_path)
    store.save_token(
        "default",
        OAuthToken(
            access_token="access",
            refresh_token="refresh",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        ),
    )
    video_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET", "Inventory must not perform provider mutations"
        resource = request.url.path.rsplit("/", 1)[-1]
        params = request.url.params
        if resource == "channels":
            return httpx.Response(
                200,
                json={"items": [{"id": "UC1", "contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]},
            )
        if resource == "playlistItems":
            assert params["part"] == "id,snippet,contentDetails,status"
            return httpx.Response(200, json=pages[str(params.get("pageToken", ""))])
        if resource == "videos":
            assert "fileDetails" in params["part"]
            batch = params["id"].split(",")
            video_requests.append(",".join(batch))
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": video_id,
                            "snippet": {
                                "title": "Original " + video_id,
                                "publishedAt": "2026-01-01T00:00:00Z",
                                "channelId": "UC1",
                            },
                            "contentDetails": {"duration": "PT30S"},
                            "status": {"privacyStatus": "public"},
                        }
                        for video_id in batch
                        if video_id in returned_ids
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
    return client, video_requests


def test_overlap_of_exact_same_playlist_item_is_not_second_video(tmp_path: Path) -> None:
    pages = {
        "": {
            "items": [_live_item("VID1", "PLI1"), _live_item("VID2", "PLI2")],
            "nextPageToken": "NEXT",
        },
        "NEXT": {
            "items": [_live_item("VID2", "PLI2"), _live_item("VID3", "PLI3")],
        },
    }
    client, requests = _setup(tmp_path, pages, {"VID1", "VID2", "VID3"})
    records = client.list_videos("UC1")
    assert [v.ref.remote_id for v in records] == ["VID1", "VID2", "VID3"]
    assert requests == ["VID1,VID2,VID3"]


def test_confirmed_deleted_upload_is_ignored_only_after_owner_videos_list_omits_it(tmp_path: Path) -> None:
    pages = {"": {"items": [_live_item("LIVE", "PLI1"), _deleted_item("DELETED", "PLI2")]}}
    client, requests = _setup(tmp_path, pages, {"LIVE"})
    assert [v.ref.remote_id for v in client.list_videos("UC1")] == ["LIVE"]
    assert requests == ["LIVE,DELETED"]


def test_unconfirmed_deleted_marker_must_still_fail_closed(tmp_path: Path) -> None:
    pages = {"": {"items": [_live_item("LIVE", "PLI1"), _deleted_item("MISSING", "PLI2", exact=False)]}}
    client, _ = _setup(tmp_path, pages, {"LIVE"})
    with pytest.raises(YouTubeApiError, match="omitted upload IDs.*MISSING"):
        client.list_videos("UC1")


def test_repeated_video_id_bound_to_different_playlist_item_ids_is_blocked(tmp_path: Path) -> None:
    pages = {"": {"items": [_live_item("VID1", "PLI1"), _live_item("VID1", "PLI2")]}}
    client, requests = _setup(tmp_path, pages, {"VID1"})
    with pytest.raises(YouTubeApiError, match="repeated video IDs"):
        client.list_videos("UC1")
    assert requests == []


def test_reused_playlist_item_id_with_different_video_ids_is_blocked(tmp_path: Path) -> None:
    pages = {"": {"items": [_live_item("VID1", "PLI1"), _live_item("VID2", "PLI1")]}}
    client, requests = _setup(tmp_path, pages, {"VID1", "VID2"})
    with pytest.raises(YouTubeApiError, match="playlist item ID bound to multiple videos"):
        client.list_videos("UC1")
    assert requests == []


def test_missing_unmarked_upload_remains_fail_closed(tmp_path: Path) -> None:
    pages = {"": {"items": [_live_item("VID1", "PLI1"), _live_item("MISSING", "PLI2")]}}
    client, requests = _setup(tmp_path, pages, {"VID1"})
    with pytest.raises(YouTubeApiError, match="omitted upload IDs.*MISSING"):
        client.list_videos("UC1")
    assert requests == ["VID1,MISSING"]


def test_deleted_playlist_text_does_not_hide_actual_live_video(tmp_path: Path) -> None:
    pages = {"": {"items": [_deleted_item("VID1", "PLI1")]}}
    client, requests = _setup(tmp_path, pages, {"VID1"})
    assert [v.ref.remote_id for v in client.list_videos("UC1")] == ["VID1"]
    assert requests == ["VID1"]
