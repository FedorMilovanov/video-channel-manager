from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

from video_channel_manager.telegram_presentation import _require_standalone_quotation
from video_channel_manager.telegram_quote_depth import build_depth_runtime_queue
from video_channel_manager.telegram_quote_runtime import SuccessorRuntimePost
from video_channel_manager.telegram_quote_source_audit import (
    assert_future_exact_source_coverage,
    load_source_web_audit,
)
from video_channel_manager.telegram_quote_standalone_review import (
    STANDALONE_REVIEW_FILENAME,
    ReviewedStandaloneSuffix,
    assert_reviewed_standalone_suffix,
    load_standalone_review,
    reviewed_title_resolutions,
)

# These openings normally depend on a preceding sentence, contrast, referent, or
# conclusion. The detector is deliberately conservative: it flags high-confidence
# dependency on omitted context and never rejects a quotation for being short.
CONTEXT_DEPENDENT_PREFIXES = (
    "а ",
    "но ",
    "и потому",
    "и поэтому",
    "поэтому",
    "следовательно",
    "таким образом",
    "отсюда",
    "посему",
    "ведь ",
    "ибо ",
    "однако ",
    "впрочем ",
    "все иные ",
    "все другие ",
    "всё это ",
    "все это ",
    "из этого ",
    "из этого следует",
    "по этой причине",
    "так что ",
    "это ",
    "этот ",
    "эта ",
    "эти ",
    "такой ",
    "такая ",
    "такие ",
    "таково ",
    "такова ",
    "таковы ",
    "он ",
    "она ",
    "оно ",
    "они ",
    "его ",
    "её ",
    "ее ",
    "их ",
    "ему ",
    "ей ",
    "им ",
    "здесь ",
    "там ",
)

# A dependent clause that opens on an unattached pronoun cannot be read on its
# own: "Если Он и я едины..." only works because the visible title names Him.
PRONOUN_DEPENDENT_CLAUSE_PREFIXES = (
    "если он ",
    "если она ",
    "если оно ",
    "если они ",
    "если его ",
    "если её ",
    "если ее ",
    "если их ",
    "если ему ",
    "если ей ",
    "если им ",
)
CONTEXT_MARKERS = CONTEXT_DEPENDENT_PREFIXES + PRONOUN_DEPENDENT_CLAUSE_PREFIXES

MIN_CONTEXT_SENTENCES = 2
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")


@dataclass(frozen=True)
class QuoteQualityIssue:
    publication_id: str
    sequence: int
    code: str
    detail: str


def semantic_blocks(post: SuccessorRuntimePost) -> tuple[str, str, str, str]:
    blocks = [block.strip() for block in post.text.replace("\r\n", "\n").strip().split("\n\n") if block.strip()]
    expected_attribution = f"— {post.attribution_text}"
    indexes = [index for index, block in enumerate(blocks) if block == expected_attribution]
    if len(indexes) != 1:
        raise ValueError(f"{post.publication_id}: expected exactly one reviewed attribution block")
    index = indexes[0]
    if index < 1 or index >= len(blocks) - 2:
        raise ValueError(f"{post.publication_id}: attribution is outside quote/context boundary")
    quote = "\n\n".join(blocks[:index]).strip()
    context = "\n\n".join(blocks[index + 1 : -1]).strip()
    hashtags = blocks[-1]
    return quote, expected_attribution, context, hashtags


def matched_context_marker(quote: str) -> str | None:
    folded = quote.casefold().lstrip("«\"'—–- ")
    return next((marker for marker in CONTEXT_MARKERS if folded.startswith(marker)), None)


