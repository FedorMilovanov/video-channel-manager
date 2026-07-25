"""Deterministic editorial checks and conservative copy fixes for platform copy."""

from video_channel_manager.editorial.youtube_copy_safe import (
    CopyFinding,
    CopyFix,
    autofix_youtube_description,
    validate_youtube_description,
)

__all__ = [
    "CopyFinding",
    "CopyFix",
    "autofix_youtube_description",
    "validate_youtube_description",
]
