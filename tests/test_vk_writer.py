from __future__ import annotations

import json
from pathlib import Path

import httpx

from video_channel_manager.platforms.vk.models import VkAccessToken
from video_channel_manager.platforms.vk.store import VkTokenStore
from video_channel_manager.platforms.vk.writer import VkUploadTicket, VkVideoWriter


def _writer(tmp_path: Path, handler: httpx.MockTransport) -> VkVideoWriter:
    store = VkTokenStore(tmp_path)
    store.save_token("legendary-poet", VkAccessToken(access_token="secret", scopes=["video", "groups"]))
    return VkVideoWriter(
        token_store=store,
        account_alias="legendary-poet",
        http_client=httpx.Client(transport=handler),
        api_base_url="https://api.example/method",
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


def test_upload_file_posts_video_file(tmp_path: Path) -> None:
    media = tmp_path / "video.mp4"
    media.write_bytes(b"video-bytes")

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://upload.example/video")
        assert b'name="video_file"' in request.content
        assert b"video-bytes" in request.content
        return httpx.Response(200, json={"size": 11, "video_id": 501})

    writer = _writer(tmp_path, httpx.MockTransport(respond))
    result = writer.upload_file(
        VkUploadTicket(owner_id=-235216998, video_id=501, upload_url="https://upload.example/video"),
        media,
    )

    assert result["video_id"] == 501
