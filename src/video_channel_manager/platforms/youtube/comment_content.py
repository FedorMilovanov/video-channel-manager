from __future__ import annotations

from pathlib import Path
from typing import Any

from video_channel_manager.editorial.content import (
    APPROVED_PROJECT_URLS,
    LEGACY_YOUTUBE_SCHEMA_NAME,
    LEGACY_YOUTUBE_SCHEMA_VERSION,
    balanced_emphasis,
    canonicalize_url,
    contains_banned_circle,
    extract_urls,
    parse_content_record,
    validate_content_record,
)
from video_channel_manager.platforms.youtube.comments import validate_comment_text
from video_channel_manager.platforms.youtube.labels import (
    ACCEPTED_VK_COMMUNITY_LABELS,
    CANONICAL_VK_COMMUNITY_LABEL,
)
from video_channel_manager.platforms.youtube.renderers import YouTubeCommentRenderer

CONTENT_SCHEMA_NAME = LEGACY_YOUTUBE_SCHEMA_NAME
CONTENT_SCHEMA_VERSION = LEGACY_YOUTUBE_SCHEMA_VERSION
SUPPORTED_CONTENT_SCHEMA_VERSIONS = frozenset({1, 2})

_ALLOWED_PROFILES = frozenset(
    {"long_form_poetry", "historical_or_essay", "cover_or_adaptation", "foreign_language_adaptation", "short"}
)
_ALLOWED_LINK_KINDS = frozenset({"site", "playlist", "vk", "primary_text", "original_work", "full_version"})
_BANNED_CIRCLE_MARKERS = frozenset({"🔵", "🔴", "🟢", "🟡", "🟠", "🟣", "⚫", "⚪", "🟤"})
_DECORATIVE_MARKERS = ("📖", "📌", "🎧", "📚", "❄️", "⚔️", "🌊", "🎭", "📝", "🎼", "🕯️", "🗂️")


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


def _render_v2(payload: dict[str, Any]) -> str:
    record = parse_content_record(payload)
    return validate_comment_text(YouTubeCommentRenderer().render(record).text)


def render_comment_content(payload: dict[str, Any]) -> str:
    version = payload.get("schema_version")
    if version == 1:
        return validate_comment_text(str(payload.get("comment_text") or ""))
    if version == 2:
        return _render_v2(payload)
    raise ValueError(f"Unsupported comment content schema version: {version}")


def _validate_v2_youtube_rules(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    profile = str(payload.get("profile") or "").strip()
    if profile not in _ALLOWED_PROFILES:
        errors.append("schema v2 requires a supported profile")
    if not str(payload.get("variation_key") or "").strip():
        errors.append("schema v2 requires variation_key")

    fact = payload.get("fact")
    if not isinstance(fact, dict):
        return errors + ["schema v2 fact must be an object"]
    heading = str(fact.get("heading") or "").strip()
    fact_text = str(fact.get("text") or "").strip()
    if not 5 <= len(heading) <= 90:
        errors.append("fact.heading must contain 5-90 characters")
    if "*" not in heading and "_" not in heading:
        errors.append("fact.heading must use restrained bold or italic emphasis")
    if not balanced_emphasis(heading):
        errors.append("fact.heading has unbalanced emphasis markers")
    if not 100 <= len(fact_text) <= 900:
        errors.append("fact.text must contain a substantial 100-900 character sourced fact")
    if contains_banned_circle(heading + fact_text):
        errors.append("colored circle markers are not allowed")

    question = payload.get("question")
    if not isinstance(question, dict):
        errors.append("schema v2 question must be an object")
    else:
        lead = str(question.get("lead") or "").strip()
        question_text = str(question.get("text") or "").strip()
        if lead and (len(lead) > 80 or not balanced_emphasis(lead)):
            errors.append("question.lead must be short and have balanced emphasis")
        if not 25 <= len(question_text) <= 280 or not question_text.endswith("?"):
            errors.append("question.text must be a specific 25-280 character question ending with ?")

    links = payload.get("links")
    if not isinstance(links, list) or not 2 <= len(links) <= 4:
        errors.append("links must contain 2-4 compact inline links")
        links = []
    link_kinds: list[str] = []
    for index, raw in enumerate(links):
        if not isinstance(raw, dict):
            errors.append(f"links[{index}] must be an object")
            continue
        kind = str(raw.get("kind") or "").strip()
        label = str(raw.get("label") or "").strip()
        link_kinds.append(kind)
        if kind not in _ALLOWED_LINK_KINDS:
            errors.append(f"links[{index}].kind is unsupported")
        if kind == "site" and not (label.startswith("📌 ") and "*" in label):
            errors.append("site link label must use the compact 📌 bold style")
        if kind == "playlist" and not (label.startswith("🎧 ") and "*" in label):
            errors.append("playlist link label must use the compact 🎧 bold style")
        if kind == "vk" and label not in ACCEPTED_VK_COMMUNITY_LABELS:
            errors.append(f"VK link label must be exactly {CANONICAL_VK_COMMUNITY_LABEL}")
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


def _validate_legacy_v1(payload: dict[str, Any], *, expected_channel_id: str | None) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_name") != CONTENT_SCHEMA_NAME:
        errors.append(f"schema_name must be {CONTENT_SCHEMA_NAME}")
    status = payload.get("status")
    if status not in {"approved", "needs-research", "draft", "fact-check", "link-check", "rejected"}:
        errors.append("unsupported editorial status")
    channel_id = str(payload.get("channel_id") or "").strip()
    video_id = str(payload.get("video_id") or "").strip()
    if not channel_id:
        errors.append("channel_id cannot be blank")
    if expected_channel_id is not None and channel_id != expected_channel_id:
        errors.append("channel_id does not match the requested channel")
    if not video_id:
        errors.append("video_id cannot be blank")
    if status == "approved" and not str(payload.get("reviewed_at") or "").strip():
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


def validate_comment_content(payload: dict[str, Any], *, expected_channel_id: str | None = None) -> list[str]:
    version = payload.get("schema_version")
    if version == 1:
        return _validate_legacy_v1(payload, expected_channel_id=expected_channel_id)
    if version != 2:
        return [f"schema_version must be one of {sorted(SUPPORTED_CONTENT_SCHEMA_VERSIONS)}"]
    errors = validate_content_record(payload, expected_channel_id=expected_channel_id)
    errors.extend(_validate_v2_youtube_rules(payload))
    return list(dict.fromkeys(errors))


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
