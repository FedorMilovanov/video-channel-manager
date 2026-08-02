#!/usr/bin/env python3
"""Verify and schedule ten daily article cards for the theological VK group.

Plan is read-only. Canary schedules only operation 1. Apply requires the canary
to be visible and verified, then schedules the remaining exact operations.
No edit, delete, or immediate-publication method is implemented.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk import VkApiClient, VkApiError, VkTokenStore
from video_channel_manager.platforms.vk.lock import local_vk_write_lock
from video_channel_manager.platforms.vk.wall_content_audit import fetch_wall_posts

PROJECT_KEY = "lord-god-strength"
COMMUNITY_ID = 60805374
OWNER_ID = -60805374
ACCOUNT_ALIAS = "legendary-poet"  # Shared credential alias, not project identity.
DECISION_SET_ID = "lord-god-article-wave-202608"
POLICY_PATH = Path("content/policies/lord-god-article-wave-202608.json")
EXPECTED_SHA = "sha256:b3467af4911d5faa2550b2c2f0e53ce051b0365651e82abfc57cae8a68a66f5a"
MOSCOW = timezone(timedelta(hours=3), name="UTC+03:00")
MIN_GAP_SECONDS = 2 * 60 * 60
MIN_FUTURE_SECONDS = 10 * 60
CARD_WAIT_SECONDS = 90
URL_RE = re.compile(r"https://gospod-bog\.ru/[^\s<>\"']+")
TRAILING_URL_PUNCTUATION = ".,;:!?)]}»”"


class PageMetadata(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.canonical = ""
        self.og_url = ""
        self.og_title = ""
        self.og_description = ""
        self.og_image = ""
        self.robots: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {str(key).lower(): str(value or "").strip() for key, value in attrs}
        tag_name = tag.lower()
        if tag_name == "meta":
            property_name = (attributes.get("property") or attributes.get("name") or "").lower()
            content = attributes.get("content", "")
            if property_name == "og:url" and not self.og_url:
                self.og_url = content
            elif property_name == "og:title" and not self.og_title:
                self.og_title = content
            elif property_name == "og:description" and not self.og_description:
                self.og_description = content
            elif property_name == "og:image" and not self.og_image:
                self.og_image = content
            elif property_name in {"robots", "googlebot", "yandex"}:
                self.robots.append(content.lower())
        elif tag_name == "link" and "canonical" in attributes.get("rel", "").lower().split():
            if not self.canonical:
                self.canonical = attributes.get("href", "")


def now_iso() -> str:
    return datetime.now(UTC).astimezone().isoformat()


def canonical_text(value: object) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def canonical_sha(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def message_sha(value: object) -> str:
    return f"sha256:{hashlib.sha256(canonical_text(value).encode()).hexdigest()}"


def normalize_url(value: object) -> str:
    source = str(value or "").strip().rstrip(TRAILING_URL_PUNCTUATION)
    parsed = urlsplit(source)
    path = parsed.path or "/"
    if path != "/" and "." not in path.rsplit("/", 1)[-1]:
        path = path.rstrip("/") + "/"
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def read_json(path: Path, fallback: object) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else fallback


def load_policy(repo: Path) -> dict[str, Any]:
    value = json.loads((repo / POLICY_PATH).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Article policy root must be an object")
    return value


def validate_policy(policy: dict[str, Any]) -> None:
    expected = {
        "schema_name": "video-manager.vk-lord-god-article-wave-policy",
        "schema_version": 2,
        "decision_set_id": DECISION_SET_ID,
        "project_key": PROJECT_KEY,
        "source_repository": "FedorMilovanov/gb-is-my-strength",
        "source_manifest_blob_sha": "952cfbd8b276fc7e877a784660fb4481dc8bd83f",
        "vk_community_id": COMMUNITY_ID,
        "vk_owner_id": OWNER_ID,
        "schedule_timezone": "UTC+03:00",
        "schedule_hour": 14,
        "minimum_gap_minutes": 120,
        "attachment_mode": "external-link-card-via-wall.parseAttachedLink",
    }
    for key, value in expected.items():
        if policy.get(key) != value:
            raise ValueError(f"Article policy identity mismatch: {key}")

    actual_sha = canonical_sha({key: value for key, value in policy.items() if key != "policy_sha256"})
    if policy.get("policy_sha256") != actual_sha or actual_sha != EXPECTED_SHA:
        raise ValueError("Article policy digest mismatch")

    operations = policy.get("operations")
    if not isinstance(operations, list) or len(operations) != 10:
        raise ValueError("Article policy must contain exactly ten operations")

    seen_operations: set[str] = set()
    seen_urls: set[str] = set()
    seen_dates: set[int] = set()
    previous_date = 0
    for ordinal, operation in enumerate(operations, start=1):
        if not isinstance(operation, dict) or operation.get("ordinal") != ordinal:
            raise ValueError(f"Invalid operation ordinal: {ordinal}")
        operation_id = str(operation.get("operation_id") or "")
        article_url = normalize_url(operation.get("url"))
        image_url = normalize_url(operation.get("og_image"))
        message = canonical_text(operation.get("message"))
        publish_at = datetime.fromisoformat(str(operation.get("publish_at") or ""))
        publish_date = operation.get("publish_date")

        if not operation_id.startswith(f"{DECISION_SET_ID}-{ordinal:02d}-"):
            raise ValueError(f"Invalid operation identity: {ordinal}")
        if not article_url.startswith("https://gospod-bog.ru/"):
            raise ValueError(f"Invalid article URL: {ordinal}")
        if not image_url.startswith("https://gospod-bog.ru/") or not image_url.endswith(".webp"):
            raise ValueError(f"Invalid OG image: {ordinal}")
        if article_url not in message or not 400 <= len(message) <= 1000:
            raise ValueError(f"Invalid post length or missing article URL: {ordinal}")
        if "💬" not in message:
            raise ValueError(f"Missing discussion question: {ordinal}")
        if operation.get("message_sha256") != message_sha(message):
            raise ValueError(f"Message digest mismatch: {ordinal}")
        if not isinstance(publish_date, int) or int(publish_at.timestamp()) != publish_date:
            raise ValueError(f"Schedule mismatch: {ordinal}")
        if publish_at.astimezone(MOSCOW).strftime("%H:%M") != "14:00":
            raise ValueError(f"Unexpected article hour: {ordinal}")
        if publish_date <= previous_date:
            raise ValueError("Article operations are not chronologically ordered")
        if operation_id in seen_operations or article_url in seen_urls or publish_date in seen_dates:
            raise ValueError("Duplicate article operation, URL, or time")

        seen_operations.add(operation_id)
        seen_urls.add(article_url)
        seen_dates.add(publish_date)
        previous_date = publish_date


def webp_dimensions(payload: bytes) -> tuple[int, int] | None:
    if len(payload) < 30 or payload[:4] != b"RIFF" or payload[8:12] != b"WEBP":
        return None
    offset = 12
    while offset + 8 <= len(payload):
        chunk_type = payload[offset : offset + 4]
        chunk_size = int.from_bytes(payload[offset + 4 : offset + 8], "little")
        data_start = offset + 8
        data_end = data_start + chunk_size
        if data_end > len(payload):
            return None
        data = payload[data_start:data_end]
        if chunk_type == b"VP8X" and len(data) >= 10:
            width = 1 + int.from_bytes(data[4:7], "little")
            height = 1 + int.from_bytes(data[7:10], "little")
            return width, height
        if chunk_type == b"VP8 " and len(data) >= 10 and data[3:6] == b"\x9d\x01\x2a":
            width = int.from_bytes(data[6:8], "little") & 0x3FFF
            height = int.from_bytes(data[8:10], "little") & 0x3FFF
            return width, height
        if chunk_type == b"VP8L" and len(data) >= 5 and data[0] == 0x2F:
            bits = int.from_bytes(data[1:5], "little")
            width = (bits & 0x3FFF) + 1
            height = ((bits >> 14) & 0x3FFF) + 1
            return width, height
        offset = data_end + (chunk_size % 2)
    return None


def verify_live_sources(policy: dict[str, Any]) -> list[dict[str, Any]]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/148 Safari/537.36"
    }
    checks: list[dict[str, Any]] = []
    with httpx.Client(headers=headers, follow_redirects=True, timeout=45.0) as http:
        for operation in policy["operations"]:
            expected_url = normalize_url(operation["url"])
            expected_image = normalize_url(operation["og_image"])
            page_response = http.get(expected_url)
            page_response.raise_for_status()
            content_type = page_response.headers.get("content-type", "").lower()
            if "text/html" not in content_type:
                raise RuntimeError(f"Article is not HTML: {operation['operation_id']}")

            metadata = PageMetadata()
            metadata.feed(page_response.text)
            canonical = normalize_url(urljoin(expected_url, metadata.canonical or metadata.og_url or expected_url))
            og_url = normalize_url(urljoin(expected_url, metadata.og_url or canonical))
            og_image = normalize_url(urljoin(expected_url, metadata.og_image))
            if canonical != expected_url or og_url != expected_url:
                raise RuntimeError(f"Live canonical metadata differs: {operation['operation_id']}")
            if og_image != expected_image:
                raise RuntimeError(f"Live OG image differs: {operation['operation_id']}")
            if not metadata.og_title or len(metadata.og_title.strip()) < 12:
                raise RuntimeError(f"Missing usable og:title: {operation['operation_id']}")
            if not metadata.og_description or len(metadata.og_description.strip()) < 60:
                raise RuntimeError(f"Missing usable og:description: {operation['operation_id']}")
            if any("noindex" in directive for directive in metadata.robots):
                raise RuntimeError(f"Article is marked noindex: {operation['operation_id']}")

            image_response = http.get(expected_image)
            image_response.raise_for_status()
            image_type = image_response.headers.get("content-type", "").lower()
            if not image_type.startswith("image/webp"):
                raise RuntimeError(f"OG image is not served as WebP: {operation['operation_id']}")
            image_bytes = image_response.content
            if len(image_bytes) < 10_000:
                raise RuntimeError(f"OG image is unexpectedly small: {operation['operation_id']}")
            dimensions = webp_dimensions(image_bytes)
            if dimensions is None:
                raise RuntimeError(f"Cannot read WebP dimensions: {operation['operation_id']}")
            width, height = dimensions
            if width < 600 or height < 315:
                raise RuntimeError(f"OG image is below 600x315: {operation['operation_id']}")
            ratio = width / height
            if not 1.45 <= ratio <= 2.15:
                raise RuntimeError(f"OG image aspect ratio is unsuitable: {operation['operation_id']}")

            checks.append(
                {
                    "operation_id": operation["operation_id"],
                    "article_url": expected_url,
                    "canonical_url": canonical,
                    "og_title": metadata.og_title,
                    "og_description_length": len(metadata.og_description),
                    "og_image": expected_image,
                    "og_image_width": width,
                    "og_image_height": height,
                    "og_image_bytes": len(image_bytes),
                    "og_image_sha256": f"sha256:{hashlib.sha256(image_bytes).hexdigest()}",
                    "status": "verified",
                }
            )
    return checks


def recursive_image_url(value: object, *, path: tuple[str, ...] = ()) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key).lower()
            next_path = (*path, key_text)
            if isinstance(child, str) and child.startswith(("http://", "https://")):
                if any(
                    marker in segment
                    for segment in next_path
                    for marker in ("photo", "image", "preview", "thumb")
                ):
                    return True
            if recursive_image_url(child, path=next_path):
                return True
    elif isinstance(value, list):
        return any(recursive_image_url(item, path=path) for item in value)
    return False


def link_payload_from_attachment(attachment: object) -> dict[str, Any] | None:
    if not isinstance(attachment, dict) or attachment.get("type") != "link":
        return None
    link = attachment.get("link")
    return link if isinstance(link, dict) else None


def link_has_image(link: dict[str, Any]) -> bool:
    photo = link.get("photo")
    if isinstance(photo, dict):
        sizes = photo.get("sizes")
        if isinstance(sizes, list) and any(
            isinstance(item, dict) and str(item.get("url") or "").startswith(("http://", "https://"))
            for item in sizes
        ):
            return True
    return recursive_image_url(link)


def photo_token(photo: object) -> str | None:
    if not isinstance(photo, dict):
        return None
    owner_id = photo.get("owner_id")
    photo_id = photo.get("id")
    if not isinstance(owner_id, int) or not isinstance(photo_id, int):
        return None
    access_key = str(photo.get("access_key") or "").strip()
    token = f"photo{owner_id}_{photo_id}"
    return f"{token}_{access_key}" if access_key else token


def parsed_photo_tokens(attachments: list[dict[str, Any]], link: dict[str, Any]) -> list[str]:
    tokens: list[str] = []
    nested = photo_token(link.get("photo"))
    if nested:
        tokens.append(nested)
    for attachment in attachments:
        if attachment.get("type") != "photo":
            continue
        token = photo_token(attachment.get("photo"))
        if token:
            tokens.append(token)
    return sorted(set(tokens))


def parse_attached_link(client: VkApiClient, article_url: str) -> dict[str, Any]:
    normalized = normalize_url(article_url)
    links_json = json.dumps(
        [{"type": "link", "link": normalized}],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    response = client._call(
        "wall.parseAttachedLink",
        params={"links": links_json, "extended": False},
    )
    data = response.get("data") if isinstance(response, dict) else None
    attachments = [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []
    links = [link_payload_from_attachment(item) for item in attachments]
    links = [item for item in links if isinstance(item, dict)]
    if len(links) != 1:
        raise RuntimeError(f"wall.parseAttachedLink returned {len(links)} link cards for {normalized}")

    link = links[0]
    resolved = normalize_url(link.get("url") or link.get("target_url") or normalized)
    if resolved != normalized:
        raise RuntimeError(f"VK resolved a different article URL: {normalized} -> {resolved}")
    photo_tokens = parsed_photo_tokens(attachments, link)
    has_image = link_has_image(link) or bool(photo_tokens)
    if not has_image:
        raise RuntimeError(f"VK parsed the article without an image: {normalized}")

    attachment_parts = [*photo_tokens, normalized]
    return {
        "article_url": normalized,
        "resolved_url": resolved,
        "attachment_type": "link",
        "title": str(link.get("title") or ""),
        "description_length": len(str(link.get("description") or "")),
        "link_card_has_image": True,
        "photo_tokens": photo_tokens,
        "wall_post_attachments": ",".join(attachment_parts),
        "status": "verified",
    }


def verify_vk_link_cards(policy: dict[str, Any], client: VkApiClient) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for operation in policy["operations"]:
        checks.append(parse_attached_link(client, str(operation["url"])))
        time.sleep(0.4)
    return checks


def post_reference(post: dict[str, Any], queue: str) -> dict[str, Any]:
    link_urls: list[str] = []
    image_states: list[bool] = []
    has_photo_attachment = False
    attachments = post.get("attachments")
    for attachment in attachments if isinstance(attachments, list) else []:
        if isinstance(attachment, dict) and attachment.get("type") == "photo":
            has_photo_attachment = photo_token(attachment.get("photo")) is not None
        link = link_payload_from_attachment(attachment)
        if link is None:
            continue
        link_url = normalize_url(link.get("url") or link.get("target_url"))
        if link_url:
            link_urls.append(link_url)
            image_states.append(link_has_image(link))

    message = canonical_text(post.get("text"))
    text_urls = [
        normalize_url(match.group(0))
        for match in URL_RE.finditer(message)
        if normalize_url(match.group(0))
    ]
    owner_id = post.get("owner_id")
    post_id = post.get("id")
    return {
        "queue": queue,
        "owner_id": owner_id if isinstance(owner_id, int) else None,
        "post_id": post_id if isinstance(post_id, int) else None,
        "date": post.get("date") if isinstance(post.get("date"), int) else None,
        "message": message,
        "link_urls": sorted(set(link_urls)),
        "text_urls": sorted(set(text_urls)),
        "link_card_has_image": bool(link_urls) and (
            has_photo_attachment or (bool(image_states) and all(image_states))
        ),
        "url": (
            f"https://vk.ru/wall{owner_id}_{post_id}"
            if isinstance(owner_id, int) and isinstance(post_id, int)
            else None
        ),
    }


def wall_snapshot(client: VkApiClient) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return (
        fetch_wall_posts(client, community_id=COMMUNITY_ID, filter_name="owner"),
        fetch_wall_posts(client, community_id=COMMUNITY_ID, filter_name="postponed"),
    )


def wall_indexes(
    published: list[dict[str, Any]],
    postponed: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    by_url: dict[str, list[dict[str, Any]]] = defaultdict(list)
    postponed_references: list[dict[str, Any]] = []
    for queue, posts in (("published", published), ("postponed", postponed)):
        for post in posts:
            reference = post_reference(post, queue)
            if queue == "postponed":
                postponed_references.append(reference)
            for article_url in set(reference["link_urls"] + reference["text_urls"]):
                by_url[article_url].append(reference)
    return dict(by_url), postponed_references


def preflight(
    policy: dict[str, Any],
    published: list[dict[str, Any]],
    postponed: list[dict[str, Any]],
    journal: dict[str, Any],
    *,
    minimum_future_seconds: int = MIN_FUTURE_SECONDS,
) -> dict[str, Any]:
    by_url, postponed_references = wall_indexes(published, postponed)
    journal_operations = (
        journal.get("operations") if isinstance(journal.get("operations"), dict) else {}
    )
    current = int(datetime.now(UTC).timestamp())
    states: list[dict[str, Any]] = []
    conflicts: list[str] = []

    for operation in policy["operations"]:
        operation_id = str(operation["operation_id"])
        article_url = normalize_url(operation["url"])
        expected_message = canonical_text(operation["message"])
        publish_date = int(operation["publish_date"])
        references = by_url.get(article_url, [])
        exact = [
            reference
            for reference in references
            if reference["message"] == expected_message
            and article_url in reference["link_urls"]
            and reference["link_card_has_image"]
            and (
                reference["queue"] == "published"
                or reference["date"] == publish_date
            )
        ]
        nearby = [
            reference
            for reference in postponed_references
            if reference not in exact
            and isinstance(reference.get("date"), int)
            and abs(int(reference["date"]) - publish_date) < MIN_GAP_SECONDS
        ]
        previous = journal_operations.get(operation_id)
        previous_status = previous.get("status") if isinstance(previous, dict) else None

        if len(exact) == 1 and len(references) == 1 and not nearby:
            state, detail = "already_applied", "one exact article card with image exists"
        elif references:
            state, detail = "conflict", "article URL already appears in another wall post"
        elif nearby:
            state, detail = "conflict", "another postponed post is within the two-hour safety gap"
        elif previous_status in {"unknown", "accepted_unverified"}:
            state, detail = "conflict", f"previous outcome requires inspection: {previous_status}"
        elif publish_date <= current + minimum_future_seconds:
            state, detail = "conflict", "approved publication time is no longer safely in the future"
        else:
            state, detail = "ready", "article is absent and the surrounding time window is free"

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
                "references": references,
                "nearby_postponed_posts": nearby,
            }
        )

    counts = Counter(item["state"] for item in states)
    return {
        "schema_name": "video-manager.vk-lord-god-article-wave-preflight",
        "schema_version": 2,
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
            "references": item["references"],
            "nearby_postponed_posts": item["nearby_postponed_posts"],
        }
        for item in report["states"]
    ]


def post_once(client: VkApiClient, operation: dict[str, Any]) -> object:
    parsed = parse_attached_link(client, str(operation["url"]))
    return client._call(
        "wall.post",
        params={
            "owner_id": OWNER_ID,
            "from_group": True,
            "message": str(operation["message"]),
            "attachments": str(parsed["wall_post_attachments"]),
            "publish_date": int(operation["publish_date"]),
            "guid": str(operation["operation_id"]),
        },
    )


def response_post_id(response: object) -> int:
    value = response if isinstance(response, int) else response.get("post_id") if isinstance(response, dict) else None
    if isinstance(value, int) and value > 0:
        return value
    raise RuntimeError(f"wall.post returned no positive post ID: {response!r}")


def wait_for_exact_card(
    client: VkApiClient,
    operation: dict[str, Any],
    post_id: int,
) -> dict[str, Any]:
    deadline = time.monotonic() + CARD_WAIT_SECONDS
    last_reference: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        postponed = fetch_wall_posts(client, community_id=COMMUNITY_ID, filter_name="postponed")
        for raw_post in postponed:
            if raw_post.get("owner_id") != OWNER_ID or raw_post.get("id") != post_id:
                continue
            reference = post_reference(raw_post, "postponed")
            last_reference = reference
            if reference["message"] != canonical_text(operation["message"]):
                raise RuntimeError(f"Accepted post text differs: {operation['operation_id']}")
            if reference["date"] != operation["publish_date"]:
                raise RuntimeError(f"Accepted post time differs: {operation['operation_id']}")
            article_url = normalize_url(operation["url"])
            if article_url in reference["link_urls"] and reference["link_card_has_image"]:
                return reference
        time.sleep(3)

    if last_reference is None:
        raise RuntimeError(f"Accepted postponed post is not visible after {CARD_WAIT_SECONDS}s")
    raise RuntimeError(f"Accepted postponed post has no verified image card after {CARD_WAIT_SECONDS}s")


def review_markdown(policy: dict[str, Any], report: dict[str, Any]) -> str:
    states = {item["operation_id"]: item["state"] for item in report["states"]}
    lines = [
        "# Господь Бог — Сила Моя: 10 ежедневных статей",
        "",
        "- Время: ежедневно в 14:00 UTC+03:00.",
        "- Интервал до любого другого отложенного поста: не менее двух часов.",
        "- Изображение: только проверенная Open Graph-карточка статьи.",
        "- Порядок записи: Plan → Canary (первая статья) → Apply (остальные девять).",
        "",
    ]
    for operation in policy["operations"]:
        lines.extend(
            [
                f"## {operation['ordinal']}. {operation['title']}",
                "",
                f"- Время: `{operation['publish_at']}`",
                f"- Статус: `{states[operation['operation_id']]}`",
                f"- Статья: {operation['url']}",
                f"- OG: {operation['og_image']}",
                "",
                str(operation["message"]),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def fresh_journal(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "video-manager.vk-lord-god-article-wave-journal",
        "schema_version": 2,
        "decision_set_id": DECISION_SET_ID,
        "policy_sha256": policy["policy_sha256"],
        "operations": {},
    }


def load_journal(path: Path, policy: dict[str, Any]) -> dict[str, Any]:
    journal = read_json(path, fresh_journal(policy))
    if not isinstance(journal, dict):
        raise RuntimeError("Invalid local article journal")
    identity_matches = (
        journal.get("decision_set_id") == DECISION_SET_ID
        and journal.get("policy_sha256") == policy["policy_sha256"]
    )
    if identity_matches:
        return journal

    old_operations = journal.get("operations")
    old_items = old_operations.values() if isinstance(old_operations, dict) else []
    statuses = {
        str(item.get("status") or "")
        for item in old_items
        if isinstance(item, dict)
    }
    risky = statuses & {"intent", "unknown", "accepted", "accepted_unverified", "verified"}
    if risky:
        raise RuntimeError(
            "Local journal belongs to an older article plan and contains remote-write state"
        )
    return fresh_journal(policy)


def write_result(path: Path, result: dict[str, Any]) -> None:
    write_json(path, result)


def execute_scope(
    *,
    mode: str,
    policy: dict[str, Any],
    client: VkApiClient,
    settings: Any,
    report: dict[str, Any],
    journal: dict[str, Any],
    journal_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    if os.environ.get("VCM_ALLOW_WALL_POSTS") != "1":
        raise RuntimeError("Execution requires VCM_ALLOW_WALL_POSTS=1")

    states = {item["operation_id"]: item["state"] for item in report["states"]}
    canary_operation = policy["operations"][0]
    canary_id = str(canary_operation["operation_id"])

    if mode == "canary":
        selected = [canary_operation]
        result_path = output_dir / "canary-result.json"
    elif mode == "apply":
        if states.get(canary_id) != "already_applied":
            raise RuntimeError("Apply requires the verified canary article post")
        selected = policy["operations"][1:]
        result_path = output_dir / "result.json"
    else:
        raise ValueError(f"Unsupported execution mode: {mode}")

    result: dict[str, Any] = {
        "schema_name": "video-manager.vk-lord-god-article-wave-result",
        "schema_version": 2,
        "mode": mode,
        "status": "running",
        "policy_sha256": policy["policy_sha256"],
        "started_at": now_iso(),
        "operations": [],
    }
    write_result(result_path, result)

    lock_path = settings.data_dir / "locks" / f"vk-wall-{COMMUNITY_ID}.lock"
    with local_vk_write_lock(
        lock_path,
        account=ACCOUNT_ALIAS,
        community_id=COMMUNITY_ID,
        operation=f"{DECISION_SET_ID}-{mode}",
    ):
        locked_published, locked_postponed = wall_snapshot(client)
        locked = preflight(policy, locked_published, locked_postponed, journal)
        if locked["conflicts"] or state_fingerprint(locked) != state_fingerprint(report):
            raise RuntimeError("Locked article preflight differs from reviewed preflight")
        locked_states = {item["operation_id"]: item["state"] for item in locked["states"]}
        journal_operations = journal.get("operations")
        if not isinstance(journal_operations, dict):
            raise RuntimeError("Invalid journal operations map")

        for operation in selected:
            operation_id = str(operation["operation_id"])
            if locked_states[operation_id] == "already_applied":
                result["operations"].append(
                    {"operation_id": operation_id, "status": "already_applied"}
                )
                write_result(result_path, result)
                continue
            if locked_states[operation_id] != "ready":
                raise RuntimeError(f"Operation is not ready: {operation_id}")

            journal_operations[operation_id] = {
                "status": "intent",
                "article_url": operation["url"],
                "publish_date": operation["publish_date"],
                "message_sha256": operation["message_sha256"],
                "intent_at": now_iso(),
            }
            journal["updated_at"] = now_iso()
            write_json(journal_path, journal)

            try:
                response = post_once(client, operation)
            except VkApiError as exc:
                explicit_rejection = exc.code is not None and not exc.retryable
                status = "rejected" if explicit_rejection else "unknown"
                journal_operations[operation_id].update(
                    {
                        "status": status,
                        "error": f"{type(exc).__name__}: {exc}",
                        "updated_at": now_iso(),
                    }
                )
                journal["updated_at"] = now_iso()
                write_json(journal_path, journal)
                result.update(
                    {
                        "status": f"stopped_{status}",
                        "error": f"{operation_id}: {exc}",
                        "stopped_at": now_iso(),
                    }
                )
                write_result(result_path, result)
                if explicit_rejection:
                    raise RuntimeError(
                        f"VK explicitly rejected {operation_id}; no post was created"
                    ) from exc
                raise RuntimeError(
                    f"wall.post outcome is unknown for {operation_id}; do not retry blindly"
                ) from exc
            except Exception as exc:
                journal_operations[operation_id].update(
                    {
                        "status": "unknown",
                        "error": f"{type(exc).__name__}: {exc}",
                        "updated_at": now_iso(),
                    }
                )
                journal["updated_at"] = now_iso()
                write_json(journal_path, journal)
                result.update(
                    {
                        "status": "stopped_unknown",
                        "error": f"{operation_id}: {exc}",
                        "stopped_at": now_iso(),
                    }
                )
                write_result(result_path, result)
                raise RuntimeError(
                    f"wall.post outcome is unknown for {operation_id}; do not retry blindly"
                ) from exc

            post_id = response_post_id(response)
            journal_operations[operation_id].update(
                {
                    "status": "accepted",
                    "post_id": post_id,
                    "accepted_at": now_iso(),
                }
            )
            journal["updated_at"] = now_iso()
            write_json(journal_path, journal)

            try:
                card = wait_for_exact_card(client, operation, post_id)
            except Exception as exc:
                journal_operations[operation_id].update(
                    {
                        "status": "accepted_unverified",
                        "error": f"{type(exc).__name__}: {exc}",
                        "updated_at": now_iso(),
                    }
                )
                journal["updated_at"] = now_iso()
                write_json(journal_path, journal)
                result.update(
                    {
                        "status": "stopped_accepted_unverified",
                        "error": f"{operation_id}: {exc}",
                        "stopped_at": now_iso(),
                    }
                )
                write_result(result_path, result)
                raise RuntimeError(
                    f"Accepted post requires inspection: {operation_id}"
                ) from exc

            journal_operations[operation_id].update(
                {
                    "status": "verified",
                    "verified_at": now_iso(),
                    "link_card_has_image": True,
                }
            )
            journal["updated_at"] = now_iso()
            write_json(journal_path, journal)
            result["operations"].append(
                {
                    "operation_id": operation_id,
                    "post_id": post_id,
                    "status": "verified",
                    "link_card_has_image": card["link_card_has_image"],
                    "publish_at": operation["publish_at"],
                }
            )
            write_result(result_path, result)
            print(
                f"SCHEDULED {operation['ordinal']}/10 "
                f"post={OWNER_ID}_{post_id} image=yes"
            )
            time.sleep(1)

        final_published, final_postponed = wall_snapshot(client)
        final = preflight(
            policy,
            final_published,
            final_postponed,
            journal,
            minimum_future_seconds=0,
        )
        write_json(
            output_dir / ("canary-postflight.json" if mode == "canary" else "postflight.json"),
            final,
        )
        expected_applied = 1 if mode == "canary" else 10
        if final["conflicts"] or final["already_applied"] != expected_applied:
            raise RuntimeError(
                f"{mode.capitalize()} postflight verified "
                f"{final['already_applied']} of expected {expected_applied}"
            )
        if mode == "canary" and final["ready"] != 9:
            raise RuntimeError("Canary postflight did not leave exactly nine ready posts")
        if mode == "apply" and final["ready"] != 0:
            raise RuntimeError("Apply postflight left unscheduled article posts")

        result.update(
            {
                "status": "completed",
                "completed_at": now_iso(),
                "verified_operations": expected_applied,
                "verified_postponed": expected_applied,
                "verified_link_cards_with_images": expected_applied,
                "separate_uploaded_images": 0,
                "conflicts": 0,
                "first_publish_at": policy["summary"]["first_publish_at"],
                "last_publish_at": (
                    canary_operation["publish_at"]
                    if mode == "canary"
                    else policy["summary"]["last_publish_at"]
                ),
            }
        )
        write_result(result_path, result)
    return result


def run(repo: Path, *, mode: str) -> int:
    repo = repo.resolve()
    output_dir = repo / "data" / "vk-wall" / DECISION_SET_ID
    output_dir.mkdir(parents=True, exist_ok=True)

    policy = load_policy(repo)
    validate_policy(policy)
    write_json(output_dir / "plan.json", policy)

    source_checks = verify_live_sources(policy)
    write_json(
        output_dir / "source-check.json",
        {
            "generated_at": now_iso(),
            "verified": len(source_checks),
            "items": source_checks,
        },
    )

    settings = get_settings()
    client = VkApiClient(
        token_store=VkTokenStore(settings.data_dir),
        account_alias=ACCOUNT_ALIAS,
        api_version=settings.vk_api_version,
    )
    community = client.get_community(COMMUNITY_ID)
    if (
        community.ref.remote_id != str(COMMUNITY_ID)
        or not community.metadata.get("managed_by_token")
    ):
        raise RuntimeError("Stored token does not manage VK community 60805374")

    parsed_cards = verify_vk_link_cards(policy, client)
    write_json(
        output_dir / "vk-link-parse.json",
        {
            "generated_at": now_iso(),
            "verified": len(parsed_cards),
            "items": parsed_cards,
        },
    )

    journal_path = output_dir / "journal.json"
    journal = load_journal(journal_path, policy)
    write_json(journal_path, journal)

    published, postponed = wall_snapshot(client)
    report = preflight(policy, published, postponed, journal)
    write_json(output_dir / "preflight.json", report)
    (output_dir / "plan-review.md").write_text(
        review_markdown(policy, report),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "mode": mode,
                "policy_sha256": policy["policy_sha256"],
                "source_pages_verified": len(source_checks),
                "source_og_images_verified": len(source_checks),
                "vk_link_cards_parsed_with_images": len(parsed_cards),
                "operations": report["total_operations"],
                "ready": report["ready"],
                "already_applied": report["already_applied"],
                "conflicts": report["conflicts"],
                "postponed_wall_posts_seen": report["postponed_wall_posts"],
                "minimum_gap_minutes": report["minimum_gap_minutes"],
                "first_publish_at": policy["summary"]["first_publish_at"],
                "last_publish_at": policy["summary"]["last_publish_at"],
                "plan_review": str(output_dir / "plan-review.md"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if report["conflicts"]:
        raise RuntimeError("Article queue blocked: " + "; ".join(report["global_conflicts"]))

    if mode == "plan":
        print("READ-ONLY ARTICLE PLAN COMPLETE. No VK writes were sent.")
        return 0

    result = execute_scope(
        mode=mode,
        policy=policy,
        client=client,
        settings=settings,
        report=report,
        journal=journal,
        journal_path=journal_path,
        output_dir=output_dir,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "mode": mode,
                "verified_operations": result["verified_operations"],
                "verified_link_cards_with_images": result[
                    "verified_link_cards_with_images"
                ],
                "result_path": str(
                    output_dir
                    / ("canary-result.json" if mode == "canary" else "result.json")
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--canary", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    selected_mode = "canary" if args.canary else "apply" if args.execute else "plan"
    return run(args.repo, mode=selected_mode)


if __name__ == "__main__":
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
        print(f"ERROR: {exc}", file=os.sys.stderr)
        raise SystemExit(2) from exc
