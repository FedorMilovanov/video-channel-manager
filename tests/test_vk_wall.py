from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import httpx
import pytest

from video_channel_manager.domain.enums import ChannelKind, PlatformName
from video_channel_manager.domain.models import ChannelRecord, RemoteRef, VideoRecord
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk.models import VkAccessToken
from video_channel_manager.platforms.vk.store import VkTokenStore
from video_channel_manager.platforms.vk.wall import (
    VkWallWriter,
    build_vk_wall_post_plan,
    calculate_vk_wall_plan_sha256,
    render_vk_wall_post,
    validate_vk_wall_post_plan,
)
from video_channel_manager.platforms.vk.writer import VkWriteError


def _audit() -> AuditPackage:
    channel_id = "235216998"
    video_id = "-235216998_456239142"
    return AuditPackage(
        channel=ChannelRecord(
            ref=RemoteRef(platform=PlatformName.VK, channel_id=channel_id, remote_id=channel_id),
            title="The Legendary Poet",
            kind=ChannelKind.COMMUNITY,
        ),
        videos=[
            VideoRecord(
                ref=RemoteRef(platform=PlatformName.VK, channel_id=channel_id, remote_id=video_id),
                title="О, Русь моя! Жена моя! ⚡ На поле Куликовом",
                description="Описание\n\n🌐 https://thelegendarypoet.ru/",
                duration_seconds=300,
                privacy_status="public",
                revision="sha256:video",
            )
        ],
    )


def _writer(tmp_path: Path, transport: httpx.MockTransport) -> VkWallWriter:
    store = VkTokenStore(tmp_path)
    store.save_token("legendary-poet", VkAccessToken(access_token="secret", scopes=["video", "groups", "wall"]))
    return VkWallWriter(
        token_store=store,
        account_alias="legendary-poet",
        http_client=httpx.Client(transport=transport),
        api_base_url="https://api.example/method",
    )


def test_render_wall_post_accepts_underscores_inside_source_urls() -> None:
    message = render_vk_wall_post(
        headline="На поле Куликовом ⚡ Александр Блок",
        lead="Пять частей одного цикла.",
        paragraphs=["Историческая память становится разговором о настоящем."],
        source_links=[
            (
                "Текст",
                "https://ru.wikisource.org/wiki/На_поле_Куликовом_(Блок)",
            )
        ],
        hashtags=["АлександрБлок", "Русская Поэзия"],
    )

    assert "На_поле_Куликовом" in message
    assert message.count("thelegendarypoet.ru") == 1
    assert "#РусскаяПоэзия" in message


def test_build_wall_plan_is_self_validating() -> None:
    message = (
        "На поле Куликовом ⚡ Александр Блок\n\n"
        "Пять частей одного цикла.\n\n"
        "🌐 The Legendary Poet: https://thelegendarypoet.ru/\n\n"
        "Источник: https://ru.wikisource.org/wiki/На_поле_Куликовом_(Блок)"
    )
    plan = build_vk_wall_post_plan(
        _audit(),
        video_remote_id="-235216998_456239142",
        message=message,
        source_links=[
            {
                "label": "Текст цикла",
                "kind": "primary_text",
                "url": "https://ru.wikisource.org/wiki/На_поле_Куликовом_(Блок)",
            }
        ],
    )

    assert plan["attachment"] == "video-235216998_456239142"
    assert plan["guid"].startswith("vcm-")
    validate_vk_wall_post_plan(plan)

    tampered = deepcopy(plan)
    tampered["message"] += " Подмена"
    with pytest.raises(ValueError, match="hash mismatch"):
        validate_vk_wall_post_plan(tampered)

    tampered["message_sha256"] = plan["message_sha256"]
    tampered["plan_sha256"] = calculate_vk_wall_plan_sha256(tampered)
    with pytest.raises(ValueError, match="hash mismatch"):
        validate_vk_wall_post_plan(tampered)


def test_wall_writer_posts_once_and_verifies_attachment(tmp_path: Path) -> None:
    calls: list[str] = []
    message = "На поле Куликовом\n\nhttps://thelegendarypoet.ru/"

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/wall.get"):
            return httpx.Response(200, json={"response": {"count": 0, "items": []}})
        if request.url.path.endswith("/wall.post"):
            assert b"from_group=1" in request.content
            assert b"attachments=video-235216998_456239142" in request.content
            return httpx.Response(200, json={"response": {"post_id": 77}})
        if request.url.path.endswith("/wall.getById"):
            return httpx.Response(
                200,
                json={
                    "response": [
                        {
                            "owner_id": -235216998,
                            "id": 77,
                            "text": message,
                            "attachments": [
                                {
                                    "type": "video",
                                    "video": {"owner_id": -235216998, "id": 456239142},
                                }
                            ],
                        }
                    ]
                },
            )
        raise AssertionError(request.url)

    writer = _writer(tmp_path, httpx.MockTransport(respond))
    result = writer.post_video(
        community_id=235216998,
        video_owner_id=-235216998,
        video_id=456239142,
        message=message,
        guid="vcm-test",
    )

    assert result.remote_id == "-235216998_77"
    assert calls == ["/method/wall.get", "/method/wall.post", "/method/wall.getById"]


def test_wall_writer_blocks_existing_video_post(tmp_path: Path) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/wall.get")
        return httpx.Response(
            200,
            json={
                "response": {
                    "count": 1,
                    "items": [
                        {
                            "id": 12,
                            "attachments": [
                                {
                                    "type": "video",
                                    "video": {"owner_id": -235216998, "id": 456239142},
                                }
                            ],
                        }
                    ],
                }
            },
        )

    writer = _writer(tmp_path, httpx.MockTransport(respond))
    with pytest.raises(VkWriteError, match="already appears"):
        writer.post_video(
            community_id=235216998,
            video_owner_id=-235216998,
            video_id=456239142,
            message="Пост",
            guid="vcm-test",
        )


def test_wall_post_does_not_retry_ambiguous_failure(tmp_path: Path) -> None:
    wall_post_calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal wall_post_calls
        if request.url.path.endswith("/wall.get"):
            return httpx.Response(200, json={"response": {"count": 0, "items": []}})
        if request.url.path.endswith("/wall.post"):
            wall_post_calls += 1
            return httpx.Response(503, text="ambiguous")
        raise AssertionError(request.url)

    writer = _writer(tmp_path, httpx.MockTransport(respond))
    with pytest.raises(VkWriteError, match="HTTP 503"):
        writer.post_video(
            community_id=235216998,
            video_owner_id=-235216998,
            video_id=456239142,
            message="Пост",
            guid="vcm-test",
        )

    assert wall_post_calls == 1
