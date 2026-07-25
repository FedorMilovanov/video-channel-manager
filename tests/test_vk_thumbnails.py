from __future__ import annotations

from pathlib import Path

import httpx

from video_channel_manager.platforms.vk.models import VkAccessToken
from video_channel_manager.platforms.vk.store import VkTokenStore
from video_channel_manager.platforms.vk.thumbnails import VkThumbnailWriter


def test_set_thumbnail_uses_vk_thumb_upload_flow(tmp_path: Path) -> None:
    store = VkTokenStore(tmp_path)
    store.save_token("legendary-poet", VkAccessToken(access_token="secret", scopes=["video", "groups"]))
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

    writer = VkThumbnailWriter(
        token_store=store,
        account_alias="legendary-poet",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
        api_base_url="https://api.example/method",
    )

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
