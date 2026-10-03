from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from video_channel_manager.telegram_quote_depth import build_depth_runtime_queue
from video_channel_manager.telegram_quote_runtime import SuccessorRuntimePost

# These openings normally depend on a preceding sentence, contrast, referent, or
# conclusion. Quote cards have no preceding source paragraph, so the future
# suffix must not begin with them. Published history is never retroactively
# subjected to this rule.
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


@dataclass(frozen=True)
class QuoteQualityIssue:
    publication_id: str
    sequence: int
    code: str
    detail: str


def semantic_blocks(post: SuccessorRuntimePost) -> tuple[str, str, str, str]:
    blocks = [block.strip() for block in post.text.replace("\r\n", "\n").strip().split("\n\n") if block.strip()]
    expected_attribution = f"— {post.source.author}, «{post.source.work}»"
    indexes = [index for index, block in enumerate(blocks) if block == expected_attribution]
    if len(indexes) != 1:
        raise ValueError(f"{post.publication_id}: expected exactly one source-bound attribution block")
    index = indexes[0]
    if index < 1 or index >= len(blocks) - 2:
        raise ValueError(f"{post.publication_id}: attribution is outside quote/context boundary")
    quote = "\n\n".join(blocks[:index]).strip()
    context = "\n\n".join(blocks[index + 1 : -1]).strip()
    hashtags = blocks[-1]
    return quote, expected_attribution, context, hashtags


def standalone_quote_issues(post: SuccessorRuntimePost) -> tuple[QuoteQualityIssue, ...]:
    quote, _attribution, context, hashtags = semantic_blocks(post)
    issues: list[QuoteQualityIssue] = []
    folded = quote.casefold().lstrip("«\"'—–- ")

    matched_prefix = next((prefix for prefix in CONTEXT_DEPENDENT_PREFIXES if folded.startswith(prefix)), None)
    if matched_prefix is not None:
        issues.append(
            QuoteQualityIssue(
                publication_id=post.publication_id,
                sequence=post.sequence,
                code="context_dependent_opening",
                detail=f"quotation begins with context-dependent prefix {matched_prefix!r}",
            )
        )

    # Brevity is not itself a defect. A short, complete aphorism can be stronger
    # and more self-contained than a longer excerpt. The gate therefore rejects
    # dependency on missing context, not an arbitrary word-count threshold.
    if len(context) < 120:
        issues.append(
            QuoteQualityIssue(
                publication_id=post.publication_id,
                sequence=post.sequence,
                code="context_too_thin",
                detail=f"editorial context has only {len(context)} characters",
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
    published_boundary: int = 15,
) -> None:
    future = posts[published_boundary:]
    if [post.sequence for post in future] != list(range(published_boundary + 1, 61)):
        raise ValueError("quote-v4 quality gate requires the exact future sequence suffix")

    issues = [issue for post in future for issue in standalone_quote_issues(post)]
    if issues:
        detail = "\n".join(
            f"{issue.sequence:02d} {issue.publication_id}: {issue.code}: {issue.detail}" for issue in issues
        )
        raise ValueError(f"quote-v4 future quality gate failed:\n{detail}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate standalone quality for the pending LordChrist quote-v4 suffix."
    )
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--translation-ledger", type=Path, required=True)
    parser.add_argument("--integrity-amendment", type=Path, required=True)
    parser.add_argument("--depth-audit", type=Path, required=True)
    parser.add_argument("--replacements", type=Path, required=True)
    parser.add_argument("--published-boundary", type=int, default=15)
    args = parser.parse_args()

    queue = build_depth_runtime_queue(
        candidate_path=args.candidate,
        translation_ledger_path=args.translation_ledger,
        integrity_amendment_path=args.integrity_amendment,
        audit_path=args.depth_audit,
        replacements_path=args.replacements,
    )
    assert_future_suffix_quality(queue.posts, published_boundary=args.published_boundary)
    print(
        json.dumps(
            {
                "release_id": queue.release_id,
                "queue_digest": queue.digest,
                "published_boundary": args.published_boundary,
                "pending_quality_verified": len(queue.posts) - args.published_boundary,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
