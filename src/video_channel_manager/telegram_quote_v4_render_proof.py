"""Read-only quote-v4 rendering proof for the exact next pending publication.

The activation checkpoint proves the durable state boundary and source evidence.
This module proves the *reader-facing* contract for the one publication that is
next in strict order: the reviewed title, the source-bound quotation, and the
source line form one tight reading unit with no blank air between them, and the
rendered provider payload stays inside the Telegram text limit.

It performs no provider call, no state write, and no ledger mutation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

from video_channel_manager.telegram_models import MAX_TELEGRAM_TEXT_LENGTH, SHA256_PATTERN, TelegramPost
from video_channel_manager.telegram_presentation import load_presentation_policy, render_post
from video_channel_manager.telegram_publisher import load_ledger, load_queue
from video_channel_manager.telegram_quote_runtime import SuccessorRuntimeQueue
from video_channel_manager.telegram_quote_runtime_activation import load_runtime_activation

V4_POLICY_ID = "lordchrist-quote-v4"
V4_ENTITY_LAYOUT = ("bold", "blockquote", "italic")
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
) -> dict[str, object]:
    """Prove the quote-v4 reading unit for the exact strict-next publication."""

    activation = load_runtime_activation(activation_path)
    policy = load_presentation_policy(presentation_policy_path)
    if policy.policy_id != V4_POLICY_ID:
        raise ValueError(f"render proof requires {V4_POLICY_ID}, not {policy.policy_id}")
    if activation.presentation_policy_id != policy.policy_id or activation.presentation_policy_sha256 != policy.digest:
        raise ValueError("render proof presentation policy differs from the rolling activation checkpoint")

    queue = load_queue(queue_path)
    if not isinstance(queue, SuccessorRuntimeQueue):
        raise ValueError("render proof requires the exact successor runtime queue")
    if queue.release_id != activation.release_id or queue.digest != activation.queue_digest:
        raise ValueError("render proof queue differs from the rolling activation checkpoint")

    ledger = load_ledger(ledger_path, queue)
    published = [post for post in queue.posts if ledger.entries[post.publication_id].state == "published"]
    pending = [post for post in queue.posts if ledger.entries[post.publication_id].state == "pending"]
    if len(published) + len(pending) != len(queue.posts):
        raise ValueError("render proof requires an exact published/pending ledger split")
    if len(published) != activation.required_published_prefix:
        raise ValueError(
            f"render proof published prefix is {len(published)}, checkpoint requires "
            f"{activation.required_published_prefix}"
        )
    if len(pending) != activation.required_pending_suffix:
        raise ValueError(
            f"render proof pending suffix is {len(pending)}, checkpoint requires {activation.required_pending_suffix}"
        )
    for post in published:
        entry = ledger.entries[post.publication_id]
        if entry.provider_effect != "verified" or not entry.message_id:
            raise ValueError(f"render proof published entry is not provider-verified: {post.publication_id}")

    if not pending:
        raise ValueError("render proof requires at least one pending publication")
    next_post = pending[0]
    if next_post.sequence != len(published) + 1:
        raise ValueError(
            f"strict next publication is sequence {next_post.sequence}, "
            f"but the verified published prefix is {len(published)}"
        )

    # The reviewed successor runtime card exposes the same quote-card fields the
    # renderer consumes; the runtime type is intentionally narrower than the
    # legacy queue model.
    rendered = render_post(cast("TelegramPost", next_post), policy)
    title = next_post.title
    attribution = f"— {next_post.source.author}, «{next_post.source.work}»"

    if not rendered.text.startswith(f"{title}\n"):
        raise ValueError("quote-v4 rendering must open with the reviewed title line")
    if f"{title}\n\n" in rendered.text:
        raise ValueError("quote-v4 rendering left blank air between the title and the quotation")
    if f"\n\n{attribution}" in rendered.text:
        raise ValueError("quote-v4 rendering left blank air between the quotation and the source line")
    if rendered.text.count(attribution) != 1:
        raise ValueError("quote-v4 rendering must carry the exact source line exactly once")
    hashtag_block = next_post.text.rsplit("\n\n", 1)[-1]
    if not rendered.text.endswith(hashtag_block):
        raise ValueError("quote-v4 rendering must keep the reviewed hashtag block as the final block")

    entities = rendered.expected_entities
    if [entity.type for entity in entities] != list(V4_ENTITY_LAYOUT):
        raise ValueError(
            "quote-v4 rendering must expose exactly one bold title, one blockquote, one italic source line"
        )
    bold, quotation, source_line = entities
    if bold.offset != 0 or bold.length != _utf16_length(title):
        raise ValueError("quote-v4 bold entity must cover exactly the reviewed title")
    if quotation.offset != _utf16_length(title) + 1:
        raise ValueError("quote-v4 quotation entity must begin on the line immediately after the title")
    if source_line.offset != quotation.offset + quotation.length + 1:
        raise ValueError("quote-v4 source entity must begin on the line immediately after the quotation")
    if source_line.length != _utf16_length(attribution):
        raise ValueError("quote-v4 source entity must cover exactly the source line")
    if not _sha256(rendered.provider_payload_sha256):
        raise ValueError("quote-v4 rendered provider payload fingerprint is invalid")
    if len(rendered.text) > MAX_TELEGRAM_TEXT_LENGTH - TEXT_LENGTH_SAFETY_MARGIN:
        raise ValueError(
            "quote-v4 rendered publication is too close to the Telegram text limit: "
            f"{len(rendered.text)} of {MAX_TELEGRAM_TEXT_LENGTH} characters"
        )

    return {
        "release_id": activation.release_id,
        "queue_digest": activation.queue_digest,
        "presentation_policy_id": policy.policy_id,
        "presentation_policy_sha256": policy.digest,
        "published_prefix": len(published),
        "pending_suffix": len(pending),
        "next_sequence": next_post.sequence,
        "next_publication_id": next_post.publication_id,
        "provider_payload_sha256": rendered.provider_payload_sha256,
        "rendered_text_length": len(rendered.text),
        "entity_layout": [entity.type for entity in entities],
        "attribution_line_immediately_follows_quotation": True,
        "provider_writes_authorized": activation.provider_writes_authorized,
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Prove quote-v4 rendering for the exact next pending publication.")
    root.add_argument("--queue", type=Path, required=True)
    root.add_argument("--ledger", type=Path, required=True)
    root.add_argument("--presentation-policy", type=Path, required=True)
    root.add_argument("--activation", type=Path, required=True)
    root.add_argument("--output", type=Path)
    return root


def main() -> int:
    args = parser().parse_args()
    proof = build_render_proof(
        queue_path=args.queue,
        ledger_path=args.ledger,
        presentation_policy_path=args.presentation_policy,
        activation_path=args.activation,
    )
    payload = json.dumps(proof, ensure_ascii=False, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
