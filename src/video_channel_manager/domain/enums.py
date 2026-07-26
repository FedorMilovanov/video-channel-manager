from enum import StrEnum


class PlatformName(StrEnum):
    YOUTUBE = "youtube"
    VK = "vk"
    LOCAL = "local"


class ChannelKind(StrEnum):
    VIDEO_CHANNEL = "video_channel"
    COMMUNITY = "community"
    LOCAL_LIBRARY = "local_library"


class CollectionKind(StrEnum):
    PLAYLIST = "playlist"
    VIDEO_ALBUM = "video_album"
    LOCAL_FOLDER = "local_folder"


class RiskLevel(StrEnum):
    READ_ONLY = "read_only"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    DESTRUCTIVE = "destructive"


class OperationType(StrEnum):
    UPDATE_VIDEO_TITLE = "update_video_title"
    UPDATE_VIDEO_DESCRIPTION = "update_video_description"
    REPLACE_DESCRIPTION_TEXT = "replace_description_text"
    ADD_DESCRIPTION_BLOCK = "add_description_block"
    REMOVE_DESCRIPTION_BLOCK = "remove_description_block"
    CREATE_COLLECTION = "create_collection"
    UPDATE_COLLECTION = "update_collection"
    ADD_TO_COLLECTION = "add_to_collection"
    REMOVE_FROM_COLLECTION = "remove_from_collection"
    REORDER_COLLECTION_ITEM = "reorder_collection_item"
    SET_THUMBNAIL = "set_thumbnail"
    CHANGE_PRIVACY = "change_privacy"
    TRANSFER_VIDEO = "transfer_video"
    DELETE_VIDEO = "delete_video"
    DELETE_COLLECTION = "delete_collection"


DESTRUCTIVE_OPERATIONS: frozenset[OperationType] = frozenset(
    {
        OperationType.DELETE_VIDEO,
        OperationType.DELETE_COLLECTION,
    }
)

MUTATING_EXISTING_TARGET_OPERATIONS: frozenset[OperationType] = frozenset(
    {
        OperationType.UPDATE_VIDEO_TITLE,
        OperationType.UPDATE_VIDEO_DESCRIPTION,
        OperationType.REPLACE_DESCRIPTION_TEXT,
        OperationType.ADD_DESCRIPTION_BLOCK,
        OperationType.REMOVE_DESCRIPTION_BLOCK,
        OperationType.UPDATE_COLLECTION,
        OperationType.ADD_TO_COLLECTION,
        OperationType.REMOVE_FROM_COLLECTION,
        OperationType.REORDER_COLLECTION_ITEM,
        OperationType.SET_THUMBNAIL,
        OperationType.CHANGE_PRIVACY,
        OperationType.DELETE_VIDEO,
        OperationType.DELETE_COLLECTION,
    }
)
