from __future__ import annotations

from typing import Any, cast

from video_channel_manager.platforms.vk.client import VkApiClient
from video_channel_manager.platforms.vk.delete_orchestrator.gateway import VkDeleteGateway


class FakePagedVkClient:
    def __init__(self, total: int) -> None:
        self.total = total
        self.calls: list[dict[str, Any]] = []

    def _call(self, method: str, *, params: dict[str, Any]) -> dict[str, Any]:
        assert method == "video.get"
        self.calls.append(dict(params))
        offset = int(params["offset"])
        count = min(int(params["count"]), 100)
        end = min(offset + count, self.total)
        items = [
            {
                "owner_id": -60805374,
                "id": 1_000_000 + index,
                "title": f"video-{index}",
            }
            for index in range(offset, end)
        ]
        return {"count": self.total, "items": items}


def test_owner_inventory_reads_every_100_item_vk_page() -> None:
    fake = FakePagedVkClient(total=251)
    progress: list[tuple[str, dict[str, object]]] = []
    gateway = VkDeleteGateway(
        cast(VkApiClient, fake),
        progress_callback=lambda stage, payload: progress.append((stage, payload)),
    )

    inventory = gateway.owner_inventory(60805374)

    assert inventory.reported_count == 251
    assert len(inventory.items) == 251
    assert len(inventory.ids) == 251
    assert [call["offset"] for call in fake.calls] == [0, 100, 200]
    assert [call["count"] for call in fake.calls] == [100, 100, 100]
    pages = [payload for stage, payload in progress if stage == "owner_inventory_page"]
    assert [payload["returned"] for payload in pages] == [100, 100, 51]
    assert progress[-1] == (
        "owner_inventory_complete",
        {"pages": 3, "collected": 251, "reported_count": 251},
    )
