from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from video_channel_manager.platforms.youtube.comments import validate_comment_text

CONTENT_SCHEMA_NAME = "video-manager.youtube-comment-content"
CONTENT_SCHEMA_VERSION = 2
SUPPORTED_CONTENT_SCHEMA_VERSIONS = frozenset({1, 2})

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
        "https://www.youtube.com/playlist?list=PLKzLtO0ERdzg",
        "https://www.youtube.com/playlist?list=PLy9lLJfoq3uYTrhcN1TDMUeks46Y-TT_M",
        "https://www.youtube.com/playlist?list=PLy9lLJfoq3ua1QeVsZutwScsM0l-asll4",
        "https://www.youtube.com/playlist?list=PLy9lLJfoq3uZcrWY0F3Qux93xos6kIS7-",
    }
)
_URL_RE = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
_SIMPLE_TRAILING_URL_PUNCTUATION = ".,;:!?»”'\""
_BRACKET_PAIRS = (("(", ")"), ("[", "]"), ("{", "}"))
_ALLOWED_FACT_TYPES = frozenset(
    {
        "composition_history",
        "first_publication",
        "manuscript_history",
        "textual_structure",
        "archival_provenance",
        "documented_context",
        "adaptation_history",
        "performance_history",
    }
)
_ALLOWED_PROFILES = frozenset(
    {
        "long_form_poetry",
        "historical_or_essay",
        "cover_or_adaptation",
        "foreign_language_adaptation",
        "short",
    }
)
_ALLOWED_LINK_KINDS = frozenset({"site", "playlist", "vk", "primary_text", "original_work", "full_version"})
_BANNED_CIRCLE_MARKERS = frozenset({"🔵", "🔴", "🟢", "🟡", "🟠", "🟣", "⚫", "⚪", "🟤"})
_DECORATIVE_MARKERS = ("📖", "📌", "🎧", "📚", "❄️", "⚔️", "🌊", "🎭", "📝", "🎼", "🕯️", "🗂️")
_BANNED_GENERIC_PHRASES = (
    "великое вечное произведение",
    "актуально как никогда",
    "говорит с каждым из нас",
    "невероятное путешествие",
    "один из величайших шедевров",
    "пророческое произведение",
    "поэт предсказал",
)


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


def _balanced_emphasis(value: str) -> bool:
    return value.count("*") % 2 == 0 and value.count("_") % 2 == 0


def _contains_banned_circle(value: str) -> bool:
    return any(marker in value for marker in _BANNED_CIRCLE_MARKERS)


def _render_v2(payload: dict[str, Any]) -> str:
    fact = payload.get("fact")
    question = payload.get("question")
    links = payload.get("links")
    if not isinstance(fact, dict) or not isinstance(question, dict) or not isinstance(links, list):
        raise ValueError("schema v2 requires fact, question, and links")

    heading = str(fact.get("heading") or "").strip()
    fact_text = str(fact.get("text") or "").strip()
    lead = str(question.get("lead") or "").strip()
    question_text = str(question.get("text") or "").strip()

    paragraphs = [heading, fact_text]
    paragraphs.append(f"{lead} {question_text}".strip())

    link_lines: list[str] = []
    for raw in links:
        if not isinstance(raw, dict):
            continue
        label = str(raw.get("label") or "").strip()
        url = str(raw.get("url") or "").strip()
        link_lines.append(f"{label} {url}".strip())
    paragraphs.append("\n".join(link_lines))
    return "\n\n".join(item for item in paragraphs if item).strip()


def render_comment_content(payload: dict[str, Any]) -> str:
    version = payload.get("schema_version")
    if version == 1:
        return validate_comment_text(str(payload.get("comment_text") or ""))
    if version == 2:
        return validate_comment_text(_render_v2(payload))
    raise ValueError(f"Unsupported comment content schema version: {version}")


