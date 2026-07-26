from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

from video_channel_manager.editorial._content_types import BANNED_CIRCLE_MARKERS

_URL_RE = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
_SIMPLE_TRAILING_URL_PUNCTUATION = ".,;:!?»”'\""
_BRACKET_PAIRS = (("(", ")"), ("[", "]"), ("{", "}"))


def _strip_trailing_url_punctuation(value: str) -> str:
    result = value.strip().rstrip(_SIMPLE_TRAILING_URL_PUNCTUATION)
    changed = True
    while result and changed:
        changed = False
        for opening, closing in _BRACKET_PAIRS:
            if result.endswith(closing) and result.count(closing) > result.count(opening):
                result = result[:-1].rstrip(_SIMPLE_TRAILING_URL_PUNCTUATION)
                changed = True
    return result


def canonicalize_url(value: str) -> str:
    raw = _strip_trailing_url_punctuation(value)
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Invalid HTTP(S) URL: {value}")
    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise ValueError(f"Invalid URL host: {value}")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"Invalid URL port: {value}") from exc
    if port is None or (scheme == "https" and port == 443) or (scheme == "http" and port == 80):
        netloc = hostname
    else:
        netloc = f"{hostname}:{port}"
    if parsed.username or parsed.password:
        raise ValueError("Credentials are not allowed in editorial URLs.")
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((scheme, netloc, path, parsed.query, ""))


def extract_urls(value: str) -> list[str]:
    return [canonicalize_url(match.group(0)) for match in _URL_RE.finditer(value)]


def balanced_emphasis(value: str) -> bool:
    return value.count("*") % 2 == 0 and value.count("_") % 2 == 0


def contains_banned_circle(value: str) -> bool:
    return any(marker in value for marker in BANNED_CIRCLE_MARKERS)
