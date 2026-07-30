from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from video_channel_manager.platforms.vk.client import VkApiClient
from video_channel_manager.platforms.vk.delete_orchestrator.models import split_remote_id
from video_channel_manager.platforms.vk.wall_content_audit import extract_video_ids_from_post, fetch_wall_posts


@dataclass(frozen=True)
class OwnerInventory:
    reported_count: int | None
    items: tuple[dict[str, Any], ...]

    @property
    def ids(self) -> frozenset[str]:
        result: set[str] = set()
        for item in self.items:
            owner_id = item.get("owner_id")
            video_id = item.get("id")
            if isinstance(owner_id, int) and isinstance(video_id, int):
                result.add(f"{owner_id}_{video_id}")
        return frozenset(result)


class DeleteGateway(Protocol):
    def exact_video(self, remote_id: str) -> dict[str, Any] | None: ...

    def owner_inventory(self, community_id: int) -> OwnerInventory: ...

    def album_ids(self, *, community_id: int, remote_id: str) -> frozenset[str]: ...

    def wall_video_ids(self, *, community_id: int, postponed: bool = False) -> frozenset[str]: ...

    def delete_once(self, *, community_id: int, remote_id: str) -> object: ...


class VkDeleteGateway:
    """Thin VK adapter with retryable reads and a deliberately non-retrying delete."""

    def __init__(self, client: VkApiClient) -> None:
        self.client = client

    def exact_video(self, remote_id: str) -> dict[str, Any] | None:
        response = self.client._call(
            "video.get",
            params={"videos": remote_id, "extended": False, "count": 1},
        )
        items = response.get("items") if isinstance(response, dict) else None
        if not isinstance(items, list):
            return None
        for raw in items:
            if not isinstance(raw, dict):
                continue
            owner_id = raw.get("owner_id")
            video_id = raw.get("id")
            if isinstance(owner_id, int) and isinstance(video_id, int) and f"{owner_id}_{video_id}" == remote_id:
                return raw
        return None

    def owner_inventory(self, community_id: int) -> OwnerInventory:
        page_size = 200
        offset = 0
        reported_count: int | None = None
        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        while True:
            response = self.client._call(
                "video.get",
                params={"owner_id": -community_id, "extended": False, "count": page_size, "offset": offset},
            )
            if not isinstance(response, dict):
                break
            raw_count = response.get("count")
            if isinstance(raw_count, int):
                reported_count = raw_count if reported_count is None else max(reported_count, raw_count)
            page = response.get("items")
            page_items = [item for item in page if isinstance(item, dict)] if isinstance(page, list) else []
            if not page_items:
                break
            for item in page_items:
                owner_id = item.get("owner_id")
                video_id = item.get("id")
                if not isinstance(owner_id, int) or not isinstance(video_id, int):
                    continue
                remote_id = f"{owner_id}_{video_id}"
                if remote_id in seen:
                    continue
                seen.add(remote_id)
                items.append(item)
            offset += len(page_items)
            if len(page_items) < page_size:
                break
        return OwnerInventory(reported_count=reported_count, items=tuple(items))

    def album_ids(self, *, community_id: int, remote_id: str) -> frozenset[str]:
        owner_id, video_id = split_remote_id(remote_id)
        response = self.client._call(
            "video.getAlbumsByVideo",
            params={
                "target_id": -community_id,
                "owner_id": owner_id,
                "video_id": video_id,
                "extended": False,
            },
        )
        if isinstance(response, list):
            return frozenset(str(value) for value in response if isinstance(value, int))
        if isinstance(response, dict):
            items = response.get("items")
            if isinstance(items, list):
                result: set[str] = set()
                for item in items:
                    if isinstance(item, int):
                        result.add(str(item))
                    elif isinstance(item, dict) and isinstance(item.get("id"), int):
                        result.add(str(item["id"]))
                return frozenset(result)
        return frozenset()

    def wall_video_ids(self, *, community_id: int, postponed: bool = False) -> frozenset[str]:
        posts = fetch_wall_posts(
            self.client,
            community_id=community_id,
            filter_name="postponed" if postponed else "owner",
        )
        result: set[str] = set()
        for post in posts:
            result.update(extract_video_ids_from_post(post))
        return frozenset(result)

    def delete_once(self, *, community_id: int, remote_id: str) -> object:
        owner_id, video_id = split_remote_id(remote_id)
        token = self.client.token_store.load_token(self.client.account_alias)
        if token.is_expired():
            from video_channel_manager.platforms.vk.client import VkApiError

            raise VkApiError(
                "VK access token is expired.",
                method="video.delete",
                code=5,
            )
        request_data = {
            "access_token": token.access_token,
            "v": self.client.api_version,
            "owner_id": str(owner_id),
            "target_id": str(-community_id),
            "video_id": str(video_id),
        }
        # Intentionally bypass VkApiClient._call: that method retries retryable
        # errors and is appropriate only for reads. A mutating request with an
        # unknown outcome must never be automatically repeated.
        return self.client._call_once("video.delete", request_data)
