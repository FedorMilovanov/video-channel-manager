from __future__ import annotations

import copy
import json
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


def _localized_raw_video() -> dict[str, Any]:
    raw = _raw_video("Before")
    raw["snippet"]["defaultAudioLanguage"] = "ru"
    raw["localizations"] = {
        "ru": {"title": "Russian title", "description": "Before"},
        "en-US": {"title": "English title", "description": "English before"},
    }
    return raw


@pytest.mark.parametrize(
    ("mutation", "expected_field"),
    [
        ("audio", "snippet.defaultAudioLanguage"),
        ("default_language", "snippet.defaultLanguage"),
        ("title", "snippet.title"),
        ("category", "snippet.categoryId"),
        ("tags", "snippet.tags"),
        ("channel", "snippet.channelId"),
        ("privacy", "status.privacyStatus"),
        ("english_description", "localizations.en-US.description"),
        ("english_title", "localizations.en-US.title"),
        ("missing_locale", "localizations.languages"),
        ("added_locale", "localizations.languages"),
        ("russian_locale_mismatch", "localizations.ru.description"),
    ],
)
def test_description_success_is_not_enough_if_other_metadata_drifts(
    tmp_path: Path, mutation: str, expected_field: str
) -> None:
    raw = _localized_raw_video()
    methods: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal raw
        methods.append(request.method)
        if request.method == "GET":
            assert "localizations" in request.url.params["part"].split(",")
            return httpx.Response(200, json={"items": [raw]})
        assert request.method == "PUT"
        payload = json.loads(request.content)
        assert payload["snippet"]["defaultAudioLanguage"] == "ru"
        raw = copy.deepcopy(raw)
        raw["snippet"]["description"] = payload["snippet"]["description"]
        if mutation == "audio":
            raw["snippet"]["defaultAudioLanguage"] = "en-US"
        elif mutation == "default_language":
            raw["snippet"]["defaultLanguage"] = "en"
        elif mutation == "title":
            raw["snippet"]["title"] = "Unexpected title"
        elif mutation == "category":
            raw["snippet"]["categoryId"] = "10"
        elif mutation == "tags":
            raw["snippet"]["tags"] = ["different"]
        elif mutation == "channel":
            raw["snippet"]["channelId"] = "other-channel"
        elif mutation == "privacy":
            raw["status"]["privacyStatus"] = "unlisted"
        elif mutation == "english_description":
            raw["localizations"]["en-US"]["description"] = "Unexpected English translation"
        elif mutation == "english_title":
            raw["localizations"]["en-US"]["title"] = "Unexpected English title"
        elif mutation == "missing_locale":
            del raw["localizations"]["en-US"]
        elif mutation == "added_locale":
            raw["localizations"]["de"] = {"title": "German", "description": "German translation"}
        elif mutation == "russian_locale_mismatch":
            raw["localizations"]["ru"]["description"] = "Unexpected Russian localization"
        else:
            pytest.fail(f"Unknown case: {mutation}")
        return httpx.Response(200, json=raw)

    writer = _writer(
        tmp_path,
        (YOUTUBE_READONLY_SCOPE, YOUTUBE_FORCE_SSL_SCOPE),
        httpx.MockTransport(handle),
        verification_delays=(),
    )
    with pytest.raises(YouTubeWriteError, match="metadata drift") as failure:
        writer.replace_description(
            video_id="video-1",
            expected_channel_id="channel-1",
            expected_revision="old",
            expected_description="Before",
            new_description="After",
        )
    assert expected_field in str(failure.value)
    assert methods == ["GET", "PUT", "GET"]  # NEVER silently retry a dangerous PUT.


def test_description_preserves_translations_and_accepts_primary_locale_sync(tmp_path: Path) -> None:
    raw = _localized_raw_video()
    methods: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal raw
        methods.append(request.method)
        if request.method == "GET":
            return httpx.Response(200, json={"items": [raw]})
        payload = json.loads(request.content)
        raw = copy.deepcopy(raw)
        raw["snippet"]["description"] = payload["snippet"]["description"]
        raw["localizations"]["ru"]["description"] = "After"
        return httpx.Response(200, json=raw)

    writer = _writer(
        tmp_path,
        (YOUTUBE_READONLY_SCOPE, YOUTUBE_FORCE_SSL_SCOPE),
        httpx.MockTransport(handle),
    )
    result = writer.replace_description(
        video_id="video-1",
        expected_channel_id="channel-1",
        expected_revision="old",
        expected_description="Before",
        new_description="After",
    )
    assert result.description == "After"
    assert result.raw["localizations"]["en-US"]["description"] == "English before"
    assert result.raw["localizations"]["ru"]["description"] == "After"
    assert methods == ["GET", "PUT", "GET"]


