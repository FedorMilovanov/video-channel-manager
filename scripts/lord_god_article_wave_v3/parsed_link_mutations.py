from __future__ import annotations

from pathlib import Path
from typing import Any

from video_channel_manager.platforms.vk import VkApiClient, VkApiError

from .common import OWNER_ID, normalize_url
from .parsed_link_contract import (
    LINK_PARSE_METHOD,
    WRITE_METHOD,
    contract_guid,
    set_stage,
)
from .parsed_link_preview import parse_link_card
from .parsed_link_state import find_exact, wait_for_exact


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
) -> tuple[int, dict[str, Any], dict[str, Any]]:
    operation_id = str(operation["operation_id"])
    article_url = normalize_url(operation["url"])
    guid = contract_guid(operation, policy, contract)

    set_stage(
        journal,
        journal_path,
        operation,
        "link_parse_intent",
        parse_method=LINK_PARSE_METHOD,
    )
    try:
        parsed = parse_link_card(
            read_client,
            operation,
            expected_metadata,
        )
    except VkApiError as exc:
        stage = "link_parse_rejected" if exc.code is not None else "link_parse_unknown"
        set_stage(
            journal,
            journal_path,
            operation,
            stage,
            parse_method=LINK_PARSE_METHOD,
            error=f"{type(exc).__name__}: {exc}",
        )
        raise RuntimeError(
            f"Link preview preparation failed safely: {operation_id}"
        ) from exc
    except Exception as exc:
        set_stage(
            journal,
            journal_path,
            operation,
            "link_parse_unknown",
            parse_method=LINK_PARSE_METHOD,
            error=f"{type(exc).__name__}: {exc}",
        )
        raise RuntimeError(
            f"Link preview preparation outcome is unknown but read-only: {operation_id}"
        ) from exc

    set_stage(
        journal,
        journal_path,
        operation,
        "link_parsed",
        parse_method=LINK_PARSE_METHOD,
        parsed_title=parsed["title"],
        link_photo_id=parsed["link_photo_id"],
    )
    set_stage(
        journal,
        journal_path,
        operation,
        "wall_post_intent",
        attachment_url=article_url,
        guid=guid,
        parsed_title=parsed["title"],
        link_photo_id=parsed["link_photo_id"],
    )
    params: dict[str, str | int | bool] = {
        "owner_id": OWNER_ID,
        "from_group": True,
        "message": str(operation["message"]),
        "attachments": article_url,
        "publish_date": int(operation["publish_date"]),
        "guid": guid,
        "link_title": str(parsed["title"]),
        "link_photo_id": str(parsed["link_photo_id"]),
    }
    try:
        response = mutation_client._call(WRITE_METHOD, params=params)
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
            parsed_title=parsed["title"],
            link_photo_id=parsed["link_photo_id"],
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
                    parsed_title=parsed["title"],
                    link_photo_id=parsed["link_photo_id"],
                    post_id=post_id,
                    reconciled_from="wall_post_unknown",
                )
                return post_id, reconciled, parsed
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
            parsed_title=parsed["title"],
            link_photo_id=parsed["link_photo_id"],
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
                parsed_title=parsed["title"],
                link_photo_id=parsed["link_photo_id"],
                post_id=post_id,
                reconciled_from="wall_post_unknown",
            )
            return post_id, reconciled, parsed
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
        parsed_title=parsed["title"],
        link_photo_id=parsed["link_photo_id"],
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
            parsed_title=parsed["title"],
            link_photo_id=parsed["link_photo_id"],
            post_id=post_id,
            error=f"{type(exc).__name__}: {exc}",
        )
        raise RuntimeError(
            f"Accepted parsed link-card post requires inspection: {operation_id}"
        ) from exc

    set_stage(
        journal,
        journal_path,
        operation,
        "verified",
        attachment_url=article_url,
        guid=guid,
        parsed_title=parsed["title"],
        link_photo_id=parsed["link_photo_id"],
        post_id=post_id,
    )
    return post_id, reference, parsed
