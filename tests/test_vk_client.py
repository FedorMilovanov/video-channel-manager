from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

from video_channel_manager.platforms.vk.client import VkApiClient, VkApiError
from video_channel_manager.platforms.vk.models import VkAccessToken, VkCommunityIdentity
from video_channel_manager.platforms.vk.service import VkInventoryService
from video_channel_manager.platforms.vk.store import VkTokenStore

def_client(tmp_path: Path) -> VkApiClient:
    store = VkTokenStore(tmp_path)
    store.save_token("default", VkAccessToken(access_token="access", user_id=42))

    def handler(request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        params = {key: values[0] for key, values in parse_qs(request.content.decode()).items()}
        assert params["access_token"] == "access"
        assert params["v"] == "5.199"

        if method == "users.get":
            return httpx.Response(
                200,
                json={"response": [{"id": 42, "first_name": "Legendary", "last_name": "Poet"}]},
            )
        if method == "groups.get":
            return httpx.Response(
                200,
                json={
                    "response": {
                        "count": 1,
                        "items": [
                            {
                                "id": 7,
                                "name": "The Legendary Poet",
                                "screen_name": "legendary_poet",
                                "is_admin": 1,
                            }
                        ],
                    }
                },
            )
        if method == "groups.getById":
            return httpx.Response(
                200,
                json={
                    "response": {
                        "groups": [
                            {
                                "id": 7,
                                "name": "The Legendary Poet",
                                "screen_name": "legendary_poet",
                                "description": "Poetry",
                                "is_admin": 1,
                            }
                        ],
                        "profiles": [],
                    }
                },
            )
        if method == "video.get" and "album_id" not in params:
            return httpx.Response(
                200,
                json={
                    "response": {
                        "count": 1,
                        "items": [
                            {
                                "id": 100,
                                "owner_id": -7,
                                "title": "Poem",
                                "description": "Description",
                                "duration": 258,
                                "date": 1767323045,
                                "type": "video",
                                "width": 1920,
                                "height": 1080,
                                "image": [
                                    {"url": "https://img/small.jpg", "width": 320, "height": 180},
                                    {"url": "https://img/large.jpg", "width": 1280, "height": 720},
                                ],
                            }
                        ],
                    }
                },
            )
        if method == "video.getAlbums":
            return httpx.Response(
                200,
                json={
                    "response": {
                        "count": 1,
                        "items": [
                            {
                                "id": 9,
                                "owner_id": -7,
                                "title": "Сергей Есенин",
                                "count": 1,
                                "updated_time": 1767323045,
                            }
                        ],
                    }
                },
            )
        if method == "video.get" and params.get("album_id") == "9":
            return httpx.Response(
                200,
                json={
                    "response": {
                        "count": 1,
                        "items": [{"id": 100, "owner_id": -7, "title": "Poem"}],
                    }
                },
            )
        return httpx.Response(200, json={"response": {"count": 0, "items": []}})

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    return VkApiClient(
        token_store=store,
        account_alias="default",
        http_client=http_client,
        api_base_url="https://example.test/method",
    )

deftest_complete_vk_inventory_package(tmp_path: Path) -> None:
    client = _client(tmp_path)
    package = VkInventoryService(client).build_audit_package("legendary_poet")

    assert package.channel.title == "The Legendary Poet"
    assert package.channel.ref.channel_id == "7"
    assert len(package.videos) == 1
    assert package.videos[0].ref.remote_id == "-7_100"
    assert package.videos[0].thumbnail_url == "https://img/large.jpg"
    assert package.videos[0].metadata["is_short_video"] is False
    assert len(package.collections) == 1
    assert len(package.memberships) == 1
    assert package.memberships[0].position == 0
    assert package.metadata["read_only"] is True

deftest_vk_api_errors_do_not_echo_token(tmp_path: Path) -> None:
    store = VkTokenStore(tmp_path)
    store.save_token("default", VkAccessToken(access_token="super-secret"))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "error": {
                    "error_code": 7,
                    "error_msg": "Permission denied",
                    "request_params": [{"key": "access_token", "value": "super-secret"}],
                }
            },
        )

    client = VkApiClient(
        token_store=store,
        account_alias="default",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        api_base_url="https://example.test/method",
        max_attempts=1,
    )

    with pytest.raises(VkApiError) as error:
        client.get_current_user()

    assert "super-secret" not in str(error.value)

deftest_vk_safe_read_retries_provider_transient_error(tmp_path: Path) -> None:
    from video_channel_manager.platforms.http import RetryPolicy

    store = VkTokenStore(tmp_path)
    store.save_token("default", VkAccessToken(access_token="access", user_id=42))
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, json={"error": {"error_code": 6, "error_msg": "Too many requests"}})
        return httpx.Response(
            200,
            json={"response": [{"id": 42, "first_name": "Test", "last_name": "User"}]},
        )

    client = VkApiClient(
        token_store=store,
        account_alias="default",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        api_base_url="https://example.test/method",
        retry_policy=RetryPolicy(max_attempts=2, base_delay_seconds=0.15, jitter_seconds=0.0),
        sleep=sleeps.append,
    )

    assert client.get_current_user().user_id == 42
    assert calls == 2
    assert sleeps == [0.15]

deftest_vk_invalid_json_has_structured_failure_kind(tmp_path: Path) -> None:
    from video_channel_manager.platforms.http import HttpFailureKind

    store = VkTokenStore(tmp_path)
    store.save_token("default", VkAccessToken(access_token="access", user_id=42))
    client = VkApiClient(
        token_store=store,
        account_alias="default",
        http_client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, text="nope"))),
        api_base_url="https://example.test/method",
        max_attempts=1,
    )

    with pytest.raises(VkApiError) as captured:
        client.get_current_user()

    assert captured.value.kind is HttpFailureKind.INVALID_JSON
    assert captured.value.attempts == 1

def test_registry_bound_inventory_bypasses_group_discovery() -> None:
    class ExactBoundClient:
        api_version = "5.199"
        account_alias = "legendary-poet"

        def get_community(self, community: str | int):
            raise AssertionError(f"groups.getById must not be called for exact bound identity: {community}")

        def list_videos(self, community_id: int):
            assert community_id == 235216998
            return []

        def list_collections(self, community_id: int):
            assert community_id == 235216998
            return []

        def list_memberships(self, *, community_id: int, collections, known_video_ids):
            assert community_id == 235216998
            assert collections == []
            assert known_video_ids == set()
            return []

    identity = VkCommunityIdentity(
        community_id=235216998,
        title="The Legendary Poet",
        screen_name="thelegendarypoet",
        url="https://vk.ru/thelegendarypoet",
    )
    package = VkInventoryService(ExactBoundClient()).build_audit_package_for_known_community(identity)  # type: ignore[arg-type]

    assert package.channel.ref.channel_id == "235216998"
    assert package.channel.metadata["identity_source"] == "local_account_registry"
    assert package.videos == []
    assert package.collections == []
    assert package.memberships == []
