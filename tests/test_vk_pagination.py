from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs

import httpx

from video_channel_manager.platforms.vk.client import VkApiClient
from video_channel_manager.platforms.vk.models import VkAccessToken
from video_channel_manager.platforms.vk.store import VkTokenStore


def test_list_videos_continues_when_vk_clamps_requested_page_size(tmp_path: Path) -> None:
    store = VkTokenStore(tmp_path)
    store.save_token("default", VkAccessToken(access_token="access", user_id=42))
    offsets: list[int] = []
    requested_counts: list[int] = []
    total = 235
    server_page_limit = 100

    def handler(request: httpx.Request) -> httpx.Response:
        params = {key: values[0] for key, values in parse_qs(request.content.decode()).items()}
        assert request.url.path.endswith("/video.get")
        offset = int(params["offset"])
        requested_count = int(params["count"])
        offsets.append(offset)
        requested_counts.append(requested_count)
        page_count = min(server_page_limit, max(0, total - offset))
        items = [
            {
                "id": 1000 + index,
                "owner_id": -7,
                "title": f"Video {index}",
                "description": "Description",
                "duration": 60,
                "date": 1767323045,
                "type": "video",
            }
            for index in range(offset, offset + page_count)
        ]
        return httpx.Response(200, json={"response": {"count": total, "items": items}})

    client = VkApiClient(
        token_store=store,
        account_alias="default",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        api_base_url="https://example.test/method",
    )

    videos = client.list_videos(7)

    assert len(videos) == total
    assert len({video.ref.remote_id for video in videos}) == total
    assert offsets == [0, 100, 200]
    assert requested_counts == [200, 200, 200]
