from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import httpx

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk import VkApiClient, VkApiError, VkTokenStore
from video_channel_manager.platforms.vk.lock import local_vk_write_lock

from . import link_cards as legacy
from .common import (
    ACCOUNT_ALIAS,
    COMMUNITY_ID,
    DECISION_SET_ID,
    HTTP_TIMEOUT_SECONDS,
    JPEG_HEIGHT,
    JPEG_WIDTH,
    MIN_FUTURE_SECONDS,
    MIN_GAP_SECONDS,
    OWNER_ID,
    POST_WAIT_SECONDS,
    URL_RE,
    bytes_sha,
    canonical_sha,
    canonical_text,
    load_policy,
    normalize_url,
    now_iso,
    read_json,
    webp_dimensions,
    write_json,
)
from .wall import state_fingerprint, wall_snapshot

DELIVERY_CONTRACT_PATH = Path(
    "content/policies/lord-god-article-wave-v3-link-card-delivery-contract.json"
)
EXPECTED_DELIVERY_CONTRACT_SHA = (
    "sha256:23ed39ed344d3429140e9bafaaee4aabd8509d0701a916c608ef8d64e68daa96"
)
LINK_CARD_BLOCKING_STAGES = frozenset(
    {
        "wall_post_intent",
        "wall_post_rejected",
        "wall_post_unknown",
        "wall_post_accepted",
        "wall_post_accepted_unverified",
    }
)


def load_delivery_contract(repo: Path) -> dict[str, Any]:
    path = repo / DELIVERY_CONTRACT_PATH
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Link-card delivery contract root must be an object")
    expected = {
        "schema_name": "video-manager.vk-lord-god-article-link-card-delivery-contract",
        "schema_version": 2,
        "decision_set_id": DECISION_SET_ID,
        "base_policy_sha256": (
            "sha256:f0175b4783e6eb8b449a4558bef662b53bd95b583deb71a01ce7edfd1202dcc7"
        ),
        "source_contract_sha256": (
            "sha256:659912a978d7b8442a9a8106783aa12eec81c2facdc1127f6cf21ead01dffac6"
        ),
        "attachment_mode": "external-link-card",
        "asset_mode": "remote-open-graph-only",
        "write_method": "wall.post",
        "attachment_value": "exact-article-url",
        "allowed_attachment_types": ["link"],
        "required_link_attachments": 1,
        "require_link_title_match": True,
        "require_link_description_match": True,
        "require_link_preview_photo": True,
        "separate_vk_photo": False,
        "vk_photo_api_calls": 0,
        "prepared_jpeg_assets": 0,
        "guid_mode": "contract-bound-sha256",
        "journal_schema_version": 2,
        "postflight_requires_exact_schedule": True,
        "postflight_requires_exact_text": True,
    }
    for key, value in expected.items():
        if raw.get(key) != value:
            raise ValueError(f"Link-card delivery contract mismatch: {key}")
    actual = canonical_sha(
        {key: value for key, value in raw.items() if key != "contract_sha256"}
    )
    if raw.get("contract_sha256") != actual or actual != EXPECTED_DELIVERY_CONTRACT_SHA:
        raise ValueError("Link-card delivery contract digest mismatch")
    return raw