def standalone_quote_issues(
    post: SuccessorRuntimePost,
    *,
    reviewed_title: str | None = None,
) -> tuple[QuoteQualityIssue, ...]:
    """Validate the visible quote-v4 unit while preserving the sealed quote text.

    The quotation itself remains source-bound and unchanged. What v4 adds is the
    reviewed title immediately before it and one reviewed reader-facing
    attribution. Only explicitly reviewed, per-publication title-context
    resolutions may rely on that title; every other context-dependent opening
    still fails, and a review entry may never turn a dependent opening into a
    self-contained one.
    """

    quote, _attribution, context, hashtags = semantic_blocks(post)
    issues: list[QuoteQualityIssue] = []

    try:
        _require_standalone_quotation(quote)
    except ValueError as exc:
        issues.append(
            QuoteQualityIssue(
                publication_id=post.publication_id,
                sequence=post.sequence,
                code="incomplete_quotation_fragment",
                detail=str(exc),
            )
        )

    marker = matched_context_marker(quote)
    if marker is not None:
        if reviewed_title is None:
            issues.append(
                QuoteQualityIssue(
                    publication_id=post.publication_id,
                    sequence=post.sequence,
                    code="context_dependent_opening",
                    detail=f"quotation begins with unresolved context-dependent prefix {marker!r}",
                )
            )
        elif reviewed_title != post.title.strip():
            issues.append(
                QuoteQualityIssue(
                    publication_id=post.publication_id,
                    sequence=post.sequence,
                    code="title_resolution_mismatch",
                    detail=f"reviewed title context {reviewed_title!r} differs from the visible title {post.title!r}",
                )
            )

    # Brevity is not itself a defect. A short, complete aphorism can be stronger
    # and more self-contained than a longer excerpt, so there is no word-count or
    # character-count floor for the quotation. The editorial paragraph, however,
    # must still be a substantive explanation rather than a bare restatement.
    sentences = [sentence for sentence in SENTENCE_SPLIT_RE.split(context.strip()) if sentence.strip()]
    if len(sentences) < MIN_CONTEXT_SENTENCES or not context.strip().endswith((".", "!", "?", "…")):
        issues.append(
            QuoteQualityIssue(
                publication_id=post.publication_id,
                sequence=post.sequence,
                code="context_not_substantive",
                detail=f"editorial context must be at least {MIN_CONTEXT_SENTENCES} complete sentences",
            )
        )
    if quote.strip() and quote.strip() in context:
        issues.append(
            QuoteQualityIssue(
                publication_id=post.publication_id,
                sequence=post.sequence,
                code="context_restates_quotation",
                detail="editorial context must explain the quotation instead of repeating it",
            )
        )

    tags = hashtags.split()
    if not 2 <= len(tags) <= 6:
        issues.append(
            QuoteQualityIssue(
                publication_id=post.publication_id,
                sequence=post.sequence,
                code="hashtag_shape",
                detail=f"expected 2..6 hashtags, got {len(tags)}",
            )
        )

    return tuple(issues)


def assert_future_suffix_quality(
    posts: tuple[SuccessorRuntimePost, ...],
    *,
    reviewed: ReviewedStandaloneSuffix,
    published_boundary: int = 15,
) -> None:
    future = posts[published_boundary:]
    if [post.sequence for post in future] != list(range(published_boundary + 1, 61)):
        raise ValueError("quote-v4 quality gate requires the exact future sequence suffix")

    assert_reviewed_standalone_suffix(reviewed, posts, published_boundary=published_boundary)
    resolutions = reviewed_title_resolutions(reviewed)
    entries = {entry.publication_id: entry for entry in reviewed.entries}

    issues: list[QuoteQualityIssue] = []
    for post in future:
        issues.extend(standalone_quote_issues(post, reviewed_title=resolutions.get(post.publication_id)))
        entry = entries[post.publication_id]
        marker = matched_context_marker(semantic_blocks(post)[0])
        if entry.opening == "title_resolved_anaphora" and marker is None:
            issues.append(
                QuoteQualityIssue(
                    publication_id=post.publication_id,
                    sequence=post.sequence,
                    code="unjustified_title_resolution",
                    detail="review claims a title-context resolution for an opening that needs no antecedent",
                )
            )

    if issues:
        detail = "\n".join(
            f"{issue.sequence:02d} {issue.publication_id}: {issue.code}: {issue.detail}" for issue in issues
        )
        raise ValueError(f"quote-v4 future quality gate failed:\n{detail}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate standalone quality and reviewed evidence for the pending LordChrist quote-v4 suffix."
    )
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--translation-ledger", type=Path, required=True)
    parser.add_argument("--integrity-amendment", type=Path, required=True)
    parser.add_argument("--depth-audit", type=Path, required=True)
    parser.add_argument("--replacements", type=Path, required=True)
    parser.add_argument("--source-web-audit", type=Path, required=True)
    parser.add_argument("--standalone-review", type=Path)
    parser.add_argument("--published-boundary", type=int, default=15)
    args = parser.parse_args()

    review_path = args.standalone_review or args.candidate.with_name(STANDALONE_REVIEW_FILENAME)
    reviewed = load_standalone_review(review_path)
    queue = build_depth_runtime_queue(
        candidate_path=args.candidate,
        translation_ledger_path=args.translation_ledger,
        integrity_amendment_path=args.integrity_amendment,
        audit_path=args.depth_audit,
        replacements_path=args.replacements,
    )
    assert_future_suffix_quality(queue.posts, reviewed=reviewed, published_boundary=args.published_boundary)

    web_audit = load_source_web_audit(args.source_web_audit)
    exact_sources = assert_future_exact_source_coverage(
        web_audit,
        candidate_path=args.candidate,
        translation_ledger_path=args.translation_ledger,
        integrity_amendment_path=args.integrity_amendment,
        depth_audit_path=args.depth_audit,
        replacements_path=args.replacements,
    )
    for entry in reviewed.entries:
        if entry.source_url != exact_sources[entry.sequence]:
            raise ValueError(f"reviewed source URL differs from the exact card source for sequence {entry.sequence}")

    print(
        json.dumps(
            {
                "release_id": queue.release_id,
                "queue_digest": queue.digest,
                "published_boundary": args.published_boundary,
                "pending_quality_verified": len(queue.posts) - args.published_boundary,
                "reviewed_pending_entries": len(reviewed.entries),
                "title_context_resolutions": len(reviewed_title_resolutions(reviewed)),
                "exact_future_source_urls": len(set(exact_sources.values())),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
