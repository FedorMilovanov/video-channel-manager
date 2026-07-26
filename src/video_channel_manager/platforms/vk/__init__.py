from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from video_channel_manager.platforms.vk.client import VkApiClient, VkApiError
from video_channel_manager.platforms.vk.lock import local_vk_write_lock
from video_channel_manager.platforms.vk.models import (
    VkAccessToken,
    VkAccount,
    VkCommunityIdentity,
    VkConfigurationError,
    VkUserIdentity,
)
from video_channel_manager.platforms.vk.service import VkInventoryService
from video_channel_manager.platforms.vk.store import VkAccountNotFoundError, VkTokenStore
from video_channel_manager.platforms.vk.text import (
    VK_VIDEO_DESCRIPTION_CAPABILITIES,
    VkDescriptionRender,
    VkTextCapabilities,
    VkTextIssue,
    render_vk_clip_description,
    render_vk_video_description,
)
from video_channel_manager.platforms.vk.text_writer import (
    VkVideoTextSnapshot,
    VkVideoTextWriter,
    canonical_vk_text,
    vk_texts_equivalent,
)
from video_channel_manager.platforms.vk.writer import VkUploadTicket, VkVideoWriter, VkWriteError

if TYPE_CHECKING:
    from video_channel_manager.platforms.vk.renderers import VKCommentRenderer, VKPostRenderer, VKVideoDescriptionRenderer

_LAZY_RENDERER_EXPORTS = frozenset({"VKCommentRenderer", "VKPostRenderer", "VKVideoDescriptionRenderer"})


def __getattr__(name: str) -> Any:
    """Avoid importing editorial renderers while low-level VK modules initialize."""

    if name in _LAZY_RENDERER_EXPORTS:
        module = import_module("video_channel_manager.platforms.vk.renderers")
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | _LAZY_RENDERER_EXPORTS)


__all__ = [
    "VKCommentRenderer",
    "VKPostRenderer",
    "VKVideoDescriptionRenderer",
    "VK_VIDEO_DESCRIPTION_CAPABILITIES",
    "VkAccessToken",
    "VkAccount",
    "VkAccountNotFoundError",
    "VkApiClient",
    "VkApiError",
    "VkCommunityIdentity",
    "VkConfigurationError",
    "VkDescriptionRender",
    "VkInventoryService",
    "VkTextCapabilities",
    "VkTextIssue",
    "VkTokenStore",
    "VkUploadTicket",
    "VkUserIdentity",
    "VkVideoTextSnapshot",
    "VkVideoTextWriter",
    "VkVideoWriter",
    "VkWriteError",
    "canonical_vk_text",
    "local_vk_write_lock",
    "render_vk_clip_description",
    "render_vk_video_description",
    "vk_texts_equivalent",
]
