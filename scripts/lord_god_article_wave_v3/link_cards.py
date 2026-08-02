from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import httpx

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk import VkApiClient, VkApiError, VkTokenStore
from video_channel_manager.platforms.vk.lock import local_vk_write_lock

from .common import (
    ACCOUNT_ALIAS,
    COMMUNITY_ID,
    DECISION_SET_ID,
    HTTP_TIMEOUT_SECONDS,
    MIN_FUTURE_SECONDS,
    MIN_GAP_SECONDS,
    OWNER_ID,
    POST_WAIT_SECONDS,
    bytes_sha,
    canonical_sha,
    canonical_text,
    load_policy,
    metadata_raw_url,
    normalize_url,
    now_iso,
    read_json,
    source_raw_url,
    write_json,
)
from .sources import (
    _compare_live_and_pinned_metadata,
    _decode_utf8,
    _metadata_from_text,
    _response_or_conflict,
    _verify_markers,
    _verify_metadata,
)
from .wall import index_wall, post_reference, state_fingerprint, wall_snapshot

LINK_CARD_CONTRACT_VERSION = 1
LINK_CARD_ATTACHMENT_MODE = "external-link-card"
LINK_CARD_ASSET_MODE = "remote-open-graph-only"
LINK_CARD_BLOCKING_STAGES = frozenset(
    {
        "wall_post_intent",
        "wall_post_rejected",
        "wall_post_unknown",
        "wall_post_accepted_unverified",
    }
)


def link_card_contract_identity(policy: dict[str, Any]) -> str:
    return canonical_sha(
        {
            "base_execution_contract_sha256": policy["execution_contract_sha256"],
            "attachment_mode": LINK_CARD_ATTACHMENT_MODE,
            "asset_mode": LINK_CARD_ASSET_MODE,
            "journal_schema_version": LINK_CARD_CONTRACT_VERSION,
            "wall_post_attachment": "exact-article-url",
            "separate_vk_photo": False,
        }
    )


