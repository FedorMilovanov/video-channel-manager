"""Read-only quote-v5 rendering proof for the exact next pending publication.

The activation checkpoint proves the durable state boundary and source evidence.
This module proves the *reader-facing* quote-v5 contract for the one publication
that is next in strict order:

* the quotation opens the post directly, with no decorative leading title;
* the reviewed source line sits tight on the line immediately under the
  quotation, forming one reading unit;
* when — and only when — the reviewed standalone evidence marks the payload as a
  load-bearing opening, the bold reviewed title leads the post and is followed
  by real paragraph air before the quotation;
* the reviewed title bindings embedded in the policy are exactly the reviewed
  ``title_resolved_anaphora`` payloads of the standalone review;
* the rendered provider payload stays inside the Telegram text limit.

It performs no provider call, no state write, and no ledger mutation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

from video_channel_manager.telegram_models import MAX_TELEGRAM_TEXT_LENGTH, SHA256_PATTERN, TelegramPost
from video_channel_manager.telegram_presentation import (
    QuotePresentationPolicyV5,
    load_presentation_policy,
    render_post,
)
from video_channel_manager.telegram_publisher import load_ledger, load_queue
from video_channel_manager.telegram_quote_progress import validate_quote_progress
from video_channel_manager.telegram_quote_runtime import SuccessorRuntimeQueue
from video_channel_manager.telegram_quote_runtime_activation import load_runtime_activation
from video_channel_manager.telegram_quote_standalone_review import load_standalone_review

V5_POLICY_ID = "lordchrist-quote-v5"
TITLE_ENTITY_LAYOUT = ("bold", "blockquote", "italic")
NO_TITLE_ENTITY_LAYOUT = ("blockquote", "italic")
TEXT_LENGTH_SAFETY_MARGIN = 100


def _utf16_length(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def _sha256(value: str) -> bool:
    import re

    return re.fullmatch(SHA256_PATTERN, value) is not None


def build_render_proof(
    *,
    queue_path: Path,
    ledger_path: Path,
    presentation_policy_path: Path,
    activation_path: Path,
    standalone_review_path: Path,
) -> dict[str, object]:
    """Prove the quote-v5 reading unit for the exact strict-next publication."""

    activation = load_runtime_activation(activation_path)
    policy = load_presentation_policy(presentation_policy_path)
    if policy.policy_id != V5_POLICY_ID:
        raise ValueError(f"render proof requires {V5_POLICY_ID}, not {policy.policy_id}")
    if not isinstance(policy, QuotePresentationPolicyV5):
        raise ValueError("render proof requires the quote-v5 presentation policy model")
    if activation.presentation_policy_id != policy.policy_id or activation.presentation_policy_sha256 != policy.digest:
        raise ValueError("render proof presentation policy differs from the rolling activation checkpoint")

    review = load_standalone_review(standalone_review_path)
    reviewed_title_payloads = {
        entry.payload_sha256 for entry in review.entries if entry.opening == "title_resolved_anaphora"
    }
    if reviewed_title_payloads != set(policy.reviewed_title_payload_sha256s):
        raise ValueError(
            "quote-v5 reviewed title bindings differ from the standalone review title-resolved payloads"
        )

    queue = load_queue(queue_path)
    if not isinstance(queue, SuccessorRuntimeQueue):
        raise ValueError("render proof requires the exact successor runtime queue")
    if queue.release_id != activation.release_id or queue.digest != activation.queue_digest:
        raise ValueError("render proof queue differs from the rolling activation checkpoint")

    ledger = load_ledger(ledger_path, queue)
    boundary = validate_quote_progress(
        queue,
        ledger,
        minimum_published=activation.required_published_prefix,
        allow_progress=activation.progress_policy == "verified_prefix",
        history_digest=activation.published_history_sha256,
        policy=policy,
        evidence_root=ledger_path.parent / "dispatches",
    )
    base = {
        "release_id": activation.release_id,
        "queue_digest": activation.queue_digest,
        "presentation_policy_id": policy.policy_id,
        "presentation_policy_sha256": policy.digest,
        "published_prefix": boundary,
        "pending_suffix": len(queue.posts) - boundary,
        "provider_writes_authorized": activation.provider_writes_authorized,
        "queue_complete": boundary == len(queue.posts),
    }
    if boundary == len(queue.posts):
        return dict(
            base,
            next_sequence=None,
            next_publication_id=None,
            entity_layout=[],
            rendered_text_length=0,
            provider_payload_sha256=None,
            attribution_line_immediately_follows_quotation=True,
        )
    next_post = queue.posts[boundary]

    review_entry = next(
        (entry for entry in review.entries if entry.publication_id == next_post.publication_id),
        None,
    )
    if review_entry is None or review_entry.payload_sha256 != next_post.payload_sha256:
        raise ValueError("render proof next publication differs from the reviewed standalone suffix")

    rendered = render_post(cast("TelegramPost", next_post), policy)
    title = next_post.title
    reviewed_attribution = " ".join(next_post.attribution_text.strip().split())
    attribution = f"— {reviewed_attribution}"
    title_required = next_post.payload_sha256 in policy.reviewed_title_payload_sha256s

    if title_required:
        if review_entry.opening != "title_resolved_anaphora":
            raise ValueError("quote-v5 title rendering requires a reviewed load-bearing opening")
        if review_entry.title_context_reference != title.strip():
            raise ValueError("quote-v5 rendered title differs from the reviewed title-context resolution")
    elif review_entry.opening != "self_contained":
        raise ValueError("quote-v5 no-title rendering requires a reviewed self-contained opening")

    hashtag_block = next_post.text.rsplit("\n\n", 1)[-1]
    if not rendered.text.endswith(hashtag_block):
        raise ValueError("quote-v5 rendering must keep the reviewed hashtag block as the final block")
    if f"\n\n{attribution}" in rendered.text:
        raise ValueError("quote-v5 rendering left blank air between the quotation and the source line")
    if rendered.text.count(attribution) != 1:
        raise ValueError("quote-v5 rendering must carry the exact source line exactly once")

    entities = rendered.expected_entities
    expected_layout = TITLE_ENTITY_LAYOUT if title_required else NO_TITLE_ENTITY_LAYOUT
    if [entity.type for entity in entities] != list(expected_layout):
        raise ValueError(
            "quote-v5 rendering must expose exactly one blockquote, one italic source line "
            "and at most one bold reviewed title"
        )
    quotation, source_line = entities[-2], entities[-1]
    if title_required:
        bold = entities[0]
        if bold.offset != 0 or bold.length != _utf16_length(title):
            raise ValueError("quote-v5 bold entity must cover exactly the reviewed title")
        if not rendered.text.startswith(f"{title}\n\n"):
            raise ValueError("quote-v5 rendering must keep real paragraph air between title and quotation")
        if quotation.offset != _utf16_length(title) + 2:
            raise ValueError("quote-v5 quotation entity must begin on the line after the title air")
        if source_line.offset != quotation.offset + quotation.length + 1:
            raise ValueError("quote-v5 source entity must begin on the line immediately after the quotation")
    else:
        if quotation.offset != 0:
            raise ValueError("quote-v5 quotation entity must open the publication directly")
        if source_line.offset != quotation.length + 1:
            raise ValueError("quote-v5 source entity must begin on the line immediately after the quotation")
        if rendered.text.startswith(title):
            raise ValueError("quote-v5 rendering must not open with a decorative leading title")
    if source_line.length != _utf16_length(attribution):
        raise ValueError("quote-v5 source entity must cover exactly the source line")

    if not _sha256(rendered.provider_payload_sha256):
        raise ValueError("quote-v5 rendered provider payload fingerprint is invalid")
    if len(rendered.text) > MAX_TELEGRAM_TEXT_LENGTH - TEXT_LENGTH_SAFETY_MARGIN:
        raise ValueError(
            "quote-v5 rendered publication is too close to the Telegram text limit: "
            f"{len(rendered.text)} of {MAX_TELEGRAM_TEXT_LENGTH} characters"
        )

    return {
        **base,
        "next_sequence": next_post.sequence,
        "next_publication_id": next_post.publication_id,
        "attribution_line": reviewed_attribution,
        "title_rendered": title_required,
        "provider_payload_sha256": rendered.provider_payload_sha256,
        "rendered_text_length": len(rendered.text),
        "entity_layout": [entity.type for entity in entities],
        "attribution_line_immediately_follows_quotation": True,
        "provider_writes_authorized": activation.provider_writes_authorized,
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Prove quote-v5 rendering for the exact next pending publication.")
    root.add_argument("--queue", type=Path, required=True)
    root.add_argument("--ledger", type=Path, required=True)
    root.add_argument("--presentation-policy", type=Path, required=True)
    root.add_argument("--activation", type=Path, required=True)
    root.add_argument("--standalone-review", type=Path, required=True)
    root.add_argument("--output", type=Path)
    return root


def main() -> int:
    args = parser().parse_args()
    proof = build_render_proof(
        queue_path=args.queue,
        ledger_path=args.ledger,
        presentation_policy_path=args.presentation_policy,
        activation_path=args.activation,
        standalone_review_path=args.standalone_review,
    )
    payload = json.dumps(proof, ensure_ascii=False, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
