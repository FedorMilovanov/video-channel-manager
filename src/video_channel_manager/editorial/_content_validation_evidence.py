from __future__ import annotations

from typing import Any

from video_channel_manager.editorial._content_types import (
    ALLOWED_FACT_TYPES,
    BANNED_GENERIC_PHRASES,
    DECORATIVE_MARKERS,
)
from video_channel_manager.editorial._content_urls import (
    balanced_emphasis,
    contains_banned_circle,
)
from video_channel_manager.editorial._content_validation_support import (
    _object,
    _source_validation,
    _string_field,
    _validate_string_list,
)


def validate_evidence(payload: dict[str, Any]) -> tuple[list[str], set[str]]:
    errors: list[str] = []
    source_errors, source_by_id, source_urls = _source_validation(payload)
    errors.extend(source_errors)
    source_ids = _validate_string_list(
        payload.get("source_ids"),
        location="source_ids",
        errors=errors,
    )
    if not source_ids:
        errors.append("source_ids must contain at least one source")
    if any(not item for item in source_ids):
        errors.append("source_ids cannot contain blanks")
    if len(source_ids) != len(set(source_ids)):
        errors.append("source_ids cannot contain duplicates")
    missing_source_ids = sorted(set(source_ids).difference(source_by_id))
    if missing_source_ids:
        errors.append(f"source_ids missing from sources: {', '.join(missing_source_ids)}")

    fact_raw = payload.get("fact")
    fact = _object(fact_raw)
    if not isinstance(fact_raw, dict):
        errors.append("fact must be an object")
    heading = _string_field(
        fact,
        "heading",
        location="fact",
        errors=errors,
    )
    fact_text = _string_field(
        fact,
        "text",
        location="fact",
        errors=errors,
    )
    fact_type = _string_field(
        fact,
        "fact_type",
        location="fact",
        errors=errors,
    )
    fact_source_ids = _validate_string_list(
        fact.get("source_ids"),
        location="fact.source_ids",
        errors=errors,
    )
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
    if len(fact_source_ids) != len(set(fact_source_ids)):
        errors.append("fact.source_ids cannot contain duplicates")
    missing_fact_sources = sorted(set(fact_source_ids).difference(source_ids))
    if missing_fact_sources:
        errors.append(f"fact.source_ids missing from source_ids: {', '.join(missing_fact_sources)}")
    if contains_banned_circle(heading + fact_text):
        errors.append("colored circle markers are not allowed")
    lowered_fact = fact_text.casefold()
    for phrase in BANNED_GENERIC_PHRASES:
        if phrase in lowered_fact:
            errors.append(f"generic or unsupported phrase is forbidden: {phrase}")

    question_raw = payload.get("question")
    question = _object(question_raw)
    if not isinstance(question_raw, dict):
        errors.append("question must be an object")
    lead = _string_field(
        question,
        "lead",
        location="question",
        errors=errors,
        optional=True,
    )
    question_text = _string_field(
        question,
        "text",
        location="question",
        errors=errors,
    )
    if lead and (len(lead) > 100 or not balanced_emphasis(lead)):
        errors.append("question.lead must be short and have balanced emphasis")
    if not 25 <= len(question_text) <= 320 or not question_text.endswith("?"):
        errors.append("question.text must be a specific 25-320 character question ending with ?")
    if contains_banned_circle(lead + question_text):
        errors.append("colored circle markers are not allowed")
    return errors, source_urls


__all__ = ["validate_evidence"]
