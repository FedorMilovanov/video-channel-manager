from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from video_channel_manager.platforms.vk.editorial_writer import VkEditorialWriter
from video_channel_manager.platforms.vk.models import VkAccessToken
from video_channel_manager.platforms.vk.store import VkTokenStore
from video_channel_manager.platforms.vk.text_writer import VkVideoTextWriter
from video_channel_manager.platforms.vk.thumbnails import VkThumbnailWriter
from video_channel_manager.platforms.vk.writer import VkVideoWriter, VkWriteError


def _store(tmp_path: Path) -> VkTokenStore:
    store = VkTokenStore(tmp_path)
    store.save_token(
        "legendary-poet",
        VkAccessToken(access_token="secret", scopes=["video", "groups"]),
    )
    return store


def test_album_create_ambiguous_server_failure_is_attempted_once(tmp_path: Path) -> None:
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url.path.endswith("/video.addAlbum")
        return httpx.Response(503, text="response lost after album create")

    writer = VkVideoWriter(
        token_store=_store(tmp_path),
        account_alias="legendary-poet",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
        api_base_url="https://api.example/method",
        max_attempts=9,
        sleep=lambda _: None,
    )

    with pytest.raises(VkWriteError, match="HTTP 503") as captured:
        writer.create_album(community_id=235216998, title="Сергей Есенин")

    assert captured.value.retryable is False
    assert captured.value.attempts == 1
    assert calls == 1


def test_album_membership_ambiguous_write_is_not_replayed(tmp_path: Path) -> None:
    calls: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/video.getAlbumsByVideo"):
            return httpx.Response(200, json={"response": []})
        if request.url.path.endswith("/video.addToAlbum"):
            return httpx.Response(503, text="response lost after membership mutation")
        raise AssertionError(request.url)

    writer = VkVideoWriter(
        token_store=_store(tmp_path),
        account_alias="legendary-poet",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
        api_base_url="https://api.example/method",
        max_attempts=9,
        sleep=lambda _: None,
    )

    with pytest.raises(VkWriteError, match="HTTP 503") as captured:
        writer.add_to_album(
            community_id=235216998,
            album_id=10,
            owner_id=-235216998,
            video_id=501,
            verification_delay_seconds=0,
        )

    assert captured.value.retryable is False
    assert captured.value.attempts == 1
    assert calls == [
        "/method/video.getAlbumsByVideo",
        "/method/video.addToAlbum",
    ]


def test_album_edit_ambiguous_server_failure_is_attempted_once(tmp_path: Path) -> None:
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url.path.endswith("/video.editAlbum")
        return httpx.Response(503, text="response lost after album edit")

    writer = VkEditorialWriter(
        token_store=_store(tmp_path),
        account_alias="legendary-poet",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
        api_base_url="https://api.example/method",
        max_attempts=9,
        sleep=lambda _: None,
    )

    with pytest.raises(VkWriteError, match="HTTP 503") as captured:
        writer.rename_album(community_id=235216998, album_id=3, title="Сергей Есенин")

    assert captured.value.retryable is False
    assert captured.value.attempts == 1
    assert calls == 1


def test_video_text_edit_ambiguous_server_failure_stops_after_one_write(tmp_path: Path) -> None:
    calls: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/video.get"):
            return httpx.Response(
                200,
                json={
                    "response": {
                        "count": 1,
                        "items": [
                            {
                                "owner_id": -235216998,
                                "id": 456239017,
                                "title": "Старое название",
                                "description": "Описание",
                            }
                        ],
                    }
                },
            )
        if request.url.path.endswith("/video.edit"):
            return httpx.Response(503, text="response lost after video edit")
        raise AssertionError(request.url)

    writer = VkVideoTextWriter(
        token_store=_store(tmp_path),
        account_alias="legendary-poet",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
        api_base_url="https://api.example/method",
        max_attempts=9,
        sleep=lambda _: None,
    )

    with pytest.raises(VkWriteError, match="HTTP 503") as captured:
        writer.replace_text_if_current(
            owner_id=-235216998,
            video_id=456239017,
            expected_title="Старое название",
            new_title="Новое название",
            expected_description="Описание",
            new_description="Описание",
            verification_delay_seconds=0,
        )

    assert captured.value.retryable is False
    assert captured.value.attempts == 1
    assert calls == ["/method/video.get", "/method/video.edit"]


def test_thumbnail_upload_ambiguous_server_failure_is_attempted_once(tmp_path: Path) -> None:
    calls = 0
    image = tmp_path / "thumbnail.jpg"
    image.write_bytes(b"jpeg-image-bytes")

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url == httpx.URL("https://upload.example/private-thumb-ticket")
        return httpx.Response(503, text="response lost after thumbnail upload")

    writer = VkThumbnailWriter(
        token_store=_store(tmp_path),
        account_alias="legendary-poet",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
        api_base_url="https://api.example/method",
        max_attempts=9,
    )

    with pytest.raises(VkWriteError, match="HTTP 503") as captured:
        writer.upload_image(
            upload_url="https://upload.example/private-thumb-ticket",
            path=image,
        )

    assert captured.value.retryable is False
    assert captured.value.attempts == 1
    assert "upload.example" not in str(captured.value)
    assert calls == 1
