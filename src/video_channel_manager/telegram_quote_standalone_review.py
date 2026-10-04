from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from video_channel_manager.telegram_models import SHA256_PATTERN, sha256_text
from video_channel_manager.telegram_quote_depth import DEPTH_QUEUE_DIGEST, DEPTH_RELEASE_ID
from video_channel_manager.telegram_quote_runtime import SuccessorRuntimePost

STANDALONE_REVIEW_FILENAME = "quote-standalone-review-v1.json"
STANDALONE_REVIEW_SCHEMA = "video-channel-manager.telegram-quote-standalone-review"
PUBLISHED_BOUNDARY = 15
EXPECTED_FUTURE_SEQUENCES = tuple(range(PUBLISHED_BOUNDARY + 1, 61))

# Retrieval-layer vocabulary. A failed automated fetch never establishes that a
# quotation is false: these classes exist so the evidence layer can say exactly
# what happened, and nothing else.
RETRIEVAL_CLASSES = Literal[
    "retrieved_live_review",
    "retrieved_via_canonical_endpoint",
    "retrieved_in_reviewed_sweep",
    "transport_failure_not_invalidating",
    "bot_protection_not_invalidating",
    "stale_url_relocated",
    "insufficient_evidence",
]

OPENING_CLASSES = Literal["self_contained", "title_resolved_anaphora"]


