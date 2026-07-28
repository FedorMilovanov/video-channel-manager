from __future__ import annotations

from video_channel_manager.platforms.vk.text_writer import (
    VkVideoTextWriter,
    vk_edit_response_succeeded,
)
from video_channel_manager.platforms.vk.writer import VkWriteError


class VkEditorialWriter(VkVideoTextWriter):
    """Guarded writer limited to VK video text and video-album title edits."""

    def rename_album(self, *, community_id: int, album_id: int, title: str) -> None:
        target_title = title.strip()
        if community_id <= 0 or album_id <= 0 or not target_title:
            raise ValueError("community_id/album_id must be positive and album title cannot be blank")
        response = self._call(
            "video.editAlbum",
            params={
                "group_id": community_id,
                "album_id": album_id,
                "title": target_title,
            },
        )
        if not vk_edit_response_succeeded(response):
            raise VkWriteError(
                f"video.editAlbum returned an unexpected response: {response!r}",
                method="video.editAlbum",
            )


__all__ = ["VkEditorialWriter"]
