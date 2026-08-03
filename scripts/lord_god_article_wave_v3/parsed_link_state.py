from __future__ import annotations

import time
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from video_channel_manager.platforms.vk import VkApiClient

from . import link_cards_hardened as core
from . import link_cards_hardened_entry as strict
from .common import (
    MIN_FUTURE_SECONDS,
    MIN_GAP_SECONDS,
    OWNER_ID,
    POST_WAIT_SECONDS,
    normalize_url,
    now_iso,
)
from .parsed_link_contract import LINK_PARSE_METHOD, execution_identity
from .wall import wall_snapshot

BLOCKING_STAGES = frozenset(
    {
        "wall_post_intent",
        "wall_post_rejected",
        "wall_post_unknown",
        "wall_post_accepted",
        "wall_post_accepted_unverified",
    }
)
READ_ONLY_STAGES = frozenset(
    {
        "",
        "link_parse_intent",
        "link_parse_rejected",
        "link_parse_unknown",
        "link_parsed",
    }
)


def preflight(
    policy: dict[str, Any],
    contract: dict[str, Any],
    expectations: dict[str, dict[str, str]],
    published: list[dict[str, Any]],
    postponed: list[dict[str, Any]],
    journal: dict[str, Any],
    *,
    minimum_future_seconds: int = MIN_FUTURE_SECONDS,
) -> dict[str, Any]:
    by_url, postponed_refs = core.index_wall_hardened(published, postponed)
    journal_ops = journal["operations"]
    current = int(datetime.now(UTC).timestamp())
    states: list[dict[str, Any]] = []
    conflicts: list[str] = []

    for operation in policy["operations"]:
        operation_id = str(operation["operation_id"])
        article_url = normalize_url(operation["url"])
        entry = journal_ops.get(operation_id)
        entry = entry if isinstance(entry, dict) else {}
        stage = str(entry.get("stage") or "")
        references = by_url.get(article_url, [])
        exact = [
            reference
            for reference in references
            if strict.strict_exact_reference(
                operation,
                reference,
                expectations[operation_id],
            )
        ]
        nearby = [
            reference
            for reference in postponed_refs
            if reference not in exact
            and isinstance(reference.get("date"), int)
            and abs(int(reference["date"]) - int(operation["publish_date"]))
            < MIN_GAP_SECONDS
        ]

        if len(exact) == 1 and len(references) == 1 and not nearby:
            state = "already_applied"
            detail = (
                "one exact parsed link-card post with reviewed metadata, exact "
                "schedule, and no extra attachments exists"
            )
        elif references:
            state = "conflict"
            detail = "article URL already appears in a non-exact wall post"
        elif nearby:
            state = "conflict"
            detail = "another postponed post is within the two-hour safety gap"
        elif stage in BLOCKING_STAGES:
            state = "conflict"
            detail = f"parsed link-card journal requires reconciliation: {stage}"
        elif stage == "verified":
            state = "conflict"
            detail = "journal says verified but no exact wall post was found"
        elif stage not in READ_ONLY_STAGES:
            state = "conflict"
            detail = f"unknown parsed link-card journal stage: {stage}"
        elif int(operation["publish_date"]) <= current + minimum_future_seconds:
            state = "conflict"
            detail = "approved publication time is no longer safely in the future"
        else:
            state = "ready"
            detail = "article is absent, parsed preview is available, and time is free"

        if state == "conflict":
            conflicts.append(f"{operation_id}: {detail}")
        states.append(
            {
                "operation_id": operation_id,
                "ordinal": operation["ordinal"],
                "article_title": operation["title"],
                "article_url": article_url,
                "publish_at": operation["publish_at"],
                "state": state,
                "detail": detail,
                "journal_stage": stage or None,
                "references": references,
                "nearby_postponed_posts": nearby,
            }
        )

    counts = Counter(item["state"] for item in states)
    return {
        "schema_name": "video-manager.vk-lord-god-article-parsed-link-preflight",
        "schema_version": 3,
        "generated_at": now_iso(),
        "policy_sha256": policy["policy_sha256"],
        "source_contract_sha256": policy["source_contract_sha256"],
        "delivery_contract_sha256": contract["contract_sha256"],
        "parsed_link_execution_contract_sha256": execution_identity(policy, contract),
        "attachment_mode": contract["attachment_mode"],
        "link_preparation_method": LINK_PARSE_METHOD,
        "allowed_attachment_types": contract["allowed_attachment_types"],
        "required_link_attachments": contract["required_link_attachments"],
        "description_match_mode": strict.DESCRIPTION_MATCH_MODE,
        "published_wall_posts": len(published),
        "postponed_wall_posts": len(postponed),
        "minimum_gap_minutes": MIN_GAP_SECONDS // 60,
        "total_operations": len(states),
        "ready": counts["ready"],
        "already_applied": counts["already_applied"],
        "conflicts": counts["conflict"],
        "global_conflicts": conflicts,
        "states": states,
    }


def state_fingerprint(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "operation_id": item["operation_id"],
            "state": item["state"],
            "journal_stage": item["journal_stage"],
            "references": item["references"],
            "nearby_postponed_posts": item["nearby_postponed_posts"],
        }
        for item in report["states"]
    ]


def find_exact(
    client: VkApiClient,
    operation: dict[str, Any],
    expected_metadata: dict[str, str],
    *,
    expected_post_id: int | None = None,
) -> dict[str, Any] | None:
    published, postponed = wall_snapshot(client)
    for queue, posts in (("published", published), ("postponed", postponed)):
        for raw_post in posts:
            if expected_post_id is not None and raw_post.get("id") != expected_post_id:
                continue
            reference = core.hardened_post_reference(raw_post, queue)
            if strict.strict_exact_reference(
                operation,
                reference,
                expected_metadata,
            ):
                return reference
    return None


def wait_for_exact(
    client: VkApiClient,
    operation: dict[str, Any],
    expected_metadata: dict[str, str],
    *,
    post_id: int,
) -> dict[str, Any]:
    deadline = time.monotonic() + POST_WAIT_SECONDS
    last: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        published, postponed = wall_snapshot(client)
        for queue, posts in (("published", published), ("postponed", postponed)):
            for raw_post in posts:
                if (
                    raw_post.get("owner_id") != OWNER_ID
                    or raw_post.get("id") != post_id
                ):
                    continue
                reference = core.hardened_post_reference(raw_post, queue)
                last = reference
                if strict.strict_exact_reference(
                    operation,
                    reference,
                    expected_metadata,
                ):
                    return reference
        time.sleep(3)
    if last is None:
        raise RuntimeError(
            f"Accepted parsed link-card post is not visible after {POST_WAIT_SECONDS}s"
        )
    raise RuntimeError(
        "Accepted post failed parsed link-card verification: "
        f"{operation['operation_id']}"
    )
