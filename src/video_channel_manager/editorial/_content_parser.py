from __future__ import annotations

from types import MappingProxyType
from typing import Any

from video_channel_manager.editorial._content_types import (
    CANONICAL_SCHEMA_NAME,
    CANONICAL_SCHEMA_VERSION,
    LEGACY_YOUTUBE_SCHEMA_NAME,
    EditorialContentRecord,
    FactBlock,
    LinkBlock,
    QuestionBlock,
    SourceLedgerEntry,
)
from video_channel_manager.editorial._content_validation import validate_content_record
from video_channel_manager.editorial._project_profiles import (
    LEGENDARY_POET,
    resolve_project_key,
)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value]


def _object(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


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
            str(platform): frozenset(_string_list(raw_surfaces)) for platform, raw_surfaces in raw_suitability.items()
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
    project_key = (
        resolve_project_key(
            payload,
            legacy_default=schema_name == LEGACY_YOUTUBE_SCHEMA_NAME,
        )
        or LEGENDARY_POET
    )
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
        project_key=project_key,
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
