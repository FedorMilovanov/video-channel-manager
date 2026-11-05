"""Read-only Milovi Cake School duplicate audit over an exact public VK wall snapshot.

Only a separately installed service application key may be used. This module
never dispatches VK writes and never claims to inspect postponed or native
Article surfaces.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from video_channel_manager.platforms.vk.client import VkApiClient

MILOVI_COMMUNITY_ID = 68859909
MILOVI_OWNER_ID = -68859909
MILOVI_SERVICE_ALIAS = "vk-milovi-cake-service-key"
MAX_PUBLIC_POSTS = 3000
PAGE_SIZE = 100
_SOURCE_ID_RE = re.compile(r"^Source ID: `([a-z0-9-]+)`$", flags=re.MULTILINE)
_ARTICLE_RE = re.compile(
    r"(?<![A-Za-z0-9.])(?:https?://)?french\.milovicake\.ru/articles/([a-z0-9-]+)/?",
    flags=re.IGNORECASE,
)


def source_ids_from_editorial(markdown: str) -> tuple[str, ...]:
    """Read exact canonical source IDs from the reviewed 10-post editorial file."""
    source_ids = tuple(_SOURCE_ID_RE.findall(markdown))
    if len(source_ids) != 10 or len(set(source_ids)) != 10:
        raise ValueError("Milovi editorial source inventory must have exactly 10 distinct IDs")
    for source_id in source_ids:
        canonical = f"https://french.milovicake.ru/articles/{source_id}/"
        if markdown.count(canonical) != 2:
            raise ValueError("Each Milovi School source URL must occur twice in the draft")
    if "project_key=milovi-cake" not in markdown or "community `68859909`" not in markdown:
        raise ValueError("Milovi School editorial identity mismatch")
    if "execution_authorized=false" not in markdown:
        raise ValueError("Milovi School editorial file is not marked provider-inert")
    return source_ids


def _post_texts(post: dict[str, Any]) -> tuple[str, ...]:
    texts: list[str] = []

    def visit(current: dict[str, Any], depth: int) -> None:
        if depth > 8:
            return
        text = current.get("text")
        if isinstance(text, str):
            texts.append(text)
        for attach in current.get("attachments") or []:
            if not isinstance(attach, dict):
                continue
            link = attach.get("link")
            if isinstance(link, dict) and isinstance(link.get("url"), str):
                texts.append(link["url"])
        for history in current.get("copy_history") or []:
            if isinstance(history, dict):
                visit(history, depth + 1)

    visit(post, 0)
    return tuple(texts)


def collect_exact_public_wall(
    client: VkApiClient,
    *,
    community_id: int = MILOVI_COMMUNITY_ID,
    max_posts: int = MAX_PUBLIC_POSTS,
) -> list[dict[str, Any]]:
    """Read exactly one entire stable public-owner wall; fail closed if incomplete."""
    if community_id != MILOVI_COMMUNITY_ID or max_posts <= 0 or max_posts > MAX_PUBLIC_POSTS:
        raise ValueError("Milovi wall identity or bounded audit ceiling mismatch")
    posts: list[dict[str, Any]] = []
    total: int | None = None
    seen: set[int] = set()

    while True:
        page = client._call(
            "wall.get",
            params={
                "owner_id": MILOVI_OWNER_ID,
                "filter": "owner",
                "count": PAGE_SIZE,
                "offset": len(posts),
            },
        )
        if not isinstance(page, dict):
            raise ValueError("VK public wall page is not an object")
        raw_total, items = page.get("count"), page.get("items")
        if type(raw_total) is not int or raw_total < 0 or not isinstance(items, list):
            raise ValueError("VK public wall count/items are malformed")
        if total is None:
            total = raw_total
            if total == 0:
                raise ValueError("Unexpected empty Milovi Cake public wall; absence unknown")
            if total > max_posts:
                raise ValueError("VK public wall exceeds reviewed audit ceiling; absence unknown")
        elif total != raw_total:
            raise ValueError("VK public wall changed during audit; absence unknown")
        if not items and len(posts) < total:
            raise ValueError("VK public wall truncated; absence unknown")
        if len(items) > PAGE_SIZE:
            raise ValueError("VK public wall returned too many items")
        for item in items:
            if not isinstance(item, dict) or item.get("owner_id") != MILOVI_OWNER_ID:
                raise ValueError("VK public wall contains wrong-owner or malformed post")
            post_id = item.get("id")
            if type(post_id) is not int or post_id <= 0 or post_id in seen:
                raise ValueError("VK public wall includes duplicate or invalid post identity")
            seen.add(post_id)
            posts.append(item)
        if len(posts) >= total:
            if len(posts) != total:
                raise ValueError("VK public wall count exceeded stable total")
            return posts


def classify_editorial_wall_posts(posts: list[dict[str, Any]], source_ids: tuple[str, ...]) -> dict[str, Any]:
    """Match actual published wall references without claiming all VK surfaces."""
    matches: dict[str, list[dict[str, Any]]] = {slug: [] for slug in source_ids}
    for post in posts:
        post_id = post["id"]
        urls = {match.group(1).lower() for text in _post_texts(post) for match in _ARTICLE_RE.finditer(text)}
        for source_id in source_ids:
            if source_id in urls:
                matches[source_id].append(
                    {"post_id": post_id, "url": f"https://vk.com/wall{MILOVI_OWNER_ID}_{post_id}"}
                )

    return {
        "schema_name": "video-manager.milovi-cake-vk-school-public-wall-service-audit",
        "schema_version": 1,
        "project_key": "milovi-cake",
        "community_id": MILOVI_COMMUNITY_ID,
        "owner_id": MILOVI_OWNER_ID,
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "transport": "official_api_read",
        "token_type": "service",
        "public_wall_complete": True,
        "published_post_count": len(posts),
        "postponed_state": "unverified_user_reported_empty",
        "native_articles_state": "unverified",
        "provider_writes": 0,
        "source_classification": [
            {
                "source_id": source_id,
                "canonical_url": f"https://french.milovicake.ru/articles/{source_id}/",
                "public_wall_presence": "found" if matches[source_id] else "not_found_on_public_wall",
                "matches": matches[source_id],
                "automatically_eligible_to_publish": False,
            }
            for source_id in source_ids
        ],
        "release_eligible": False,
    }
