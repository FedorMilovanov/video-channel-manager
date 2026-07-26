from __future__ import annotations

from video_channel_manager.domain.enums import PlatformName
from video_channel_manager.domain.models import ChannelRecord, CollectionRecord, VideoRecord
from video_channel_manager.platforms.base import PlatformCapabilities
from video_channel_manager.platforms.youtube.client import YouTubeApiClient


class YouTubeAdapter:
    """Current YouTube adapter is deliberately read-only."""

    def __init__(self, client: YouTubeApiClient) -> None:
        self.client = client

    def capabilities(self) -> PlatformCapabilities:
        return PlatformCapabilities(platform=PlatformName.YOUTUBE, readable=True, supported_operations=frozenset())

    def list_channels(self) -> list[ChannelRecord]:
        return self.client.list_my_channels()

    def list_videos(self, channel_id: str) -> list[VideoRecord]:
        return self.client.list_videos(channel_id)

    def list_collections(self, channel_id: str) -> list[CollectionRecord]:
        return self.client.list_collections(channel_id)