def test_metadata_postflight_retry_reads_again_but_does_not_repeat_put(tmp_path: Path) -> None:
    raw = _localized_raw_video()
    methods: list[str] = []
    saved = False
    reads_after_save = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal raw, saved, reads_after_save
        methods.append(request.method)
        if request.method == "PUT":
            payload = json.loads(request.content)
            raw = copy.deepcopy(raw)
            raw["snippet"]["description"] = payload["snippet"]["description"]
            saved = True
            return httpx.Response(200, json=raw)
        if saved:
            reads_after_save += 1
            if reads_after_save == 1:
                stale = copy.deepcopy(raw)
                stale["localizations"]["en-US"]["description"] = "Temporary translation drift"
                return httpx.Response(200, json={"items": [stale]})
        return httpx.Response(200, json={"items": [raw]})

    writer = _writer(
        tmp_path,
        (YOUTUBE_READONLY_SCOPE, YOUTUBE_FORCE_SSL_SCOPE),
        httpx.MockTransport(handle),
        verification_delays=(0.0,),
    )
    result = writer.replace_description(
        video_id="video-1",
        expected_channel_id="channel-1",
        expected_revision="old",
        expected_description="Before",
        new_description="After",
    )
    assert result.description == "After"
    assert methods == ["GET", "PUT", "GET", "GET"]


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


def test_youtube_put_has_longer_read_timeout_but_reads_keep_client_default(tmp_path: Path) -> None:
    raw = _raw_video("Before")
    observed: list[tuple[str, float | None, float | None]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal raw
        timeouts = request.extensions["timeout"]
        observed.append((request.method, timeouts["read"], timeouts["connect"]))
        if request.method == "PUT":
            payload = __import__("json").loads(request.content)
            raw = {**raw, "snippet": {**raw["snippet"], "description": payload["snippet"]["description"]}}
            return httpx.Response(200, json=raw)
        return httpx.Response(200, json={"items": [raw]})

    writer = _writer(
        tmp_path,
        (YOUTUBE_READONLY_SCOPE, YOUTUBE_FORCE_SSL_SCOPE),
        httpx.MockTransport(handle),
    )
    read_timeout = writer._http_client.timeout.read
    snapshot = writer.read_description("video-1")
    result = writer.replace_description(
        video_id="video-1",
        expected_channel_id="channel-1",
        expected_revision=snapshot.revision,
        expected_description="Before",
        new_description="After",
    )
    assert result.description == "After"
    assert observed == [
        ("GET", read_timeout, writer._http_client.timeout.connect),
        ("GET", read_timeout, writer._http_client.timeout.connect),
        ("PUT", 120.0, 45.0),
        ("GET", read_timeout, writer._http_client.timeout.connect),
    ]


def test_youtube_longer_timeout_never_retries_ambiguous_put(tmp_path: Path) -> None:
    raw = _raw_video("Before")
    methods: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        if request.method == "PUT":
            assert request.extensions["timeout"]["read"] == 120.0
            raise httpx.ReadTimeout("simulated slow videos.update response", request=request)
        return httpx.Response(200, json={"items": [raw]})

    writer = _writer(
        tmp_path,
        (YOUTUBE_READONLY_SCOPE, YOUTUBE_FORCE_SSL_SCOPE),
        httpx.MockTransport(handle),
        retry_policy=RetryPolicy(max_attempts=8),
    )
    with pytest.raises(YouTubeWriteError, match="ReadTimeout"):
        writer.replace_description(
            video_id="video-1",
            expected_channel_id="channel-1",
            expected_revision="old",
            expected_description="Before",
            new_description="After",
        )
    assert methods == ["GET", "PUT"]


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


@pytest.mark.parametrize(
    ("failure_kind", "expected_detail"),
    [
        ("persistent_locale_drift", "localizations.en-US.description"),
        ("persistent_stale_description", "after 3 reads"),
    ],
)
def test_exhausted_postwrite_reads_fail_closed_without_replaying_put(
    tmp_path: Path, failure_kind: str, expected_detail: str
) -> None:
    raw = _localized_raw_video()
    methods: list[str] = []
    sleeps: list[float] = []

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal raw
        methods.append(request.method)
        if request.method == "PUT":
            raw = copy.deepcopy(raw)
            if failure_kind == "persistent_locale_drift":
                raw["snippet"]["description"] = "After"
                raw["localizations"]["en-US"]["description"] = "Unexpected translation"
            return httpx.Response(200, json=raw)
        return httpx.Response(200, json={"items": [raw]})

    writer = _writer(
        tmp_path,
        (YOUTUBE_READONLY_SCOPE, YOUTUBE_FORCE_SSL_SCOPE),
        httpx.MockTransport(handle),
        verification_delays=(0.1, 0.0),
        sleep=sleeps.append,
    )
    with pytest.raises(YouTubeWriteError, match="Verification failed") as failure:
        writer.replace_description(
            video_id="video-1",
            expected_channel_id="channel-1",
            expected_revision="old",
            expected_description="Before",
            new_description="After",
        )

    assert expected_detail in str(failure.value)
    assert methods == ["GET", "PUT", "GET", "GET", "GET"]
    assert sleeps == [0.1]


def test_recovery_rejects_other_channel_before_mutation(tmp_path: Path) -> None:
    raw = _raw_video("After")
    raw["snippet"]["channelId"] = "different-channel"
    methods: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        assert request.method == "GET"
        return httpx.Response(200, json={"items": [raw]})

    writer = _writer(
        tmp_path,
        (YOUTUBE_READONLY_SCOPE, YOUTUBE_FORCE_SSL_SCOPE),
        httpx.MockTransport(handle),
    )
    with pytest.raises(YouTubeRevisionConflictError, match="Channel mismatch"):
        writer.restore_description_if_current(
            video_id="video-1",
            expected_channel_id="channel-1",
            expected_current_description="After",
            restore_description="Before",
        )
    assert methods == ["GET"]
