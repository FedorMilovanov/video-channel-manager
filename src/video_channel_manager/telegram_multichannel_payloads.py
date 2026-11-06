from __future__ import annotations

from video_channel_manager.telegram_multichannel_transport import (
    GenericMessagePayload,
    GenericPhotoPayload,
    GenericRichPhotoPayload,
    GenericPollPayload,
)
from video_channel_manager.telegram_multichannel_video import GenericVideoPayload

GenericProviderPayload = (
    GenericMessagePayload | GenericPollPayload | GenericPhotoPayload | GenericRichPhotoPayload | GenericVideoPayload
)

__all__ = [
    "GenericMessagePayload",
    "GenericPhotoPayload",
    "GenericRichPhotoPayload",
    "GenericPollPayload",
    "GenericProviderPayload",
    "GenericVideoPayload",
]
