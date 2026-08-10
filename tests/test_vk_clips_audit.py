from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

from video_channel_manager.platforms.vk.clips_audit import build_vk_clips_audit_snapshot
from video_channel_manager.platforms.vk.client import VkApiClient, VkApiError
from video_channel_manager.platforms.vk.models import VkAccessToken
from video_channel_manager.platforms.vk.store import VkTokenStore

MILOVI_COMMUNITY_ID = 68859909
MILOVI_OWNER_ID = -68859909
KNOWN_SHREK_CLIP = "-68859909_456239130"


def _client(tmp_path: Path, *, mode: str = "ok") -> tuple[VkApiClient, list[dict[str, str]]]:
    store = VkTokenStore(tmp_path)
    store.save_token("legendary-poet", VkAccessToken(access_token="access", user_id=42))
    requests: list[dict[str, str]] = []
    video_ids = [456239130, *range(1000, 1200)]

    def handler(request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        params = {key: values[0] for key, values in parse_qs(request.content.decode()).items()}
        requests.append({"method": method, **params})
        assert params["access_token"] == "access"
        assert params["v"] == "5.199"

        if method == "groups.getById":
            return httpx.Response(
                200,
                json={
                    "response": {
                        "groups": [
                            {
                                "id": MILOVI_COMMUNITY_ID,
                                "name": "Milovi Cake - Торты и Десерты - Санкт-Петербург",
                                "screen_name": "milovi_cake",
                                "description": "Cakes",
                                "is_admin": 0 if mode == "not-managed" else 1,
                            }
                        ],
                        "profiles": [],
                    }
                },
            )

        if method == "video.search":
            assert params["owner_id"] == str(MILOVI_OWNER_ID)
            assert params["filters"] == "short"
            assert params["sort"] == "0"
            assert params["extended"] == "0"
            assert params["count"] == "200"
            offset = int(params["offset"])
            page_ids = video_ids[offset : offset + 200]
            items = [
                {
                    "id": video_id,
                    "owner_id": MILOVI_OWNER_ID,
                    "type": "short_video",
                    "title": f"Cake {video_id}",
                    "description": "Milovi Cake",
                    "duration": 30,
                    "date": 1765000000 + index,
                    "width": 1080,
                    "height": 1920,
                    "views": index,
                }
                for index, video_id in enumerate(page_ids, start=offset)
            ]
            if mode == "foreign-owner" and items:
                items[0]["owner_id"] = -235216998
            if mode == "wrong-type" and items:
                items[0]["type"] = "video"
            return httpx.Response(200, json={"response": {"count": len(video_ids), "items": items}})

        raise AssertionError(f"unexpected VK method: {method}")

    client = VkApiClient(
        token_store=store,
        account_alias="legendary-poet",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        api_base_url="https://example.test/method",
    )
    return client, requests


def test_vk_clips_snapshot_paginates_and_proves_known_clip(tmp_path: Path) -> None:
    client, requests = _client(tmp_path)

    snapshot = build_vk_clips_audit_snapshot(
        client,
        project_key="milovi-cake",
        community_id=MILOVI_COMMUNITY_ID,
        owner_id=MILOVI_OWNER_ID,
        required_remote_ids=[KNOWN_SHREK_CLIP],
    )

    assert snapshot["schema"] == "vk-clips-readonly-audit-v1"
    assert snapshot["project_key"] == "milovi-cake"
    assert snapshot["community"]["managed_by_token"] is True
    assert snapshot["coverage"]["clip_count"] == 201
    assert snapshot["coverage"]["required_remote_ids_found"] == [KNOWN_SHREK_CLIP]
    assert snapshot["clips"][0]["remote_id"] == KNOWN_SHREK_CLIP
    assert snapshot["clips"][0]["permalink"] == "https://vk.com/clip-68859909_456239130"
    search_requests = [request for request in requests if request["method"] == "video.search"]
    assert [request["offset"] for request in search_requests] == ["0", "200"]


@pytest.mark.parametrize("mode, message", [("foreign-owner", "foreign owner"), ("wrong-type", "non-Clip type")])
def test_vk_clips_snapshot_rejects_non_exact_search_results(tmp_path: Path, mode: str, message: str) -> None:
    client, _ = _client(tmp_path, mode=mode)

    with pytest.raises(VkApiError, match=message):
        build_vk_clips_audit_snapshot(
            client,
            project_key="milovi-cake",
            community_id=MILOVI_COMMUNITY_ID,
            owner_id=MILOVI_OWNER_ID,
        )


def test_vk_clips_snapshot_requires_management_access(tmp_path: Path) -> None:
    client, requests = _client(tmp_path, mode="not-managed")

    with pytest.raises(VkApiError, match="management access"):
        build_vk_clips_audit_snapshot(
            client,
            project_key="milovi-cake",
            community_id=MILOVI_COMMUNITY_ID,
            owner_id=MILOVI_OWNER_ID,
        )

    assert not any(request["method"] == "video.search" for request in requests)


def test_vk_clips_snapshot_rejects_cross_project_identity_before_provider_call(tmp_path: Path) -> None:
    client, requests = _client(tmp_path)

    with pytest.raises(ValueError, match="canonical project identity"):
        build_vk_clips_audit_snapshot(
            client,
            project_key="legendary-poet",
            community_id=MILOVI_COMMUNITY_ID,
            owner_id=MILOVI_OWNER_ID,
        )

    assert requests == []
