from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

from video_channel_manager.platforms.vk.milovi_immediate_wall import (
    MILOVI_COMMUNITY_ID,
    MILOVI_OWNER_ID,
    MILOVI_SOURCE_ALLOWLIST,
    MiloviImmediateWallAuthority,
    MiloviImmediateWallRecoveryRequired,
    MiloviImmediateWallWriter,
)
from video_channel_manager.platforms.vk.models import VkAccessToken
from video_channel_manager.platforms.vk.store import VkTokenStore
from video_channel_manager.platforms.vk.writer import VkWriteError

VIDEO_ID = 456240001
MESSAGE = "Торт Milovi Cake\n\nhttps://milovicake.ru/"
GUID = "vcm-milovi-323-d48QLgOuiTs"


def _writer(tmp_path: Path, transport: httpx.MockTransport) -> MiloviImmediateWallWriter:
    store = VkTokenStore(tmp_path)
    store.save_token(
        "shared-vk-user",
        VkAccessToken(access_token="secret", scopes=["video", "groups", "wall"]),
    )
    return MiloviImmediateWallWriter(
        token_store=store,
        account_alias="shared-vk-user",
        http_client=httpx.Client(transport=transport),
        api_base_url="https://api.example/method",
    )


def _short_video() -> dict[str, object]:
    return {
        "owner_id": MILOVI_OWNER_ID,
        "id": VIDEO_ID,
        "title": "Торт Milovi Cake",
        "duration": 20,
        "type": "short_video",
        "processing": 0,
        "converting": 0,
        "can_watch": 1,
    }


def _wall_post(post_id: int, *, video_id: int = VIDEO_ID, text: str = MESSAGE) -> dict[str, object]:
    return {
        "owner_id": MILOVI_OWNER_ID,
        "id": post_id,
        "date": 1786550000,
        "text": text,
        "attachments": [
            {
                "type": "video",
                "video": {"owner_id": MILOVI_OWNER_ID, "id": video_id},
            }
        ],
    }


def _surface(request: httpx.Request) -> str:
    return parse_qs(request.content.decode("utf-8"))["filter"][0]


def _video_get_response(item: dict[str, object] | None = None) -> httpx.Response:
    items = [] if item is None else [item]
    return httpx.Response(200, json={"response": {"count": len(items), "items": items}})


def test_issue_323_allowlist_is_exact_and_blocks_silu() -> None:
    assert len(MILOVI_SOURCE_ALLOWLIST) == 12
    assert "d48QLgOuiTs" in MILOVI_SOURCE_ALLOWLIST
    assert "SiluLt5Bz1c" not in MILOVI_SOURCE_ALLOWLIST

    authority = MiloviImmediateWallAuthority(source_video_id="d48QLgOuiTs")
    assert authority.project_key == "milovi-cake"
    assert authority.community_id == MILOVI_COMMUNITY_ID
    assert authority.owner_id == MILOVI_OWNER_ID
    assert authority.as_dict()["publication_mode"] == "immediate"
    assert authority.as_dict()["publish_date"] is None

    with pytest.raises(ValueError, match="not authorized"):
        MiloviImmediateWallAuthority(source_video_id="SiluLt5Bz1c")
    with pytest.raises(ValueError, match="not authorized"):
        MiloviImmediateWallAuthority(source_video_id="outside-scope")


def test_immediate_wall_refuses_ordinary_video_before_mutation(tmp_path: Path) -> None:
    wall_post_calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal wall_post_calls
        if request.url.path.endswith("/video.get"):
            item = _short_video()
            item["type"] = "video"
            return _video_get_response(item)
        if request.url.path.endswith("/wall.post"):
            wall_post_calls += 1
        raise AssertionError(request.url)

    writer = _writer(tmp_path, httpx.MockTransport(respond))
    with pytest.raises(VkWriteError, match="type=short_video"):
        writer.post_verified_clip_now(
            authority=MiloviImmediateWallAuthority(source_video_id="d48QLgOuiTs"),
            video_id=VIDEO_ID,
            message=MESSAGE,
            guid=GUID,
        )
    assert wall_post_calls == 0


