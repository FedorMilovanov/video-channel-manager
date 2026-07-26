"""Canonical editorial records, platform rendering, and conservative copy checks."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

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

if TYPE_CHECKING:
    from video_channel_manager.editorial.preview import preview_payload, preview_records, renderer_for

_LAZY_PREVIEW_EXPORTS = frozenset({"preview_payload", "preview_records", "renderer_for"})


def __getattr__(name: str) -> Any:
    """Load platform-dependent preview helpers only when they are requested."""

    if name in _LAZY_PREVIEW_EXPORTS:
        module = import_module("video_channel_manager.editorial.preview")
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | _LAZY_PREVIEW_EXPORTS)


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
