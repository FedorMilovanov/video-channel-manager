from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from video_channel_manager.platforms.http import RetryPolicy
from video_channel_manager.platforms.vk.editorial_writer import VkEditorialWriter
from video_channel_manager.platforms.vk.models import VkAccessToken
from video_channel_manager.platforms.vk.store import VkTokenStore
from video_channel_manager.platforms.vk.text_writer import VkVideoTextWriter
from video_channel_manager.platforms.vk.thumbnails import VkThumbnailWriter
from video_channel_manager.platforms.vk.writer import VkVideoWriter, VkWriteError
from video_channel_manager.platforms.youtube.comments import YouTubeCommentError, YouTubeCommentWriter
from video_channel_manager.platforms.youtube.models import InstalledClientConfig, OAuthToken
from video_channel_manager.platforms.youtube.oauth import YOUTUBE_FORCE_SSL_SCOPE, YOUTUBE_READONLY_SCOPE
from video_channel_manager.platforms.youtube.store import TokenStore


def _vk_store(tmp_path: Path) -> VkTokenStore:
    store = VkTokenStore(tmp_path / "vk")
    store.save_token(
        "legendary-poet",
        VkAccessToken(access_token="secret", scopes=["video", "groups"]),
    )
    return store


def _vk_writer(
    writer_type: type[VkVideoWriter],
    tmp_path: Path,
    handler: httpx.MockTransport,
) -> VkVideoWriter:
    return writer_type(
        token_store=_vk_store(tmp_path),
        account_alias="legendary-poet",
        http_client=httpx.Client(transport=handler),
        api_base_url="https://api.example/method",
    )


def test_vk_album_create_rejects_invalid_input_before_dispatch(tmp_path: Path) -> None:
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    writer = _vk_writer(VkVideoWriter, tmp_path, httpx.MockTransport(respond))
    with pytest.raises(ValueError, match="community_id"):
        writer.create_album(community_id=0, title="Album")
    with pytest.raises(ValueError, match="blank"):
        writer.create_album(community_id=235216998, title="   ")
    assert calls == 0


def test_vk_album_add_rejects_invalid_identity_before_dispatch(tmp_path: Path) -> None:
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    writer = _vk_writer(VkVideoWriter, tmp_path, httpx.MockTransport(respond))
    with pytest.raises(ValueError, match="album_id"):
        writer.add_to_album(
            community_id=235216998,
            album_id=0,
            owner_id=-235216998,
            video_id=501,
        )
    assert calls == 0


def test_vk_album_edit_rejects_invalid_target_before_dispatch(tmp_path: Path) -> None:
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    writer = _vk_writer(VkEditorialWriter, tmp_path, httpx.MockTransport(respond))
    assert isinstance(writer, VkEditorialWriter)
    with pytest.raises(ValueError, match="album_id"):
        writer.rename_album(community_id=235216998, album_id=0, title="Album")
    with pytest.raises(ValueError, match="blank"):
        writer.rename_album(community_id=235216998, album_id=3, title="   ")
    assert calls == 0


def test_vk_video_text_conflict_stops_before_mutation_dispatch(tmp_path: Path) -> None:
    edit_calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal edit_calls
        if request.url.path.endswith("/video.get"):
            return httpx.Response(
                200,
                json={
                    "response": {
                        "count": 1,
                        "items": [
                            {
                                "owner_id": -235216998,
                                "id": 456239017,
                                "title": "Manually changed",
                                "description": "Description",
                            }
                        ],
                    }
                },
            )
        if request.url.path.endswith("/video.edit"):
            edit_calls += 1
        raise AssertionError(request.url)

    writer = _vk_writer(VkVideoTextWriter, tmp_path, httpx.MockTransport(respond))
    assert isinstance(writer, VkVideoTextWriter)
    with pytest.raises(VkWriteError, match="title no longer matches"):
        writer.replace_text_if_current(
            owner_id=-235216998,
            video_id=456239017,
            expected_title="Reviewed title",
            new_title="Approved title",
            expected_description="Description",
            new_description="Description",
            verification_delay_seconds=0,
        )
    assert edit_calls == 0


def test_vk_thumbnail_commit_rejects_invalid_payload_before_dispatch(tmp_path: Path) -> None:
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    writer = _vk_writer(VkThumbnailWriter, tmp_path, httpx.MockTransport(respond))
    assert isinstance(writer, VkThumbnailWriter)
    with pytest.raises(ValueError, match="owner_id"):
        writer.save_uploaded_thumbnail(owner_id=0, video_id=501, upload_payload={"thumb_json": "{}"})
    with pytest.raises(ValueError, match="thumb_json"):
        writer.save_uploaded_thumbnail(owner_id=-235216998, video_id=501, upload_payload={})
    assert calls == 0


def _youtube_token() -> OAuthToken:
    return OAuthToken(
        access_token="access",
        refresh_token="refresh",
        scopes=[YOUTUBE_READONLY_SCOPE, YOUTUBE_FORCE_SSL_SCOPE],
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


def _youtube_comment(comment_id: str, text: str) -> dict[str, Any]:
    return {
        "id": comment_id,
        "snippet": {
            "channelId": "channel-1",
            "videoId": "video-1",
            "textOriginal": text,
            "authorChannelId": {"value": "channel-1"},
            "authorDisplayName": "The Legendary Poet",
            "publishedAt": "2026-07-25T12:00:00Z",
            "updatedAt": "2026-07-25T12:00:00Z",
            "moderationStatus": "published",
        },
    }


def test_youtube_comment_update_timeout_is_attempted_once(tmp_path: Path) -> None:
    put_calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal put_calls
        if request.method == "GET" and request.url.path == "/comments":
            return httpx.Response(200, json={"items": [_youtube_comment("comment-1", "Reviewed before")]})
        assert request.method == "PUT"
        assert request.url.path == "/comments"
        put_calls += 1
        raise httpx.ReadTimeout("response lost after update dispatch", request=request)

    store = TokenStore(tmp_path / "youtube")
    store.save_token("account", _youtube_token())
    writer = YouTubeCommentWriter(
        client_config=InstalledClientConfig(client_id="client", client_secret="secret"),
        token_store=store,
        account_alias="account",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
        api_base_url="https://youtube.test",
        verify_delays_seconds=(0.0,),
        retry_policy=RetryPolicy(max_attempts=7),
        sleep=lambda _: None,
    )

    with pytest.raises(YouTubeCommentError, match="ambiguous_mutation"):
        writer.update_top_level_comment(
            comment_id="comment-1",
            video_id="video-1",
            expected_channel_id="channel-1",
            expected_text="Reviewed before",
            new_text="Approved after",
        )
    assert put_calls == 1
