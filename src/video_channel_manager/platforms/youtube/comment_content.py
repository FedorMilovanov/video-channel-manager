from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from video_channel_manager.platforms.youtube.comments import validate_comment_text

CONTENT_SCHEMA_NAME = "video-manager.youtube-comment-content"
CONTENT_SCHEMA_VERSION = 1

APPROVED_PROJECT_URLS = frozenset(
    {
        "https://thelegendarypoet.ru/",
        "https://vk.com/thelegendarypoet",
        "https://t.me/thelegendarypoet",
        "https://rutube.ru/channel/74579453/",
        "https://www.youtube.com/@TheLegendaryPoet/playlists",
        "https://www.youtube.com/playlist?list=PLy9lLJfoq3uYdxFo5bxzXEUI8HYIo-sHb",
        "https://www.youtube.com/playlist?list=PLy9lLJfoq3uaxXMvilfZIYVXsf4fY18T8",
        "https://www.youtube.com/playlist?list=PLy9lLJfoq3uaI7EGOexBWQp7WX-KVabKM",
        "https://www.youtube.com/playlist?list=PLy9lLJfoq3uapKkid7HzfXHmSi3FR2y3Q",
        "https://www.youtube.com/playlist?list=PLy9lLJfoq3ubOdGfY8orpQzGNAAvkqul5",
        "https://www.youtube.com/playlist?list=PLy9lLJfoq3ua0FhqDhByHxyaBjVrk0-pE",
        "https://www.youtube.com/playlist?list=PLy9lLJfoq3ua3Q9BQe1Dhuzn7Knbz2djU",
    }
)
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
        raise ValueError("Credentials are not allowed in comment URLs.")
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((scheme, netloc, path, parsed.query, ""))


def extract_urls(value: str) -> list[str]:
    urls: list[str] = []
    for match in _URL_RE.finditer(value):
        urls.append(canonicalize_url(match.group(0)))
    return urls


def _source_map(payload: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], set[str]]:
    raw_sources = payload.get("sources")
    if not isinstance(raw_sources, list):
        raise ValueError("sources must be a list")
    source_by_id: dict[str, dict[str, Any]] = {}
    source_urls: set[str] = set()
    for index, raw in enumerate(raw_sources):
        if not isinstance(raw, dict):
            raise ValueError(f"sources[{index}] must be an object")
        source_id = str(raw.get("source_id") or "").strip()
        if not source_id:
            raise ValueError(f"sources[{index}].source_id cannot be blank")
        if source_id in source_by_id:
            raise ValueError(f"duplicate source_id: {source_id}")
        url = str(raw.get("url") or "").strip()
        path = str(raw.get("path") or "").strip()
        if bool(url) == bool(path):
            raise ValueError(f"source {source_id} must declare exactly one of url or path")
        if url:
            source_urls.add(canonicalize_url(url))
        if path:
            source_path = Path(path)
            if source_path.is_absolute() or ".." in source_path.parts:
                raise ValueError(f"source {source_id} has an unsafe repository path")
        source_by_id[source_id] = raw
    return source_by_id, source_urls


def validate_comment_content(payload: dict[str, Any], *, expected_channel_id: str | None = None) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_name") != CONTENT_SCHEMA_NAME:
        errors.append(f"schema_name must be {CONTENT_SCHEMA_NAME}")
    if payload.get("schema_version") != CONTENT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {CONTENT_SCHEMA_VERSION}")
    if payload.get("status") not in {"approved", "needs-research", "draft", "fact-check", "link-check", "rejected"}:
        errors.append("unsupported editorial status")
    channel_id = str(payload.get("channel_id") or "").strip()
    video_id = str(payload.get("video_id") or "").strip()
    if not channel_id:
        errors.append("channel_id cannot be blank")
    if expected_channel_id is not None and channel_id != expected_channel_id:
        errors.append("channel_id does not match the requested channel")
    if not video_id:
        errors.append("video_id cannot be blank")
    reviewed_at = str(payload.get("reviewed_at") or "").strip()
    if payload.get("status") == "approved" and not reviewed_at:
        errors.append("approved content requires reviewed_at")

    try:
        comment_text = validate_comment_text(str(payload.get("comment_text") or ""))
    except ValueError as exc:
        errors.append(f"comment_text: {exc}")
        comment_text = ""

    try:
        source_by_id, source_urls = _source_map(payload)
    except ValueError as exc:
        errors.append(str(exc))
        source_by_id, source_urls = {}, set()

    raw_source_ids = payload.get("source_ids")
    if not isinstance(raw_source_ids, list) or not raw_source_ids:
        errors.append("source_ids must contain at least one source")
        source_ids: list[str] = []
    else:
        source_ids = [str(item).strip() for item in raw_source_ids]
        if any(not item for item in source_ids):
            errors.append("source_ids cannot contain blanks")
        if len(source_ids) != len(set(source_ids)):
            errors.append("source_ids cannot contain duplicates")
    missing_source_ids = sorted(set(source_ids).difference(source_by_id))
    if missing_source_ids:
        errors.append(f"source_ids missing from sources: {', '.join(missing_source_ids)}")

    approved_urls = {canonicalize_url(item) for item in APPROVED_PROJECT_URLS}
    allowed_urls = source_urls | approved_urls
    try:
        comment_urls = extract_urls(comment_text)
    except ValueError as exc:
        errors.append(str(exc))
        comment_urls = []
    unapproved_urls = sorted(set(comment_urls).difference(allowed_urls))
    if unapproved_urls:
        errors.append(f"comment contains URLs absent from sources/project link map: {', '.join(unapproved_urls)}")
    return errors


__all__ = [
    "APPROVED_PROJECT_URLS",
    "CONTENT_SCHEMA_NAME",
    "CONTENT_SCHEMA_VERSION",
    "canonicalize_url",
    "extract_urls",
    "validate_comment_content",
]
