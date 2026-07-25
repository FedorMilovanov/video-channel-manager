"""Canonical editorial content contract and backward-compatible public API."""

from video_channel_manager.editorial._content_parser import parse_content_record, validate_content_collection
from video_channel_manager.editorial._content_types import (
    APPROVED_PROJECT_URLS,
    CANONICAL_SCHEMA_NAME,
    CANONICAL_SCHEMA_VERSION,
    LEGACY_YOUTUBE_SCHEMA_NAME,
    LEGACY_YOUTUBE_SCHEMA_VERSION,
    EditorialContentRecord,
    FactBlock,
    LinkBlock,
    QuestionBlock,
    SourceLedgerEntry,
)
from video_channel_manager.editorial._content_urls import (
    balanced_emphasis,
    canonicalize_url,
    contains_banned_circle,
    extract_urls,
)
from video_channel_manager.editorial._content_validation import validate_content_record

__all__ = [
    "APPROVED_PROJECT_URLS",
    "CANONICAL_SCHEMA_NAME",
    "CANONICAL_SCHEMA_VERSION",
    "EditorialContentRecord",
    "FactBlock",
    "LEGACY_YOUTUBE_SCHEMA_NAME",
    "LEGACY_YOUTUBE_SCHEMA_VERSION",
    "LinkBlock",
    "QuestionBlock",
    "SourceLedgerEntry",
    "balanced_emphasis",
    "canonicalize_url",
    "contains_banned_circle",
    "extract_urls",
    "parse_content_record",
    "validate_content_collection",
    "validate_content_record",
]
