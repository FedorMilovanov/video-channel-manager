from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest

from video_channel_manager.platforms.http import HttpFailureKind, RetryPolicy
from video_channel_manager.platforms.vk import flood_control as vk_flood_control
from video_channel_manager.platforms.vk.client import VkApiClient, VkApiError
from video_channel_manager.platforms.vk.flood_control import VkFloodControlGate
from video_channel_manager.platforms.vk.models import VkAccessToken
from video_channel_manager.platforms.vk.store import VkTokenStore
from video_channel_manager.platforms.vk.writer import VkVideoWriter, VkWriteError


def test_flood_gate_persists_exact_method_until_explicit_clear(tmp_path: Path) -> None:
    gate = VkFloodControlGate(tmp_path, "legendary-poet")

    assert gate.get("wall.get") is None
    first = gate.record("wall.get")
    second = VkFloodControlGate(tmp_path, "legendary-poet").record("wall.get")

    assert first.occurrences == 1
    assert second.occurrences == 2
    assert second.first_observed_at == first.first_observed_at
    assert gate.get("video.get") is None
    assert [entry.method for entry in gate.list_open()] == ["wall.get"]

    assert gate.clear("wall.get") is True
    assert gate.get("wall.get") is None
    assert gate.clear("wall.get") is False


def test_flood_gate_retries_windows_permission_error_when_lock_disappears(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate = VkFloodControlGate(tmp_path, "legendary-poet")
    original_open = vk_flood_control.os.open
    attempts = 0

    def flaky_open(path: object, flags: int, mode: int = 0o777) -> int:
        nonlocal attempts
        if Path(path) == gate.lock_path and attempts == 0:
            attempts += 1
            raise PermissionError(13, "simulated Windows O_EXCL contention", str(path))
        return original_open(path, flags, mode)

    monkeypatch.setattr(vk_flood_control, "_WINDOWS_LOCK_PERMISSION_IS_CONTENTION", True)
    monkeypatch.setattr(vk_flood_control.os, "open", flaky_open)
    monkeypatch.setattr(vk_flood_control.time, "sleep", lambda _seconds: None)

    entry = gate.record("wall.get")

    assert entry.occurrences == 1
    assert attempts == 1
    assert gate.get("wall.get") == entry


def test_read_client_code_9_is_single_attempt_and_opens_method_circuit(tmp_path: Path) -> None:
    store = VkTokenStore(tmp_path)
    store.save_token("legendary-poet", VkAccessToken(access_token="access", user_id=42))
    calls = 0
    sleeps: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={"error": {"error_code": 9, "error_msg": "Flood control"}},
        )

    client = VkApiClient(
        token_store=store,
        account_alias="legendary-poet",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        api_base_url="https://example.test/method",
        retry_policy=RetryPolicy(max_attempts=4, base_delay_seconds=0.01, jitter_seconds=0.0),
        sleep=sleeps.append,
    )

    with pytest.raises(VkApiError) as first:
        client.get_current_user()

    assert first.value.code == 9
    assert first.value.kind is HttpFailureKind.PROVIDER_FLOOD_CONTROL
    assert first.value.retryable is False
    assert first.value.attempts == 1
    assert calls == 1
    assert sleeps == []

    with pytest.raises(VkApiError) as second:
        client.get_current_user()

    assert second.value.code == 9
    assert second.value.kind is HttpFailureKind.PROVIDER_FLOOD_CONTROL
    assert second.value.retryable is False
    assert second.value.attempts == 0
    assert "circuit is open" in str(second.value)
    assert calls == 1


def test_write_client_safe_read_code_9_does_not_retry_or_block_other_methods(tmp_path: Path) -> None:
    store = VkTokenStore(tmp_path)
    store.save_token(
        "legendary-poet",
        VkAccessToken(access_token="access", scopes=["video", "groups", "wall"]),
    )
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        calls.append(method)
        if method == "video.get":
            return httpx.Response(
                200,
                json={"error": {"error_code": 9, "error_msg": "Flood control"}},
            )
        if method == "video.getAlbumsByVideo":
            return httpx.Response(200, json={"response": []})
        raise AssertionError(method)

    writer = VkVideoWriter(
        token_store=store,
        account_alias="legendary-poet",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        api_base_url="https://example.test/method",
        retry_policy=RetryPolicy(max_attempts=4, base_delay_seconds=0.01, jitter_seconds=0.0),
        sleep=lambda _seconds: (_ for _ in ()).throw(AssertionError("code 9 must not sleep/retry")),
    )

    with pytest.raises(VkWriteError) as captured:
        writer.read_video(owner_id=-235216998, video_id=501)

    assert captured.value.code == 9
    assert captured.value.kind is HttpFailureKind.PROVIDER_FLOOD_CONTROL
    assert captured.value.retryable is False
    assert captured.value.attempts == 1
    assert calls == ["video.get"]

    # The circuit is method-scoped: a successful unrelated read is still allowed.
    assert (
        writer.album_ids_for_video(
            community_id=235216998,
            owner_id=-235216998,
            video_id=501,
        )
        == set()
    )
    assert calls == ["video.get", "video.getAlbumsByVideo"]

    with pytest.raises(VkWriteError) as local_stop:
        writer.read_video(owner_id=-235216998, video_id=501)

    assert local_stop.value.attempts == 0
    assert calls == ["video.get", "video.getAlbumsByVideo"]


def test_flood_gate_concurrent_records_do_not_lose_occurrences(tmp_path: Path) -> None:
    def record_once(_index: int) -> None:
        VkFloodControlGate(tmp_path, "legendary-poet").record("video.get")

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(record_once, range(24)))

    entry = VkFloodControlGate(tmp_path, "legendary-poet").get("video.get")
    assert entry is not None
    assert entry.occurrences == 24
    assert not list((tmp_path / "vk" / "flood-control").glob("*.tmp"))