def load_hardened_policy(
    repo: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    base = load_policy(repo)
    contract = load_delivery_contract(repo)
    if contract["base_policy_sha256"] != base["policy_sha256"]:
        raise ValueError("Delivery contract does not bind the current base policy")
    if contract["source_contract_sha256"] != base["source_contract_sha256"]:
        raise ValueError("Delivery contract does not bind the current source contract")
    effective = copy.deepcopy(base)
    effective["attachment_mode"] = contract["attachment_mode"]
    effective["asset_mode"] = contract["asset_mode"]
    effective["delivery_contract_sha256"] = contract["contract_sha256"]
    return effective, contract


def execution_identity(
    policy: dict[str, Any],
    contract: dict[str, Any],
) -> str:
    return canonical_sha(
        {
            "base_execution_contract_sha256": policy["execution_contract_sha256"],
            "delivery_contract_sha256": contract["contract_sha256"],
            "operations": [
                {
                    "operation_id": operation["operation_id"],
                    "message_sha256": operation["message_sha256"],
                    "article_url": normalize_url(operation["url"]),
                    "publish_date": operation["publish_date"],
                }
                for operation in policy["operations"]
            ],
        }
    )


def contract_guid(
    operation: dict[str, Any],
    policy: dict[str, Any],
    contract: dict[str, Any],
) -> str:
    digest = execution_identity(policy, contract).split(":", 1)[1]
    return f"lgaw3-{int(operation['ordinal']):02d}-{digest[:24]}"


def _has_preview_photo(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    photo_id = value.get("id")
    if isinstance(photo_id, int) and photo_id > 0:
        return True
    sizes = value.get("sizes")
    if isinstance(sizes, list) and any(isinstance(item, dict) for item in sizes):
        return True
    orig_photo = value.get("orig_photo")
    return isinstance(orig_photo, dict) and bool(orig_photo)


def hardened_post_reference(
    post: dict[str, Any],
    queue: str,
) -> dict[str, Any]:
    text = canonical_text(post.get("text"))
    text_urls = sorted(
        {
            normalize_url(match.group(0))
            for match in URL_RE.finditer(text)
            if normalize_url(match.group(0))
        }
    )
    attachment_types: list[str] = []
    link_cards: list[dict[str, Any]] = []
    separate_photo_count = 0
    attachments = post.get("attachments")
    for attachment in attachments if isinstance(attachments, list) else []:
        if not isinstance(attachment, dict):
            attachment_types.append("<invalid>")
            continue
        attachment_type = str(attachment.get("type") or "<missing>").strip()
        attachment_types.append(attachment_type)
        if attachment_type == "photo":
            separate_photo_count += 1
        if attachment_type != "link":
            continue
        link = attachment.get("link")
        if not isinstance(link, dict):
            link_cards.append(
                {
                    "url": "",
                    "title": "",
                    "description": "",
                    "has_preview_photo": False,
                }
            )
            continue
        link_cards.append(
            {
                "url": normalize_url(link.get("url") or link.get("target_url")),
                "title": canonical_text(link.get("title")),
                "description": canonical_text(link.get("description")),
                "has_preview_photo": _has_preview_photo(link.get("photo")),
            }
        )

    owner_id = post.get("owner_id")
    post_id = post.get("id")
    return {
        "queue": queue,
        "owner_id": owner_id if isinstance(owner_id, int) else None,
        "post_id": post_id if isinstance(post_id, int) else None,
        "date": post.get("date") if isinstance(post.get("date"), int) else None,
        "message": text,
        "text_urls": text_urls,
        "attachment_types": attachment_types,
        "attachment_count": len(attachment_types),
        "link_urls": sorted(
            {card["url"] for card in link_cards if card.get("url")}
        ),
        "link_cards": link_cards,
        "separate_photo_count": separate_photo_count,
        "has_photo": separate_photo_count > 0,
        "url": (
            f"https://vk.ru/wall{owner_id}_{post_id}"
            if isinstance(owner_id, int) and isinstance(post_id, int)
            else None
        ),
    }


def index_wall_hardened(
    published: list[dict[str, Any]],
    postponed: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    by_url: dict[str, list[dict[str, Any]]] = defaultdict(list)
    postponed_refs: list[dict[str, Any]] = []
    for queue, posts in (("published", published), ("postponed", postponed)):
        for post in posts:
            reference = hardened_post_reference(post, queue)
            if queue == "postponed":
                postponed_refs.append(reference)
            for url in set(reference["text_urls"] + reference["link_urls"]):
                by_url[url].append(reference)
    return dict(by_url), postponed_refs


def _description_matches(actual: object, expected: object) -> bool:
    actual_text = canonical_text(actual)
    expected_text = canonical_text(expected)
    if not actual_text or not expected_text:
        return False
    if actual_text == expected_text:
        return True
    shorter, longer = sorted((actual_text, expected_text), key=len)
    return len(shorter) >= 40 and longer.startswith(shorter)


def build_link_expectations(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, str]]:
    expectations: dict[str, dict[str, str]] = {}
    for row in rows:
        operation_id = str(row.get("operation_id") or "")
        title = canonical_text(row.get("live_page_og_title"))
        description = canonical_text(row.get("live_page_og_description"))
        if not operation_id or not title or not description:
            raise RuntimeError(
                f"Missing audited OG metadata expectation: {operation_id or '<unknown>'}"
            )
        expectations[operation_id] = {
            "title": title,
            "description": description,
        }
    if len(expectations) != 10:
        raise RuntimeError(
            f"Expected OG metadata for ten operations, found {len(expectations)}"
        )
    return expectations


def exact_reference(
    operation: dict[str, Any],
    reference: dict[str, Any],
    expected_metadata: dict[str, str],
) -> bool:
    article_url = normalize_url(operation["url"])
    if reference["owner_id"] != OWNER_ID:
        return False
    if reference["date"] != operation["publish_date"]:
        return False
    if reference["message"] != canonical_text(operation["message"]):
        return False
    if article_url not in reference["text_urls"]:
        return False
    if reference["attachment_types"] != ["link"]:
        return False
    cards = reference["link_cards"]
    if not isinstance(cards, list) or len(cards) != 1:
        return False
    card = cards[0]
    if not isinstance(card, dict) or card.get("url") != article_url:
        return False
    if canonical_text(card.get("title")) != canonical_text(expected_metadata["title"]):
        return False
    if not _description_matches(
        card.get("description"),
        expected_metadata["description"],
    ):
        return False
    if not bool(card.get("has_preview_photo")):
        return False
    if reference["has_photo"]:
        return False
    return True


def audit_sources(
    policy: dict[str, Any],
    contract: dict[str, Any],
    *,
    client_factory: Callable[..., httpx.Client] = httpx.Client,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, manifest = legacy.audit_link_card_sources(
        policy,
        client_factory=client_factory,
    )
    rows_by_id = {
        str(row["operation_id"]): row
        for row in rows
        if isinstance(row, dict) and row.get("operation_id")
    }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/148 Safari/537.36"
        )
    }
    with client_factory(
        headers=headers,
        follow_redirects=True,
        timeout=HTTP_TIMEOUT_SECONDS,
    ) as http:
        for operation in policy["operations"]:
            operation_id = str(operation["operation_id"])
            row = rows_by_id[operation_id]
            checks = row["checks"]
            checks["og_image_dimensions_verified"] = False
            image_url = normalize_url(operation["image_url"])
            try:
                response = http.get(image_url)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                row["conflicts"].append(
                    {
                        "code": "og_dimension_http_error",
                        "detail": str(exc),
                    }
                )
                continue
            payload = response.content
            dimensions = webp_dimensions(payload)
            row["dimension_check_sha256"] = bytes_sha(payload)
            row["og_image_dimensions"] = (
                list(dimensions) if dimensions is not None else None
            )
            if dimensions is None:
                row["conflicts"].append(
                    {
                        "code": "og_image_dimensions_unreadable",
                        "detail": "OG image is not a readable WebP",
                    }
                )
                continue
            width, height = dimensions
            ratio = width / height
            target_ratio = JPEG_WIDTH / JPEG_HEIGHT
            row["og_image_ratio"] = ratio
            if width < 600 or height < 315:
                row["conflicts"].append(
                    {
                        "code": "og_image_dimensions_too_small",
                        "detail": f"{width}x{height} is below 600x315",
                    }
                )
                continue
            if abs(ratio - target_ratio) > 0.08:
                row["conflicts"].append(
                    {
                        "code": "og_image_ratio_mismatch",
                        "detail": (
                            f"ratio {ratio:.4f} differs from target "
                            f"{target_ratio:.4f}"
                        ),
                    }
                )
                continue
            checks["og_image_dimensions_verified"] = True

    for row in rows:
        row["status"] = "verified" if not row["conflicts"] else "conflict"

    global_conflicts = manifest.get("global_conflicts")
    if not isinstance(global_conflicts, list):
        global_conflicts = []
    conflict_count = sum(len(row["conflicts"]) for row in rows) + len(
        global_conflicts
    )
    manifest.update(
        {
            "schema_name": (
                "video-manager.vk-lord-god-article-link-card-hardened-sources"
            ),
            "schema_version": 2,
            "delivery_contract_sha256": contract["contract_sha256"],
            "link_card_execution_contract_sha256": execution_identity(
                policy, contract
            ),
            "attachment_mode": contract["attachment_mode"],
            "asset_mode": contract["asset_mode"],
            "status": "verified" if conflict_count == 0 else "blocked",
            "og_image_dimensions_verified": sum(
                bool(row["checks"].get("og_image_dimensions_verified"))
                for row in rows
            ),
            "prepared_jpeg_assets": 0,
            "vk_photo_uploads_required": False,
            "conflicts": conflict_count,
            "conflicting_operations": sum(
                row["status"] == "conflict" for row in rows
            ),
            "global_conflicts": global_conflicts,
            "items": rows,
        }
    )
    manifest["manifest_sha256"] = canonical_sha(
        {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    )
    return rows, manifest


def fresh_journal(
    policy: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_name": "video-manager.vk-lord-god-article-link-card-journal",
        "schema_version": contract["journal_schema_version"],
        "decision_set_id": DECISION_SET_ID,
        "policy_sha256": policy["policy_sha256"],
        "source_contract_sha256": policy["source_contract_sha256"],
        "delivery_contract_sha256": contract["contract_sha256"],
        "link_card_execution_contract_sha256": execution_identity(policy, contract),
        "operations": {},
    }


def load_journal(
    path: Path,
    policy: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    expected = fresh_journal(policy, contract)
    journal = read_json(path, expected)
    if not isinstance(journal, dict):
        raise RuntimeError("Invalid local hardened link-card journal")
    operations = journal.get("operations")
    if not isinstance(operations, dict):
        raise RuntimeError("Invalid hardened link-card journal operations map")
    identity_keys = (
        "schema_name",
        "schema_version",
        "decision_set_id",
        "policy_sha256",
        "source_contract_sha256",
        "delivery_contract_sha256",
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
                "Hardened link-card journal belongs to another execution "
                "contract and contains write state"
            )
        return expected
    return journal


def set_stage(
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
    by_url, postponed_refs = index_wall_hardened(published, postponed)
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
            if exact_reference(
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
                "one exact post with the reviewed link title, description, "
                "preview image, exact schedule, and no extra attachments exists"
            )
        elif references:
            state = "conflict"
            detail = "article URL already appears in a non-exact wall post"
        elif nearby:
            state = "conflict"
            detail = "another postponed post is within the two-hour safety gap"
        elif stage in LINK_CARD_BLOCKING_STAGES:
            state = "conflict"
            detail = f"hardened link-card journal requires reconciliation: {stage}"
        elif stage == "verified":
            state = "conflict"
            detail = "journal says verified but no exact wall post was found"
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
        "schema_name": (
            "video-manager.vk-lord-god-article-link-card-hardened-preflight"
        ),
        "schema_version": 2,
        "generated_at": now_iso(),
        "policy_sha256": policy["policy_sha256"],
        "source_contract_sha256": policy["source_contract_sha256"],
        "delivery_contract_sha256": contract["contract_sha256"],
        "link_card_execution_contract_sha256": execution_identity(policy, contract),
        "attachment_mode": contract["attachment_mode"],
        "allowed_attachment_types": contract["allowed_attachment_types"],
        "required_link_attachments": contract["required_link_attachments"],
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
            reference = hardened_post_reference(raw_post, queue)
            if exact_reference(operation, reference, expected_metadata):
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
                reference = hardened_post_reference(raw_post, queue)
                last = reference
                if exact_reference(operation, reference, expected_metadata):
                    return reference
        time.sleep(3)
    if last is None:
        raise RuntimeError(
            f"Accepted link-card post is not visible after {POST_WAIT_SECONDS}s"
        )
    raise RuntimeError(
        "Accepted post failed hardened link-card verification: "
        f"{operation['operation_id']}"
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


def submit(
    *,
    operation: dict[str, Any],
    expected_metadata: dict[str, str],
    policy: dict[str, Any],
    contract: dict[str, Any],
    read_client: VkApiClient,
    mutation_client: VkApiClient,
    journal: dict[str, Any],
    journal_path: Path,
) -> tuple[int, dict[str, Any]]:
    operation_id = str(operation["operation_id"])
    article_url = normalize_url(operation["url"])
    guid = contract_guid(operation, policy, contract)
    set_stage(
        journal,
        journal_path,
        operation,
        "wall_post_intent",
        attachment_url=article_url,
        guid=guid,
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
                "guid": guid,
            },
        )
    except VkApiError as exc:
        explicit = exc.code is not None and not exc.retryable
        stage = "wall_post_rejected" if explicit else "wall_post_unknown"
        set_stage(
            journal,
            journal_path,
            operation,
            stage,
            attachment_url=article_url,
            guid=guid,
            error=f"{type(exc).__name__}: {exc}",
        )
        if not explicit:
            reconciled = find_exact(
                read_client,
                operation,
                expected_metadata,
            )
            if reconciled and isinstance(reconciled.get("post_id"), int):
                post_id = int(reconciled["post_id"])
                set_stage(
                    journal,
                    journal_path,
                    operation,
                    "verified",
                    attachment_url=article_url,
                    guid=guid,
                    post_id=post_id,
                    reconciled_from="wall_post_unknown",
                )
                return post_id, reconciled
        raise RuntimeError(
            f"wall.post outcome is {stage}; do not retry blindly: {operation_id}"
        ) from exc
    except Exception as exc:
        set_stage(
            journal,
            journal_path,
            operation,
            "wall_post_unknown",
            attachment_url=article_url,
            guid=guid,
            error=f"{type(exc).__name__}: {exc}",
        )
        reconciled = find_exact(
            read_client,
            operation,
            expected_metadata,
        )
        if reconciled and isinstance(reconciled.get("post_id"), int):
            post_id = int(reconciled["post_id"])
            set_stage(
                journal,
                journal_path,
                operation,
                "verified",
                attachment_url=article_url,
                guid=guid,
                post_id=post_id,
                reconciled_from="wall_post_unknown",
            )
            return post_id, reconciled
        raise RuntimeError(
            f"wall.post outcome is unknown; do not retry blindly: {operation_id}"
        ) from exc

    post_id = response_post_id(response)
    set_stage(
        journal,
        journal_path,
        operation,
        "wall_post_accepted",
        attachment_url=article_url,
        guid=guid,
        post_id=post_id,
    )
    try:
        reference = wait_for_exact(
            read_client,
            operation,
            expected_metadata,
            post_id=post_id,
        )
    except Exception as exc:
        set_stage(
            journal,
            journal_path,
            operation,
            "wall_post_accepted_unverified",
            attachment_url=article_url,
            guid=guid,
            post_id=post_id,
            error=f"{type(exc).__name__}: {exc}",
        )
        raise RuntimeError(
            f"Accepted link-card post requires inspection: {operation_id}"
        ) from exc

    set_stage(
        journal,
        journal_path,
        operation,
        "verified",
        attachment_url=article_url,
        guid=guid,
        post_id=post_id,
    )
    return post_id, reference


def review_markdown(
    policy: dict[str, Any],
    contract: dict[str, Any],
    report: dict[str, Any],
    expectations: dict[str, dict[str, str]],
) -> str:
    states = {item["operation_id"]: item["state"] for item in report["states"]}
    lines = [
        "# Господь Бог — Сила Моя: 10 усиленно проверяемых link-карточек",
        "",
        f"- Delivery contract: `{contract['contract_sha256']}`",
        "- Время: ежедневно в 14:00 UTC+03:00.",
        "- Единственное вложение: точный URL статьи.",
        "- Дополнительные фото, видео, документы и прочие вложения запрещены.",
        "- Заголовок и описание карточки сверяются с проверенными OG-метаданными.",
        "- Встроенная превью-обложка карточки обязательна.",
        "- Отдельные фотографии VK не загружаются и не прикрепляются.",
        "- Порядок: Plan → Canary → ручная проверка → Apply.",
        "",
    ]
    for operation in policy["operations"]:
        operation_id = str(operation["operation_id"])
        expected = expectations[operation_id]
        lines.extend(
            [
                f"## {operation['ordinal']}. {operation['title']}",
                "",
                f"- Время: `{operation['publish_at']}`",
                f"- Статус: `{states[operation_id]}`",
                f"- Link-card URL: {operation['url']}",
                f"- Ожидаемый заголовок: {expected['title']}",
                f"- Ожидаемое описание: {expected['description']}",
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
    contract: dict[str, Any],
    expectations: dict[str, dict[str, str]],
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
            raise RuntimeError("Apply requires the verified hardened link-card canary")
        selected = policy["operations"][1:]
        result_path = output_dir / "link-card-result.json"
    else:
        raise ValueError(f"Unsupported execution mode: {mode}")

    result: dict[str, Any] = {
        "schema_name": (
            "video-manager.vk-lord-god-article-link-card-hardened-result"
        ),
        "schema_version": 2,
        "mode": mode,
        "status": "running",
        "policy_sha256": policy["policy_sha256"],
        "source_contract_sha256": policy["source_contract_sha256"],
        "delivery_contract_sha256": contract["contract_sha256"],
        "link_card_execution_contract_sha256": execution_identity(policy, contract),
        "attachment_mode": contract["attachment_mode"],
        "allowed_attachment_types": contract["allowed_attachment_types"],
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
        operation=f"{DECISION_SET_ID}-link-card-hardened-{mode}",
    ):
        locked_published, locked_postponed = wall_snapshot(read_client)
        locked = preflight(
            policy,
            contract,
            expectations,
            locked_published,
            locked_postponed,
            journal,
        )
        if (
            locked["conflicts"]
            or state_fingerprint(locked) != state_fingerprint(report)
        ):
            raise RuntimeError(
                "Locked hardened link-card preflight differs from reviewed preflight"
            )
        locked_states = {
            item["operation_id"]: item["state"] for item in locked["states"]
        }

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

            post_id, reference = submit(
                operation=operation,
                expected_metadata=expectations[operation_id],
                policy=policy,
                contract=contract,
                read_client=read_client,
                mutation_client=mutation_client,
                journal=journal,
                journal_path=journal_path,
            )
            card = reference["link_cards"][0]
            result["operations"].append(
                {
                    "operation_id": operation_id,
                    "post_id": post_id,
                    "status": "verified",
                    "publish_at": operation["publish_at"],
                    "article_url_in_text": True,
                    "single_link_attachment_verified": (
                        reference["attachment_types"] == ["link"]
                    ),
                    "link_title_verified": (
                        canonical_text(card["title"])
                        == canonical_text(expectations[operation_id]["title"])
                    ),
                    "link_description_verified": _description_matches(
                        card["description"],
                        expectations[operation_id]["description"],
                    ),
                    "link_preview_photo_verified": bool(
                        card["has_preview_photo"]
                    ),
                    "separate_photo_absent": not bool(reference["has_photo"]),
                }
            )
            write_json(result_path, result)
            print(
                f"SCHEDULED HARDENED LINK CARD {operation['ordinal']}/10 "
                f"post={OWNER_ID}_{post_id} photo=no extras=no "
                "title=yes description=yes preview=yes"
            )
            time.sleep(1)

        final_published, final_postponed = wall_snapshot(read_client)
        final = preflight(
            policy,
            contract,
            expectations,
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
                f"{mode.capitalize()} hardened link-card postflight verified "
                f"{final['already_applied']} of {expected_applied}"
            )
        if mode == "canary" and final["ready"] != 9:
            raise RuntimeError(
                "Canary did not leave exactly nine ready link-card posts"
            )
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
                "verified_hardened_link_cards": expected_applied,
                "verified_single_link_attachments": expected_applied,
                "verified_link_titles": expected_applied,
                "verified_link_descriptions": expected_applied,
                "verified_link_preview_photos": expected_applied,
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

    policy, contract = load_hardened_policy(repo)
    write_json(output_dir / "link-card-plan.json", policy)
    write_json(output_dir / "link-card-delivery-contract.json", contract)

    source_rows, source_manifest = audit_sources(policy, contract)
    source_audit_path = output_dir / "link-card-source-audit.json"
    write_json(source_audit_path, source_manifest)
    expectations = build_link_expectations(source_rows)
    expected_source_summary = {
        "schema_version": 2,
        "status": "verified",
        "expected_external_resources": 40,
        "external_urls_checked": 40,
        "article_pages_verified": 10,
        "live_content_markers_verified": 10,
        "og_images_verified": 10,
        "og_image_dimensions_verified": 10,
        "pinned_source_files_verified": 10,
        "pinned_metadata_files_verified": 10,
        "live_metadata_matches_pinned_source": 10,
        "prepared_jpeg_assets": 0,
        "vk_photo_uploads_required": False,
        "conflicts": 0,
    }
    source_gate_errors = [
        f"{key}={source_manifest.get(key)!r}, expected {value!r}"
        for key, value in expected_source_summary.items()
        if source_manifest.get(key) != value
    ]
    if source_gate_errors:
        print(json.dumps(source_manifest, ensure_ascii=False, indent=2))
        raise RuntimeError(
            "Hardened link-card source audit blocked the queue: "
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

    legacy_observation = legacy.observe_legacy_photo_journal(
        output_dir / "journal.json"
    )
    write_json(
        output_dir / "legacy-photo-journal-observation.json",
        legacy_observation,
    )

    journal_path = output_dir / "link-card-journal-v2.json"
    journal = load_journal(journal_path, policy, contract)
    write_json(journal_path, journal)

    published, postponed = wall_snapshot(read_client)
    report = preflight(
        policy,
        contract,
        expectations,
        published,
        postponed,
        journal,
    )
    preflight_path = output_dir / "link-card-preflight.json"
    write_json(preflight_path, report)
    review_path = output_dir / "link-card-plan-review.md"
    review_path.write_text(
        review_markdown(policy, contract, report, expectations),
        encoding="utf-8",
    )

    summary = {
        "mode": mode,
        "policy_sha256": policy["policy_sha256"],
        "source_contract_sha256": policy["source_contract_sha256"],
        "delivery_contract_sha256": contract["contract_sha256"],
        "link_card_execution_contract_sha256": execution_identity(
            policy, contract
        ),
        "attachment_mode": contract["attachment_mode"],
        "asset_mode": contract["asset_mode"],
        **{key: source_manifest[key] for key in expected_source_summary},
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
        "source_audit": str(source_audit_path),
        "plan_review": str(review_path),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if report["conflicts"]:
        raise RuntimeError(
            "Hardened link-card article queue blocked: "
            + "; ".join(report["global_conflicts"])
        )

    if mode == "plan":
        print(
            "READ-ONLY HARDENED LINK-CARD PLAN COMPLETE. "
            "No photo upload, photo save, or wall post was sent."
        )
        return 0

    result = execute_scope(
        mode=mode,
        policy=policy,
        contract=contract,
        expectations=expectations,
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
                "verified_hardened_link_cards": result[
                    "verified_hardened_link_cards"
                ],
                "verified_single_link_attachments": result[
                    "verified_single_link_attachments"
                ],
                "verified_link_titles": result["verified_link_titles"],
                "verified_link_descriptions": result[
                    "verified_link_descriptions"
                ],
                "verified_link_preview_photos": result[
                    "verified_link_preview_photos"
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
