from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from video_channel_manager.platforms.http import HttpFailureKind, RetryPolicy
from video_channel_manager.platforms.vk.models import VkAccessToken
from video_channel_manager.platforms.vk.store import VkTokenStore
from video_channel_manager.platforms.vk.thumbnails import VkThumbnailWriter
from video_channel_manager.platforms.vk.writer import VkWriteError


def _store(tmp_path: Path) -> VkTokenStore:
    store = VkTokenStore(tmp_path)
    store.save_token("synthetic-vk-thumb-transport", VkAccessToken(access_token="secret", scopes=["video", "groups"]))
    return store


def test_thumbnail_safe_reservation_retries_provider_transient_error(tmp_path: Path) -> None:
    calls = 0
    sleeps: list[float] = []

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, json={"error": {"error_code": 6, "error_msg": "too many"}})
        return httpx.Response(200, json={"response": {"upload_url": "https://upload.example/thumb"}})

    client = httpx.Client(transport=httpx.MockTransport(respond))
    writer = VkThumbnailWriter(
        token_store=_store(tmp_path),
        account_alias="synthetic-vk-thumb-transport",
        http_client=client,
        api_base_url="https://api.example/method",
        retry_policy=RetryPolicy(max_attempts=3, base_delay_seconds=0.25, jitter_seconds=0.0),
        sleep=sleeps.append,
        jitter=lambda: 0.0,
    )

    assert writer.get_upload_url(owner_id=-235216998) == "https://upload.example/thumb"
    assert calls == 2
    assert sleeps == [0.25]


@pytest.mark.parametrize("error_code", [9, "9"])
def test_thumbnail_flood_9_opens_method_circuit_and_never_retries(tmp_path: Path, error_code: int | str) -> None:
    """VK flood code 9 is a durable circuit, not a transient retryable response."""
    calls = 0
    sleeps: list[float] = []

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url.host == "api.vk.ru"
        assert request.url.path == "/method/video.getThumbUploadUrl"
        return httpx.Response(
            200,
            json={"error": {"error_code": error_code, "error_msg": "Flood control"}},
        )

    store = _store(tmp_path)
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        writer = VkThumbnailWriter(
            token_store=store,
            account_alias="synthetic-vk-thumb-transport",
            http_client=client,
            retry_policy=RetryPolicy(max_attempts=8, base_delay_seconds=0.25, jitter_seconds=0.0),
            sleep=sleeps.append,
            jitter=lambda: 0.0,
        )
        with pytest.raises(VkWriteError) as first:
            writer.get_upload_url(owner_id=-235216998)
        assert first.value.code == 9
        assert first.value.kind is HttpFailureKind.PROVIDER_FLOOD_CONTROL
        assert first.value.retryable is False
        assert first.value.attempts == 1
        assert calls == 1
        assert sleeps == []
        assert writer.flood_control.get("video.getThumbUploadUrl") is not None

        with pytest.raises(VkWriteError) as blocked:
            writer.get_upload_url(owner_id=-235216998)
        assert blocked.value.code == 9
        assert blocked.value.kind is HttpFailureKind.PROVIDER_FLOOD_CONTROL
        assert blocked.value.retryable is False
        assert blocked.value.attempts == 0
        assert calls == 1
        assert sleeps == []


def test_thumbnail_upload_transport_is_single_attempt_and_redacted(tmp_path: Path) -> None:
    image = tmp_path / "thumb.jpg"
    image.write_bytes(b"jpeg")
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout(f"lost response from {request.url}", request=request)

    client = httpx.Client(transport=httpx.MockTransport(respond))
    writer = VkThumbnailWriter(
        token_store=_store(tmp_path),
        account_alias="synthetic-vk-thumb-transport",
        http_client=client,
        retry_policy=RetryPolicy(max_attempts=9),
    )

    with pytest.raises(VkWriteError) as captured:
        writer.upload_image(upload_url="https://upload.example/private-token", path=image)

    assert calls == 1
    assert captured.value.attempts == 1
    assert captured.value.retryable is False
    assert captured.value.kind is HttpFailureKind.TRANSPORT
    assert "upload.example" not in str(captured.value)
    assert "private-token" not in str(captured.value)


def test_thumbnail_save_provider_transient_error_is_not_replayed(tmp_path: Path) -> None:
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"error": {"error_code": 6, "error_msg": "ambiguous"}})

    client = httpx.Client(transport=httpx.MockTransport(respond))
    writer = VkThumbnailWriter(
        token_store=_store(tmp_path),
        account_alias="synthetic-vk-thumb-transport",
        http_client=client,
        retry_policy=RetryPolicy(max_attempts=8),
    )

    with pytest.raises(VkWriteError) as captured:
        writer.save_uploaded_thumbnail(
            owner_id=-235216998,
            video_id=456239134,
            upload_payload={"thumb_json": '{"photo":"payload"}'},
        )

    assert calls == 1
    assert captured.value.attempts == 1
    assert captured.value.retryable is False
    assert captured.value.kind is HttpFailureKind.PROVIDER_TRANSIENT


def test_thumbnail_borrowed_client_remains_open(tmp_path: Path) -> None:
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})))
    writer = VkThumbnailWriter(
        token_store=_store(tmp_path),
        account_alias="synthetic-vk-thumb-transport",
        http_client=client,
    )

    writer.close()

    assert client.is_closed is False
    client.close()
