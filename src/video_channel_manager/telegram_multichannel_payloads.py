from __future__ import annotations

from video_channel_manager.telegram_multichannel_transport import (
    GenericMessagePayload,
    GenericPhotoPayload,
    GenericPollPayload,
)
from video_channel_manager.telegram_multichannel_video import GenericVideoPayload

GenericProviderPayload = GenericMessagePayload | GenericPollPayload | GenericPhotoPayload | GenericVideoPayload

__all__ = [
    "GenericMessagePayload",
    "GenericPhotoPayload",
    "GenericPollPayload",
    "GenericProviderPayload",
    "GenericVideoPayload",
]
