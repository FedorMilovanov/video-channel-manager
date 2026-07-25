from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

from video_channel_manager.platforms.vk.models import VkAccessToken
from video_channel_manager.platforms.vk.store import VkTokenStore
from video_channel_manager.platforms.vk.thumbnails import VkThumbnailWriter
from video_channel_manager.platforms.vk.writer import VkWriteError


def _writer(tmp_path: Path, transport: httpx.MockTransport, *, max_attempts: int = 4) -> VkThumbnailWriter:
    store = VkTokenStore(tmp_path)
    store.save_token("legendary-poet", VkAccessToken(access_token="secret", scopes=["video", "groups"]))
    return VkThumbnailWriter(
        token_store=store,
        account_alias="legendary-poet",
        http_client=httpx.Client(transport=transport),
        api_base_url="https://api.example/method",
        max_attempts=max_attempts,
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


def test_get_thumbnail_upload_url_retries_transient_failure(tmp_path: Path) -> None:
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, text="temporary")
        return httpx.Response(200, json={"response": {"upload_url": "https://upload.example/thumb"}})

    writer = _writer(tmp_path, httpx.MockTransport(respond), max_attempts=4)

    assert writer.get_upload_url(owner_id=-235216998) == "https://upload.example/thumb"
    assert calls == 2


def test_save_uploaded_thumbnail_does_not_retry_ambiguous_failure(tmp_path: Path) -> None:
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url.path.endswith("/video.saveUploadedThumb")
        return httpx.Response(503, text="ambiguous")

    writer = _writer(tmp_path, httpx.MockTransport(respond), max_attempts=4)

    with pytest.raises(VkWriteError, match="HTTP 503") as error:
        writer.save_uploaded_thumbnail(
            owner_id=-235216998,
            video_id=456239134,
            upload_payload={"thumb_json": '{"photo":"payload"}'},
        )

    assert error.value.retryable is True
    assert calls == 1


def test_save_uploaded_thumbnail_checks_photo_owner(tmp_path: Path) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "response": {
                    "photo_id": 78,
                    "photo_owner_id": -999,
                    "photo_hash": "hash-2",
                }
            },
        )

    writer = _writer(tmp_path, httpx.MockTransport(respond))

    with pytest.raises(VkWriteError, match="photo owner"):
        writer.save_uploaded_thumbnail(
            owner_id=-235216998,
            video_id=456239134,
            upload_payload={"thumb_json": '{"photo":"payload"}'},
        )


def test_upload_image_rejects_empty_file(tmp_path: Path) -> None:
    image = tmp_path / "empty.jpg"
    image.write_bytes(b"")
    writer = _writer(tmp_path, httpx.MockTransport(lambda request: httpx.Response(500)))

    with pytest.raises(ValueError, match="empty"):
        writer.upload_image(upload_url="https://upload.example/thumb", path=image)
