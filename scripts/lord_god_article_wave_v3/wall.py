from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from video_channel_manager.platforms.vk import VkApiClient
from video_channel_manager.platforms.vk.wall_content_audit import fetch_wall_posts

from .common import (
    BLOCKING_JOURNAL_STAGES,
    COMMUNITY_ID,
    DECISION_SET_ID,
    MIN_FUTURE_SECONDS,
    MIN_GAP_SECONDS,
    OWNER_ID,
    PHOTO_TOKEN_RE,
    RESUMABLE_WITH_PHOTO,
    URL_RE,
    canonical_text,
    normalize_url,
    now_iso,
    read_json,
)


def photo_token(photo: object) -> str | None:
    if not isinstance(photo, dict):
        return None
    owner_id = photo.get("owner_id")
    photo_id = photo.get("id")
    if not isinstance(owner_id, int) or not isinstance(photo_id, int):
        return None
    access_key = str(photo.get("access_key") or "").strip()
    base = f"photo{owner_id}_{photo_id}"
    return f"{base}_{access_key}" if access_key else base


def photo_identity_from_token(value: object) -> str | None:
    token = str(value or "").strip()
    match = PHOTO_TOKEN_RE.fullmatch(token)
    return match.group(1) if match else None


def post_reference(post: dict[str, Any], queue: str) -> dict[str, Any]:
    text = canonical_text(post.get("text"))
    text_urls = sorted(
        {
            normalize_url(match.group(0))
            for match in URL_RE.finditer(text)
            if normalize_url(match.group(0))
        }
    )
    link_urls: list[str] = []
    photo_tokens: list[str] = []
    attachments = post.get("attachments")
    for attachment in attachments if isinstance(attachments, list) else []:
        if not isinstance(attachment, dict):
            continue
        attachment_type = str(attachment.get("type") or "")
        if attachment_type == "photo":
            token = photo_token(attachment.get("photo"))
            if token:
                photo_tokens.append(token)
        elif attachment_type == "link":
            link = attachment.get("link")
            if isinstance(link, dict):
                value = normalize_url(link.get("url") or link.get("target_url"))
                if value:
                    link_urls.append(value)

    owner_id = post.get("owner_id")
    post_id = post.get("id")
    return {
        "queue": queue,
        "owner_id": owner_id if isinstance(owner_id, int) else None,
        "post_id": post_id if isinstance(post_id, int) else None,
        "date": post.get("date") if isinstance(post.get("date"), int) else None,
        "message": text,
        "text_urls": sorted(set(text_urls)),
        "link_urls": sorted(set(link_urls)),
        "photo_tokens": sorted(set(photo_tokens)),
        "photo_identities": sorted(
            {
                identity
                for token in photo_tokens
                if (identity := photo_identity_from_token(token)) is not None
            }
        ),
        "has_photo": bool(photo_tokens),
        "url": (
            f"https://vk.ru/wall{owner_id}_{post_id}"
            if isinstance(owner_id, int) and isinstance(post_id, int)
            else None
        ),
    }


