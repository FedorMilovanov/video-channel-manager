from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

from video_channel_manager.domain.enums import ChannelKind, PlatformName
from video_channel_manager.domain.models import ChannelRecord, RemoteRef, VideoRecord
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk.models import VkAccessToken
from video_channel_manager.platforms.vk.store import VkTokenStore
from video_channel_manager.platforms.vk.wall import (
    VkWallRecoveryRequired,
    VkWallWriter,
    build_vk_wall_post_plan,
    calculate_vk_wall_plan_sha256,
    render_vk_wall_post,
    validate_vk_wall_post_plan,
)
from video_channel_manager.platforms.vk.writer import VkWriteError

COMMUNITY_ID = 235216998
OWNER_ID = -COMMUNITY_ID
VIDEO_ID = 456239142
NOW = datetime(2026, 8, 4, 2, 0, tzinfo=UTC)
PUBLISH_AT = NOW + timedelta(hours=12)
PUBLISH_DATE = int(PUBLISH_AT.timestamp())


def _audit() -> AuditPackage:
    channel_id = str(COMMUNITY_ID)
    video_remote_id = f"{OWNER_ID}_{VIDEO_ID}"
    return AuditPackage(
        channel=ChannelRecord(
            ref=RemoteRef(platform=PlatformName.VK, channel_id=channel_id, remote_id=channel_id),
            title="The Legendary Poet",
            kind=ChannelKind.COMMUNITY,
        ),
        videos=[
            VideoRecord(
                ref=RemoteRef(platform=PlatformName.VK, channel_id=channel_id, remote_id=video_remote_id),
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


def _video_post(
    post_id: int,
    *,
    text: str,
    date: int = PUBLISH_DATE,
    video_id: int = VIDEO_ID,
) -> dict[str, object]:
    return {
        "owner_id": OWNER_ID,
        "id": post_id,
        "date": date,
        "text": text,
        "attachments": [
            {
                "type": "video",
                "video": {"owner_id": OWNER_ID, "id": video_id},
            }
        ],
    }


def _surface_filter(request: httpx.Request) -> str:
    return parse_qs(request.content.decode("utf-8"))["filter"][0]


def test_render_wall_post_accepts_underscores_inside_source_urls() -> None:
    message = render_vk_wall_post(
        project_key="legendary-poet",
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


def test_render_wall_post_requires_registered_project() -> None:
    with pytest.raises(ValueError, match="registered project_key"):
        render_vk_wall_post(
            project_key="unknown",
            headline="Заголовок",
            lead="Лид",
            paragraphs=[],
            source_links=[],
        )


def test_build_wall_plan_is_project_bound_postponed_and_self_validating() -> None:
    message = (
        "На поле Куликовом ⚡ Александр Блок\n\n"
        "Пять частей одного цикла.\n\n"
        "🌐 Проект: https://thelegendarypoet.ru/\n\n"
        "Источник: https://ru.wikisource.org/wiki/На_поле_Куликовом_(Блок)"
    )
    plan = build_vk_wall_post_plan(
        _audit(),
        video_remote_id=f"{OWNER_ID}_{VIDEO_ID}",
        message=message,
        source_links=[
            {
                "label": "Текст цикла",
                "kind": "primary_text",
                "url": "https://ru.wikisource.org/wiki/На_поле_Куликовом_(Блок)",
            }
        ],
        publish_at=PUBLISH_AT,
        now=NOW,
    )

    assert plan["project_key"] == "legendary-poet"
    assert plan["target_owner_id"] == OWNER_ID
    assert plan["attachment"] == f"video{OWNER_ID}_{VIDEO_ID}"
    assert plan["publication_mode"] == "postponed"
    assert plan["immediate_publication_authorized"] is False
    assert plan["publish_date"] == PUBLISH_DATE
    assert plan["guid"].startswith("vcm-")
    validate_vk_wall_post_plan(plan)

    tampered = deepcopy(plan)
    tampered["message"] += " Подмена"
    with pytest.raises(ValueError, match="hash mismatch"):
        validate_vk_wall_post_plan(tampered)

    tampered = deepcopy(plan)
    tampered["immediate_publication_authorized"] = True
    tampered["plan_sha256"] = calculate_vk_wall_plan_sha256(tampered)
    with pytest.raises(ValueError, match="not authorized"):
        validate_vk_wall_post_plan(tampered)

    tampered = deepcopy(plan)
    tampered["publish_date"] += 60
    tampered["plan_sha256"] = calculate_vk_wall_plan_sha256(tampered)
    with pytest.raises(ValueError, match="guid"):
        validate_vk_wall_post_plan(tampered)


def test_wall_writer_posts_once_to_postponed_and_reconciles_exact_delta(tmp_path: Path) -> None:
    calls: list[str] = []
    message = "На поле Куликовом\n\nhttps://thelegendarypoet.ru/"
    wall_get_calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal wall_get_calls
        calls.append(request.url.path)
        if request.url.path.endswith("/wall.get"):
            wall_get_calls += 1
            surface = _surface_filter(request)
            if wall_get_calls <= 2:
                return httpx.Response(200, json={"response": {"count": 0, "items": []}})
            if surface == "owner":
                return httpx.Response(200, json={"response": {"count": 0, "items": []}})
            return httpx.Response(
                200,
                json={"response": {"count": 1, "items": [_video_post(77, text=message)]}},
            )
        if request.url.path.endswith("/wall.post"):
            form = parse_qs(request.content.decode("utf-8"))
            assert form["from_group"] == ["1"]
            assert form["attachments"] == [f"video{OWNER_ID}_{VIDEO_ID}"]
            assert form["publish_date"] == [str(PUBLISH_DATE)]
            assert form["guid"] == ["vcm-test"]
            return httpx.Response(200, json={"response": {"post_id": 77}})
        raise AssertionError(request.url)

    writer = _writer(tmp_path, httpx.MockTransport(respond))
    result = writer.post_video(
        community_id=COMMUNITY_ID,
        video_owner_id=OWNER_ID,
        video_id=VIDEO_ID,
        message=message,
        guid="vcm-test",
        publish_at=PUBLISH_AT,
        now=NOW,
    )

    assert result.remote_id == f"{OWNER_ID}_77"
    assert result.publish_date == PUBLISH_DATE
    assert result.before_snapshot_sha256.startswith("sha256:")
    assert result.after_snapshot_sha256.startswith("sha256:")
    assert calls == [
        "/method/wall.get",
        "/method/wall.get",
        "/method/wall.post",
        "/method/wall.get",
        "/method/wall.get",
    ]


def test_wall_writer_blocks_existing_video_on_postponed_surface(tmp_path: Path) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/wall.get")
        if _surface_filter(request) == "owner":
            return httpx.Response(200, json={"response": {"count": 0, "items": []}})
        return httpx.Response(
            200,
            json={"response": {"count": 1, "items": [_video_post(12, text="Старый пост")]}},
        )

    writer = _writer(tmp_path, httpx.MockTransport(respond))
    with pytest.raises(VkWriteError, match="published/postponed"):
        writer.post_video(
            community_id=COMMUNITY_ID,
            video_owner_id=OWNER_ID,
            video_id=VIDEO_ID,
            message="Пост",
            guid="vcm-test",
            publish_at=PUBLISH_AT,
            now=NOW,
        )


def test_wall_writer_blocks_schedule_slot_collision(tmp_path: Path) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/wall.get")
        if _surface_filter(request) == "owner":
            return httpx.Response(200, json={"response": {"count": 0, "items": []}})
        return httpx.Response(
            200,
            json={
                "response": {
                    "count": 1,
                    "items": [_video_post(13, text="Другой пост", video_id=VIDEO_ID + 1)],
                }
            },
        )

    writer = _writer(tmp_path, httpx.MockTransport(respond))
    with pytest.raises(VkWriteError, match="schedule slot"):
        writer.post_video(
            community_id=COMMUNITY_ID,
            video_owner_id=OWNER_ID,
            video_id=VIDEO_ID,
            message="Пост",
            guid="vcm-test",
            publish_at=PUBLISH_AT,
            now=NOW,
        )


def test_wall_post_does_not_retry_ambiguous_failure_and_stays_unknown(tmp_path: Path) -> None:
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
    with pytest.raises(VkWallRecoveryRequired, match="exactly one postponed"):
        writer.post_video(
            community_id=COMMUNITY_ID,
            video_owner_id=OWNER_ID,
            video_id=VIDEO_ID,
            message="Пост",
            guid="vcm-test",
            publish_at=PUBLISH_AT,
            now=NOW,
        )

    assert wall_post_calls == 1


def test_ambiguous_wall_response_can_reconcile_exact_post_without_replay(tmp_path: Path) -> None:
    wall_post_calls = 0
    wall_get_calls = 0
    message = "Пост"

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal wall_post_calls, wall_get_calls
        if request.url.path.endswith("/wall.get"):
            wall_get_calls += 1
            surface = _surface_filter(request)
            if wall_get_calls <= 2 or surface == "owner":
                return httpx.Response(200, json={"response": {"count": 0, "items": []}})
            return httpx.Response(
                200,
                json={"response": {"count": 1, "items": [_video_post(88, text=message)]}},
            )
        if request.url.path.endswith("/wall.post"):
            wall_post_calls += 1
            return httpx.Response(503, text="response lost after acceptance")
        raise AssertionError(request.url)

    writer = _writer(tmp_path, httpx.MockTransport(respond))
    result = writer.post_video(
        community_id=COMMUNITY_ID,
        video_owner_id=OWNER_ID,
        video_id=VIDEO_ID,
        message=message,
        guid="vcm-test",
        publish_at=PUBLISH_AT,
        now=NOW,
    )

    assert result.remote_id == f"{OWNER_ID}_88"
    assert wall_post_calls == 1


def test_incomplete_wall_surface_blocks_before_mutation(tmp_path: Path) -> None:
    wall_post_calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal wall_post_calls
        if request.url.path.endswith("/wall.get"):
            return httpx.Response(
                200,
                json={
                    "response": {
                        "count": 2,
                        "items": [_video_post(90, text="Нерелевантно", video_id=VIDEO_ID + 1)],
                    }
                },
            )
        if request.url.path.endswith("/wall.post"):
            wall_post_calls += 1
        raise AssertionError(request.url)

    writer = _writer(tmp_path, httpx.MockTransport(respond))
    with pytest.raises(VkWriteError, match="preflight snapshot is incomplete"):
        writer.post_video(
            community_id=COMMUNITY_ID,
            video_owner_id=OWNER_ID,
            video_id=VIDEO_ID,
            message="Пост",
            guid="vcm-test",
            publish_at=PUBLISH_AT,
            now=NOW,
            max_posts_per_surface=1,
        )

    assert wall_post_calls == 0
