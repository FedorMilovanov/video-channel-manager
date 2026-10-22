"""Fault-stage proofs for the Instagram and YouTube-release mutation boundaries.

Before this module the register covered VK, Telegram, the Wave engine and the PowerShell operator
boundary. Instagram publish/upload and the YouTube release uploader dispatched provider writes
outside any static inventory: Instagram through two private helpers with no classification at all,
and the YouTube release provider through a `_mutation_request` helper whose resource was a
parameter, so the scanner could not see a resource name and therefore saw nothing.

Both now have one classified dispatch point per effect, and this module proves the three stages
the register requires of every boundary:

* `before_dispatch` — the call is refused before a single HTTP request exists;
* `after_dispatch_before_response` — a lost response is ambiguous, one attempt, never retried;
* `after_response_before_commit` — a response is classified by evidence and never assumed to mean
  success.

Every test counts real transport attempts through `httpx.MockTransport`, so "one attempt" is an
observation, not a reading of the source.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import httpx
import pytest

from video_channel_manager.instagram.local_resumable import (
    InstagramLocalPublishManifest,
    InstagramResumableProviderClient,
)
from video_channel_manager.instagram.production import (
    InstagramConfigurationError,
    InstagramProviderClient,
    InstagramProviderError,
    InstagramPublishManifest,
    InstagramRuntimeConfig,
    InstagramTransportError,
)
from video_channel_manager.platforms.youtube.models import InstalledClientConfig, OAuthToken
from video_channel_manager.platforms.youtube.oauth import YOUTUBE_FORCE_SSL_SCOPE, YOUTUBE_READONLY_SCOPE
from video_channel_manager.platforms.youtube.store import TokenStore
from video_channel_manager.youtube_release_provider import YouTubeReleaseProvider, YouTubeReleaseProviderError

ACCOUNT_ID = "17841400000000000"
MEDIA_BYTES = b"verified reel bytes"
MEDIA_SHA256 = f"sha256:{hashlib.sha256(MEDIA_BYTES).hexdigest()}"
MEDIA_URL = "https://cdn.example.com/reel.mp4"
UPLOAD_URI = "https://rupload.facebook.com/ig-api-upload/v25.0/container-1"
SESSION = "https://www.googleapis.com/upload/youtube/v3/videos?upload_id=abc123"


def _instagram_config(*, login_mode: str = "instagram") -> InstagramRuntimeConfig:
    return InstagramRuntimeConfig(
        login_mode=login_mode,  # type: ignore[arg-type]
        graph_host="https://graph.facebook.com" if login_mode == "facebook" else "https://graph.instagram.com",
        api_version="v25.0",
        account_id=ACCOUNT_ID,
        expected_username="example_creator",
        access_token="test-token",
        writes_enabled=True,
        media_allowed_hosts=("cdn.example.com",),
        timeout_seconds=1.0,
        poll_interval_seconds=0.0,
        poll_attempts=1,
    )


def _reel_manifest() -> InstagramPublishManifest:
    return InstagramPublishManifest(
        publication_key="fault.stage.reel.001",
        account_id=ACCOUNT_ID,
        video_url=MEDIA_URL,
        media_sha256=MEDIA_SHA256,
        media_size_bytes=len(MEDIA_BYTES),
        media_content_type="video/mp4",
        caption="Caption",
    )


def _local_manifest() -> InstagramLocalPublishManifest:
    return InstagramLocalPublishManifest(
        publication_key="fault.stage.local.001",
        account_id=ACCOUNT_ID,
        media_sha256=MEDIA_SHA256,
        media_size_bytes=len(MEDIA_BYTES),
        caption="Caption",
    )


def _instagram_client(
    *, login_mode: str, handler: Callable[[httpx.Request], httpx.Response]
) -> tuple[InstagramProviderClient, list[httpx.Request]]:
    """A client over a counting transport, so an attempt is observed rather than inferred."""

    requests: list[httpx.Request] = []

    def counting(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    transport = httpx.MockTransport(counting)
    client_class = InstagramResumableProviderClient if login_mode == "facebook" else InstagramProviderClient
    client = client_class(
        _instagram_config(login_mode=login_mode),
        client=httpx.Client(transport=transport),
        media_client=httpx.Client(transport=transport),
    )
    return client, requests


# --------------------------------------------------------------------------------------------------
# Instagram boundaries
# --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        pytest.param(lambda client: client.create_reel_container(_reel_manifest()), id="POST:media"),
        pytest.param(lambda client: client.publish_container("container-1"), id="POST:media_publish"),
    ],
)
def test_instagram_unclassified_graph_write_is_refused_before_dispatch(call: Callable[[Any], Any]) -> None:
    """The choke point itself refuses a write that does not name its provider resource."""

    client, requests = _instagram_client(
        login_mode="instagram",
        handler=lambda request: httpx.Response(200, json={"id": "x"}, request=request),
    )
    try:
        with pytest.raises(InstagramConfigurationError, match="must declare an explicit provider resource"):
            client._request("POST", f"{ACCOUNT_ID}/media")
        assert requests == []
    finally:
        client.close()


@pytest.mark.parametrize(
    ("call", "exception"),
    [
        pytest.param(
            lambda client: client.create_reel_container(_reel_manifest()), InstagramTransportError, id="POST:media"
        ),
        pytest.param(
            lambda client: client.publish_container("container-1"), InstagramTransportError, id="POST:media_publish"
        ),
    ],
)
def test_instagram_lost_graph_response_is_one_ambiguous_attempt(
    call: Callable[[Any], Any], exception: type[Exception]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("no response", request=request)

    client, requests = _instagram_client(login_mode="instagram", handler=handler)
    try:
        with pytest.raises(exception):
            call(client)
        assert len(requests) == 1, "a lost response must not be retried"
    finally:
        client.close()


@pytest.mark.parametrize(
    "call",
    [
        pytest.param(lambda client: client.create_reel_container(_reel_manifest()), id="POST:media"),
        pytest.param(lambda client: client.publish_container("container-1"), id="POST:media_publish"),
    ],
)
def test_instagram_server_error_is_reported_and_never_means_success(call: Callable[[Any], Any]) -> None:
    client, requests = _instagram_client(
        login_mode="instagram",
        handler=lambda request: httpx.Response(500, json={"error": {"message": "boom"}}, request=request),
    )
    try:
        with pytest.raises(InstagramProviderError, match="boom"):
            call(client)
        assert len(requests) == 1
    finally:
        client.close()


def test_instagram_resumable_container_lost_response_is_one_ambiguous_attempt() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("no response", request=request)

    client, requests = _instagram_client(login_mode="facebook", handler=handler)
    try:
        with pytest.raises(InstagramTransportError):
            client.create_resumable_reel_container(_local_manifest())  # type: ignore[attr-defined]
        assert len(requests) == 1
    finally:
        client.close()


def test_instagram_resumable_container_requires_supported_mode_before_dispatch() -> None:
    """The local resumable contour is bound to the reviewed Facebook Login mode."""

    requests: list[httpx.Request] = []
    transport = httpx.MockTransport(
        lambda request: (requests.append(request), httpx.Response(200, json={"id": "x"}, request=request))[1]
    )
    # An Instagram-Login runtime on the resumable client: the exact misconfiguration the gate exists for.
    client = InstagramResumableProviderClient(
        _instagram_config(login_mode="instagram"),
        client=httpx.Client(transport=transport),
        media_client=httpx.Client(transport=transport),
    )
    try:
        with pytest.raises(InstagramConfigurationError, match="Facebook Login"):
            client.create_resumable_reel_container(_local_manifest())  # type: ignore[attr-defined]
        assert requests == []
    finally:
        client.close()


def test_instagram_resumable_container_response_without_uri_is_not_a_container() -> None:
    client, requests = _instagram_client(
        login_mode="facebook",
        handler=lambda request: httpx.Response(200, json={"id": "container-1"}, request=request),
    )
    try:
        with pytest.raises(InstagramProviderError, match="upload URI"):
            client.create_resumable_reel_container(_local_manifest())  # type: ignore[attr-defined]
        assert len(requests) == 1
    finally:
        client.close()


def test_instagram_resumable_binary_upload_refuses_a_foreign_upload_uri_before_dispatch() -> None:
    client, requests = _instagram_client(
        login_mode="facebook",
        handler=lambda request: httpx.Response(200, json={"success": True}, request=request),
    )
    try:
        with pytest.raises(InstagramProviderError, match="rupload.facebook.com"):
            client.upload_local_video(  # type: ignore[attr-defined]
                "https://evil.example.com/upload", _BytesStream(MEDIA_BYTES), file_size=len(MEDIA_BYTES)
            )
        assert requests == []
    finally:
        client.close()


def test_instagram_resumable_binary_upload_lost_response_is_one_ambiguous_attempt() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("no response", request=request)

    client, requests = _instagram_client(login_mode="facebook", handler=handler)
    try:
        with pytest.raises(InstagramTransportError, match="resumable binary upload"):
            client.upload_local_video(  # type: ignore[attr-defined]
                UPLOAD_URI, _BytesStream(MEDIA_BYTES), file_size=len(MEDIA_BYTES)
            )
        assert len(requests) == 1
    finally:
        client.close()


def test_instagram_resumable_binary_upload_rejection_is_not_a_success() -> None:
    client, requests = _instagram_client(
        login_mode="facebook",
        handler=lambda request: httpx.Response(
            400, json={"debug_info": {"message": "bad bytes"}}, request=request
        ),
    )
    try:
        with pytest.raises(InstagramProviderError):
            client.upload_local_video(  # type: ignore[attr-defined]
                UPLOAD_URI, _BytesStream(MEDIA_BYTES), file_size=len(MEDIA_BYTES)
            )
        assert len(requests) == 1
    finally:
        client.close()


def test_instagram_resumable_binary_upload_sends_exactly_one_body_of_the_declared_size() -> None:
    seen: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.content)
        return httpx.Response(200, json={"success": True}, request=request)

    client, requests = _instagram_client(login_mode="facebook", handler=handler)
    try:
        client.upload_local_video(UPLOAD_URI, _BytesStream(MEDIA_BYTES), file_size=len(MEDIA_BYTES))  # type: ignore[attr-defined]
        assert len(requests) == 1
        assert seen == [MEDIA_BYTES]
    finally:
        client.close()


class _BytesStream:
    """A binary stream over exact bytes, standing in for the local MP4 file."""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload


# --------------------------------------------------------------------------------------------------
# YouTube release boundaries
# --------------------------------------------------------------------------------------------------

_THUMBNAIL = b"thumbnail bytes"


def _youtube_provider(
    tmp_path: Path,
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    write_scope: bool = True,
) -> tuple[YouTubeReleaseProvider, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def counting(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    store = TokenStore(tmp_path / "data")
    scopes = [YOUTUBE_READONLY_SCOPE] + ([YOUTUBE_FORCE_SSL_SCOPE] if write_scope else [])
    store.save_token(
        "legendary-poet",
        OAuthToken(
            access_token="test-token",
            scopes=scopes,
            expires_at=datetime.now(UTC) + timedelta(hours=2),
        ),
    )
    provider = YouTubeReleaseProvider(
        client_config=InstalledClientConfig(client_id="client", client_secret="secret"),
        token_store=store,
        account_alias="legendary-poet",
        http_client=httpx.Client(transport=httpx.MockTransport(counting)),
        sleep=lambda _seconds: None,
        jitter=lambda: 0.0,
    )
    return provider, requests


def _thumbnail_file(tmp_path: Path) -> Path:
    path = tmp_path / "thumb.jpg"
    path.write_bytes(_THUMBNAIL)
    return path


def _invoke(provider: YouTubeReleaseProvider, name: str, tmp_path: Path) -> Any:
    media = tmp_path / "media.bin"
    media.write_bytes(b"x" * 10)
    calls: dict[str, Callable[[], Any]] = {
        "videos.insert.resumable-session": lambda: provider.start_upload_session(
            snippet={"title": "Black Man"},
            status={"privacyStatus": "private"},
            media_size_bytes=10,
            media_mime_type="video/mp4",
        ),
        "videos.insert.resumable-media": lambda: provider.upload_media(
            session_url=SESSION,
            media_path=media,
            media_size_bytes=10,
            media_mime_type="video/mp4",
            offset=0,
        ),
        "videos.update.metadata-status": lambda: provider.update_metadata_status(
            video_id="video-1",
            snippet={"title": "Black Man"},
            status={"privacyStatus": "private"},
        ),
        "thumbnails.set": lambda: provider.set_thumbnail(
            video_id="video-1",
            thumbnail_path=_thumbnail_file(tmp_path),
            mime_type="image/jpeg",
        ),
        "playlistItems.insert": lambda: provider.insert_playlist_item(
            playlist_id="PL-1",
            video_id="video-1",
        ),
        "videos.update.visibility": lambda: provider.update_visibility(
            video_id="video-1",
            status={"privacyStatus": "public"},
        ),
    }
    return calls[name]()


YOUTUBE_RESOURCES = (
    "videos.insert.resumable-session",
    "videos.insert.resumable-media",
    "videos.update.metadata-status",
    "thumbnails.set",
    "playlistItems.insert",
    "videos.update.visibility",
)


@pytest.mark.parametrize("resource", YOUTUBE_RESOURCES)
def test_youtube_release_write_requires_force_ssl_scope_before_dispatch(tmp_path: Path, resource: str) -> None:
    """Every boundary shares the write-scope gate, and the gate is evaluated before HTTP."""

    provider, requests = _youtube_provider(
        tmp_path,
        lambda request: httpx.Response(200, json={"id": "video-1"}, request=request),
        write_scope=False,
    )
    try:
        with pytest.raises(YouTubeReleaseProviderError, match="read-only"):
            _invoke(provider, resource, tmp_path)
        assert requests == []
    finally:
        provider.close()


@pytest.mark.parametrize("resource", YOUTUBE_RESOURCES)
def test_youtube_release_lost_response_is_may_exist_and_one_attempt(tmp_path: Path, resource: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("no response", request=request)

    provider, requests = _youtube_provider(tmp_path, handler)
    try:
        result = _invoke(provider, resource, tmp_path)
        assert result.provider_effect == "may_exist"
        assert len(requests) == 1, "an ambiguous mutation must not be retried"
    finally:
        provider.close()


@pytest.mark.parametrize("resource", YOUTUBE_RESOURCES)
def test_youtube_release_server_error_is_may_exist_and_one_attempt(tmp_path: Path, resource: str) -> None:
    provider, requests = _youtube_provider(
        tmp_path, lambda request: httpx.Response(503, text="unavailable", request=request)
    )
    try:
        result = _invoke(provider, resource, tmp_path)
        assert result.provider_effect == "may_exist"
        assert len(requests) == 1
    finally:
        provider.close()


@pytest.mark.parametrize("resource", YOUTUBE_RESOURCES)
def test_youtube_release_client_rejection_is_confirmed_absent(tmp_path: Path, resource: str) -> None:
    """A 4xx is a recorded rejection, not an unknown and not a success."""

    provider, requests = _youtube_provider(
        tmp_path, lambda request: httpx.Response(400, text="bad request", request=request)
    )
    try:
        result = _invoke(provider, resource, tmp_path)
        assert result.provider_effect == "confirmed_absent"
        assert len(requests) == 1
    finally:
        provider.close()


@pytest.mark.parametrize("resource", YOUTUBE_RESOURCES)
def test_youtube_release_connect_failure_is_confirmed_absent_before_dispatch(
    tmp_path: Path, resource: str
) -> None:
    """A connection that never opened cannot have created a provider effect."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    provider, requests = _youtube_provider(tmp_path, handler)
    try:
        result = _invoke(provider, resource, tmp_path)
        assert result.provider_effect == "confirmed_absent"
        assert result.evidence["known_no_dispatch"] is True
        assert len(requests) == 1
    finally:
        provider.close()


def test_youtube_release_status_probe_sends_no_body(tmp_path: Path) -> None:
    """The one direct verb outside the mutation helper is a zero-byte status query."""

    bodies: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(request.content)
        return httpx.Response(308, headers={"Range": "bytes=0-4"}, request=request)

    provider, requests = _youtube_provider(tmp_path, handler)
    try:
        result = provider.query_upload_status(session_url=SESSION, media_size_bytes=10)
        assert len(requests) == 1
        assert bodies == [b""], "the status probe must never upload bytes"
        assert requests[0].method == "PUT"
        assert result.runtime["next_offset"] == 5
    finally:
        provider.close()