def wall_snapshot(
    client: VkApiClient,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return (
        fetch_wall_posts(client, community_id=COMMUNITY_ID, filter_name="owner"),
        fetch_wall_posts(client, community_id=COMMUNITY_ID, filter_name="postponed"),
    )


def index_wall(
    published: list[dict[str, Any]],
    postponed: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    by_url: dict[str, list[dict[str, Any]]] = defaultdict(list)
    postponed_refs: list[dict[str, Any]] = []
    for queue, posts in (("published", published), ("postponed", postponed)):
        for post in posts:
            reference = post_reference(post, queue)
            if queue == "postponed":
                postponed_refs.append(reference)
            for url in set(reference["text_urls"] + reference["link_urls"]):
                by_url[url].append(reference)
    return dict(by_url), postponed_refs


def exact_reference(
    operation: dict[str, Any],
    reference: dict[str, Any],
    *,
    expected_photo_token: str | None,
) -> bool:
    article_url = normalize_url(operation["url"])
    if reference["message"] != canonical_text(operation["message"]):
        return False
    if article_url not in reference["text_urls"]:
        return False
    if not reference["has_photo"]:
        return False
    if reference["queue"] == "postponed" and reference["date"] != operation["publish_date"]:
        return False
    if expected_photo_token:
        expected_identity = photo_identity_from_token(expected_photo_token)
        if expected_identity is None:
            return False
        if expected_identity not in reference["photo_identities"]:
            return False
    return True


def fresh_journal(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "video-manager.vk-lord-god-article-wave-journal",
        "schema_version": 3,
        "decision_set_id": DECISION_SET_ID,
        "policy_sha256": policy["policy_sha256"],
        "operations": {},
    }


def load_journal(path: Path, policy: dict[str, Any]) -> dict[str, Any]:
    journal = read_json(path, fresh_journal(policy))
    if not isinstance(journal, dict):
        raise RuntimeError("Invalid local article journal")
    if (
        journal.get("decision_set_id") != DECISION_SET_ID
        or journal.get("policy_sha256") != policy["policy_sha256"]
    ):
        operations = journal.get("operations")
        if not isinstance(operations, dict):
            raise RuntimeError("Invalid journal operations map")
        stages = {
            str(value.get("stage") or "")
            for value in operations.values()
            if isinstance(value, dict)
        }
        if stages - {"", "prepared", "photo_upload_failed"}:
            raise RuntimeError(
                "Local journal belongs to another plan and contains remote-write state"
            )
        return fresh_journal(policy)
    operations = journal.get("operations")
    if not isinstance(operations, dict):
        raise RuntimeError("Invalid journal operations map")
    return journal


def preflight(
    policy: dict[str, Any],
    published: list[dict[str, Any]],
    postponed: list[dict[str, Any]],
    journal: dict[str, Any],
    *,
    minimum_future_seconds: int = MIN_FUTURE_SECONDS,
) -> dict[str, Any]:
    by_url, postponed_refs = index_wall(published, postponed)
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
        expected_photo = str(entry.get("photo_token") or "").strip() or None
        references = by_url.get(article_url, [])
        exact = [
            ref
            for ref in references
            if exact_reference(
                operation,
                ref,
                expected_photo_token=expected_photo,
            )
        ]
        nearby = [
            ref
            for ref in postponed_refs
            if ref not in exact
            and isinstance(ref.get("date"), int)
            and abs(int(ref["date"]) - int(operation["publish_date"])) < MIN_GAP_SECONDS
        ]

        if len(exact) == 1 and len(references) == 1 and not nearby:
            state = "already_applied"
            detail = "one exact post with the reviewed text URL and a wall photo exists"
        elif references:
            state = "conflict"
            detail = "article URL already appears in another wall post"
        elif nearby:
            state = "conflict"
            detail = "another postponed post is within the two-hour safety gap"
        elif stage in BLOCKING_JOURNAL_STAGES:
            state = "conflict"
            detail = f"journal stage requires reconciliation: {stage}"
        elif stage == "verified":
            state = "conflict"
            detail = "journal says verified but no exact wall post was found"
        elif int(operation["publish_date"]) <= current + minimum_future_seconds:
            state = "conflict"
            detail = "approved publication time is no longer safely in the future"
        else:
            state = "ready"
            detail = (
                f"resumable from {stage}"
                if stage in RESUMABLE_WITH_PHOTO
                else "article is absent and the surrounding time window is free"
            )

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
        "schema_name": "video-manager.vk-lord-god-article-wave-preflight",
        "schema_version": 3,
        "generated_at": now_iso(),
        "policy_sha256": policy["policy_sha256"],
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


def verify_upload_server(read_client: VkApiClient) -> dict[str, Any]:
    response = read_client._call(
        "photos.getWallUploadServer",
        params={"group_id": COMMUNITY_ID},
    )
    upload_url = (
        str(response.get("upload_url") or "").strip()
        if isinstance(response, dict)
        else ""
    )
    parsed = urlsplit(upload_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError("photos.getWallUploadServer returned no usable HTTPS URL")
    return {
        "method": "photos.getWallUploadServer",
        "group_id": COMMUNITY_ID,
        "upload_server_host": parsed.netloc,
        "verified": True,
    }
