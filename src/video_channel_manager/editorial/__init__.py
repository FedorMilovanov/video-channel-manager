"""Canonical editorial records, platform rendering, and conservative copy checks."""

from __future__ import annotations

from typing import Any

from video_channel_manager.editorial.content import (
    CANONICAL_SCHEMA_NAME,
    CANONICAL_SCHEMA_VERSION,
    EditorialContentRecord,
    parse_content_record,
    validate_content_collection,
    validate_content_record,
)
from video_channel_manager.editorial.youtube_copy_safe import (
    CopyFinding,
    CopyFix,
    autofix_youtube_description,
    validate_youtube_description,
)

_PREVIEW_EXPORTS = frozenset({"preview_payload", "preview_records", "renderer_for"})


def __getattr__(name: str) -> Any:
    """Load renderer-dependent preview helpers only when explicitly requested.

    Keeping these imports lazy prevents the package initializers for ``editorial``
    and ``platforms.youtube`` from recursively importing each other's renderer
    modules while either module is still being initialized.
    """

    if name in _PREVIEW_EXPORTS:
        from video_channel_manager.editorial import preview

        return getattr(preview, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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
