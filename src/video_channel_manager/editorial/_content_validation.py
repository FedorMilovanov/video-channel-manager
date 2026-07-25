from __future__ import annotations

from typing import Any

from video_channel_manager.editorial._content_types import (
    ALLOWED_FACT_TYPES,
    ALLOWED_LINK_KINDS,
    ALLOWED_PROFILES,
    ALLOWED_STATUSES,
    APPROVED_PROJECT_URLS,
    BANNED_GENERIC_PHRASES,
    CANONICAL_SCHEMA_NAME,
    CANONICAL_SCHEMA_VERSION,
    DECORATIVE_MARKERS,
    LEGACY_YOUTUBE_SCHEMA_NAME,
    LEGACY_YOUTUBE_SCHEMA_VERSION,
)
from video_channel_manager.editorial._content_urls import balanced_emphasis, canonicalize_url, contains_banned_circle
from video_channel_manager.editorial._content_validation_support import (
    _object,
    _source_validation,
    _string_list,
    _valid_aware_datetime,
    _valid_stable_id,
    _validate_platform_metadata,
)


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
    if status not in ALLOWED_STATUSES:
        errors.append("unsupported editorial status")
    profile = str(payload.get("profile") or "").strip()
    if profile not in ALLOWED_PROFILES:
        errors.append("content requires a supported profile")
    variation_key = str(payload.get("variation_key") or "").strip()
    if not variation_key:
        errors.append("content requires variation_key")
    elif not _valid_stable_id(variation_key):
        errors.append("variation_key must be a stable 2-160 character identifier")
    content_id = str(payload.get("content_id") or "").strip()
    if schema_is_canonical and not content_id:
        errors.append("canonical content requires content_id")
    elif content_id and not _valid_stable_id(content_id):
        errors.append("content_id must be a stable 2-160 character identifier")
    channel_id = str(payload.get("channel_id") or "").strip()
    if expected_channel_id is not None and channel_id != expected_channel_id:
        errors.append("channel_id does not match the requested channel")
    if schema_is_legacy and not channel_id:
        errors.append("channel_id cannot be blank")
    video_id = str(payload.get("video_id") or "").strip()
    if schema_is_legacy and not video_id:
        errors.append("video_id cannot be blank")
    if status == "approved" and not _valid_aware_datetime(payload.get("reviewed_at")):
        errors.append("approved content requires a timezone-aware reviewed_at")

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
    if not any(marker in heading for marker in DECORATIVE_MARKERS):
        errors.append("fact.heading must use one contextual marker")
    if not balanced_emphasis(heading):
        errors.append("fact.heading has unbalanced emphasis markers")
    if not 100 <= len(fact_text) <= 1200:
        errors.append("fact.text must contain a substantial 100-1200 character sourced fact")
    if fact_type not in ALLOWED_FACT_TYPES:
        errors.append("fact.fact_type is unsupported")
    if not fact_source_ids:
        errors.append("fact.source_ids must contain at least one evidence source")
    missing_fact_sources = sorted(set(fact_source_ids).difference(source_ids))
    if missing_fact_sources:
        errors.append(f"fact.source_ids missing from source_ids: {', '.join(missing_fact_sources)}")
    if contains_banned_circle(heading + fact_text):
        errors.append("colored circle markers are not allowed")
    lowered_fact = fact_text.casefold()
    for phrase in BANNED_GENERIC_PHRASES:
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
        if kind not in ALLOWED_LINK_KINDS:
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
            if platform not in ALLOWED_SURFACES:
                errors.append(f"links[{index}].platforms contains unsupported platform: {platform}")
        if surfaces and not platforms:
            errors.append(f"links[{index}].surfaces requires platforms")
        for platform in platforms:
            allowed_surfaces = ALLOWED_SURFACES.get(platform)
            if allowed_surfaces is None:
                continue
            unknown_surfaces = sorted(set(surfaces).difference(allowed_surfaces))
            if unknown_surfaces:
                errors.append(
                    f"links[{index}].surfaces contains unsupported {platform} surfaces: {', '.join(unknown_surfaces)}"
                )
    if len(link_kinds) != len(set(link_kinds)):
        errors.append("links cannot repeat the same kind")

    errors.extend(_validate_platform_metadata(payload, schema_is_canonical=schema_is_canonical))
    return errors
