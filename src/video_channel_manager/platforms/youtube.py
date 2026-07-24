from video_channel_manager.domain.enums import OperationType, PlatformName
from video_channel_manager.domain.models import ChannelRecord, CollectionRecord, VideoRecord
from video_channel_manager.platforms.base import PlatformCapabilities


class YouTubeAdapter:
    """YouTube boundary. OAuth and live calls arrive in the next milestone."""

    def capabilities(self) -> PlatformCapabilities:
        return PlatformCapabilities(
            platform=PlatformName.YOUTUBE,
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
                    OperationType.CHANGE_PRIVACY,
                }
            ),
        )

    def list_channels(self) -> list[ChannelRecord]:
        raise NotImplementedError("YouTube OAuth and inventory are not implemented yet")

    def list_videos(self, channel_id: str) -> list[VideoRecord]:
        raise NotImplementedError("YouTube OAuth and inventory are not implemented yet")

    def list_collections(self, channel_id: str) -> list[CollectionRecord]:
        raise NotImplementedError("YouTube OAuth and inventory are not implemented yet")
