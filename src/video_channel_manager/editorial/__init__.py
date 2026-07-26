"""Canonical editorial records, platform rendering, and conservative copy checks."""

from video_channel_manager.editorial.content import (
    CANONICAL_SCHEMA_NAME,
    CANONICAL_SCHEMA_VERSION,
    EditorialContentRecord,
    parse_content_record,
    validate_content_collection,
    validate_content_record,
)
from video_channel_manager.editorial.preview import preview_payload, preview_records, renderer_for
from video_channel_manager.editorial.youtube_copy_safe import (
    CopyFinding,
    CopyFix,
    autofix_youtube_description,
    validate_youtube_description,
)

__all__ = [
    "CANONICAL_SCHEMA_NAME",
    "CANONICAL_SCHEMA_VERSION",
    "CopyFinding",
    "CopyFix",
    "EditorialContentRecord",
    "autofix_youtube_description",
    "parse_content_record",
    "preview_payload",
    "preview_records",
    "renderer_for",
    "validate_content_collection",
    "validate_content_record",
    "validate_youtube_description",
]
