from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs

import httpx

from video_channel_manager.platforms.vk.models import VkAccessToken
from video_channel_manager.platforms.vk.store import VkTokenStore
from video_channel_manager.platforms.vk.thumbnails import VkThumbnailWriter


def _writer(tmp_path: Path, transport: httpx.MockTransport) -> VkThumbnailWriter:
    store = VkTokenStore(tmp_path)
    store.save_token("legendary-poet", VkAccessToken(access_token="secret", scopes=["video", "groups"]))
    return VkThumbnailWriter(
        token_store=store,
        account_alias="legendary-poet",
        http_client=httpx.Client(transport=transport),
        api_base_url="https://api.example/method",
    )


def test_set_thumbnail_uses_vk_thumb_upload_flow(tmp_path: Path) -> None:
    image = tmp_path / "youtube-thumbnail.jpg"
    image.write_bytes(b"jpeg-image-bytes")
    calls: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/video.getThumbUploadUrl"):
            assert b"owner_id=-235216998" in request.content
            return httpx.Response(200, json={"response": {"upload_url": "https://upload.example/thumb"}})
        if request.url == httpx.URL("https://upload.example/thumb"):
            assert b'name="file"' in request.content
            assert b"jpeg-image-bytes" in request.content
            return httpx.Response(
                200,
                json={
                    "thumb_json": '{"photo":"payload"}',
                    "thumb_size": "1280x720",
                    "random_tag": "tag-1",
                },
            )
        if request.url.path.endswith("/video.saveUploadedThumb"):
            assert b"owner_id=-235216998" in request.content
            assert b"video_id=456239134" in request.content
            assert b"set_thumb=1" in request.content
            assert b"thumb_size=1280x720" in request.content
            return httpx.Response(
                200,
                json={
                    "response": {
                        "photo_id": 77,
                        "photo_owner_id": -235216998,
                        "photo_hash": "hash-1",
                        "image": [],
                    }
                },
            )
        raise AssertionError(request.url)

    writer = _writer(tmp_path, httpx.MockTransport(respond))

    result = writer.set_thumbnail(
        owner_id=-235216998,
        video_id=456239134,
        path=image,
    )

    assert result["photo_id"] == 77
    assert calls == [
        "/method/video.getThumbUploadUrl",
        "/thumb",
        "/method/video.saveUploadedThumb",
    ]


def test_set_thumbnail_accepts_current_raw_vk_upload_payload(tmp_path: Path) -> None:
    image = tmp_path / "youtube-thumbnail.jpg"
    image.write_bytes(b"jpeg-image-bytes")
    upload_payload = {
        "sha": "4631599efade90800e9c73c141f9cb16b7c2cdb5fc3534065f2b79fc",
        "secret": "-6442740244585555424",
        "meta": {
            "height": "720",
            "kid": "55d1d5974642594b09349c4d54ea4a54",
            "width": "1280",
        },
        "hash": "eb7188c5cb242bc0d533bd8e4298938f",
        "server": "999999",
        "user_id": 631487,
        "group_id": 235216998,
        "request_id": "8C6tgk98uYCM5ykP3CBnQb_uoolDsg",
        "album_id": -76,
    }

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/video.getThumbUploadUrl"):
            return httpx.Response(200, json={"response": {"upload_url": "https://upload.example/thumb"}})
        if request.url == httpx.URL("https://upload.example/thumb"):
            return httpx.Response(200, json=upload_payload)
        if request.url.path.endswith("/video.saveUploadedThumb"):
            form = parse_qs(request.content.decode("utf-8"))
            assert form["owner_id"] == ["-235216998"]
            assert form["video_id"] == ["456239134"]
            assert form["set_thumb"] == ["1"]
            assert json.loads(form["thumb_json"][0]) == upload_payload
            return httpx.Response(
                200,
                json={
                    "response": {
                        "photo_id": 78,
                        "photo_owner_id": -235216998,
                        "photo_hash": "hash-2",
                        "image": [],
                    }
                },
            )
        raise AssertionError(request.url)

    writer = _writer(tmp_path, httpx.MockTransport(respond))
    result = writer.set_thumbnail(
        owner_id=-235216998,
        video_id=456239134,
        path=image,
    )

    assert result["photo_id"] == 78
