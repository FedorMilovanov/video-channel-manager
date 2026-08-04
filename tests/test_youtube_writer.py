from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from video_channel_manager.platforms.http import RetryPolicy
from video_channel_manager.platforms.youtube import (
    InstalledClientConfig,
    OAuthToken,
    TokenStore,
    YOUTUBE_FORCE_SSL_SCOPE,
    YOUTUBE_READONLY_SCOPE,
    YouTubeDescriptionWriter,
    YouTubeRevisionConflictError,
    YouTubeWriteError,
    YouTubeWriteScopeError,
)
from video_channel_manager.platforms.youtube.writer import descriptions_equivalent


def _token(*scopes: str) -> OAuthToken:
    return OAuthToken(
        access_token="access",
        refresh_token="refresh",
        scopes=list(scopes),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


def _config() -> InstalledClientConfig:
    return InstalledClientConfig(client_id="client", client_secret="secret")


def _raw_video(description: str) -> dict[str, Any]:
    return {
        "id": "video-1",
        "etag": "etag-1",
        "snippet": {
            "channelId": "channel-1",
            "title": "Title",
            "description": description,
            "categoryId": "22",
            "tags": ["one", "two"],
            "defaultLanguage": "ru",
        },
        "contentDetails": {"duration": "PT4M"},
        "status": {"privacyStatus": "public"},
    }


def _writer(
    tmp_path: Path,
    scopes: tuple[str, ...],
    handler: httpx.MockTransport,
    *,
    verification_delays: tuple[float, ...] = (),
    retry_policy: RetryPolicy | None = None,
    sleep: Any = lambda _: None,
) -> YouTubeDescriptionWriter:
    store = TokenStore(tmp_path)
    store.save_token("account", _token(*scopes))
    client = httpx.Client(transport=handler)
    return YouTubeDescriptionWriter(
        client_config=_config(),
        token_store=store,
        account_alias="account",
        http_client=client,
        api_base_url="https://youtube.test",
        verification_delays=verification_delays,
        retry_policy=retry_policy,
        sleep=sleep,
    )


def test_read_only_token_can_preflight_description(tmp_path: Path) -> None:
    raw = _raw_video("Before")

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        return httpx.Response(200, json={"items": [raw]})

    writer = _writer(tmp_path, (YOUTUBE_READONLY_SCOPE,), httpx.MockTransport(handle))
    snapshot = writer.read_description("video-1")
    assert snapshot.channel_id == "channel-1"
    assert snapshot.description == "Before"


def test_read_only_token_cannot_write(tmp_path: Path) -> None:
    raw = _raw_video("Before")

    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": [raw]})

    writer = _writer(tmp_path, (YOUTUBE_READONLY_SCOPE,), httpx.MockTransport(handle))
    current = writer.read_description("video-1")
    with pytest.raises(YouTubeWriteScopeError):
        writer.replace_description(
            video_id="video-1",
            expected_channel_id="channel-1",
            expected_revision=current.revision,
            expected_description="Before",
            new_description="After",
        )


def test_description_conflict_stops_before_put(tmp_path: Path) -> None:
    raw = _raw_video("Changed remotely")
    methods: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        return httpx.Response(200, json={"items": [raw]})

    writer = _writer(
        tmp_path,
        (YOUTUBE_READONLY_SCOPE, YOUTUBE_FORCE_SSL_SCOPE),
        httpx.MockTransport(handle),
    )
    with pytest.raises(YouTubeRevisionConflictError):
        writer.replace_description(
            video_id="video-1",
            expected_channel_id="channel-1",
            expected_revision="sha256:stale",
            expected_description="Before",
            new_description="After",
        )
    assert methods == ["GET"]


def test_revision_drift_with_same_description_is_safe(tmp_path: Path) -> None:
    raw = _raw_video("Before")
    raw["etag"] = "server-refreshed-etag"
    methods: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal raw
        methods.append(request.method)
        if request.method == "GET":
            return httpx.Response(200, json={"items": [raw]})
        body = __import__("json").loads(request.content.decode("utf-8"))
        raw = {**raw, "snippet": {**raw["snippet"], "description": body["snippet"]["description"]}}
        return httpx.Response(200, json=raw)

    writer = _writer(
        tmp_path,
        (YOUTUBE_READONLY_SCOPE, YOUTUBE_FORCE_SSL_SCOPE),
        httpx.MockTransport(handle),
    )
    verified = writer.replace_description(
        video_id="video-1",
        expected_channel_id="channel-1",
        expected_revision="sha256:stale",
        expected_description="Before",
        new_description="After",
    )
    assert verified.description == "After"
    assert methods == ["GET", "PUT", "GET"]


def test_write_preserves_mutable_snippet_fields_and_verifies(tmp_path: Path) -> None:
    raw = _raw_video("Before")
    put_body: dict[str, Any] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal raw, put_body
        if request.method == "GET":
            return httpx.Response(200, json={"items": [raw]})
        assert request.method == "PUT"
        put_body = dict(__import__("json").loads(request.content.decode("utf-8")))
        raw = {**raw, "snippet": {**raw["snippet"], "description": put_body["snippet"]["description"]}}
        return httpx.Response(200, json=raw)

    writer = _writer(
        tmp_path,
        (YOUTUBE_READONLY_SCOPE, YOUTUBE_FORCE_SSL_SCOPE),
        httpx.MockTransport(handle),
    )
    current = writer.read_description("video-1")
    verified = writer.replace_description(
        video_id="video-1",
        expected_channel_id="channel-1",
        expected_revision=current.revision,
        expected_description="Before",
        new_description="After",
    )
    assert verified.description == "After"
    assert put_body == {
        "id": "video-1",
        "snippet": {
            "title": "Title",
            "categoryId": "22",
            "description": "After",
            "tags": ["one", "two"],
            "defaultLanguage": "ru",
        },
    }


def test_verification_accepts_youtube_invisible_character_normalization(tmp_path: Path) -> None:
    raw = _raw_video("Before")

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal raw
        if request.method == "GET":
            return httpx.Response(200, json={"items": [raw]})
        body = __import__("json").loads(request.content.decode("utf-8"))
        stored = str(body["snippet"]["description"]).replace("\ufeff", "")
        raw = {**raw, "etag": "etag-2", "snippet": {**raw["snippet"], "description": stored}}
        return httpx.Response(200, json=raw)

    writer = _writer(
        tmp_path,
        (YOUTUBE_READONLY_SCOPE, YOUTUBE_FORCE_SSL_SCOPE),
        httpx.MockTransport(handle),
    )
    current = writer.read_description("video-1")
    verified = writer.replace_description(
        video_id="video-1",
        expected_channel_id="channel-1",
        expected_revision=current.revision,
        expected_description="Before",
        new_description="После слова\ufeff невидимый разделитель.",
    )
    assert descriptions_equivalent(verified.description, "После слова\ufeff невидимый разделитель.")


def test_verification_retries_eventually_consistent_get(tmp_path: Path) -> None:
    raw = _raw_video("Before")
    stored_after = False
    post_put_reads = 0
    methods: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal raw, stored_after, post_put_reads
        methods.append(request.method)
        if request.method == "PUT":
            body = __import__("json").loads(request.content.decode("utf-8"))
            raw = {**raw, "snippet": {**raw["snippet"], "description": body["snippet"]["description"]}}
            stored_after = True
            return httpx.Response(200, json=raw)
        if stored_after:
            post_put_reads += 1
            if post_put_reads == 1:
                stale = {**raw, "snippet": {**raw["snippet"], "description": "Before"}}
                return httpx.Response(200, json={"items": [stale]})
        return httpx.Response(200, json={"items": [raw]})

    writer = _writer(
        tmp_path,
        (YOUTUBE_READONLY_SCOPE, YOUTUBE_FORCE_SSL_SCOPE),
        httpx.MockTransport(handle),
        verification_delays=(0.0, 0.0),
    )
    current = writer.read_description("video-1")
    verified = writer.replace_description(
        video_id="video-1",
        expected_channel_id="channel-1",
        expected_revision=current.revision,
        expected_description="Before",
        new_description="After",
    )
    assert verified.description == "After"
    assert methods == ["GET", "GET", "PUT", "GET", "GET"]


def test_recovery_ignores_server_revision_drift_when_after_text_is_unchanged(tmp_path: Path) -> None:
    raw = _raw_video("After")
    methods: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal raw
        methods.append(request.method)
        if request.method == "GET":
            raw = {**raw, "etag": f"etag-{len(methods)}"}
            return httpx.Response(200, json={"items": [raw]})
        body = __import__("json").loads(request.content.decode("utf-8"))
        raw = {**raw, "snippet": {**raw["snippet"], "description": body["snippet"]["description"]}}
        return httpx.Response(200, json=raw)

    writer = _writer(
        tmp_path,
        (YOUTUBE_READONLY_SCOPE, YOUTUBE_FORCE_SSL_SCOPE),
        httpx.MockTransport(handle),
    )
    restored = writer.restore_description_if_current(
        video_id="video-1",
        expected_channel_id="channel-1",
        expected_current_description="After",
        restore_description="Before",
    )
    assert restored.description == "Before"
    assert methods == ["GET", "PUT", "GET"]


def test_recovery_refuses_unknown_third_state(tmp_path: Path) -> None:
    raw = _raw_video("Manually edited")
    methods: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        return httpx.Response(200, json={"items": [raw]})

    writer = _writer(
        tmp_path,
        (YOUTUBE_READONLY_SCOPE, YOUTUBE_FORCE_SSL_SCOPE),
        httpx.MockTransport(handle),
    )
    with pytest.raises(YouTubeRevisionConflictError):
        writer.restore_description_if_current(
            video_id="video-1",
            expected_channel_id="channel-1",
            expected_current_description="After",
            restore_description="Before",
        )
    assert methods == ["GET"]


def test_description_safe_read_retries_transient_http(tmp_path: Path) -> None:
    raw = _raw_video("Before")
    calls = 0
    sleeps: list[float] = []

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, text="temporary")
        return httpx.Response(200, json={"items": [raw]})

    writer = _writer(
        tmp_path,
        (YOUTUBE_READONLY_SCOPE,),
        httpx.MockTransport(handle),
        retry_policy=RetryPolicy(max_attempts=2, base_delay_seconds=0.3, jitter_seconds=0.0),
        sleep=sleeps.append,
    )

    assert writer.read_description("video-1").description == "Before"
    assert calls == 2
    assert sleeps == [0.3]


def test_description_mutation_server_error_is_not_retried(tmp_path: Path) -> None:
    raw = _raw_video("Before")
    put_calls = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal put_calls
        if request.method == "GET":
            return httpx.Response(200, json={"items": [raw]})
        put_calls += 1
        return httpx.Response(503, text="uncertain")

    writer = _writer(
        tmp_path,
        (YOUTUBE_READONLY_SCOPE, YOUTUBE_FORCE_SSL_SCOPE),
        httpx.MockTransport(handle),
        retry_policy=RetryPolicy(max_attempts=8),
    )
    current = writer.read_description("video-1")

    with pytest.raises(YouTubeWriteError, match="attempts=1"):
        writer.replace_description(
            video_id="video-1",
            expected_channel_id="channel-1",
            expected_revision=current.revision,
            expected_description="Before",
            new_description="After",
        )

    assert put_calls == 1
