from __future__ import annotations

from video_channel_manager.domain.enums import ChannelKind, PlatformName
from video_channel_manager.domain.models import ChannelRecord, RemoteRef
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk.client import VkApiClient
from video_channel_manager.platforms.vk.models import VkCommunityIdentity


class VkInventoryService:
    def __init__(self, client: VkApiClient) -> None:
        self.client = client

    def _build_from_channel(self, channel: ChannelRecord) -> AuditPackage:
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

    def build_audit_package(self, community: str | int) -> AuditPackage:
        """Discover a community through VK and then read its complete inventory."""

        return self._build_from_channel(self.client.get_community(community))

    def build_audit_package_for_known_community(
        self,
        community: VkCommunityIdentity,
    ) -> AuditPackage:
        """Read inventory for an exact community already bound in the local registry.

        Project-bound production paths do not need a redundant groups.getById
        discovery call after the account registry and immutable runtime have
        already selected one exact community ID.
        """

        community_id = int(community.community_id)
        channel = ChannelRecord(
            ref=RemoteRef(
                platform=PlatformName.VK,
                channel_id=str(community_id),
                remote_id=str(community_id),
            ),
            title=community.title,
            kind=ChannelKind.COMMUNITY,
            url=community.url,
            metadata={
                "owner_id": -community_id,
                "managed_by_token": True,
                "identity_source": "local_account_registry",
                "screen_name": community.screen_name,
            },
        )
        return self._build_from_channel(channel)
