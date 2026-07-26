from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from video_channel_manager.platforms.youtube.comments import (
    YouTubeCommentConflictError,
    YouTubeCommentWriter,
    YouTubeCommentsDisabledError,
    comments_equivalent,
)
from video_channel_manager.platforms.youtube.models import InstalledClientConfig, OAuthToken
from video_channel_manager.platforms.youtube.oauth import YOUTUBE_FORCE_SSL_SCOPE, YOUTUBE_READONLY_SCOPE
from video_channel_manager.platforms.youtube.store import TokenStore


def _token(*scopes: str) -> OAuthToken:
    return OAuthToken(
        access_token="access",
        refresh_token="refresh",
        scopes=list(scopes),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


def _writer(tmp_path: Path, handler: httpx.MockTransport) -> YouTubeCommentWriter:
    store = TokenStore(tmp_path)
    store.save_token("account", _token(YOUTUBE_READONLY_SCOPE, YOUTUBE_FORCE_SSL_SCOPE))
    return YouTubeCommentWriter(
        client_config=InstalledClientConfig(client_id="client", client_secret="secret"),
        token_store=store,
        account_alias="account",
        http_client=httpx.Client(transport=handler),
        api_base_url="https://youtube.test",
    )


def _video() -> dict[str, Any]:
    return {
        "id": "video-1",
        "snippet": {"channelId": "channel-1", "title": "Title"},
        "status": {"privacyStatus": "public"},
    }


def _comment(comment_id: str, text: str, *, author_channel_id: str = "channel-1") -> dict[str, Any]:
    return {
        "id": comment_id,
        "snippet": {
            "channelId": "channel-1",
            "videoId": "video-1",
            "textOriginal": text,
            "authorChannelId": {"value": author_channel_id},
            "authorDisplayName": "The Legendary Poet",
            "publishedAt": "2026-07-25T12:00:00Z",
            "updatedAt": "2026-07-25T12:00:00Z",
            "moderationStatus": "published",
        },
    }


def _thread(comment_id: str, text: str, *, author_channel_id: str = "channel-1") -> dict[str, Any]:
    return {
        "id": f"thread-{comment_id}",
        "snippet": {
            "channelId": "channel-1",
            "videoId": "video-1",
            "topLevelComment": _comment(comment_id, text, author_channel_id=author_channel_id),
        },
    }


def test_list_comments_paginates_and_preserves_author_channel(tmp_path: Path) -> None:
    calls = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        assert request.url.path == "/commentThreads"
        calls += 1
        if calls == 1:
            return httpx.Response(200, json={"items": [_thread("comment-1", "One")], "nextPageToken": "next"})
        assert request.url.params["pageToken"] == "next"
        return httpx.Response(200, json={"items": [_thread("comment-2", "Two", author_channel_id="viewer-2")]})

    writer = _writer(tmp_path, httpx.MockTransport(handle))
    comments = writer.list_top_level_comments("video-1")
    assert [item.comment_id for item in comments] == ["comment-1", "comment-2"]
    assert comments[0].author_channel_id == "channel-1"
    assert comments[1].author_channel_id == "viewer-2"


def test_comments_disabled_is_classified_separately(tmp_path: Path) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "error": {
                    "message": "The video has disabled comments.",
                    "errors": [{"reason": "commentsDisabled"}],
                }
            },
        )

    writer = _writer(tmp_path, httpx.MockTransport(handle))
    with pytest.raises(YouTubeCommentsDisabledError):
        writer.list_top_level_comments("video-1")


def test_create_comment_is_verified_and_idempotent(tmp_path: Path) -> None:
    created: dict[str, Any] | None = None
    posted_bodies: list[dict[str, Any]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal created
        if request.url.path == "/videos":
            return httpx.Response(200, json={"items": [_video()]})
        if request.url.path == "/commentThreads" and request.method == "GET":
            return httpx.Response(200, json={"items": [created] if created else []})
        if request.url.path == "/commentThreads" and request.method == "POST":
            body = json.loads(request.content.decode("utf-8"))
            posted_bodies.append(body)
            text = body["snippet"]["topLevelComment"]["snippet"]["textOriginal"]
            created = _thread("comment-1", text)
            return httpx.Response(200, json=created)
        if request.url.path == "/comments":
            assert created is not None
            return httpx.Response(200, json={"items": [created["snippet"]["topLevelComment"]]})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    writer = _writer(tmp_path, httpx.MockTransport(handle))
    first = writer.create_top_level_comment(
        video_id="video-1",
        expected_channel_id="channel-1",
        text="Первая строка.  \n\nВторая строка.",
    )
    second = writer.create_top_level_comment(
        video_id="video-1",
        expected_channel_id="channel-1",
        text="Первая строка.\n\nВторая строка.",
    )
    assert first.comment_id == second.comment_id == "comment-1"
    assert len(posted_bodies) == 1
    assert posted_bodies[0]["snippet"]["videoId"] == "video-1"
    assert comments_equivalent(first.text, "Первая строка.\n\nВторая строка.")


def test_create_refuses_a_different_existing_channel_comment(tmp_path: Path) -> None:
    methods: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        if request.url.path == "/videos":
            return httpx.Response(200, json={"items": [_video()]})
        if request.url.path == "/commentThreads":
            return httpx.Response(200, json={"items": [_thread("comment-1", "Older channel comment")]})
        raise AssertionError(request.url)

    writer = _writer(tmp_path, httpx.MockTransport(handle))
    with pytest.raises(YouTubeCommentConflictError):
        writer.create_top_level_comment(
            video_id="video-1",
            expected_channel_id="channel-1",
            text="New approved comment",
        )
    assert methods == ["GET", "GET"]


def test_update_requires_exact_reviewed_before_text(tmp_path: Path) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/comments":
            return httpx.Response(200, json={"items": [_comment("comment-1", "Manually changed")]})
        raise AssertionError(request.url)

    writer = _writer(tmp_path, httpx.MockTransport(handle))
    with pytest.raises(YouTubeCommentConflictError):
        writer.update_top_level_comment(
            comment_id="comment-1",
            video_id="video-1",
            expected_channel_id="channel-1",
            expected_text="Reviewed before",
            new_text="Approved after",
        )