def test_immediate_wall_posts_without_publish_date_and_verifies_published_delta(tmp_path: Path) -> None:
    wall_get_calls = 0
    wall_post_calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal wall_get_calls, wall_post_calls
        if request.url.path.endswith("/video.get"):
            return _video_get_response(_short_video())
        if request.url.path.endswith("/wall.get"):
            wall_get_calls += 1
            surface = _surface(request)
            if wall_get_calls <= 2:
                return httpx.Response(200, json={"response": {"count": 0, "items": []}})
            if surface == "postponed":
                return httpx.Response(200, json={"response": {"count": 0, "items": []}})
            return httpx.Response(200, json={"response": {"count": 1, "items": [_wall_post(77)]}})
        if request.url.path.endswith("/wall.post"):
            wall_post_calls += 1
            form = parse_qs(request.content.decode("utf-8"))
            assert form["owner_id"] == [str(MILOVI_OWNER_ID)]
            assert form["from_group"] == ["1"]
            assert form["attachments"] == [f"video{MILOVI_OWNER_ID}_{VIDEO_ID}"]
            assert form["guid"] == [GUID]
            assert "publish_date" not in form
            return httpx.Response(200, json={"response": {"post_id": 77}})
        raise AssertionError(request.url)

    writer = _writer(tmp_path, httpx.MockTransport(respond))
    result = writer.post_verified_clip_now(
        authority=MiloviImmediateWallAuthority(source_video_id="d48QLgOuiTs"),
        video_id=VIDEO_ID,
        message=MESSAGE,
        guid=GUID,
    )

    assert result.remote_id == f"{MILOVI_OWNER_ID}_77"
    assert result.video_remote_id == f"{MILOVI_OWNER_ID}_{VIDEO_ID}"
    assert result.source_video_id == "d48QLgOuiTs"
    assert wall_post_calls == 1


def test_immediate_wall_blocks_existing_published_or_postponed_attachment(tmp_path: Path) -> None:
    wall_post_calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal wall_post_calls
        if request.url.path.endswith("/video.get"):
            return _video_get_response(_short_video())
        if request.url.path.endswith("/wall.get"):
            if _surface(request) == "owner":
                return httpx.Response(200, json={"response": {"count": 1, "items": [_wall_post(12)]}})
            return httpx.Response(200, json={"response": {"count": 0, "items": []}})
        if request.url.path.endswith("/wall.post"):
            wall_post_calls += 1
        raise AssertionError(request.url)

    writer = _writer(tmp_path, httpx.MockTransport(respond))
    with pytest.raises(VkWriteError, match="already appears"):
        writer.post_verified_clip_now(
            authority=MiloviImmediateWallAuthority(source_video_id="d48QLgOuiTs"),
            video_id=VIDEO_ID,
            message=MESSAGE,
            guid=GUID,
        )
    assert wall_post_calls == 0


def test_ambiguous_immediate_wall_response_reconciles_without_replay(tmp_path: Path) -> None:
    wall_get_calls = 0
    wall_post_calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal wall_get_calls, wall_post_calls
        if request.url.path.endswith("/video.get"):
            return _video_get_response(_short_video())
        if request.url.path.endswith("/wall.get"):
            wall_get_calls += 1
            surface = _surface(request)
            if wall_get_calls <= 2:
                return httpx.Response(200, json={"response": {"count": 0, "items": []}})
            if surface == "postponed":
                return httpx.Response(200, json={"response": {"count": 0, "items": []}})
            return httpx.Response(200, json={"response": {"count": 1, "items": [_wall_post(88)]}})
        if request.url.path.endswith("/wall.post"):
            wall_post_calls += 1
            return httpx.Response(503, text="response lost after acceptance")
        raise AssertionError(request.url)

    writer = _writer(tmp_path, httpx.MockTransport(respond))
    result = writer.post_verified_clip_now(
        authority=MiloviImmediateWallAuthority(source_video_id="d48QLgOuiTs"),
        video_id=VIDEO_ID,
        message=MESSAGE,
        guid=GUID,
    )
    assert result.remote_id == f"{MILOVI_OWNER_ID}_88"
    assert wall_post_calls == 1


def test_ambiguous_immediate_wall_without_exact_post_stops_without_replay(tmp_path: Path) -> None:
    wall_post_calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal wall_post_calls
        if request.url.path.endswith("/video.get"):
            return _video_get_response(_short_video())
        if request.url.path.endswith("/wall.get"):
            return httpx.Response(200, json={"response": {"count": 0, "items": []}})
        if request.url.path.endswith("/wall.post"):
            wall_post_calls += 1
            return httpx.Response(503, text="ambiguous")
        raise AssertionError(request.url)

    writer = _writer(tmp_path, httpx.MockTransport(respond))
    with pytest.raises(MiloviImmediateWallRecoveryRequired, match="exactly one published"):
        writer.post_verified_clip_now(
            authority=MiloviImmediateWallAuthority(source_video_id="d48QLgOuiTs"),
            video_id=VIDEO_ID,
            message=MESSAGE,
            guid=GUID,
        )
    assert wall_post_calls == 1
