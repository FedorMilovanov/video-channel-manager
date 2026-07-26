from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from video_channel_manager.platforms.vk.models import VkAccessToken
from video_channel_manager.platforms.vk.store import VkTokenStore
from video_channel_manager.platforms.vk.writer import VkUploadTicket, VkVideoWriter, VkWriteError


def _writer(tmp_path: Path, handler: httpx.MockTransport, *, max_attempts: int = 4) -> VkVideoWriter:
    store = VkTokenStore(tmp_path)
    store.save_token("legendary-poet", VkAccessToken(access_token="secret", scopes=["video", "groups"]))
    return VkVideoWriter(
        token_store=store,
        account_alias="legendary-poet",
        http_client=httpx.Client(transport=handler),
        api_base_url="https://api.example/method",
        max_attempts=max_attempts,
    )


def test_create_album_and_begin_upload(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/video.addAlbum"):
            return httpx.Response(200, json={"response": {"album_id": 77}})
        if request.url.path.endswith("/video.save"):
            return httpx.Response(
                200,
                json={
                    "response": {
                        "owner_id": -235216998,
                        "video_id": 501,
                        "upload_url": "https://upload.example/video",
                    }
                },
            )
        raise AssertionError(request.url)

    writer = _writer(tmp_path, httpx.MockTransport(respond))

    assert writer.create_album(community_id=235216998, title="Сергей Есенин") == 77
    ticket = writer.begin_upload(community_id=235216998, title="Берёза", description="Описание")

    assert ticket.remote_id == "-235216998_501"
    assert len(requests) == 2
    assert b"access_token=secret" in requests[0].content
    assert b"group_id=235216998" in requests[0].content
    assert b"wallpost=0" in requests[1].content


def test_add_to_album_is_idempotent(tmp_path: Path) -> None:
    calls: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/video.getAlbumsByVideo"):
            return httpx.Response(200, json={"response": [10]})
        raise AssertionError(request.url)

    writer = _writer(tmp_path, httpx.MockTransport(respond))

    added = writer.add_to_album(
        community_id=235216998,
        album_id=10,
        owner_id=-235216998,
        video_id=501,
    )

    assert added is False
    assert calls == ["/method/video.getAlbumsByVideo"]


def test_add_to_album_uses_verified_membership_not_response_shape(tmp_path: Path) -> None:
    calls: list[str] = []
    album_checks = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal album_checks
        calls.append(request.url.path)
        if request.url.path.endswith("/video.getAlbumsByVideo"):
            album_checks += 1
            albums = [] if album_checks == 1 else [10]
            return httpx.Response(200, json={"response": albums})
        if request.url.path.endswith("/video.addToAlbum"):
            return httpx.Response(200, json={"response": 0})
        raise AssertionError(request.url)

    writer = _writer(tmp_path, httpx.MockTransport(respond))

    added = writer.add_to_album(
        community_id=235216998,
        album_id=10,
        owner_id=-235216998,
        video_id=501,
        verification_delay_seconds=0,
    )

    assert added is True
    assert calls == [
        "/method/video.getAlbumsByVideo",
        "/method/video.addToAlbum",
        "/method/video.getAlbumsByVideo",
    ]


def test_upload_file_posts_video_file(tmp_path: Path) -> None:
    media = tmp_path / "video.mp4"
    media.write_bytes(b"video-bytes")

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://upload.example/video")
        assert b'name="video_file"' in request.content
        assert b"video-bytes" in request.content
        return httpx.Response(200, json={"size": 11, "video_id": "501"})

    writer = _writer(tmp_path, httpx.MockTransport(respond))
    result = writer.upload_file(
        VkUploadTicket(owner_id=-235216998, video_id=501, upload_url="https://upload.example/video"),
        media,
    )

    assert result["video_id"] == "501"


def test_begin_upload_does_not_retry_ambiguous_server_failure(tmp_path: Path) -> None:
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url.path.endswith("/video.save")
        return httpx.Response(503, text="ambiguous failure")

    writer = _writer(tmp_path, httpx.MockTransport(respond), max_attempts=4)

    with pytest.raises(VkWriteError, match="HTTP 503") as error:
        writer.begin_upload(community_id=235216998, title="Берёза", description="Описание")

    assert error.value.retryable is True
    assert calls == 1


def test_read_video_retries_transient_failure_and_checks_identity(tmp_path: Path) -> None:
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url.path.endswith("/video.get")
        if calls == 1:
            return httpx.Response(503, text="temporary")
        return httpx.Response(
            200,
            json={
                "response": {
                    "count": 1,
                    "items": [{"owner_id": -235216998, "id": 501, "title": "Берёза"}],
                }
            },
        )

    writer = _writer(tmp_path, httpx.MockTransport(respond), max_attempts=4)

    item = writer.read_video(owner_id=-235216998, video_id=501)

    assert item is not None
    assert item["title"] == "Берёза"
    assert calls == 2


def test_read_video_rejects_unexpected_identity(tmp_path: Path) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "response": {
                    "count": 1,
                    "items": [{"owner_id": -235216998, "id": 999, "title": "Другой ролик"}],
                }
            },
        )

    writer = _writer(tmp_path, httpx.MockTransport(respond))

    with pytest.raises(VkWriteError, match="unexpected identity"):
        writer.read_video(owner_id=-235216998, video_id=501)


def test_wait_until_available_rejects_nonpositive_timing(tmp_path: Path) -> None:
    writer = _writer(tmp_path, httpx.MockTransport(lambda request: httpx.Response(500)))
    ticket = VkUploadTicket(owner_id=-235216998, video_id=501, upload_url="https://upload.example/video")

    with pytest.raises(ValueError, match="must be positive"):
        writer.wait_until_available(ticket, timeout_seconds=0)
