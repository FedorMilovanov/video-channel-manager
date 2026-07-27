from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from video_channel_manager.platforms.vk.editorial_writer import VkEditorialWriter
from video_channel_manager.platforms.vk.models import VkAccessToken
from video_channel_manager.platforms.vk.store import VkTokenStore
from video_channel_manager.platforms.vk.text_writer import (
    VkVideoTextWriter,
    vk_edit_response_succeeded,
)
from video_channel_manager.platforms.vk.writer import VkWriteError


def _store(tmp_path: Path) -> VkTokenStore:
    store = VkTokenStore(tmp_path)
    store.save_token(
        "legendary-poet",
        VkAccessToken(access_token="secret", scopes=["video", "groups"]),
    )
    return store


def test_vk_edit_response_succeeded_accepts_scalar_and_structured_success() -> None:
    assert vk_edit_response_succeeded(1) is True
    assert vk_edit_response_succeeded(True) is True
    assert vk_edit_response_succeeded({"success": 1, "access_key": "key"}) is True
    assert vk_edit_response_succeeded({"success": True}) is True
    assert vk_edit_response_succeeded({"access_key": "key"}) is False
    assert vk_edit_response_succeeded(0) is False


def test_replace_text_accepts_structured_success_and_verifies_live_state(tmp_path: Path) -> None:
    current = {
        "owner_id": -235216998,
        "id": 456239017,
        "title": "Старое название",
        "description": "Описание",
    }
    calls: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/video.get"):
            return httpx.Response(200, json={"response": {"count": 1, "items": [dict(current)]}})
        if request.url.path.endswith("/video.edit"):
            current["title"] = "Новое название"
            return httpx.Response(
                200,
                json={"response": {"access_key": "20286989e196b83cf1", "success": 1}},
            )
        raise AssertionError(request.url)

    writer = VkVideoTextWriter(
        token_store=_store(tmp_path),
        account_alias="legendary-poet",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
        api_base_url="https://api.example/method",
    )

    updated = writer.replace_text_if_current(
        owner_id=-235216998,
        video_id=456239017,
        expected_title="Старое название",
        new_title="Новое название",
        expected_description="Описание",
        new_description="Описание",
        verification_delay_seconds=0,
    )

    assert updated.title == "Новое название"
    assert updated.description == "Описание"
    assert calls == [
        "/method/video.get",
        "/method/video.edit",
        "/method/video.get",
    ]


def test_replace_text_rejects_structured_response_without_success(tmp_path: Path) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
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
            return httpx.Response(200, json={"response": {"access_key": "key"}})
        raise AssertionError(request.url)

    writer = VkVideoTextWriter(
        token_store=_store(tmp_path),
        account_alias="legendary-poet",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
        api_base_url="https://api.example/method",
    )

    with pytest.raises(VkWriteError, match="unexpected response"):
        writer.replace_text_if_current(
            owner_id=-235216998,
            video_id=456239017,
            expected_title="Старое название",
            new_title="Новое название",
            expected_description="Описание",
            new_description="Описание",
            verification_delay_seconds=0,
        )


def test_rename_album_accepts_structured_success(tmp_path: Path) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/video.editAlbum")
        return httpx.Response(200, json={"response": {"success": 1, "access_key": "key"}})

    writer = VkEditorialWriter(
        token_store=_store(tmp_path),
        account_alias="legendary-poet",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
        api_base_url="https://api.example/method",
    )

    writer.rename_album(community_id=235216998, album_id=3, title="Сергей Есенин")