def audit_link_card_sources(
    policy: dict[str, Any],
    *,
    client_factory: Callable[..., httpx.Client] = httpx.Client,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/148 Safari/537.36"
        )
    }
    rows: list[dict[str, Any]] = []
    checked_urls: list[str] = []
    global_conflicts: list[dict[str, str]] = []

    with client_factory(
        headers=headers,
        follow_redirects=True,
        timeout=HTTP_TIMEOUT_SECONDS,
    ) as http:
        for operation in policy["operations"]:
            operation_id = str(operation["operation_id"])
            article_url = normalize_url(operation["url"])
            image_url = normalize_url(operation["image_url"])
            content_url = source_raw_url(policy, operation)
            metadata_url = metadata_raw_url(policy, operation)
            markers = [str(value) for value in operation["source_markers"]]
            row: dict[str, Any] = {
                "operation_id": operation_id,
                "article_url": article_url,
                "image_url": image_url,
                "content_source_path": str(operation["source_path"]),
                "content_source_url": content_url,
                "metadata_source_path": str(operation["metadata_source_path"]),
                "metadata_source_url": metadata_url,
                "conflicts": [],
                "checks": {
                    "live_page_verified": False,
                    "live_content_markers_verified": False,
                    "live_og_image_verified": False,
                    "content_source_verified": False,
                    "metadata_source_verified": False,
                    "live_metadata_matches_pinned_source": False,
                },
            }
            live_metadata = None
            pinned_metadata = None

            page_response = _response_or_conflict(
                http,
                url=article_url,
                row=row,
                stage="live_page",
                checked_urls=checked_urls,
            )
            if page_response is not None:
                content_type = page_response.headers.get("content-type", "")
                row["live_page_content_type"] = content_type
                if "text/html" not in content_type.lower():
                    row["conflicts"].append(
                        {
                            "code": "live_page_not_html",
                            "detail": f"Unexpected content-type: {content_type}",
                        }
                    )
                else:
                    live_metadata = _metadata_from_text(
                        page_response.text,
                        row=row,
                        stage="live_page",
                    )
                    if live_metadata is not None and _verify_metadata(
                        live_metadata,
                        article_url=article_url,
                        image_url=image_url,
                        row=row,
                        stage="live_page",
                    ):
                        row["checks"]["live_page_verified"] = True
                    if _verify_markers(
                        page_response.text,
                        markers,
                        row=row,
                        stage="live_content",
                    ):
                        row["checks"]["live_content_markers_verified"] = True

            metadata_response = _response_or_conflict(
                http,
                url=metadata_url,
                row=row,
                stage="metadata_source",
                checked_urls=checked_urls,
            )
            if metadata_response is not None:
                row["metadata_source_bytes"] = len(metadata_response.content)
                row["metadata_source_sha256"] = bytes_sha(metadata_response.content)
                metadata_text = _decode_utf8(
                    metadata_response.content,
                    row=row,
                    stage="metadata_source",
                )
                if metadata_text is not None:
                    pinned_metadata = _metadata_from_text(
                        metadata_text,
                        row=row,
                        stage="metadata_source",
                    )
                    if pinned_metadata is not None and _verify_metadata(
                        pinned_metadata,
                        article_url=article_url,
                        image_url=image_url,
                        row=row,
                        stage="metadata_source",
                    ):
                        row["checks"]["metadata_source_verified"] = True

            if live_metadata is not None and pinned_metadata is not None:
                if _compare_live_and_pinned_metadata(
                    live_metadata,
                    pinned_metadata,
                    row=row,
                ):
                    row["checks"]["live_metadata_matches_pinned_source"] = True

            image_response = _response_or_conflict(
                http,
                url=image_url,
                row=row,
                stage="live_og_image",
                checked_urls=checked_urls,
            )
            if image_response is not None:
                image_content_type = image_response.headers.get("content-type", "")
                row["image_content_type"] = image_content_type
                row["image_bytes"] = len(image_response.content)
                row["image_sha256"] = bytes_sha(image_response.content)
                if not image_content_type.lower().startswith("image/"):
                    row["conflicts"].append(
                        {
                            "code": "live_og_image_not_image",
                            "detail": f"Unexpected content-type: {image_content_type}",
                        }
                    )
                elif len(image_response.content) < 10_000:
                    row["conflicts"].append(
                        {
                            "code": "live_og_image_too_small",
                            "detail": f"Only {len(image_response.content)} bytes",
                        }
                    )
                else:
                    row["checks"]["live_og_image_verified"] = True

            content_response = _response_or_conflict(
                http,
                url=content_url,
                row=row,
                stage="content_source",
                checked_urls=checked_urls,
            )
            if content_response is not None:
                source_bytes = content_response.content
                row["content_source_bytes"] = len(source_bytes)
                row["content_source_sha256"] = bytes_sha(source_bytes)
                if len(source_bytes) < 40:
                    row["conflicts"].append(
                        {
                            "code": "content_source_too_small",
                            "detail": f"Only {len(source_bytes)} bytes",
                        }
                    )
                source_text = _decode_utf8(
                    source_bytes,
                    row=row,
                    stage="content_source",
                )
                if source_text is not None and _verify_markers(
                    source_text,
                    markers,
                    row=row,
                    stage="content_source",
                ):
                    if len(source_bytes) >= 40:
                        row["checks"]["content_source_verified"] = True

            row["status"] = "verified" if not row["conflicts"] else "conflict"
            rows.append(row)

    expected_urls = {
        url
        for operation in policy["operations"]
        for url in (
            normalize_url(operation["url"]),
            normalize_url(operation["image_url"]),
            source_raw_url(policy, operation),
            metadata_raw_url(policy, operation),
        )
    }
    if len(expected_urls) != 40:
        global_conflicts.append(
            {
                "code": "external_resource_contract_not_unique",
                "detail": f"Expected 40 unique resources, found {len(expected_urls)}",
            }
        )
    checked_unique = len(set(checked_urls))
    if checked_unique != 40:
        global_conflicts.append(
            {
                "code": "external_resource_audit_incomplete",
                "detail": f"Attempted {checked_unique} of 40 unique resources",
            }
        )

    def verified(check: str) -> int:
        return sum(bool(row["checks"].get(check)) for row in rows)

    conflicting_operations = sum(row["status"] == "conflict" for row in rows)
    conflict_count = sum(len(row["conflicts"]) for row in rows) + len(
        global_conflicts
    )
    manifest: dict[str, Any] = {
        "schema_name": "video-manager.vk-lord-god-article-link-card-sources",
        "schema_version": 1,
        "generated_at": now_iso(),
        "policy_sha256": policy["policy_sha256"],
        "source_contract_sha256": policy["source_contract_sha256"],
        "link_card_execution_contract_sha256": link_card_contract_identity(policy),
        "attachment_mode": LINK_CARD_ATTACHMENT_MODE,
        "asset_mode": LINK_CARD_ASSET_MODE,
        "status": "verified" if conflict_count == 0 else "blocked",
        "expected_external_resources": 40,
        "external_urls_checked": checked_unique,
        "article_pages_verified": verified("live_page_verified"),
        "live_content_markers_verified": verified(
            "live_content_markers_verified"
        ),
        "og_images_verified": verified("live_og_image_verified"),
        "pinned_source_files_verified": verified("content_source_verified"),
        "pinned_metadata_files_verified": verified("metadata_source_verified"),
        "live_metadata_matches_pinned_source": verified(
            "live_metadata_matches_pinned_source"
        ),
        "prepared_jpeg_assets": 0,
        "vk_photo_uploads_required": False,
        "conflicts": conflict_count,
        "conflicting_operations": conflicting_operations,
        "global_conflicts": global_conflicts,
        "items": rows,
    }
    manifest["manifest_sha256"] = canonical_sha(
        {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    )
    return rows, manifest


def fresh_link_card_journal(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "video-manager.vk-lord-god-article-link-card-journal",
        "schema_version": LINK_CARD_CONTRACT_VERSION,
        "decision_set_id": DECISION_SET_ID,
        "policy_sha256": policy["policy_sha256"],
        "source_contract_sha256": policy["source_contract_sha256"],
        "link_card_execution_contract_sha256": link_card_contract_identity(policy),
        "operations": {},
    }


def load_link_card_journal(path: Path, policy: dict[str, Any]) -> dict[str, Any]:
    journal = read_json(path, fresh_link_card_journal(policy))
    if not isinstance(journal, dict):
        raise RuntimeError("Invalid local link-card journal")
    operations = journal.get("operations")
    if not isinstance(operations, dict):
        raise RuntimeError("Invalid link-card journal operations map")
    expected = fresh_link_card_journal(policy)
    identity_keys = (
        "schema_name",
        "schema_version",
        "decision_set_id",
        "policy_sha256",
        "source_contract_sha256",
        "link_card_execution_contract_sha256",
    )
    if any(journal.get(key) != expected[key] for key in identity_keys):
        stages = {
            str(value.get("stage") or "")
            for value in operations.values()
            if isinstance(value, dict)
        }
        if stages - {""}:
            raise RuntimeError(
                "Link-card journal belongs to another execution contract and contains write state"
            )
        return expected
    return journal


def set_link_card_stage(
    journal: dict[str, Any],
    journal_path: Path,
    operation: dict[str, Any],
    stage: str,
    **values: object,
) -> dict[str, Any]:
    operations = journal["operations"]
    operation_id = str(operation["operation_id"])
    entry = operations.get(operation_id)
    if not isinstance(entry, dict):
        entry = {
            "operation_id": operation_id,
            "article_url": operation["url"],
            "publish_date": operation["publish_date"],
            "message_sha256": operation["message_sha256"],
        }
        operations[operation_id] = entry
    entry.update({"stage": stage, "updated_at": now_iso(), **values})
    journal["updated_at"] = now_iso()
    write_json(journal_path, journal)
    return entry


def observe_legacy_photo_journal(path: Path) -> dict[str, Any]:
    raw = read_json(path, {})
    operations = raw.get("operations") if isinstance(raw, dict) else None
    stages: list[dict[str, str]] = []
    if isinstance(operations, dict):
        for operation_id, value in operations.items():
            if not isinstance(value, dict):
                continue
            stage = str(value.get("stage") or "").strip()
            if stage:
                stages.append(
                    {
                        "operation_id": str(operation_id),
                        "stage": stage,
                    }
                )
    remote_photo_may_exist = any(
        item["stage"]
        in {
            "photo_save_intent",
            "photo_save_unknown",
            "photo_saved",
            "wall_post_intent",
            "wall_post_unknown",
            "wall_post_accepted_unverified",
            "verified",
        }
        for item in stages
    )
    return {
        "schema_name": "video-manager.vk-lord-god-article-legacy-photo-observation",
        "schema_version": 1,
        "generated_at": now_iso(),
        "legacy_journal_path": str(path),
        "legacy_journal_exists": path.is_file(),
        "stages": stages,
        "remote_photo_may_exist": remote_photo_may_exist,
        "legacy_photo_state_is_not_reused": True,
        "note": (
            "A saved but unattached VK photo may exist. Link-card execution never "
            "reuses, attaches, retries, or deletes that legacy photo state."
        ),
    }


def link_card_exact_reference(
    operation: dict[str, Any],
    reference: dict[str, Any],
) -> bool:
    article_url = normalize_url(operation["url"])
    if reference["message"] != canonical_text(operation["message"]):
        return False
    if article_url not in reference["text_urls"]:
        return False
    if article_url not in reference["link_urls"]:
        return False
    if reference["has_photo"]:
        return False
    if reference["queue"] == "postponed" and reference["date"] != operation["publish_date"]:
        return False
    return True


def preflight_link_cards(
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
        references = by_url.get(article_url, [])
        exact = [
            reference
            for reference in references
            if link_card_exact_reference(operation, reference)
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
                "one exact post with reviewed text, exact external link card, "
                "and no separate photo exists"
            )
        elif references:
            state = "conflict"
            detail = "article URL already appears in a non-exact wall post"
        elif nearby:
            state = "conflict"
            detail = "another postponed post is within the two-hour safety gap"
        elif stage in LINK_CARD_BLOCKING_STAGES:
            state = "conflict"
            detail = f"link-card journal stage requires reconciliation: {stage}"
        elif stage == "verified":
            state = "conflict"
            detail = "link-card journal says verified but no exact wall post was found"
        elif int(operation["publish_date"]) <= current + minimum_future_seconds:
            state = "conflict"
            detail = "approved publication time is no longer safely in the future"
        else:
            state = "ready"
            detail = "article is absent and the surrounding time window is free"

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
        "schema_name": "video-manager.vk-lord-god-article-link-card-preflight",
        "schema_version": 1,
        "generated_at": now_iso(),
        "policy_sha256": policy["policy_sha256"],
        "source_contract_sha256": policy["source_contract_sha256"],
        "link_card_execution_contract_sha256": link_card_contract_identity(policy),
        "attachment_mode": LINK_CARD_ATTACHMENT_MODE,
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


def find_exact_link_card(
    client: VkApiClient,
    operation: dict[str, Any],
    *,
    expected_post_id: int | None = None,
) -> dict[str, Any] | None:
    _, postponed = wall_snapshot(client)
    for raw_post in postponed:
        if expected_post_id is not None and raw_post.get("id") != expected_post_id:
            continue
        reference = post_reference(raw_post, "postponed")
        if link_card_exact_reference(operation, reference):
            return reference
    return None


def wait_for_exact_link_card(
    client: VkApiClient,
    operation: dict[str, Any],
    *,
    post_id: int,
) -> dict[str, Any]:
    deadline = time.monotonic() + POST_WAIT_SECONDS
    last: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        _, postponed = wall_snapshot(client)
        for raw_post in postponed:
            if raw_post.get("owner_id") != OWNER_ID or raw_post.get("id") != post_id:
                continue
            reference = post_reference(raw_post, "postponed")
            last = reference
            if reference["message"] != canonical_text(operation["message"]):
                raise RuntimeError(f"Accepted post text differs: {operation['operation_id']}")
            if reference["date"] != operation["publish_date"]:
                raise RuntimeError(f"Accepted post time differs: {operation['operation_id']}")
            article_url = normalize_url(operation["url"])
            if article_url not in reference["text_urls"]:
                raise RuntimeError(
                    f"Accepted post text lacks article URL: {operation['operation_id']}"
                )
            if article_url not in reference["link_urls"]:
                raise RuntimeError(
                    f"Accepted post lacks external link card: {operation['operation_id']}"
                )
            if reference["has_photo"]:
                raise RuntimeError(
                    f"Accepted post unexpectedly has a separate photo: {operation['operation_id']}"
                )
            return reference
        time.sleep(3)
    if last is None:
        raise RuntimeError(
            f"Accepted postponed link-card post is not visible after {POST_WAIT_SECONDS}s"
        )
    raise RuntimeError(
        f"Accepted postponed post is not an exact link card after {POST_WAIT_SECONDS}s"
    )


def response_post_id(response: object) -> int:
    value = (
        response
        if isinstance(response, int)
        else response.get("post_id")
        if isinstance(response, dict)
        else None
    )
    if isinstance(value, int) and value > 0:
        return value
    raise RuntimeError(f"wall.post returned no positive post ID: {response!r}")


def submit_link_card_post(
    *,
    operation: dict[str, Any],
    read_client: VkApiClient,
    mutation_client: VkApiClient,
    journal: dict[str, Any],
    journal_path: Path,
) -> tuple[int, dict[str, Any]]:
    operation_id = str(operation["operation_id"])
    article_url = normalize_url(operation["url"])
    set_link_card_stage(
        journal,
        journal_path,
        operation,
        "wall_post_intent",
        attachment_url=article_url,
    )
    try:
        response = mutation_client._call(
            "wall.post",
            params={
                "owner_id": OWNER_ID,
                "from_group": True,
                "message": str(operation["message"]),
                "attachments": article_url,
                "publish_date": int(operation["publish_date"]),
                "guid": f"{operation_id}-link-card-v1",
            },
        )
    except VkApiError as exc:
        explicit = exc.code is not None and not exc.retryable
        stage = "wall_post_rejected" if explicit else "wall_post_unknown"
        set_link_card_stage(
            journal,
            journal_path,
            operation,
            stage,
            attachment_url=article_url,
            error=f"{type(exc).__name__}: {exc}",
        )
        if not explicit:
            reconciled = find_exact_link_card(read_client, operation)
            if reconciled and isinstance(reconciled.get("post_id"), int):
                post_id = int(reconciled["post_id"])
                set_link_card_stage(
                    journal,
                    journal_path,
                    operation,
                    "verified",
                    attachment_url=article_url,
                    post_id=post_id,
                    reconciled_from="wall_post_unknown",
                )
                return post_id, reconciled
        raise RuntimeError(
            f"wall.post link-card outcome is {stage}; do not retry blindly: {operation_id}"
        ) from exc
    except Exception as exc:
        set_link_card_stage(
            journal,
            journal_path,
            operation,
            "wall_post_unknown",
            attachment_url=article_url,
            error=f"{type(exc).__name__}: {exc}",
        )
        reconciled = find_exact_link_card(read_client, operation)
        if reconciled and isinstance(reconciled.get("post_id"), int):
            post_id = int(reconciled["post_id"])
            set_link_card_stage(
                journal,
                journal_path,
                operation,
                "verified",
                attachment_url=article_url,
                post_id=post_id,
                reconciled_from="wall_post_unknown",
            )
            return post_id, reconciled
        raise RuntimeError(
            f"wall.post link-card outcome is unknown; do not retry blindly: {operation_id}"
        ) from exc

    post_id = response_post_id(response)
    set_link_card_stage(
        journal,
        journal_path,
        operation,
        "wall_post_accepted",
        attachment_url=article_url,
        post_id=post_id,
    )
    try:
        reference = wait_for_exact_link_card(
            read_client,
            operation,
            post_id=post_id,
        )
    except Exception as exc:
        set_link_card_stage(
            journal,
            journal_path,
            operation,
            "wall_post_accepted_unverified",
            attachment_url=article_url,
            post_id=post_id,
            error=f"{type(exc).__name__}: {exc}",
        )
        raise RuntimeError(
            f"Accepted link-card post requires inspection: {operation_id}"
        ) from exc

    set_link_card_stage(
        journal,
        journal_path,
        operation,
        "verified",
        attachment_url=article_url,
        post_id=post_id,
    )
    return post_id, reference


def review_markdown(policy: dict[str, Any], report: dict[str, Any]) -> str:
    states = {item["operation_id"]: item["state"] for item in report["states"]}
    lines = [
        "# Господь Бог — Сила Моя: 10 link-карточек",
        "",
        "- Время: ежедневно в 14:00 UTC+03:00.",
        "- Интервал до другого отложенного поста: не менее двух часов.",
        "- Вложение: точный URL статьи как внешняя link-карточка VK.",
        "- Отдельные фотографии VK не загружаются и не прикрепляются.",
        "- OG-изображение, заголовок и описание берутся с сайта.",
        "- Порядок: Plan → Canary → ручная проверка → Apply.",
        "",
    ]
    for operation in policy["operations"]:
        lines.extend(
            [
                f"## {operation['ordinal']}. {operation['title']}",
                "",
                f"- Время: `{operation['publish_at']}`",
                f"- Статус: `{states[operation['operation_id']]}`",
                f"- Link-card URL: {operation['url']}",
                f"- Проверенный OG image: {operation['image_url']}",
                "",
                str(operation["message"]),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def execute_scope(
    *,
    mode: str,
    policy: dict[str, Any],
    read_client: VkApiClient,
    mutation_client: VkApiClient,
    settings: Any,
    report: dict[str, Any],
    journal: dict[str, Any],
    journal_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    if os.environ.get("VCM_ALLOW_WALL_POSTS") != "1":
        raise RuntimeError("Execution requires VCM_ALLOW_WALL_POSTS=1")

    states = {item["operation_id"]: item["state"] for item in report["states"]}
    canary = policy["operations"][0]
    canary_id = str(canary["operation_id"])
    if mode == "canary":
        selected = [canary]
        result_path = output_dir / "link-card-canary-result.json"
    elif mode == "apply":
        if states.get(canary_id) != "already_applied":
            raise RuntimeError("Apply requires the verified link-card canary post")
        selected = policy["operations"][1:]
        result_path = output_dir / "link-card-result.json"
    else:
        raise ValueError(f"Unsupported execution mode: {mode}")

    result: dict[str, Any] = {
        "schema_name": "video-manager.vk-lord-god-article-link-card-result",
        "schema_version": 1,
        "mode": mode,
        "status": "running",
        "policy_sha256": policy["policy_sha256"],
        "source_contract_sha256": policy["source_contract_sha256"],
        "link_card_execution_contract_sha256": link_card_contract_identity(policy),
        "attachment_mode": LINK_CARD_ATTACHMENT_MODE,
        "separate_vk_photo": False,
        "started_at": now_iso(),
        "operations": [],
    }
    write_json(result_path, result)

    lock_path = settings.data_dir / "locks" / f"vk-wall-{COMMUNITY_ID}.lock"
    with local_vk_write_lock(
        lock_path,
        account=ACCOUNT_ALIAS,
        community_id=COMMUNITY_ID,
        operation=f"{DECISION_SET_ID}-link-card-{mode}",
    ):
        locked_published, locked_postponed = wall_snapshot(read_client)
        locked = preflight_link_cards(
            policy,
            locked_published,
            locked_postponed,
            journal,
        )
        if locked["conflicts"] or state_fingerprint(locked) != state_fingerprint(report):
            raise RuntimeError("Locked link-card preflight differs from reviewed preflight")
        locked_states = {item["operation_id"]: item["state"] for item in locked["states"]}

        for operation in selected:
            operation_id = str(operation["operation_id"])
            if locked_states[operation_id] == "already_applied":
                result["operations"].append(
                    {"operation_id": operation_id, "status": "already_applied"}
                )
                write_json(result_path, result)
                continue
            if locked_states[operation_id] != "ready":
                raise RuntimeError(f"Operation is not ready: {operation_id}")

            post_id, reference = submit_link_card_post(
                operation=operation,
                read_client=read_client,
                mutation_client=mutation_client,
                journal=journal,
                journal_path=journal_path,
            )
            result["operations"].append(
                {
                    "operation_id": operation_id,
                    "post_id": post_id,
                    "status": "verified",
                    "publish_at": operation["publish_at"],
                    "article_url_in_text": True,
                    "external_link_card_verified": (
                        normalize_url(operation["url"]) in reference["link_urls"]
                    ),
                    "separate_photo_absent": not bool(reference["has_photo"]),
                }
            )
            write_json(result_path, result)
            print(
                f"SCHEDULED LINK CARD {operation['ordinal']}/10 "
                f"post={OWNER_ID}_{post_id} photo=no url-card=yes"
            )
            time.sleep(1)

        final_published, final_postponed = wall_snapshot(read_client)
        final = preflight_link_cards(
            policy,
            final_published,
            final_postponed,
            journal,
            minimum_future_seconds=0,
        )
        postflight_path = (
            output_dir / "link-card-canary-postflight.json"
            if mode == "canary"
            else output_dir / "link-card-postflight.json"
        )
        write_json(postflight_path, final)
        expected_applied = 1 if mode == "canary" else 10
        if final["conflicts"] or final["already_applied"] != expected_applied:
            raise RuntimeError(
                f"{mode.capitalize()} link-card postflight verified "
                f"{final['already_applied']} of {expected_applied}"
            )
        if mode == "canary" and final["ready"] != 9:
            raise RuntimeError("Canary did not leave exactly nine ready link-card posts")
        if mode == "apply" and final["ready"] != 0:
            raise RuntimeError("Apply left unscheduled link-card article posts")

        verified_now = sum(
            1 for item in result["operations"] if item.get("status") == "verified"
        )
        result.update(
            {
                "status": "completed",
                "completed_at": now_iso(),
                "verified_operations": expected_applied,
                "verified_postponed": expected_applied,
                "verified_external_link_cards": expected_applied,
                "verified_posts_without_separate_photos": expected_applied,
                "verified_operations_this_run": verified_now,
                "verified_article_urls_in_text": expected_applied,
                "conflicts": 0,
                "first_publish_at": policy["summary"]["first_publish_at"],
                "last_publish_at": (
                    canary["publish_at"]
                    if mode == "canary"
                    else policy["summary"]["last_publish_at"]
                ),
            }
        )
        write_json(result_path, result)
    return result


def run(repo: Path, *, mode: str) -> int:
    repo = repo.resolve()
    output_dir = repo / "data" / "vk-wall" / DECISION_SET_ID
    output_dir.mkdir(parents=True, exist_ok=True)

    policy = load_policy(repo)
    write_json(output_dir / "link-card-plan.json", policy)

    _, source_manifest = audit_link_card_sources(policy)
    source_audit_path = output_dir / "link-card-source-audit.json"
    write_json(source_audit_path, source_manifest)
    source_summary = {
        "source_manifest_schema_version": source_manifest["schema_version"],
        "status": source_manifest["status"],
        "expected_external_resources": source_manifest[
            "expected_external_resources"
        ],
        "external_urls_checked": source_manifest["external_urls_checked"],
        "article_pages_verified": source_manifest["article_pages_verified"],
        "live_content_markers_verified": source_manifest[
            "live_content_markers_verified"
        ],
        "og_images_verified": source_manifest["og_images_verified"],
        "pinned_source_files_verified": source_manifest[
            "pinned_source_files_verified"
        ],
        "pinned_metadata_files_verified": source_manifest[
            "pinned_metadata_files_verified"
        ],
        "live_metadata_matches_pinned_source": source_manifest[
            "live_metadata_matches_pinned_source"
        ],
        "prepared_jpeg_assets": source_manifest["prepared_jpeg_assets"],
        "vk_photo_uploads_required": source_manifest[
            "vk_photo_uploads_required"
        ],
        "conflicts": source_manifest["conflicts"],
        "source_audit": str(source_audit_path),
    }
    expected_source_summary = {
        "source_manifest_schema_version": 1,
        "status": "verified",
        "expected_external_resources": 40,
        "external_urls_checked": 40,
        "article_pages_verified": 10,
        "live_content_markers_verified": 10,
        "og_images_verified": 10,
        "pinned_source_files_verified": 10,
        "pinned_metadata_files_verified": 10,
        "live_metadata_matches_pinned_source": 10,
        "prepared_jpeg_assets": 0,
        "vk_photo_uploads_required": False,
        "conflicts": 0,
    }
    source_gate_errors = [
        f"{key}={source_summary.get(key)!r}, expected {value!r}"
        for key, value in expected_source_summary.items()
        if source_summary.get(key) != value
    ]
    if source_gate_errors:
        print(json.dumps(source_summary, ensure_ascii=False, indent=2))
        raise RuntimeError(
            "Link-card source audit blocked the queue: "
            + "; ".join(source_gate_errors)
            + f"; all findings are in {source_audit_path}"
        )

    settings = get_settings()
    read_client = VkApiClient(
        token_store=VkTokenStore(settings.data_dir),
        account_alias=ACCOUNT_ALIAS,
        api_version=settings.vk_api_version,
        max_attempts=4,
    )
    mutation_client = VkApiClient(
        token_store=VkTokenStore(settings.data_dir),
        account_alias=ACCOUNT_ALIAS,
        api_version=settings.vk_api_version,
        max_attempts=1,
    )
    community = read_client.get_community(COMMUNITY_ID)
    if (
        community.ref.remote_id != str(COMMUNITY_ID)
        or not community.metadata.get("managed_by_token")
    ):
        raise RuntimeError("Stored token does not manage VK community 60805374")

    legacy_observation = observe_legacy_photo_journal(output_dir / "journal.json")
    write_json(
        output_dir / "legacy-photo-journal-observation.json",
        legacy_observation,
    )

    journal_path = output_dir / "link-card-journal.json"
    journal = load_link_card_journal(journal_path, policy)
    write_json(journal_path, journal)

    published, postponed = wall_snapshot(read_client)
    report = preflight_link_cards(policy, published, postponed, journal)
    preflight_path = output_dir / "link-card-preflight.json"
    write_json(preflight_path, report)
    review_path = output_dir / "link-card-plan-review.md"
    review_path.write_text(review_markdown(policy, report), encoding="utf-8")

    summary = {
        "mode": mode,
        "policy_sha256": policy["policy_sha256"],
        "source_contract_sha256": policy["source_contract_sha256"],
        "link_card_execution_contract_sha256": link_card_contract_identity(policy),
        "attachment_mode": LINK_CARD_ATTACHMENT_MODE,
        "asset_mode": LINK_CARD_ASSET_MODE,
        **source_summary,
        "vk_photo_api_calls": 0,
        "legacy_photo_state_observed": legacy_observation[
            "remote_photo_may_exist"
        ],
        "operations": report["total_operations"],
        "ready": report["ready"],
        "already_applied": report["already_applied"],
        "conflicts": report["conflicts"],
        "postponed_wall_posts_seen": report["postponed_wall_posts"],
        "minimum_gap_minutes": report["minimum_gap_minutes"],
        "first_publish_at": policy["summary"]["first_publish_at"],
        "last_publish_at": policy["summary"]["last_publish_at"],
        "preflight": str(preflight_path),
        "plan_review": str(review_path),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if report["conflicts"]:
        raise RuntimeError(
            "Link-card article queue blocked: "
            + "; ".join(report["global_conflicts"])
        )

    if mode == "plan":
        print(
            "READ-ONLY LINK-CARD PLAN COMPLETE. "
            "No photo upload, photo save, or wall post was sent."
        )
        return 0

    result = execute_scope(
        mode=mode,
        policy=policy,
        read_client=read_client,
        mutation_client=mutation_client,
        settings=settings,
        report=report,
        journal=journal,
        journal_path=journal_path,
        output_dir=output_dir,
    )
    result_path = output_dir / (
        "link-card-canary-result.json"
        if mode == "canary"
        else "link-card-result.json"
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "mode": mode,
                "verified_operations": result["verified_operations"],
                "verified_external_link_cards": result[
                    "verified_external_link_cards"
                ],
                "verified_posts_without_separate_photos": result[
                    "verified_posts_without_separate_photos"
                ],
                "result_path": str(result_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--canary", action="store_true")
    modes.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    selected_mode = "canary" if args.canary else "apply" if args.execute else "plan"
    return run(args.repo, mode=selected_mode)


def guarded_main() -> None:
    try:
        raise SystemExit(main())
    except (
        httpx.HTTPError,
        json.JSONDecodeError,
        OSError,
        RuntimeError,
        ValueError,
        VkApiError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
