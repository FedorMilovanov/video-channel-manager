from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit

CANONICAL_SCHEMA_NAME = "video-manager.editorial-content"
CANONICAL_SCHEMA_VERSION = 1
LEGACY_YOUTUBE_SCHEMA_NAME = "video-manager.youtube-comment-content"
LEGACY_YOUTUBE_SCHEMA_VERSION = 2

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
_ALLOWED_STATUSES = frozenset({"approved", "needs-research", "draft", "fact-check", "link-check", "rejected"})
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
        "short_form",
        "short",
        "essay",
        "historical",
        "historical_or_essay",
        "music_cover",
        "cover_or_adaptation",
        "foreign_language_adaptation",
    }
)
_ALLOWED_LINK_KINDS = frozenset(
    {
        "site",
        "playlist",
        "vk",
        "vk_album",
        "primary_text",
        "original_work",
        "full_version",
        "article",
    }
)
_ALLOWED_SURFACES = {
    "youtube": frozenset({"comment", "description"}),
    "vk": frozenset({"video_description", "post", "comment"}),
}
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
    "поэт-пророк",
    "поэты-пророки",
    "шедевр на все времена",
)


@dataclass(frozen=True, slots=True)
class SourceLedgerEntry:
    source_id: str
    title: str
    url: str | None = None
    path: str | None = None


@dataclass(frozen=True, slots=True)
class FactBlock:
    heading: str
    text: str
    fact_type: str
    source_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class QuestionBlock:
    text: str
    lead: str = ""


@dataclass(frozen=True, slots=True)
class LinkBlock:
    kind: str
    label: str
    url: str
    platforms: tuple[str, ...] = ()
    surfaces: tuple[str, ...] = ()

    def is_suitable(self, platform: str, surface: str) -> bool:
        return (not self.platforms or platform in self.platforms) and (not self.surfaces or surface in self.surfaces)


@dataclass(frozen=True, slots=True)
class EditorialContentRecord:
    schema_name: str
    schema_version: int
    origin_schema_name: str
    status: str
    profile: str
    variation_key: str
    content_id: str
    channel_id: str | None
    video_id: str | None
    video_title: str | None
    reviewed_at: str | None
    source_ids: tuple[str, ...]
    fact: FactBlock
    question: QuestionBlock
    links: tuple[LinkBlock, ...]
    sources: tuple[SourceLedgerEntry, ...]
    rendering_metadata: Mapping[str, Any]
    platform_suitability: Mapping[str, frozenset[str]]
    platform_targets: Mapping[str, str]

    def supports(self, platform: str, surface: str) -> bool:
        return surface in self.platform_suitability.get(platform, frozenset())

    def links_for(self, platform: str, surface: str) -> tuple[LinkBlock, ...]:
        return tuple(link for link in self.links if link.is_suitable(platform, surface))

    def target_for(self, platform: str, surface: str) -> str | None:
        exact = self.platform_targets.get(f"{platform}.{surface}")
        if exact:
            return exact
        return self.platform_targets.get(platform)


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
    return any(marker in value for marker in _BANNED_CIRCLE_MARKERS)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value]


