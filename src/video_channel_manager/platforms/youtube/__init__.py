from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from video_channel_manager.platforms.youtube.adapter import YouTubeAdapter
from video_channel_manager.platforms.youtube.client import YouTubeApiClient, YouTubeApiError
from video_channel_manager.platforms.youtube.comments import (
    TopLevelCommentSnapshot,
    VideoIdentity,
    YouTubeCommentConflictError,
    YouTubeCommentError,
    YouTubeCommentWriter,
    YouTubeCommentsDisabledError,
    canonicalize_comment_text,
    comment_text_sha256,
    comments_equivalent,
    validate_comment_text,
)
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

if TYPE_CHECKING:
    from video_channel_manager.platforms.youtube.renderers import YouTubeCommentRenderer, YouTubeDescriptionRenderer

_LAZY_RENDERER_EXPORTS = frozenset({"YouTubeCommentRenderer", "YouTubeDescriptionRenderer"})


def __getattr__(name: str) -> Any:
    """Avoid importing editorial renderers while low-level YouTube modules initialize."""

    if name in _LAZY_RENDERER_EXPORTS:
        module = import_module("video_channel_manager.platforms.youtube.renderers")
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | _LAZY_RENDERER_EXPORTS)


__all__ = [
    "AccountNotFoundError",
    "ChannelIdentity",
    "InstalledClientConfig",
    "InstalledOAuthFlow",
    "OAuthFlowError",
    "OAuthToken",
    "TokenStore",
    "TopLevelCommentSnapshot",
    "VideoDescriptionSnapshot",
    "VideoIdentity",
    "YOUTUBE_FORCE_SSL_SCOPE",
    "YOUTUBE_READONLY_SCOPE",
    "YouTubeAccount",
    "YouTubeAdapter",
    "YouTubeApiClient",
    "YouTubeApiError",
    "YouTubeCommentConflictError",
    "YouTubeCommentError",
    "YouTubeCommentRenderer",
    "YouTubeCommentWriter",
    "YouTubeCommentsDisabledError",
    "YouTubeDescriptionRenderer",
    "YouTubeDescriptionWriter",
    "YouTubeInventoryService",
    "YouTubeRevisionConflictError",
    "YouTubeWriteError",
    "YouTubeWriteScopeError",
    "canonicalize_comment_text",
    "canonicalize_description",
    "comment_text_sha256",
    "comments_equivalent",
    "descriptions_equivalent",
    "validate_comment_text",
]
