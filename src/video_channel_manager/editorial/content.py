"""Canonical editorial content contract and backward-compatible public API."""

from video_channel_manager.editorial._content_parser import parse_content_record, validate_content_collection
from video_channel_manager.editorial._content_types import (
    APPROVED_PROJECT_URLS,
    CANONICAL_SCHEMA_NAME,
    CANONICAL_SCHEMA_VERSION,
    DECORATIVE_MARKERS,
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
from video_channel_manager.editorial._project_profiles import (
    LEGENDARY_POET,
    LORD_GOD_STRENGTH,
    PROJECT_CHANNEL_IDS,
    PROJECT_KEYS,
    PROJECT_LINK_PROFILES,
    resolve_project_key,
)

__all__ = [
    "APPROVED_PROJECT_URLS",
    "CANONICAL_SCHEMA_NAME",
    "CANONICAL_SCHEMA_VERSION",
    "DECORATIVE_MARKERS",
    "EditorialContentRecord",
    "FactBlock",
    "LEGACY_YOUTUBE_SCHEMA_NAME",
    "LEGACY_YOUTUBE_SCHEMA_VERSION",
    "LEGENDARY_POET",
    "LORD_GOD_STRENGTH",
    "LinkBlock",
    "PROJECT_CHANNEL_IDS",
    "PROJECT_KEYS",
    "PROJECT_LINK_PROFILES",
    "QuestionBlock",
    "SourceLedgerEntry",
    "balanced_emphasis",
    "canonicalize_url",
    "contains_banned_circle",
    "extract_urls",
    "parse_content_record",
    "resolve_project_key",
    "validate_content_collection",
    "validate_content_record",
]
