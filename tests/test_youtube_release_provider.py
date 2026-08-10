from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

import video_channel_manager.youtube_release_provider as provider_module
from video_channel_manager.platforms.youtube.models import InstalledClientConfig, OAuthToken
from video_channel_manager.platforms.youtube.oauth import YOUTUBE_FORCE_SSL_SCOPE, YOUTUBE_READONLY_SCOPE
from video_channel_manager.platforms.youtube.store import TokenStore
from video_channel_manager.youtube_release_provider import (
    YouTubeReleaseProvider,
    YouTubeReleaseProviderError,
)

SESSION = "https://www.googleapis.com/upload/youtube/v3/videos?upload_id=abc123"


def _provider(
    tmp_path: Path,
    handler,
    *,
    write_scope: bool = True,
) -> YouTubeReleaseProvider:
    store = TokenStore(tmp_path / "data")
    scopes = [YOUTUBE_READONLY_SCOPE]
    if write_scope:
        scopes.append(YOUTUBE_FORCE_SSL_SCOPE)
    store.save_token(
        "legendary-poet",
        OAuthToken(
            access_token="test-token",
            scopes=scopes,
            expires_at=datetime.now(UTC) + timedelta(hours=2),
        ),
    )
    config = InstalledClientConfig(client_id="client", client_secret="secret")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return YouTubeReleaseProvider(
        client_config=config,
        token_store=store,
        account_alias="legendary-poet",
        http_client=client,
        sleep=lambda _seconds: None,
        jitter=lambda: 0.0,
    )


