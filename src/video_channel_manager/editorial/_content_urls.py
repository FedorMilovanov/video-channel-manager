from __future__ import annotations

import re

from video_channel_manager.application.identity import canonicalize_http_url
from video_channel_manager.editorial._content_types import BANNED_CIRCLE_MARKERS

_URL_RE = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)


def canonicalize_url(value: str) -> str:
    """Compatibility value backed by the versioned URL identity contract."""
    return canonicalize_http_url(value).canonical


def extract_urls(value: str) -> list[str]:
    return [canonicalize_url(match.group(0)) for match in _URL_RE.finditer(value)]


def balanced_emphasis(value: str) -> bool:
    return value.count("*") % 2 == 0 and value.count("_") % 2 == 0


def contains_banned_circle(value: str) -> bool:
    return any(marker in value for marker in BANNED_CIRCLE_MARKERS)