def _object(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _source_validation(payload: dict[str, Any]) -> tuple[list[str], dict[str, dict[str, Any]], set[str]]:
    errors: list[str] = []
    raw_sources = payload.get("sources")
    if not isinstance(raw_sources, list):
        return ["sources must be a list"], {}, set()
    source_by_id: dict[str, dict[str, Any]] = {}
    source_urls: set[str] = set()
    for index, raw_value in enumerate(raw_sources):
        if not isinstance(raw_value, dict):
            errors.append(f"sources[{index}] must be an object")
            continue
        source_id = str(raw_value.get("source_id") or "").strip()
        if not source_id:
            errors.append(f"sources[{index}].source_id cannot be blank")
            continue
        if source_id in source_by_id:
            errors.append(f"duplicate source_id: {source_id}")
            continue
        title = str(raw_value.get("title") or "").strip()
        if not title:
            errors.append(f"source {source_id} must have a title")
        url = str(raw_value.get("url") or "").strip()
        path = str(raw_value.get("path") or "").strip()
        if bool(url) == bool(path):
            errors.append(f"source {source_id} must declare exactly one of url or path")
        if url:
            try:
                source_urls.add(canonicalize_url(url))
            except ValueError as exc:
                errors.append(f"source {source_id}: {exc}")
        if path:
            source_path = Path(path)
            if source_path.is_absolute() or ".." in source_path.parts:
                errors.append(f"source {source_id} has an unsafe repository path")
        source_by_id[source_id] = raw_value
    return errors, source_by_id, source_urls


def _validate_platform_metadata(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    suitability = payload.get("platform_suitability", {})
    if suitability is not None and not isinstance(suitability, dict):
        errors.append("platform_suitability must be an object")
    elif isinstance(suitability, dict):
        for platform, raw_surfaces in suitability.items():
            if platform not in _ALLOWED_SURFACES:
                errors.append(f"unsupported platform_suitability platform: {platform}")
                continue
            surfaces = _string_list(raw_surfaces)
            unknown = sorted(set(surfaces).difference(_ALLOWED_SURFACES[platform]))
            if unknown:
                errors.append(f"unsupported {platform} surfaces: {', '.join(unknown)}")
    rendering_metadata = payload.get("rendering_metadata", {})
    if rendering_metadata is not None and not isinstance(rendering_metadata, dict):
        errors.append("rendering_metadata must be an object")
    platform_targets = payload.get("platform_targets", {})
    if platform_targets is not None and not isinstance(platform_targets, dict):
        errors.append("platform_targets must be an object")
    elif isinstance(platform_targets, dict):
        for key, value in platform_targets.items():
            if not str(key).strip() or not str(value).strip():
                errors.append("platform_targets cannot contain blank keys or values")
    return errors


def validate_content_record(payload: dict[str, Any], *, expected_channel_id: str | None = None) -> list[str]:
    errors: list[str] = []
    schema_name = str(payload.get("schema_name") or "")
    version = payload.get("schema_version")
    schema_is_canonical = schema_name == CANONICAL_SCHEMA_NAME and version == CANONICAL_SCHEMA_VERSION
    schema_is_legacy = schema_name == LEGACY_YOUTUBE_SCHEMA_NAME and version == LEGACY_YOUTUBE_SCHEMA_VERSION
    if not schema_is_canonical and not schema_is_legacy:
        errors.append(
            f"schema must be {CANONICAL_SCHEMA_NAME} v{CANONICAL_SCHEMA_VERSION} or "
            f"{LEGACY_YOUTUBE_SCHEMA_NAME} v{LEGACY_YOUTUBE_SCHEMA_VERSION}"
        )

    status = str(payload.get("status") or "").strip()
    if status not in _ALLOWED_STATUSES:
        errors.append("unsupported editorial status")
    profile = str(payload.get("profile") or "").strip()
    if profile not in _ALLOWED_PROFILES:
        errors.append("content requires a supported profile")
    variation_key = str(payload.get("variation_key") or "").strip()
    if not variation_key:
        errors.append("content requires variation_key")
    channel_id = str(payload.get("channel_id") or "").strip()
    if expected_channel_id is not None and channel_id != expected_channel_id:
        errors.append("channel_id does not match the requested channel")
    if schema_is_legacy and not channel_id:
        errors.append("channel_id cannot be blank")
    video_id = str(payload.get("video_id") or "").strip()
    if schema_is_legacy and not video_id:
        errors.append("video_id cannot be blank")
    reviewed_at = str(payload.get("reviewed_at") or "").strip()
    if status == "approved" and not reviewed_at:
        errors.append("approved content requires reviewed_at")

    source_errors, source_by_id, source_urls = _source_validation(payload)
    errors.extend(source_errors)
    source_ids = _string_list(payload.get("source_ids"))
    if not source_ids:
        errors.append("source_ids must contain at least one source")
    if any(not item for item in source_ids):
        errors.append("source_ids cannot contain blanks")
    if len(source_ids) != len(set(source_ids)):
        errors.append("source_ids cannot contain duplicates")
    missing_source_ids = sorted(set(source_ids).difference(source_by_id))
    if missing_source_ids:
        errors.append(f"source_ids missing from sources: {', '.join(missing_source_ids)}")

    fact = _object(payload.get("fact"))
    if not fact:
        errors.append("fact must be an object")
    heading = str(fact.get("heading") or "").strip()
    fact_text = str(fact.get("text") or "").strip()
    fact_type = str(fact.get("fact_type") or "").strip()
    fact_source_ids = _string_list(fact.get("source_ids"))
    if not 5 <= len(heading) <= 100:
        errors.append("fact.heading must contain 5-100 characters")
    if not any(marker in heading for marker in _DECORATIVE_MARKERS):
        errors.append("fact.heading must use one contextual marker")
    if not balanced_emphasis(heading):
        errors.append("fact.heading has unbalanced emphasis markers")
    if not 100 <= len(fact_text) <= 1200:
        errors.append("fact.text must contain a substantial 100-1200 character sourced fact")
    if fact_type not in _ALLOWED_FACT_TYPES:
        errors.append("fact.fact_type is unsupported")
    if not fact_source_ids:
        errors.append("fact.source_ids must contain at least one evidence source")
    missing_fact_sources = sorted(set(fact_source_ids).difference(source_ids))
    if missing_fact_sources:
        errors.append(f"fact.source_ids missing from source_ids: {', '.join(missing_fact_sources)}")
    if contains_banned_circle(heading + fact_text):
        errors.append("colored circle markers are not allowed")
    lowered_fact = fact_text.casefold()
    for phrase in _BANNED_GENERIC_PHRASES:
        if phrase in lowered_fact:
            errors.append(f"generic or unsupported phrase is forbidden: {phrase}")

    question = _object(payload.get("question"))
    if not question:
        errors.append("question must be an object")
    lead = str(question.get("lead") or "").strip()
    question_text = str(question.get("text") or "").strip()
    if lead and (len(lead) > 100 or not balanced_emphasis(lead)):
        errors.append("question.lead must be short and have balanced emphasis")
    if not 25 <= len(question_text) <= 320 or not question_text.endswith("?"):
        errors.append("question.text must be a specific 25-320 character question ending with ?")
    if contains_banned_circle(lead + question_text):
        errors.append("colored circle markers are not allowed")

    raw_links = payload.get("links")
    if not isinstance(raw_links, list) or not 1 <= len(raw_links) <= 5:
        errors.append("links must contain 1-5 compact inline links")
        raw_links = []
    link_kinds: list[str] = []
    approved_urls = {canonicalize_url(item) for item in APPROVED_PROJECT_URLS}
    allowed_urls = source_urls | approved_urls
    for index, raw_value in enumerate(raw_links):
        if not isinstance(raw_value, dict):
            errors.append(f"links[{index}] must be an object")
            continue
        kind = str(raw_value.get("kind") or "").strip()
        label = str(raw_value.get("label") or "").strip()
        url = str(raw_value.get("url") or "").strip()
        link_kinds.append(kind)
        if kind not in _ALLOWED_LINK_KINDS:
            errors.append(f"links[{index}].kind is unsupported")
        if not label or "\n" in label:
            errors.append(f"links[{index}].label must be one compact line")
        if not balanced_emphasis(label):
            errors.append(f"links[{index}].label has unbalanced emphasis")
        if contains_banned_circle(label):
            errors.append("colored circle markers are not allowed")
        try:
            canonical_url = canonicalize_url(url)
        except ValueError as exc:
            errors.append(f"links[{index}].url: {exc}")
            canonical_url = ""
        if canonical_url and canonical_url not in allowed_urls:
            errors.append(f"links[{index}].url is absent from sources/project link map: {canonical_url}")
        platforms = _string_list(raw_value.get("platforms"))
        surfaces = _string_list(raw_value.get("surfaces"))
        for platform in platforms:
            if platform not in _ALLOWED_SURFACES:
                errors.append(f"links[{index}].platforms contains unsupported platform: {platform}")
        if surfaces and not platforms:
            errors.append(f"links[{index}].surfaces requires platforms")
        for platform in platforms:
            allowed_surfaces = _ALLOWED_SURFACES.get(platform)
            if allowed_surfaces is None:
                continue
            unknown_surfaces = sorted(set(surfaces).difference(allowed_surfaces))
            if unknown_surfaces:
                errors.append(
                    f"links[{index}].surfaces contains unsupported {platform} surfaces: "
                    f"{', '.join(unknown_surfaces)}"
                )
    if len(link_kinds) != len(set(link_kinds)):
        errors.append("links cannot repeat the same kind")

    errors.extend(_validate_platform_metadata(payload))
    return errors


def _default_suitability() -> dict[str, frozenset[str]]:
    return {
        "youtube": frozenset({"comment", "description"}),
        "vk": frozenset({"video_description", "post", "comment"}),
    }


def parse_content_record(
    payload: dict[str, Any],
    *,
    expected_channel_id: str | None = None,
) -> EditorialContentRecord:
    errors = validate_content_record(payload, expected_channel_id=expected_channel_id)
    if errors:
        raise ValueError("; ".join(errors))

    fact_payload = _object(payload.get("fact"))
    question_payload = _object(payload.get("question"))
    links_payload = payload.get("links")
    sources_payload = payload.get("sources")
    assert isinstance(links_payload, list)
    assert isinstance(sources_payload, list)

    links = tuple(
        LinkBlock(
            kind=str(raw["kind"]).strip(),
            label=str(raw["label"]).strip(),
            url=str(raw["url"]).strip(),
            platforms=tuple(_string_list(raw.get("platforms"))),
            surfaces=tuple(_string_list(raw.get("surfaces"))),
        )
        for raw in links_payload
        if isinstance(raw, dict)
    )
    sources = tuple(
        SourceLedgerEntry(
            source_id=str(raw["source_id"]).strip(),
            title=str(raw["title"]).strip(),
            url=str(raw.get("url") or "").strip() or None,
            path=str(raw.get("path") or "").strip() or None,
        )
        for raw in sources_payload
        if isinstance(raw, dict)
    )
    suitability = _default_suitability()
    raw_suitability = payload.get("platform_suitability")
    if isinstance(raw_suitability, dict):
        suitability = {
            str(platform): frozenset(_string_list(raw_surfaces))
            for platform, raw_surfaces in raw_suitability.items()
        }
    raw_rendering = payload.get("rendering_metadata")
    rendering_metadata = MappingProxyType(dict(raw_rendering) if isinstance(raw_rendering, dict) else {})
    raw_targets = payload.get("platform_targets")
    platform_targets = MappingProxyType(
        {str(key).strip(): str(value).strip() for key, value in raw_targets.items()}
        if isinstance(raw_targets, dict)
        else {}
    )
    video_id = str(payload.get("video_id") or "").strip() or None
    variation_key = str(payload["variation_key"]).strip()
    content_id = str(payload.get("content_id") or "").strip() or video_id or variation_key
    schema_name = str(payload.get("schema_name") or "")
    return EditorialContentRecord(
        schema_name=CANONICAL_SCHEMA_NAME,
        schema_version=CANONICAL_SCHEMA_VERSION,
        origin_schema_name=schema_name,
        status=str(payload["status"]).strip(),
        profile=str(payload["profile"]).strip(),
        variation_key=variation_key,
        content_id=content_id,
        channel_id=str(payload.get("channel_id") or "").strip() or None,
        video_id=video_id,
        video_title=str(payload.get("video_title") or "").strip() or None,
        reviewed_at=str(payload.get("reviewed_at") or "").strip() or None,
        source_ids=tuple(_string_list(payload.get("source_ids"))),
        fact=FactBlock(
            heading=str(fact_payload["heading"]).strip(),
            text=str(fact_payload["text"]).strip(),
            fact_type=str(fact_payload["fact_type"]).strip(),
            source_ids=tuple(_string_list(fact_payload.get("source_ids"))),
        ),
        question=QuestionBlock(
            lead=str(question_payload.get("lead") or "").strip(),
            text=str(question_payload["text"]).strip(),
        ),
        links=links,
        sources=sources,
        rendering_metadata=rendering_metadata,
        platform_suitability=MappingProxyType(suitability),
        platform_targets=platform_targets,
    )


def validate_content_collection(records: list[EditorialContentRecord]) -> list[str]:
    errors: list[str] = []
    seen_content_ids: set[str] = set()
    seen_variation_keys: set[str] = set()
    for record in records:
        if record.content_id in seen_content_ids:
            errors.append(f"duplicate content_id: {record.content_id}")
        seen_content_ids.add(record.content_id)
        if record.variation_key in seen_variation_keys:
            errors.append(f"duplicate variation_key: {record.variation_key}")
        seen_variation_keys.add(record.variation_key)
    return errors


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
