from video_channel_manager.domain.enums import OperationType, PlatformName
from video_channel_manager.domain.models import ChannelRecord, CollectionRecord, VideoRecord
from video_channel_manager.platforms.base import PlatformCapabilities


class VKAdapter:
    """VK boundary. OAuth and live calls arrive after read-only YouTube inventory."""

    def capabilities(self) -> PlatformCapabilities:
        return PlatformCapabilities(
            platform=PlatformName.VK,
            readable=False,
            supported_operations=frozenset(
                {
                    OperationType.UPDATE_VIDEO_TITLE,
                    OperationType.UPDATE_VIDEO_DESCRIPTION,
                    OperationType.CREATE_COLLECTION,
                    OperationType.UPDATE_COLLECTION,
                    OperationType.ADD_TO_COLLECTION,
                    OperationType.REMOVE_FROM_COLLECTION,
                    OperationType.REORDER_COLLECTION_ITEM,
                    OperationType.SET_THUMBNAIL,
                    OperationType.TRANSFER_VIDEO,
                }
            ),
        )

    def list_channels(self) -> list[ChannelRecord]:
        raise NotImplementedError("VK OAuth and inventory are not implemented yet")

    def list_videos(self, channel_id: str) -> list[VideoRecord]:
        raise NotImplementedError("VK OAuth and inventory are not implemented yet")

    def list_collections(self, channel_id: str) -> list[CollectionRecord]:
        raise NotImplementedError("VK OAuth and inventory are not implemented yet")
