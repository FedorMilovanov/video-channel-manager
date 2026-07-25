from video_channel_manager.platforms.youtube.adapter import YouTubeAdapter
from video_channel_manager.platforms.youtube.client import YouTubeApiClient, YouTubeApiError
from video_channel_manager.platforms.youtube.models import (
    ChannelIdentity,
    InstalledClientConfig,
    OAuthToken,
    YouTubeAccount,
)
from video_channel_manager.platforms.youtube.oauth import (
    InstalledOAuthFlow,
    OAuthFlowError,
    YOUTUBE_FORCE_SSL_SCOPE,
    YOUTUBE_READONLY_SCOPE,
)
from video_channel_manager.platforms.youtube.resilient_writer import YouTubeDescriptionWriter
from video_channel_manager.platforms.youtube.service import YouTubeInventoryService
from video_channel_manager.platforms.youtube.store import AccountNotFoundError, TokenStore
from video_channel_manager.platforms.youtube.writer import (
    VideoDescriptionSnapshot,
    YouTubeRevisionConflictError,
    YouTubeWriteError,
    YouTubeWriteScopeError,
    canonicalize_description,
    descriptions_equivalent,
)

__all__ = [
    "AccountNotFoundError",
    "ChannelIdentity",
    "InstalledClientConfig",
    "InstalledOAuthFlow",
    "OAuthFlowError",
    "OAuthToken",
    "TokenStore",
    "VideoDescriptionSnapshot",
    "YOUTUBE_FORCE_SSL_SCOPE",
    "YOUTUBE_READONLY_SCOPE",
    "YouTubeAccount",
    "YouTubeAdapter",
    "YouTubeApiClient",
    "YouTubeApiError",
    "YouTubeDescriptionWriter",
    "YouTubeInventoryService",
    "YouTubeRevisionConflictError",
    "YouTubeWriteError",
    "YouTubeWriteScopeError",
    "canonicalize_description",
    "descriptions_equivalent",
]
