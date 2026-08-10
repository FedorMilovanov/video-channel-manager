from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

from video_channel_manager.platforms.vk.clips_owner_probe import (
    VK_OWNER_CLIPS_PROBE_API_VERSION,
    build_vk_owner_clips_probe_snapshot,
)
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
    ids = [456239130, *range(456239200, 456239225)]

    def handler(request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        params = {key: values[0] for key, values in parse_qs(request.content.decode()).items()}
        requests.append({"method": method, **params})
        assert params["access_token"] == "access"
        assert params["v"] == VK_OWNER_CLIPS_PROBE_API_VERSION

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
                                "is_admin": 1,
                            }
                        ],
                        "profiles": [],
                    }
                },
            )

        if method == "shortVideo.getOwnerVideos":
            assert params["owner_id"] == str(MILOVI_OWNER_ID)
            assert params["count"] == "24"
            if mode == "provider-error":
                return httpx.Response(
                    200,
                    json={"error": {"error_code": 3, "error_msg": "Unknown method passed"}},
                )
            offset = int(params["offset"])
            page_ids = ids[offset : offset + 24]
            items = [
                {
                    "id": video_id,
                    "owner_id": MILOVI_OWNER_ID,
                    "type": "short_video",
                    "title": f"Clip {video_id}",
                    "duration": 30,
                    "date": 1765000000 + index,
                    "width": 1080,
                    "height": 1920,
                }
                for index, video_id in enumerate(page_ids, start=offset)
            ]
            if mode == "mixed-type" and offset == 0 and len(items) > 1:
                items[1]["type"] = "video"
            if mode == "nested" and items:
                items = [{"video": item, "source": "grid"} for item in items]
            if mode == "foreign-owner" and items:
                target = items[0]["video"] if "video" in items[0] else items[0]
                target["owner_id"] = -235216998
            return httpx.Response(
                200,
                json={
                    "response": {
                        "count": len(ids),
                        "items": items,
                        "offset": offset,
                    }
                },
            )

        raise AssertionError(f"unexpected VK method: {method}")

    client = VkApiClient(
        token_store=store,
        account_alias="legendary-poet",
        api_version=VK_OWNER_CLIPS_PROBE_API_VERSION,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        api_base_url="https://example.test/method",
    )
    return client, requests


def test_owner_clips_probe_paginates_and_finds_known_clip(tmp_path: Path) -> None:
    client, requests = _client(tmp_path)

    snapshot = build_vk_owner_clips_probe_snapshot(
        client,
        project_key="milovi-cake",
        community_id=MILOVI_COMMUNITY_ID,
        owner_id=MILOVI_OWNER_ID,
        required_remote_ids=[KNOWN_SHREK_CLIP],
    )

    assert snapshot["schema"] == "vk-owner-clips-experimental-probe-v1"
    assert snapshot["provider_probe"]["status"] == "ok"
    assert snapshot["provider_probe"]["provider_reported_total"] == 26
    assert snapshot["provider_probe"]["retrieved_raw_item_count"] == 26
    assert snapshot["provider_probe"]["pagination_complete"] is True
    assert snapshot["coverage"]["clip_count"] == 26
    assert snapshot["coverage"]["required_remote_ids_found_as_clips"] == [KNOWN_SHREK_CLIP]
    assert snapshot["coverage"]["surface_complete_claim"] is False
    probe_requests = [request for request in requests if request["method"] == "shortVideo.getOwnerVideos"]
    assert [request["offset"] for request in probe_requests] == ["0", "24"]


def test_owner_clips_probe_preserves_provider_error_as_evidence(tmp_path: Path) -> None:
    client, _ = _client(tmp_path, mode="provider-error")

    snapshot = build_vk_owner_clips_probe_snapshot(
        client,
        project_key="milovi-cake",
        community_id=MILOVI_COMMUNITY_ID,
        owner_id=MILOVI_OWNER_ID,
        required_remote_ids=[KNOWN_SHREK_CLIP],
    )

    assert snapshot["provider_probe"]["status"] == "error"
    assert snapshot["provider_probe"]["error"]["code"] == 3
    assert snapshot["provider_probe"]["retrieved_raw_item_count"] == 0
    assert snapshot["coverage"]["clip_count"] == 0
    assert snapshot["coverage"]["required_remote_ids_missing_from_probe"] == [KNOWN_SHREK_CLIP]


def test_owner_clips_probe_handles_nested_video_shape(tmp_path: Path) -> None:
    client, _ = _client(tmp_path, mode="nested")

    snapshot = build_vk_owner_clips_probe_snapshot(
        client,
        project_key="milovi-cake",
        community_id=MILOVI_COMMUNITY_ID,
        owner_id=MILOVI_OWNER_ID,
    )

    assert snapshot["coverage"]["candidate_count"] == 26
    assert snapshot["coverage"]["clip_count"] == 26
    assert snapshot["shape_noise"] == []
    assert snapshot["endpoint_candidates"][0]["raw"]["source"] == "grid"


def test_owner_clips_probe_keeps_non_clip_type_as_candidate_not_native_clip(tmp_path: Path) -> None:
    client, _ = _client(tmp_path, mode="mixed-type")

    snapshot = build_vk_owner_clips_probe_snapshot(
        client,
        project_key="milovi-cake",
        community_id=MILOVI_COMMUNITY_ID,
        owner_id=MILOVI_OWNER_ID,
    )

    assert snapshot["coverage"]["candidate_count"] == 26
    assert snapshot["coverage"]["clip_count"] == 25
    assert snapshot["coverage"]["returned_type_counts"] == {"short_video": 25, "video": 1}


def test_owner_clips_probe_rejects_foreign_owner(tmp_path: Path) -> None:
    client, _ = _client(tmp_path, mode="foreign-owner")

    with pytest.raises(VkApiError, match="foreign owner"):
        build_vk_owner_clips_probe_snapshot(
            client,
            project_key="milovi-cake",
            community_id=MILOVI_COMMUNITY_ID,
            owner_id=MILOVI_OWNER_ID,
        )


def test_owner_clips_probe_rejects_cross_project_before_provider_call(tmp_path: Path) -> None:
    client, requests = _client(tmp_path)

    with pytest.raises(ValueError, match="canonical project identity"):
        build_vk_owner_clips_probe_snapshot(
            client,
            project_key="legendary-poet",
            community_id=MILOVI_COMMUNITY_ID,
            owner_id=MILOVI_OWNER_ID,
        )

    assert requests == []


def test_owner_clips_probe_requires_observed_api_version(tmp_path: Path) -> None:
    client, requests = _client(tmp_path)
    client.api_version = "5.199"

    with pytest.raises(ValueError, match="requires the exact observed web-client API version"):
        build_vk_owner_clips_probe_snapshot(
            client,
            project_key="milovi-cake",
            community_id=MILOVI_COMMUNITY_ID,
            owner_id=MILOVI_OWNER_ID,
        )

    assert requests == []
