from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from urllib.parse import urlsplit

ARTICLE_SOURCE_LEDGER_SCHEMA = "video-manager.video-article-source-ledger"
ARTICLE_SOURCE_LEDGER_VERSION = 1
_FRONT_MATTER_VALUE_RE = re.compile(r'^([A-Za-z0-9_]+):\s*["\']?(.*?)["\']?\s*$')
_REQUIRED_EDITORIAL_RULES = (
    "facts_require_claim_source_mapping",
    "interpretation_must_be_labeled",
    "automatic_literary_rewriting",
    "publish_only_after_human_review",
)


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _required_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a nonblank string")
    return value.strip()


def _absolute_http_url(value: object, field: str) -> str:
    normalized = _required_string(value, field)
    parsed = urlsplit(normalized)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{field} must be an absolute http(s) URL")
    return normalized


def parse_article_front_matter(article_text: str) -> dict[str, str]:
    lines = article_text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("Article must begin with YAML front matter")
    try:
        closing_index = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration as exc:
        raise ValueError("Article front matter is not closed") from exc

    result: dict[str, str] = {}
    for line in lines[1:closing_index]:
        if not line or line[0].isspace() or line.lstrip().startswith("-"):
            continue
        match = _FRONT_MATTER_VALUE_RE.match(line)
        if match is None:
            continue
        key, raw_value = match.groups()
        value = raw_value.strip().strip('"').strip("'")
        result[key] = value
    return result


def validate_article_source_ledger(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("schema_name") != ARTICLE_SOURCE_LEDGER_SCHEMA:
        raise ValueError("Unexpected video article source ledger schema")
    if payload.get("schema_version") != ARTICLE_SOURCE_LEDGER_VERSION:
        raise ValueError("Unsupported video article source ledger version")

    for field in ("status", "proposed_slug", "youtube_video_id", "vk_video_id"):
        _required_string(payload.get(field), field)
    article_url = payload.get("article_url")
    if article_url is not None:
        _absolute_http_url(article_url, "article_url")

    raw_sources = payload.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise ValueError("sources must be a nonempty array")
    source_ids: set[str] = set()
    source_kinds: list[str] = []
    for index, raw_source in enumerate(raw_sources):
        if not isinstance(raw_source, dict):
            raise ValueError(f"sources[{index}] must be an object")
        source_id = _required_string(raw_source.get("source_id"), f"sources[{index}].source_id")
        if source_id in source_ids:
            raise ValueError(f"Duplicate source_id: {source_id}")
        source_ids.add(source_id)
        kind = _required_string(raw_source.get("kind"), f"sources[{index}].kind")
        source_kinds.append(kind.casefold())
        _required_string(raw_source.get("title"), f"sources[{index}].title")
        _absolute_http_url(raw_source.get("url"), f"sources[{index}].url")

    if not any("primary" in kind or "author_note" in kind for kind in source_kinds):
        raise ValueError("Source ledger must include at least one primary or author-note source")

    raw_claims = payload.get("claims")
    if not isinstance(raw_claims, list) or not raw_claims:
        raise ValueError("claims must be a nonempty array")
    claim_ids: set[str] = set()
    for index, raw_claim in enumerate(raw_claims):
        if not isinstance(raw_claim, dict):
            raise ValueError(f"claims[{index}] must be an object")
        claim_id = _required_string(raw_claim.get("claim_id"), f"claims[{index}].claim_id")
        if claim_id in claim_ids:
            raise ValueError(f"Duplicate claim_id: {claim_id}")
        claim_ids.add(claim_id)
        _required_string(raw_claim.get("claim"), f"claims[{index}].claim")
        claim_sources = raw_claim.get("source_ids")
        if not isinstance(claim_sources, list) or not claim_sources:
            raise ValueError(f"claims[{index}].source_ids must be a nonempty array")
        normalized_claim_sources = [
            _required_string(item, f"claims[{index}].source_ids") for item in claim_sources
        ]
        missing = sorted(set(normalized_claim_sources) - source_ids)
        if missing:
            raise ValueError(f"Claim {claim_id} references unknown source IDs: {missing}")

    rules = payload.get("editorial_rules")
    if not isinstance(rules, dict):
        raise ValueError("editorial_rules must be an object")
    for rule in _REQUIRED_EDITORIAL_RULES:
        value = rules.get(rule)
        if rule == "automatic_literary_rewriting":
            if value is not False:
                raise ValueError("automatic_literary_rewriting must be false")
        elif value is not True:
            raise ValueError(f"{rule} must be true")

    return {
        "claims": len(raw_claims),
        "sources": len(raw_sources),
        "ledger_sha256": canonical_sha256(payload),
    }


def validate_article_source_bundle(article_text: str, payload: dict[str, Any]) -> dict[str, Any]:
    summary = validate_article_source_ledger(payload)
    front_matter = parse_article_front_matter(article_text)
    comparisons = {
        "slug": (front_matter.get("slug"), payload.get("proposed_slug")),
        "status": (front_matter.get("status"), payload.get("status")),
        "youtube_video_id": (front_matter.get("youtube_video_id"), payload.get("youtube_video_id")),
        "vk_video_id": (front_matter.get("vk_video_id"), payload.get("vk_video_id")),
    }
    mismatches = [
        f"{field}: article={article_value!r}, ledger={ledger_value!r}"
        for field, (article_value, ledger_value) in comparisons.items()
        if article_value != ledger_value
    ]
    if mismatches:
        raise ValueError("Article/source-ledger identity mismatch: " + "; ".join(mismatches))
    return {**summary, "front_matter_fields": len(front_matter)}


__all__ = [
    "ARTICLE_SOURCE_LEDGER_SCHEMA",
    "ARTICLE_SOURCE_LEDGER_VERSION",
    "canonical_sha256",
    "parse_article_front_matter",
    "validate_article_source_bundle",
    "validate_article_source_ledger",
]