def _validate_v2_structure(payload: dict[str, Any], source_ids: list[str]) -> list[str]:
    errors: list[str] = []
    variation_key = str(payload.get("variation_key") or "").strip()
    profile = str(payload.get("profile") or "").strip()
    if not variation_key:
        errors.append("schema v2 requires variation_key")
    if profile not in _ALLOWED_PROFILES:
        errors.append("schema v2 requires a supported profile")

    fact = payload.get("fact")
    if not isinstance(fact, dict):
        errors.append("schema v2 fact must be an object")
        fact = {}
    heading = str(fact.get("heading") or "").strip()
    fact_text = str(fact.get("text") or "").strip()
    fact_type = str(fact.get("fact_type") or "").strip()
    fact_source_ids_raw = fact.get("source_ids")
    fact_source_ids = (
        [str(item).strip() for item in fact_source_ids_raw]
        if isinstance(fact_source_ids_raw, list)
        else []
    )
    if not 5 <= len(heading) <= 90:
        errors.append("fact.heading must contain 5-90 characters")
    if not any(marker in heading for marker in _DECORATIVE_MARKERS):
        errors.append("fact.heading must use one contextual marker")
    if "*" not in heading and "_" not in heading:
        errors.append("fact.heading must use restrained bold or italic emphasis")
    if not _balanced_emphasis(heading):
        errors.append("fact.heading has unbalanced emphasis markers")
    if not 100 <= len(fact_text) <= 900:
        errors.append("fact.text must contain a substantial 100-900 character sourced fact")
    if fact_type not in _ALLOWED_FACT_TYPES:
        errors.append("fact.fact_type is unsupported")
    if not fact_source_ids:
        errors.append("fact.source_ids must contain at least one evidence source")
    missing_fact_sources = sorted(set(fact_source_ids).difference(source_ids))
    if missing_fact_sources:
        errors.append(f"fact.source_ids missing from source_ids: {', '.join(missing_fact_sources)}")
    if _contains_banned_circle(heading + fact_text):
        errors.append("colored circle markers are not allowed")
    if not _balanced_emphasis(fact_text):
        errors.append("fact.text has unbalanced emphasis markers")
    lowered_fact = fact_text.casefold()
    for phrase in _BANNED_GENERIC_PHRASES:
        if phrase in lowered_fact:
            errors.append(f"generic or unsupported phrase is forbidden: {phrase}")

    question = payload.get("question")
    if not isinstance(question, dict):
        errors.append("schema v2 question must be an object")
        question = {}
    lead = str(question.get("lead") or "").strip()
    question_text = str(question.get("text") or "").strip()
    if lead and (len(lead) > 80 or not _balanced_emphasis(lead)):
        errors.append("question.lead must be short and have balanced emphasis")
    if not 25 <= len(question_text) <= 280 or not question_text.endswith("?"):
        errors.append("question.text must be a specific 25-280 character question ending with ?")
    if _contains_banned_circle(lead + question_text):
        errors.append("colored circle markers are not allowed")

    links = payload.get("links")
    link_kinds: list[str] = []
    if not isinstance(links, list) or not 2 <= len(links) <= 4:
        errors.append("links must contain 2-4 compact inline links")
        links = []
    for index, raw in enumerate(links):
        if not isinstance(raw, dict):
            errors.append(f"links[{index}] must be an object")
            continue
        kind = str(raw.get("kind") or "").strip()
        label = str(raw.get("label") or "").strip()
        url = str(raw.get("url") or "").strip()
        link_kinds.append(kind)
        if kind not in _ALLOWED_LINK_KINDS:
            errors.append(f"links[{index}].kind is unsupported")
        if not label or "\n" in label:
            errors.append(f"links[{index}].label must be one compact line")
        if not _balanced_emphasis(label):
            errors.append(f"links[{index}].label has unbalanced emphasis")
        if _contains_banned_circle(label):
            errors.append("colored circle markers are not allowed")
        try:
            canonicalize_url(url)
        except ValueError as exc:
            errors.append(f"links[{index}].url: {exc}")
        if kind == "site" and not (label.startswith("📌 ") and "*" in label):
            errors.append("site link label must use the compact 📌 bold style")
        if kind == "playlist" and not (label.startswith("🎧 ") and "*" in label):
            errors.append("playlist link label must use the compact 🎧 bold style")
        if kind == "vk" and label != "*Сообщество проекта VK:*":
            errors.append("VK link label must be exactly *Сообщество проекта VK:*")
        if kind == "primary_text" and not (label.startswith("📚 ") and ("*" in label or "_" in label)):
            errors.append("primary-text link label must use the compact 📚 emphasized style")
    if len(link_kinds) != len(set(link_kinds)):
        errors.append("links cannot repeat the same kind")
    required_kinds = {"site", "vk"}
    if profile in {"long_form_poetry", "cover_or_adaptation", "foreign_language_adaptation"}:
        required_kinds.add("playlist")
    if profile == "short":
        required_kinds.add("full_version")
    missing_link_kinds = sorted(required_kinds.difference(link_kinds))
    if missing_link_kinds:
        errors.append(f"profile {profile} is missing link kinds: {', '.join(missing_link_kinds)}")

    try:
        rendered = _render_v2(payload)
    except ValueError as exc:
        errors.append(str(exc))
        rendered = ""
    if rendered:
        lines = [line.strip() for line in rendered.splitlines() if line.strip()]
        if any(line in _BANNED_CIRCLE_MARKERS or line in _DECORATIVE_MARKERS for line in lines):
            errors.append("standalone emoji-only lines are not allowed")
        marker_count = sum(rendered.count(marker) for marker in _DECORATIVE_MARKERS)
        if marker_count > 4:
            errors.append("comment uses more than four decorative markers")
    return errors


def validate_comment_content(payload: dict[str, Any], *, expected_channel_id: str | None = None) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_name") != CONTENT_SCHEMA_NAME:
        errors.append(f"schema_name must be {CONTENT_SCHEMA_NAME}")
    version = payload.get("schema_version")
    if version not in SUPPORTED_CONTENT_SCHEMA_VERSIONS:
        errors.append(f"schema_version must be one of {sorted(SUPPORTED_CONTENT_SCHEMA_VERSIONS)}")
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

    if version == 2:
        errors.extend(_validate_v2_structure(payload, source_ids))

    try:
        comment_text = render_comment_content(payload)
    except ValueError as exc:
        errors.append(f"comment_text: {exc}")
        comment_text = ""

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
    "SUPPORTED_CONTENT_SCHEMA_VERSIONS",
    "canonicalize_url",
    "extract_urls",
    "render_comment_content",
    "validate_comment_content",
]