def test_start_upload_session_persists_only_valid_google_location(tmp_path: Path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.method == "POST"
        assert request.url.params["uploadType"] == "resumable"
        return httpx.Response(200, headers={"Location": SESSION}, request=request)

    provider = _provider(tmp_path, handler)
    try:
        result = provider.start_upload_session(
            snippet={"title": "Black Man"},
            status={"privacyStatus": "private"},
            media_size_bytes=100,
            media_mime_type="video/mp4",
        )
    finally:
        provider.close()
    assert calls == 1
    assert result.provider_effect == "verified"
    assert result.runtime["session_url"] == SESSION
    assert result.runtime["session_url_sha256"].startswith("sha256:")


def test_start_upload_session_missing_location_is_ambiguous(tmp_path: Path) -> None:
    provider = _provider(
        tmp_path,
        lambda request: httpx.Response(200, json={}, request=request),
    )
    try:
        result = provider.start_upload_session(
            snippet={"title": "Black Man"},
            status={"privacyStatus": "private"},
            media_size_bytes=100,
            media_mime_type="video/mp4",
        )
    finally:
        provider.close()
    assert result.provider_effect == "may_exist"


def test_start_upload_session_rejects_non_google_location(tmp_path: Path) -> None:
    provider = _provider(
        tmp_path,
        lambda request: httpx.Response(
            200,
            headers={"Location": "https://evil.example/upload/youtube/v3/videos?x=1"},
            request=request,
        ),
    )
    try:
        result = provider.start_upload_session(
            snippet={"title": "Black Man"},
            status={"privacyStatus": "private"},
            media_size_bytes=100,
            media_mime_type="video/mp4",
        )
    finally:
        provider.close()
    assert result.provider_effect == "may_exist"
    assert "allowed Google API host" in result.evidence["reason"]


def test_mutation_read_timeout_is_may_exist_and_not_retried(tmp_path: Path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("unknown outcome", request=request)

    provider = _provider(tmp_path, handler)
    try:
        result = provider.start_upload_session(
            snippet={"title": "Black Man"},
            status={"privacyStatus": "private"},
            media_size_bytes=100,
            media_mime_type="video/mp4",
        )
    finally:
        provider.close()
    assert calls == 1
    assert result.provider_effect == "may_exist"
    assert result.evidence["known_no_dispatch"] is False


def test_mutation_connect_error_is_confirmed_absent_and_not_retried(tmp_path: Path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("never connected", request=request)

    provider = _provider(tmp_path, handler)
    try:
        result = provider.start_upload_session(
            snippet={"title": "Black Man"},
            status={"privacyStatus": "private"},
            media_size_bytes=100,
            media_mime_type="video/mp4",
        )
    finally:
        provider.close()
    assert calls == 1
    assert result.provider_effect == "confirmed_absent"
    assert result.evidence["known_no_dispatch"] is True


def test_write_requires_force_ssl_scope_before_http(tmp_path: Path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, request=request)

    provider = _provider(tmp_path, handler, write_scope=False)
    try:
        with pytest.raises(YouTubeReleaseProviderError, match="read-only"):
            provider.start_upload_session(
                snippet={"title": "Black Man"},
                status={"privacyStatus": "private"},
                media_size_bytes=100,
                media_mime_type="video/mp4",
            )
    finally:
        provider.close()
    assert calls == 0


def test_upload_308_proves_incomplete_and_exact_next_offset(tmp_path: Path) -> None:
    media = tmp_path / "video.mp4"
    media.write_bytes(b"0123456789")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["content-range"] == "bytes 0-9/10"
        return httpx.Response(308, headers={"Range": "bytes=0-4"}, request=request)

    provider = _provider(tmp_path, handler)
    try:
        result = provider.upload_media(
            session_url=SESSION,
            media_path=media,
            media_size_bytes=10,
            media_mime_type="video/mp4",
            offset=0,
        )
    finally:
        provider.close()
    assert result.provider_effect == "confirmed_absent"
    assert result.runtime["next_offset"] == 5
    assert result.runtime["resume_requires_status_query"] is False


def test_upload_invalid_308_range_remains_ambiguous(tmp_path: Path) -> None:
    media = tmp_path / "video.mp4"
    media.write_bytes(b"0123456789")
    provider = _provider(
        tmp_path,
        lambda request: httpx.Response(308, headers={"Range": "garbage"}, request=request),
    )
    try:
        result = provider.upload_media(
            session_url=SESSION,
            media_path=media,
            media_size_bytes=10,
            media_mime_type="video/mp4",
            offset=0,
        )
    finally:
        provider.close()
    assert result.provider_effect == "may_exist"
    assert result.runtime["resume_requires_status_query"] is True


def test_upload_completion_requires_exact_video_id(tmp_path: Path) -> None:
    media = tmp_path / "video.mp4"
    media.write_bytes(b"0123456789")
    provider = _provider(
        tmp_path,
        lambda request: httpx.Response(201, json={"id": "video123"}, request=request),
    )
    try:
        result = provider.upload_media(
            session_url=SESSION,
            media_path=media,
            media_size_bytes=10,
            media_mime_type="video/mp4",
            offset=0,
        )
    finally:
        provider.close()
    assert result.provider_effect == "verified"
    assert result.remote_id == "video123"
    assert result.runtime["next_offset"] == 10


def test_upload_success_without_video_id_is_may_exist(tmp_path: Path) -> None:
    media = tmp_path / "video.mp4"
    media.write_bytes(b"0123456789")
    provider = _provider(
        tmp_path,
        lambda request: httpx.Response(200, json={}, request=request),
    )
    try:
        result = provider.upload_media(
            session_url=SESSION,
            media_path=media,
            media_size_bytes=10,
            media_mime_type="video/mp4",
            offset=0,
        )
    finally:
        provider.close()
    assert result.provider_effect == "may_exist"
    assert result.runtime["resume_requires_status_query"] is True


def test_upload_rejects_invalid_offset_before_http(tmp_path: Path) -> None:
    media = tmp_path / "video.mp4"
    media.write_bytes(b"0123456789")
    provider = _provider(
        tmp_path,
        lambda request: pytest.fail("HTTP must not be called"),
    )
    try:
        with pytest.raises(YouTubeReleaseProviderError, match="offset"):
            provider.upload_media(
                session_url=SESSION,
                media_path=media,
                media_size_bytes=10,
                media_mime_type="video/mp4",
                offset=10,
            )
    finally:
        provider.close()


def test_status_query_308_returns_server_next_offset(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["content-range"] == "bytes */10"
        assert request.headers["content-length"] == "0"
        return httpx.Response(308, headers={"Range": "bytes=0-6"}, request=request)

    provider = _provider(tmp_path, handler)
    try:
        result = provider.query_upload_status(session_url=SESSION, media_size_bytes=10)
    finally:
        provider.close()
    assert result.provider_effect == "confirmed_absent"
    assert result.runtime["next_offset"] == 7


def test_status_query_can_prove_completed_video(tmp_path: Path) -> None:
    provider = _provider(
        tmp_path,
        lambda request: httpx.Response(200, json={"id": "video123"}, request=request),
    )
    try:
        result = provider.query_upload_status(session_url=SESSION, media_size_bytes=10)
    finally:
        provider.close()
    assert result.provider_effect == "verified"
    assert result.remote_id == "video123"


def test_playlist_readback_follows_all_pages(tmp_path: Path) -> None:
    calls: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        token = request.url.params.get("pageToken")
        calls.append(token)
        if token is None:
            return httpx.Response(
                200,
                json={
                    "items": [{"contentDetails": {"videoId": "other"}}],
                    "nextPageToken": "page-2",
                },
                request=request,
            )
        return httpx.Response(
            200,
            json={"items": [{"contentDetails": {"videoId": "video123"}}]},
            request=request,
        )

    provider = _provider(tmp_path, handler)
    try:
        assert provider.playlist_contains_video("PL-one", "video123") is True
    finally:
        provider.close()
    assert calls == [None, "page-2"]


def test_playlist_missing_after_full_pagination_returns_false(tmp_path: Path) -> None:
    provider = _provider(
        tmp_path,
        lambda request: httpx.Response(
            200,
            json={"items": [{"contentDetails": {"videoId": "other"}}]},
            request=request,
        ),
    )
    try:
        assert provider.playlist_contains_video("PL-one", "video123") is False
    finally:
        provider.close()


def test_insert_playlist_item_persists_returned_membership_id_but_waits_for_readback(
    tmp_path: Path,
) -> None:
    provider = _provider(
        tmp_path,
        lambda request: httpx.Response(200, json={"id": "membership-1"}, request=request),
    )
    try:
        result = provider.insert_playlist_item(playlist_id="PL-one", video_id="video123")
    finally:
        provider.close()
    assert result.provider_effect == "may_exist"
    assert result.remote_id == "membership-1"
    assert result.evidence["accepted_response"] is True


def test_metadata_update_accepted_response_stays_may_exist_until_readback(tmp_path: Path) -> None:
    provider = _provider(
        tmp_path,
        lambda request: httpx.Response(200, json={"id": "video123"}, request=request),
    )
    try:
        result = provider.update_metadata_status(
            video_id="video123",
            snippet={"title": "Black Man"},
            status={"privacyStatus": "private"},
        )
    finally:
        provider.close()
    assert result.provider_effect == "may_exist"
    assert result.runtime["accepted_response"] is True


def test_visibility_update_accepted_response_stays_may_exist_until_readback(tmp_path: Path) -> None:
    provider = _provider(
        tmp_path,
        lambda request: httpx.Response(200, json={"id": "video123"}, request=request),
    )
    try:
        result = provider.update_visibility(
            video_id="video123",
            status={"privacyStatus": "public"},
        )
    finally:
        provider.close()
    assert result.provider_effect == "may_exist"
    assert result.evidence["accepted_response"] is True


def test_thumbnail_valid_json_receipt_is_verified(tmp_path: Path) -> None:
    image = tmp_path / "cover.jpg"
    image.write_bytes(b"image")
    provider = _provider(
        tmp_path,
        lambda request: httpx.Response(200, json={"items": [{"url": "x"}]}, request=request),
    )
    try:
        result = provider.set_thumbnail(
            video_id="video123",
            thumbnail_path=image,
            mime_type="image/jpeg",
        )
    finally:
        provider.close()
    assert result.provider_effect == "verified"
    assert result.remote_id == "video123"


def test_thumbnail_invalid_json_remains_ambiguous(tmp_path: Path) -> None:
    image = tmp_path / "cover.jpg"
    image.write_bytes(b"image")
    provider = _provider(
        tmp_path,
        lambda request: httpx.Response(200, text="not-json", request=request),
    )
    try:
        result = provider.set_thumbnail(
            video_id="video123",
            thumbnail_path=image,
            mime_type="image/jpeg",
        )
    finally:
        provider.close()
    assert result.provider_effect == "may_exist"


def test_read_video_requires_exact_single_id(tmp_path: Path) -> None:
    provider = _provider(
        tmp_path,
        lambda request: httpx.Response(200, json={"items": []}, request=request),
    )
    try:
        with pytest.raises(YouTubeReleaseProviderError, match="not found"):
            provider.read_video("video123")
    finally:
        provider.close()


def test_top_level_comment_reuses_repository_writer(monkeypatch, tmp_path: Path) -> None:
    class FakeWriter:
        def __init__(self, **kwargs) -> None:
            assert kwargs["account_alias"] == "legendary-poet"

        def create_top_level_comment(self, **kwargs):
            assert kwargs["video_id"] == "video123"
            return type(
                "Snapshot",
                (),
                {
                    "thread_id": "thread-1",
                    "comment_id": "comment-1",
                    "text_sha256": "sha256:" + "a" * 64,
                    "channel_id": "UC-78ys2S3cQ3lpqgXfo-SvQ",
                },
            )()

    monkeypatch.setattr(provider_module, "YouTubeCommentWriter", FakeWriter)
    provider = _provider(
        tmp_path,
        lambda request: pytest.fail("Fake comment writer should own provider behavior"),
    )
    try:
        result = provider.create_top_level_comment(
            video_id="video123",
            expected_channel_id="UC-78ys2S3cQ3lpqgXfo-SvQ",
            text="Pinned later manually",
        )
    finally:
        provider.close()
    assert result.provider_effect == "verified"
    assert result.remote_id == "comment-1"
