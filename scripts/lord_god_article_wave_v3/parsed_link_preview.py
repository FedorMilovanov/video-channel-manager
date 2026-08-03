from __future__ import annotations

import json
from typing import Any

from video_channel_manager.platforms.vk import VkApiClient

from . import link_cards_hardened_entry as strict
from .common import canonical_sha, canonical_text, normalize_url, now_iso
from .parsed_link_contract import LINK_PARSE_METHOD


def parse_request_json(article_url: object) -> str:
    url = normalize_url(article_url)
    if not url:
        raise ValueError("Cannot parse an empty article URL")
    return json.dumps(
        [{"url": url}],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _attachment_type(value: object) -> str:
    if not isinstance(value, dict):
        return "<invalid>"
    return str(value.get("type") or "<missing>").strip()


def parse_link_response(
    response: object,
    *,
    article_url: object,
    expected_metadata: dict[str, str],
) -> dict[str, Any]:
    if not isinstance(response, dict):
        raise RuntimeError("wall.parseAttachedLink returned a non-object response")
    data = response.get("data")
    if not isinstance(data, list):
        raise RuntimeError("wall.parseAttachedLink returned no attachment array")

    expected_url = normalize_url(article_url)
    link_attachments: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    matching_links: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    for attachment in data:
        if not isinstance(attachment, dict) or attachment.get("type") != "link":
            continue
        link = attachment.get("link")
        if not isinstance(link, dict):
            continue
        parsed_url = normalize_url(link.get("url") or link.get("target_url"))
        candidate = (attachment, link, parsed_url)
        link_attachments.append(candidate)
        if parsed_url == expected_url:
            matching_links.append(candidate)

    if not matching_links:
        if len(link_attachments) == 1:
            parsed_url = link_attachments[0][2]
            raise RuntimeError(
                f"Parsed link URL mismatch: {parsed_url!r}, expected {expected_url!r}"
            )
        attachment_types = [_attachment_type(item) for item in data]
        link_urls = [item[2] for item in link_attachments]
        raise RuntimeError(
            "wall.parseAttachedLink returned no matching link attachment; "
            f"attachment_types={attachment_types!r}; link_urls={link_urls!r}"
        )
    if len(matching_links) != 1:
        raise RuntimeError(
            "wall.parseAttachedLink returned multiple matching link attachments"
        )

    _, link, parsed_url = matching_links[0]
    title = canonical_text(link.get("title"))
    description = canonical_text(link.get("description"))
    if title != canonical_text(expected_metadata["title"]):
        raise RuntimeError("Parsed link title does not match audited OG title")
    if not strict.strict_description_matches(
        description,
        expected_metadata["description"],
    ):
        raise RuntimeError("Parsed link description does not match audited OG description")

    photo = link.get("photo")
    if not isinstance(photo, dict):
        raise RuntimeError("Parsed link has no preview photo")
    owner_id = photo.get("owner_id")
    photo_id = photo.get("id")
    if not isinstance(owner_id, int) or owner_id == 0:
        raise RuntimeError("Parsed link preview photo has no valid owner_id")
    if not isinstance(photo_id, int) or photo_id <= 0:
        raise RuntimeError("Parsed link preview photo has no valid id")

    ignored_attachment_types = [
        _attachment_type(item)
        for item in data
        if not (
            isinstance(item, dict)
            and item.get("type") == "link"
            and isinstance(item.get("link"), dict)
            and normalize_url(
                item["link"].get("url") or item["link"].get("target_url")
            )
            == expected_url
        )
    ]
    return {
        "article_url": parsed_url,
        "title": title,
        "description": description,
        "photo_owner_id": owner_id,
        "photo_id": photo_id,
        "link_photo_id": f"{owner_id}_{photo_id}",
        "attachment_type": "link",
        "has_preview_photo": True,
        "response_attachment_count": len(data),
        "ignored_attachment_types": ignored_attachment_types,
    }


def parse_link_card(
    client: VkApiClient,
    operation: dict[str, Any],
    expected_metadata: dict[str, str],
) -> dict[str, Any]:
    article_url = normalize_url(operation["url"])
    response = client._call(
        LINK_PARSE_METHOD,
        params={"links": parse_request_json(article_url)},
    )
    return parse_link_response(
        response,
        article_url=article_url,
        expected_metadata=expected_metadata,
    )


def audit_parsed_link_cards(
    client: VkApiClient,
    policy: dict[str, Any],
    expectations: dict[str, dict[str, str]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for operation in policy["operations"]:
        operation_id = str(operation["operation_id"])
        item: dict[str, Any] = {
            "operation_id": operation_id,
            "article_url": normalize_url(operation["url"]),
            "status": "blocked",
            "conflicts": [],
        }
        try:
            parsed = parse_link_card(
                client,
                operation,
                expectations[operation_id],
            )
            item.update(
                {
                    "status": "verified",
                    "parsed_title": parsed["title"],
                    "parsed_description": parsed["description"],
                    "link_photo_id": parsed["link_photo_id"],
                    "preview_photo_owner_id": parsed["photo_owner_id"],
                    "preview_photo_id": parsed["photo_id"],
                    "attachment_type": parsed["attachment_type"],
                    "has_preview_photo": parsed["has_preview_photo"],
                    "response_attachment_count": parsed[
                        "response_attachment_count"
                    ],
                    "ignored_attachment_types": parsed[
                        "ignored_attachment_types"
                    ],
                }
            )
        except Exception as exc:
            item["conflicts"].append(
                {
                    "code": "parse_attached_link_failed",
                    "detail": f"{type(exc).__name__}: {exc}",
                }
            )
        items.append(item)

    conflicts = sum(len(item["conflicts"]) for item in items)
    report = {
        "schema_name": "video-manager.vk-lord-god-article-parsed-link-audit",
        "schema_version": 1,
        "generated_at": now_iso(),
        "method": LINK_PARSE_METHOD,
        "calls": len(items),
        "operations": len(items),
        "verified": sum(item["status"] == "verified" for item in items),
        "conflicts": conflicts,
        "separate_vk_photo": False,
        "vk_photo_api_calls": 0,
        "prepared_jpeg_assets": 0,
        "items": items,
    }
    report["report_sha256"] = canonical_sha(
        {key: value for key, value in report.items() if key != "report_sha256"}
    )
    return items, report
