"""Reviewed, not-yet-applied content findings for the sealed pending suffix.

The depth-v2 pending suffix 16..60 is sealed: `successor-release-v2.json` pins
the candidate and translation-ledger digests, `successor-depth-release-v1.json`
pins the audit/replacement blobs, and the durable depth-v2 publication ledger
binds every pending card payload hash. Editing a sealed card therefore forces a
new release identity plus a durable-state rebind, which is exactly what must not
happen silently while the release is being hardened.

This module keeps such findings explicit instead of letting them disappear into
reviewer memory: every entry is bound to the *current* sealed quotation digest,
so applying the correction in a later reviewed release breaks this record until
the record itself is updated. Nothing here authorizes a provider write and
nothing here modifies a sealed card.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from video_channel_manager.telegram_models import SHA256_PATTERN
from video_channel_manager.telegram_quote_depth import DEPTH_QUEUE_DIGEST, DEPTH_RELEASE_ID
from video_channel_manager.telegram_quote_quality_v4 import semantic_blocks
from video_channel_manager.telegram_quote_runtime import SuccessorRuntimePost
from video_channel_manager.telegram_quote_standalone_review import quotation_sha256

CONTENT_FINDINGS_FILENAME = "quote-pending-content-findings-v1.json"
CONTENT_FINDINGS_SCHEMA = "video-channel-manager.telegram-quote-pending-content-findings"
PUBLISHED_BOUNDARY = 15
FINDING_KINDS = Literal["translation_grammar", "wording_clarity", "missing_evidence"]
RESEAL_REQUIREMENTS = Literal[
    "successor-release-v2",
    "successor-depth-release-v1",
    "successor-depth-runtime-activation-v4",
    "durable-depth-v2-ledger-binding",
]


class PendingContentFinding(BaseModel):
    """One reviewed defect in a sealed pending card, with the prepared correction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: int = Field(ge=PUBLISHED_BOUNDARY + 1, le=60)
    publication_id: str = Field(pattern=r"^lordchrist-successor-depth-v2-[a-z0-9-]{4,100}$")
    quotation_sha256: str = Field(pattern=SHA256_PATTERN)
    kind: FINDING_KINDS
    severity: Literal["editorial_language", "evidence_gap"]
    finding: str = Field(min_length=60, max_length=700)
    proposed_quotation_ru: str = Field(min_length=10, max_length=1800)
    source_fragment: str = Field(min_length=20, max_length=1400)
    origin: Literal["reviewed_sealed_translation"]
    not_applied_because: str = Field(min_length=60, max_length=700)
    requires_reseal_of: tuple[RESEAL_REQUIREMENTS, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def finding_contract(self) -> "PendingContentFinding":
        if self.proposed_quotation_ru.strip() == self.source_fragment.strip():
            raise ValueError("a proposed correction must differ from the sealed source fragment")
        if quotation_sha256(self.proposed_quotation_ru) == self.quotation_sha256:
            raise ValueError("a proposed correction must differ from the sealed reviewed quotation")
        if self.proposed_quotation_ru.count("«") != self.proposed_quotation_ru.count("»"):
            raise ValueError("a proposed correction must keep balanced quotation marks")
        if "durable-depth-v2-ledger-binding" not in self.requires_reseal_of:
            raise ValueError("a sealed pending correction must record the durable state rebind it requires")
        return self


class PendingContentFindings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-quote-pending-content-findings"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    release_id: Literal["lordchrist-successor-depth-v2"]
    queue_digest: str = Field(pattern=SHA256_PATTERN)
    published_boundary: Literal[15]
    reviewed_on: date
    method: str = Field(min_length=60, max_length=900)
    entries: tuple[PendingContentFinding, ...]

    @model_validator(mode="after")
    def findings_contract(self) -> "PendingContentFindings":
        if self.queue_digest != DEPTH_QUEUE_DIGEST or self.release_id != DEPTH_RELEASE_ID:
            raise ValueError("pending content findings must bind the sealed depth-v2 release")
        ids = [entry.publication_id for entry in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("pending content findings must be unique per publication")
        if any(entry.sequence <= self.published_boundary for entry in self.entries):
            raise ValueError("published sequences are immutable and cannot carry pending findings")
        return self


def load_pending_content_findings(path: Path) -> PendingContentFindings:
    try:
        return PendingContentFindings.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid pending content findings {path}: {exc}") from exc


def assert_findings_match_pending_suffix(
    findings: PendingContentFindings,
    posts: tuple[SuccessorRuntimePost, ...],
    *,
    published_boundary: int = PUBLISHED_BOUNDARY,
) -> dict[str, int]:
    """Prove the record is truthful, and that no finding was silently applied.

    Every finding must still point at the exact sealed quotation it was raised
    against. When a later release applies a prepared correction, this check
    fails until the finding is removed and the correction is re-sealed, which is
    precisely why the record cannot rot into a stale note.
    """

    future = tuple(post for post in posts if post.sequence > published_boundary)
    by_sequence = {post.sequence: post for post in future}
    if [post.sequence for post in future] != list(range(published_boundary + 1, 61)):
        raise ValueError("pending content findings require the exact pending suffix 16 through 60")

    verified = 0
    for entry in findings.entries:
        post = by_sequence.get(entry.sequence)
        if post is None or post.publication_id != entry.publication_id:
            raise ValueError(f"pending content finding points at a foreign publication: {entry.publication_id}")
        quotation, _, _, _ = semantic_blocks(post)
        if quotation_sha256(quotation) != entry.quotation_sha256:
            raise ValueError(
                "sealed pending quotation changed under a recorded finding; re-seal the finding with the release: "
                f"{entry.publication_id}"
            )
        verified += 1
    return {"verified_findings": verified, "pending_suffix": len(future)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("findings", type=Path, help="reviewed pending content findings artifact")
    parser.add_argument("--queue", type=Path, required=True, help="materialized depth-v2 runtime queue")
    parser.add_argument("--published-boundary", type=int, default=PUBLISHED_BOUNDARY)
    args = parser.parse_args(argv)

    from video_channel_manager.telegram_publisher import load_queue
    from video_channel_manager.telegram_quote_runtime import SuccessorRuntimeQueue

    findings = load_pending_content_findings(args.findings)
    queue = load_queue(args.queue)
    if not isinstance(queue, SuccessorRuntimeQueue):
        raise ValueError("pending content findings require the materialized depth-v2 runtime queue")
    summary = assert_findings_match_pending_suffix(findings, queue.posts, published_boundary=args.published_boundary)
    print(
        json.dumps(
            {
                "release_id": findings.release_id,
                "queue_digest": findings.queue_digest,
                "reviewed_on": findings.reviewed_on.isoformat(),
                "open_findings": len(findings.entries),
                **summary,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
