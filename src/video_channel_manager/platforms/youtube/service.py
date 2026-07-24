from __future__ import annotations

from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.youtube.client import YouTubeApiClient, YouTubeApiError


class YouTubeInventoryService:
    def __init__(self, client: YouTubeApiClient) -> None:
        self.client = client

    def build_audit_package(self, channel_id: str) -> AuditPackage:
        channels = self.client.list_my_channels()
        channel = next((item for item in channels if item.ref.remote_id == channel_id), None)
        if channel is None:
            raise YouTubeApiError(
                f"Channel {channel_id} is not available to this OAuth account. Run 'youtube channels' to list choices."
            )
        videos = self.client.list_videos(channel_id)
        collections = self.client.list_collections(channel_id)
        memberships = self.client.list_memberships(
            channel_id=channel_id,
            collections=collections,
            known_video_ids={item.ref.remote_id for item in videos},
        )
        return AuditPackage(
            channel=channel,
            videos=videos,
            collections=collections,
            memberships=memberships,
            metadata={
                "source": "youtube-data-api-v3",
                "account_alias": self.client.account_alias,
                "read_only": True,
            },
        )