class ReviewedStandaloneEntry(BaseModel):
    """One human-reviewed standalone judgement for a pending quote card.

    The entry binds the reviewed verdict to the exact content identity it was
    made against (payload hash, visible quotation, displayed attribution), so a
    later content change cannot silently inherit an earlier review.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: int = Field(ge=PUBLISHED_BOUNDARY + 1, le=60)
    publication_id: str = Field(pattern=r"^lordchrist-successor-depth-v2-[a-z0-9-]{4,100}$")
    payload_sha256: str = Field(pattern=SHA256_PATTERN)
    quotation_sha256: str = Field(pattern=SHA256_PATTERN)
    attribution_line: str = Field(min_length=4, max_length=260)
    opening: OPENING_CLASSES
    title_context_reference: str | None = Field(default=None, min_length=2, max_length=160)
    standalone_verdict: Literal["accepted"] = "accepted"
    reviewer_note: str = Field(min_length=60, max_length=700)
    source_url: str = Field(pattern=r"^https://")
    source_canonical_url: str = Field(pattern=r"^https://")
    source_retrieval: RETRIEVAL_CLASSES
    source_note: str = Field(min_length=20, max_length=700)

    @field_validator("source_url", "source_canonical_url")
    @classmethod
    def require_public_source_url(cls, value: str) -> str:
        parsed = urlparse(value)
        host = (parsed.hostname or "").casefold()
        if parsed.scheme != "https" or not host or "." not in host:
            raise ValueError(f"reviewed source URL must be public HTTPS: {value}")
        return value

    @model_validator(mode="after")
    def standalone_opening_contract(self) -> "ReviewedStandaloneEntry":
        note = " ".join(self.reviewer_note.split())
        if len(note) < 60:
            raise ValueError("reviewed standalone note must state the editorial justification")
        if self.opening == "title_resolved_anaphora":
            if self.title_context_reference is None:
                raise ValueError("title-resolved anaphora requires the exact reviewed visible title")
        elif self.title_context_reference is not None:
            raise ValueError("self-contained quotations must not claim a title-context resolution")
        if self.attribution_line.count("«") != self.attribution_line.count("»"):
            raise ValueError("reviewed attribution line must keep balanced quotation marks")
        return self


class ReviewedStandaloneSuffix(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-quote-standalone-review"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    release_id: Literal["lordchrist-successor-depth-v2"]
    queue_digest: str = Field(pattern=SHA256_PATTERN)
    published_boundary: Literal[15]
    reviewed_on: date
    method: str = Field(min_length=120, max_length=1500)
    entries: tuple[ReviewedStandaloneEntry, ...]

    @model_validator(mode="after")
    def exact_reviewed_suffix(self) -> "ReviewedStandaloneSuffix":
        if self.release_id != DEPTH_RELEASE_ID or self.queue_digest != DEPTH_QUEUE_DIGEST:
            raise ValueError("standalone review differs from the exact depth-v2 release identity")
        if tuple(entry.sequence for entry in self.entries) != EXPECTED_FUTURE_SEQUENCES:
            raise ValueError("standalone review must cover every pending sequence 16..60 exactly once")
        ids = [entry.publication_id for entry in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("standalone review publication ids must be unique")
        resolved = [entry.publication_id for entry in self.entries if entry.opening == "title_resolved_anaphora"]
        if len(resolved) != len(set(resolved)):
            raise ValueError("standalone review title-context resolutions must be unique")
        return self


def load_standalone_review(path: Path) -> ReviewedStandaloneSuffix:
    try:
        return ReviewedStandaloneSuffix.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid LordChrist quote standalone review {path}: {exc}") from exc


def quotation_sha256(quotation: str) -> str:
    return sha256_text(quotation.strip())


def reviewed_title_resolutions(reviewed: ReviewedStandaloneSuffix) -> dict[str, str]:
    """Map publication id to the exact reviewed visible title that resolves the opening."""

    return {
        entry.publication_id: entry.title_context_reference or ""
        for entry in reviewed.entries
        if entry.opening == "title_resolved_anaphora"
    }


def assert_reviewed_standalone_suffix(
    reviewed: ReviewedStandaloneSuffix,
    posts: tuple[SuccessorRuntimePost, ...],
    *,
    published_boundary: int = PUBLISHED_BOUNDARY,
) -> None:
    """Cross-check the reviewed editorial ledger against the exact runtime suffix."""

    future = posts[published_boundary:]
    if tuple(post.sequence for post in future) != EXPECTED_FUTURE_SEQUENCES:
        raise ValueError("standalone review requires the exact pending runtime suffix")

    by_id = {entry.publication_id: entry for entry in reviewed.entries}
    for post in future:
        entry = by_id.get(post.publication_id)
        if entry is None:
            raise ValueError(f"standalone review is missing pending publication {post.publication_id}")
        if entry.sequence != post.sequence:
            raise ValueError(f"standalone review sequence differs for {post.publication_id}")
        if entry.payload_sha256 != post.payload_sha256:
            raise ValueError(f"standalone review is bound to different content: {post.publication_id}")
        if entry.attribution_line != " ".join(post.attribution_text.strip().split()):
            raise ValueError(f"standalone review attribution differs from the displayed line: {post.publication_id}")
        blocks = [block.strip() for block in post.text.replace("\r\n", "\n").strip().split("\n\n") if block.strip()]
        attribution = f"— {post.attribution_text}"
        if attribution not in blocks:
            raise ValueError(f"runtime text does not carry the reviewed attribution: {post.publication_id}")
        quotation = "\n\n".join(blocks[: blocks.index(attribution)]).strip()
        if entry.quotation_sha256 != quotation_sha256(quotation):
            raise ValueError(f"standalone review quotation differs from the reviewed text: {post.publication_id}")
        if entry.opening == "title_resolved_anaphora" and entry.title_context_reference != post.title:
            raise ValueError(f"title-context resolution is not bound to the visible title: {post.publication_id}")
        if entry.opening == "self_contained" and entry.title_context_reference is not None:
            raise ValueError(f"self-contained review must not claim a title resolution: {post.publication_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the reviewed standalone ledger for pending quote cards.")
    parser.add_argument("path", type=Path)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--translation-ledger", type=Path, required=True)
    parser.add_argument("--integrity-amendment", type=Path, required=True)
    parser.add_argument("--depth-audit", type=Path, required=True)
    parser.add_argument("--replacements", type=Path, required=True)
    parser.add_argument("--published-boundary", type=int, default=PUBLISHED_BOUNDARY)
    args = parser.parse_args()

    from video_channel_manager.telegram_quote_depth import build_depth_runtime_queue

    reviewed = load_standalone_review(args.path)
    queue = build_depth_runtime_queue(
        candidate_path=args.candidate,
        translation_ledger_path=args.translation_ledger,
        integrity_amendment_path=args.integrity_amendment,
        audit_path=args.depth_audit,
        replacements_path=args.replacements,
    )
    assert_reviewed_standalone_suffix(reviewed, queue.posts, published_boundary=args.published_boundary)
    print(
        json.dumps(
            {
                "release_id": reviewed.release_id,
                "queue_digest": reviewed.queue_digest,
                "published_boundary": reviewed.published_boundary,
                "reviewed_pending_entries": len(reviewed.entries),
                "title_context_resolutions": len(reviewed_title_resolutions(reviewed)),
                "reviewed_on": reviewed.reviewed_on.isoformat(),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
