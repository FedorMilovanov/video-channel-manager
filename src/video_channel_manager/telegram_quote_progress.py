"""Provider-free validation of a contiguous, verified quote publication prefix.

A migration boundary is immutable history, not the expected count on every cron.
Only the verified prefix may grow; gaps, ambiguous attempts, foreign targets and
modified payloads remain blocking. No state is repaired or written here.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from video_channel_manager.telegram_models import TelegramLedger, TelegramPost, canonical_json, sha256_text
from video_channel_manager.telegram_presentation import (
    PresentationPolicyContract,
    load_rendered_post,
    verify_rendered_post,
)
from video_channel_manager.telegram_quote_runtime import SuccessorRuntimeQueue

CHAT_ID = -1001295216957
BOT_ID = 8716602202
BOT_USERNAME = "preaching_mp3_bot"
PRISTINE_EFFECTS = frozenset({"impossible", "not_dispatched", "confirmed_absent"})


def published_history_digest(ledger: TelegramLedger, boundary: int) -> str:
    """Bind the accepted history, including receipts/provenance, in ledger order."""
    return sha256_text(
        canonical_json([entry.model_dump(mode="json") for entry in list(ledger.entries.values())[:boundary]])
    )


def validate_quote_progress(
    queue: SuccessorRuntimeQueue,
    ledger: TelegramLedger,
    *,
    minimum_published: int,
    allow_progress: bool = False,
    history_digest: str | None = None,
    policy: PresentationPolicyContract | None = None,
    evidence_root: Path | None = None,
) -> int:
    """Return the actual verified prefix, never an inferred/repaired boundary.

    Ongoing production additionally binds every newly published card to its
    already-durable rendered payload. A verified #16 under v3 (or missing v4
    evidence) cannot unlock #17. Telegram's existing send path only records
    verified after checking the returned text, entities and target exactly.
    """
    expected_ids = [post.publication_id for post in queue.posts]
    if ledger.queue_digest != queue.digest or list(ledger.entries) != expected_ids:
        raise ValueError("durable ledger ordering/inventory differs from the exact runtime queue")
    if history_digest is not None and published_history_digest(ledger, minimum_published) != history_digest:
        raise ValueError("immutable published history differs from the accepted migration checkpoint")

    prefix = 0
    pending_seen = False
    message_ids: set[int] = set()
    for post in queue.posts:
        entry = ledger.entries[post.publication_id]
        if entry.payload_sha256 != post.payload_sha256:
            raise ValueError(f"runtime progress payload differs: {post.publication_id}")
        if entry.state == "published":
            if pending_seen:
                raise ValueError(f"published entry after pending gap violates strict order: {post.publication_id}")
            if entry.provider_effect != "verified" or not entry.message_id:
                raise ValueError(f"runtime checkpoint requires verified published prefix: {post.publication_id}")
            if (
                entry.actual_chat_id != CHAT_ID
                or entry.actual_chat_username != "lordchrist"
                or entry.bot_id != BOT_ID
                or entry.bot_username != BOT_USERNAME
            ):
                raise ValueError(f"published progress target differs from canonical LordChrist: {post.publication_id}")
            if entry.message_id in message_ids:
                raise ValueError("published progress contains duplicate Telegram message identity")
            message_ids.add(entry.message_id)
            prefix += 1
            if allow_progress and prefix > minimum_published:
                if evidence_root is None or policy is None:
                    raise ValueError("ongoing quote progress requires durable v4 rendering evidence")
                # Published entries already have schema-validated provenance. Require
                # decimal GitHub IDs before using them as relative path components.
                if not entry.workflow_run_id or not entry.workflow_run_id.isdecimal():
                    raise ValueError("published quote run id is not a numeric GitHub identity")
                evidence = evidence_root / f"{entry.workflow_run_id}-{entry.workflow_run_attempt}" / "rendered.json"
                rendered = load_rendered_post(evidence)
                verify_rendered_post(cast(TelegramPost, post), policy, rendered)
        else:
            pending_seen = True
            if entry.state != "pending" or entry.provider_effect not in PRISTINE_EFFECTS:
                raise ValueError(f"runtime checkpoint requires pristine pending suffix: {post.publication_id}")
            if any(
                value is not None
                for value in (
                    entry.intent_id,
                    entry.dispatch_mode,
                    entry.scheduled_slot,
                    entry.workflow_run_id,
                    entry.workflow_run_attempt,
                    entry.github_sha,
                    entry.github_workflow_sha,
                    entry.attempted_at_utc,
                    entry.published_at_utc,
                    entry.message_id,
                    entry.message_url,
                    entry.actual_chat_id,
                    entry.actual_chat_username,
                    entry.bot_id,
                    entry.bot_username,
                )
            ):
                raise ValueError(
                    f"pending runtime checkpoint retains dispatch/provider identity: {post.publication_id}"
                )
    if prefix < minimum_published:
        raise ValueError(f"verified published prefix {prefix} is behind migration boundary {minimum_published}")
    if not allow_progress and prefix != minimum_published:
        raise ValueError(f"published prefix is {prefix}, checkpoint requires {minimum_published}")
    return prefix
