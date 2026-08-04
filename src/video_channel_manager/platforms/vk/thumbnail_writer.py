from __future__ import annotations

from typing import Any

from video_channel_manager.platforms.vk.thumbnails import VkThumbnailWriter
from video_channel_manager.platforms.vk.writer import VkWriteError


class VerifiedVkThumbnailWriter(VkThumbnailWriter):
    """Thumbnail writer with exact, retry-safe video.get postflight readback."""

    def get_video_thumbnail_state(self, *, owner_id: int, video_id: int) -> dict[str, Any]:
        if owner_id == 0 or video_id <= 0:
            raise ValueError("owner_id cannot be zero and video_id must be positive")
        response = self._call(
            "video.get",
            params={"videos": f"{owner_id}_{video_id}", "extended": False},
            retry_transient=True,
        )
        items = response.get("items") if isinstance(response, dict) else None
        if not isinstance(items, list):
            raise VkWriteError(
                "video.get thumbnail readback returned no items list.",
                method="video.get",
            )
        exact = [
            item
            for item in items
            if isinstance(item, dict) and item.get("owner_id") == owner_id and item.get("id") == video_id
        ]
        if len(exact) != 1:
            raise VkWriteError(
                f"video.get thumbnail readback returned {len(exact)} exact matches; expected one.",
                method="video.get",
            )
        return exact[0]


__all__ = ["VerifiedVkThumbnailWriter"]
