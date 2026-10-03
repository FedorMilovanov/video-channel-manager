from __future__ import annotations

import argparse
import ipaddress
import json
from datetime import date
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from video_channel_manager.telegram_models import SHA256_PATTERN
from video_channel_manager.telegram_quote_depth import (
    DEPTH_QUEUE_DIGEST,
    DEPTH_RELEASE_ID,
    load_depth_audit,
    load_depth_replacements,
)
from video_channel_manager.telegram_quote_successor import load_successor_corpus

EXPECTED_FUTURE_SEQUENCES = tuple(range(16, 61))
CORE_SOURCE_FAMILIES = frozenset({"ccel.org", "newadvent.org", "spurgeon.org", "ligonier.org", "gty.org"})


def _core_family(host: str | None) -> str | None:
    if host in {"ccel.org", "www.ccel.org"}:
        return "ccel.org"
    if host in {"newadvent.org", "www.newadvent.org"}:
        return "newadvent.org"
    if host in {"spurgeon.org", "www.spurgeon.org"}:
        return "spurgeon.org"
    if host in {"ligonier.org", "www.ligonier.org", "learn.ligonier.org"}:
        return "ligonier.org"
    if host in {"gty.org", "www.gty.org"}:
        return "gty.org"
    return None


def _require_public_https(raw_url: str) -> str:
    parsed = urlparse(raw_url)
    host = (parsed.hostname or "").casefold()
    if parsed.scheme != "https" or not host or "." not in host:
        raise ValueError(f"web-audit URL must be a public HTTPS URL: {raw_url}")
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        raise ValueError(f"web-audit URL must not target a local host: {raw_url}")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return raw_url
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_unspecified:
        raise ValueError(f"web-audit URL must not target a private/reserved address: {raw_url}")
    return raw_url


class QuoteSourceWebAudit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-quote-source-web-audit"]
    schema_version: Literal[2]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    release_id: Literal["lordchrist-successor-depth-v2"]
    queue_digest: str = Field(pattern=SHA256_PATTERN)
    published_boundary: Literal[15]
    future_sequences_reviewed: tuple[int, ...]
    checked_on: date
    minimum_research_pages: int = Field(ge=50)
    research_pages_reviewed: int = Field(ge=50)
    method: str = Field(min_length=120, max_length=1200)
    research_pages: tuple[str, ...]

    @field_validator("research_pages")
    @classmethod
    def validate_pages(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("web-audit research URLs must be unique")
        for raw_url in value:
            _require_public_https(raw_url)
        return value

    @model_validator(mode="after")
    def exact_audit_contract(self) -> "QuoteSourceWebAudit":
        if self.release_id != DEPTH_RELEASE_ID or self.queue_digest != DEPTH_QUEUE_DIGEST:
            raise ValueError("web audit differs from the exact depth-v2 release identity")
        if self.future_sequences_reviewed != EXPECTED_FUTURE_SEQUENCES:
            raise ValueError("web audit must explicitly cover every pending sequence 16..60 exactly once")
        if self.research_pages_reviewed != len(self.research_pages):
            raise ValueError("web-audit page count differs from its URL inventory")
        if len(self.research_pages) < self.minimum_research_pages:
            raise ValueError("web audit does not meet its minimum research-page requirement")
        families = {family for url in self.research_pages if (family := _core_family(urlparse(url).hostname)) is not None}
        if not CORE_SOURCE_FAMILIES.issubset(families):
            missing = sorted(CORE_SOURCE_FAMILIES - families)
            raise ValueError(f"web audit is missing reviewed core source families: {missing}")
        return self


def load_source_web_audit(path: Path) -> QuoteSourceWebAudit:
    try:
        return QuoteSourceWebAudit.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid LordChrist quote source web audit {path}: {exc}") from exc


def future_exact_source_urls(
    *,
    candidate_path: Path,
    translation_ledger_path: Path,
    integrity_amendment_path: Path,
    depth_audit_path: Path,
    replacements_path: Path,
) -> dict[int, str]:
    corpus = load_successor_corpus(candidate_path, translation_ledger_path, integrity_amendment_path)
    audit = load_depth_audit(depth_audit_path)
    replacements = load_depth_replacements(replacements_path)
    replacement_by_key = {entry.replacement_key: entry for entry in replacements.entries}

    result: dict[int, str] = {}
    for audit_entry in audit.entries[15:]:
        sequence = audit_entry.sequence
        if audit_entry.verdict == "keep":
            result[sequence] = corpus.posts[sequence - 1].source.url
            continue
        if audit_entry.verdict == "replace" and audit_entry.replacement_key is not None:
            result[sequence] = replacement_by_key[audit_entry.replacement_key].source.url
            continue
        raise ValueError(f"pending sequence {sequence} has an invalid depth-audit verdict")

    if tuple(result) != EXPECTED_FUTURE_SEQUENCES:
        raise ValueError("exact-source inventory must cover pending sequences 16..60 in order")
    return result


def assert_future_exact_source_coverage(
    audit: QuoteSourceWebAudit,
    *,
    candidate_path: Path,
    translation_ledger_path: Path,
    integrity_amendment_path: Path,
    depth_audit_path: Path,
    replacements_path: Path,
) -> dict[int, str]:
    exact_sources = future_exact_source_urls(
        candidate_path=candidate_path,
        translation_ledger_path=translation_ledger_path,
        integrity_amendment_path=integrity_amendment_path,
        depth_audit_path=depth_audit_path,
        replacements_path=replacements_path,
    )
    reviewed = set(audit.research_pages)
    missing = {sequence: url for sequence, url in exact_sources.items() if url not in reviewed}
    if missing:
        detail = "\n".join(f"{sequence:02d} {url}" for sequence, url in missing.items())
        raise ValueError(f"web audit is missing exact source URLs for pending quote cards:\n{detail}")
    return exact_sources


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate LordChrist quote source web-audit evidence.")
    parser.add_argument("path", type=Path)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--translation-ledger", type=Path, required=True)
    parser.add_argument("--integrity-amendment", type=Path, required=True)
    parser.add_argument("--depth-audit", type=Path, required=True)
    parser.add_argument("--replacements", type=Path, required=True)
    args = parser.parse_args()
    audit = load_source_web_audit(args.path)
    exact_sources = assert_future_exact_source_coverage(
        audit,
        candidate_path=args.candidate,
        translation_ledger_path=args.translation_ledger,
        integrity_amendment_path=args.integrity_amendment,
        depth_audit_path=args.depth_audit,
        replacements_path=args.replacements,
    )
    print(
        json.dumps(
            {
                "release_id": audit.release_id,
                "queue_digest": audit.queue_digest,
                "published_boundary": audit.published_boundary,
                "future_sequences_reviewed": len(audit.future_sequences_reviewed),
                "exact_future_source_urls": len(set(exact_sources.values())),
                "research_pages_reviewed": audit.research_pages_reviewed,
                "checked_on": audit.checked_on.isoformat(),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
