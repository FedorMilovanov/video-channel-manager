from video_channel_manager.application.cross_platform.engine import compare_audit_packages
from video_channel_manager.application.cross_platform.models import (
    CollectionGap,
    CrossPlatformComparison,
    MatchCandidateEvidence,
    MatchConflict,
    MissingVideo,
    VideoMatch,
)
from video_channel_manager.application.cross_platform.normalize import normalize_title
from video_channel_manager.application.cross_platform.render import render_comparison_markdown

__all__ = [
    "CollectionGap",
    "CrossPlatformComparison",
    "MatchCandidateEvidence",
    "MatchConflict",
    "MissingVideo",
    "VideoMatch",
    "compare_audit_packages",
    "normalize_title",
    "render_comparison_markdown",
]
