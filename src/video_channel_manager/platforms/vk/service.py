from __future__ import annotations

from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk.client import VkApiClient


class VkInventoryService:
    def __init__(self, client: VkApiClient) -> None:
        self.client = client

    def build_audit_package(self, community: str | int) -> AuditPackage:
        channel = self.client.get_community(community)
        community_id = int(channel.ref.channel_id)
        videos = self.client.list_videos(community_id)
        collections = self.client.list_collections(community_id)
        memberships = self.client.list_memberships(
            community_id=community_id,
            collections=collections,
            known_video_ids={item.ref.remote_id for item in videos},
        )
        return AuditPackage(
            channel=channel,
            videos=videos,
            collections=collections,
            memberships=memberships,
            metadata={
                "source": "vk-api",
                "api_version": self.client.api_version,
                "account_alias": self.client.account_alias,
                "read_only": True,
                "system_albums_included": True,
                "system_albums_are_not_editorial_collections": True,
            },
        )
