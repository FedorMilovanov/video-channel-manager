from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterable
from urllib.parse import urlsplit

from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk.catalog import canonical_sha256, text_sha256
from video_channel_manager.platforms.vk.text import render_vk_video_description
from video_channel_manager.platforms.vk.text_writer import canonical_vk_text
from video_channel_manager.platforms.vk.writer import VkVideoWriter, VkWriteError

VK_WALL_PLAN_SCHEMA = "video-manager.vk-wall-post-plan"
VK_WALL_PLAN_VERSION = 1
VK_WALL_POLICY_VERSION = "vk-wall-editorial-v1"
_DEFAULT_SITE_URL = "https://thelegendarypoet.ru/"


@dataclass(frozen=True, slots=True)
class VkWallPostResult:
    owner_id: int
    post_id: int
    message: str
    video_remote_id: str

    @property
    def remote_id(self) -> str:
        return f"{self.owner_id}_{self.post_id}"


def _absolute_http_url(value: str, field: str) -> str:
    normalized = value.strip()
    parsed = urlsplit(normalized)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{field} must be an absolute http(s) URL")
    return normalized


def _parse_video_remote_id(remote_id: str) -> tuple[int, int]:
    owner_text, separator, video_text = remote_id.partition("_")
    if not separator:
        raise ValueError(f"Invalid VK video remote ID: {remote_id}")
    try:
        owner_id = int(owner_text)
        video_id = int(video_text)
    except ValueError as exc:
        raise ValueError(f"Invalid VK video remote ID: {remote_id}") from exc
    if owner_id == 0 or video_id <= 0:
        raise ValueError(f"Invalid VK video remote ID: {remote_id}")
    return owner_id, video_id


def _assert_plain_vk_message(message: str) -> str:
    normalized = canonical_vk_text(message)
    rendered = render_vk_video_description(normalized, site_url="", brand_line="")
    if rendered.text != normalized or rendered.issues:
        issue_codes = ", ".join(item.code for item in rendered.issues) or "text would be transformed"
        raise ValueError(f"VK wall message is not stable plain text: {issue_codes}")
    return normalized


def render_vk_wall_post(
    *,
    headline: str,
    lead: str,
    paragraphs: Iterable[str],
    source_links: Iterable[tuple[str, str]],
    article_url: str | None = None,
    site_url: str = _DEFAULT_SITE_URL,
    hashtags: Iterable[str] = (),
) -> str:
    normalized_headline = canonical_vk_text(headline)
    normalized_lead = canonical_vk_text(lead)
    if not normalized_headline or not normalized_lead:
        raise ValueError("VK wall headline and lead cannot be blank")

    route_url = (
        _absolute_http_url(article_url, "article_url") if article_url else _absolute_http_url(site_url, "site_url")
    )
    paragraph_list = [canonical_vk_text(item) for item in paragraphs if canonical_vk_text(item)]
    links: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for label, raw_url in source_links:
        url = _absolute_http_url(raw_url, "source link")
        if url in seen_urls:
            continue
        seen_urls.add(url)
        links.append((canonical_vk_text(label) or "Источник", url))

    normalized_tags: list[str] = []
    seen_tags: set[str] = set()
    for raw_tag in hashtags:
        tag = "#" + re.sub(r"\s+", "", str(raw_tag).strip().lstrip("#"))
        if len(tag) > 1 and tag.casefold() not in seen_tags:
            seen_tags.add(tag.casefold())
            normalized_tags.append(tag)

    sections = [normalized_headline, normalized_lead, *paragraph_list, "▶ Смотреть видео — во вложении."]
    route_label = "📚 Полная статья" if article_url else "🌐 The Legendary Poet"
    sections.append(f"{route_label}: {route_url}")
    if links:
        sections.append("Первоисточники:\n" + "\n".join(f"• {label}: {url}" for label, url in links))
    if normalized_tags:
        sections.append(" ".join(normalized_tags))
    message = _assert_plain_vk_message("\n\n".join(sections))

    expected_site_occurrences = 1 if "thelegendarypoet.ru" in route_url else 0
    if message.count("thelegendarypoet.ru") != expected_site_occurrences:
        raise ValueError("The Legendary Poet route must occur exactly once in the wall message")
    return message


def calculate_vk_wall_plan_sha256(plan: dict[str, Any]) -> str:
    return canonical_sha256({key: value for key, value in plan.items() if key != "plan_sha256"})


def build_vk_wall_post_plan(
    target: AuditPackage,
    *,
    video_remote_id: str,
    message: str,
    source_links: list[dict[str, str]],
    article_url: str | None = None,
) -> dict[str, Any]:
    if target.channel.ref.platform.value != "vk":
        raise ValueError("VK wall plan target must be a VK AuditPackage")
    community_id = int(target.channel.ref.channel_id)
    owner_id, video_id = _parse_video_remote_id(video_remote_id)
    if owner_id != -community_id:
        raise ValueError(f"Video owner {owner_id} differs from community owner {-community_id}")
    videos = {item.ref.remote_id: item for item in target.videos}
    video = videos.get(video_remote_id)
    if video is None:
        raise ValueError(f"Video {video_remote_id} is absent from the reviewed VK snapshot")
    normalized_message = _assert_plain_vk_message(message)
    if not normalized_message:
        raise ValueError("VK wall message cannot be blank")
    if len(normalized_message) > 15000:
        raise ValueError("VK wall message exceeds the 15,000-character project policy")
    normalized_article_url = _absolute_http_url(article_url, "article_url") if article_url else None
    normalized_sources = []
    for item in source_links:
        label = canonical_vk_text(item.get("label", "")) or "Источник"
        url = _absolute_http_url(item.get("url", ""), "source link")
        normalized_sources.append({"label": label, "url": url, "kind": str(item.get("kind") or "source")})

    guid_seed = f"{community_id}:{video_remote_id}:{text_sha256(normalized_message)}"
    guid = "vcm-" + hashlib.sha256(guid_seed.encode("utf-8")).hexdigest()[:28]
    plan: dict[str, Any] = {
        "schema_name": VK_WALL_PLAN_SCHEMA,
        "schema_version": VK_WALL_PLAN_VERSION,
        "policy_version": VK_WALL_POLICY_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "target_snapshot_id": str(target.snapshot_id),
        "target_community_id": community_id,
        "video_remote_id": video_remote_id,
        "video_owner_id": owner_id,
        "video_id": video_id,
        "expected_video_title": canonical_vk_text(video.title),
        "expected_video_title_sha256": text_sha256(video.title),
        "expected_video_description": canonical_vk_text(video.description),
        "expected_video_description_sha256": text_sha256(video.description),
        "message": normalized_message,
        "message_sha256": text_sha256(normalized_message),
        "attachment": f"video{video_remote_id}",
        "guid": guid,
        "article_url": normalized_article_url,
        "source_links": normalized_sources,
    }
    plan["plan_sha256"] = calculate_vk_wall_plan_sha256(plan)
    validate_vk_wall_post_plan(plan)
    return plan


def validate_vk_wall_post_plan(plan: dict[str, Any]) -> None:
    if plan.get("schema_name") != VK_WALL_PLAN_SCHEMA or plan.get("schema_version") != VK_WALL_PLAN_VERSION:
        raise ValueError("Unsupported VK wall post plan schema")
    community_id = plan.get("target_community_id")
    if not isinstance(community_id, int) or community_id <= 0:
        raise ValueError("target_community_id must be positive")
    owner_id, video_id = _parse_video_remote_id(str(plan.get("video_remote_id") or ""))
    if owner_id != -community_id or plan.get("video_owner_id") != owner_id or plan.get("video_id") != video_id:
        raise ValueError("VK wall plan video identity is inconsistent")
    if plan.get("attachment") != f"video{owner_id}_{video_id}":
        raise ValueError("VK wall plan attachment does not match the video identity")
    for field in ("expected_video_title", "expected_video_description", "message"):
        if plan.get(f"{field}_sha256") != text_sha256(str(plan.get(field) or "")):
            raise ValueError(f"VK wall plan hash mismatch: {field}")
    _assert_plain_vk_message(str(plan.get("message") or ""))
    if not isinstance(plan.get("guid"), str) or not plan["guid"].startswith("vcm-"):
        raise ValueError("VK wall plan guid is invalid")
    expected = calculate_vk_wall_plan_sha256(plan)
    if plan.get("plan_sha256") != expected:
        raise ValueError("VK wall plan self-digest does not match its contents")


def _post_has_video(post: dict[str, Any], *, owner_id: int, video_id: int) -> bool:
    for attachment in post.get("attachments") or []:
        if not isinstance(attachment, dict) or attachment.get("type") != "video":
            continue
        video = attachment.get("video")
        if isinstance(video, dict) and video.get("owner_id") == owner_id and video.get("id") == video_id:
            return True
    return False


class VkWallWriter(VkVideoWriter):
    """Narrow VK wall writer with duplicate scans and postcondition verification."""

    def find_video_posts(
        self,
        *,
        community_id: int,
        video_owner_id: int,
        video_id: int,
        max_posts: int = 500,
    ) -> list[dict[str, Any]]:
        if community_id <= 0 or video_owner_id == 0 or video_id <= 0 or max_posts <= 0:
            raise ValueError("Invalid wall duplicate-scan parameters")
        matches: list[dict[str, Any]] = []
        offset = 0
        while offset < max_posts:
            count = min(100, max_posts - offset)
            response = self._call(
                "wall.get",
                params={"owner_id": -community_id, "filter": "owner", "count": count, "offset": offset},
                retry_transient=True,
            )
            if not isinstance(response, dict) or not isinstance(response.get("items"), list):
                raise VkWriteError("wall.get returned an invalid response", method="wall.get")
            items = [item for item in response["items"] if isinstance(item, dict)]
            matches.extend(item for item in items if _post_has_video(item, owner_id=video_owner_id, video_id=video_id))
            if len(items) < count:
                break
            offset += count
        return matches

    def read_post(self, *, community_id: int, post_id: int) -> dict[str, Any] | None:
        if community_id <= 0 or post_id <= 0:
            raise ValueError("community_id and post_id must be positive")
        response = self._call(
            "wall.getById",
            params={"posts": f"{-community_id}_{post_id}"},
            retry_transient=True,
        )
        items = response.get("items") if isinstance(response, dict) else response
        if not isinstance(items, list) or not items:
            return None
        item = items[0]
        return item if isinstance(item, dict) else None

    def post_video(
        self,
        *,
        community_id: int,
        video_owner_id: int,
        video_id: int,
        message: str,
        guid: str,
    ) -> VkWallPostResult:
        duplicates = self.find_video_posts(
            community_id=community_id,
            video_owner_id=video_owner_id,
            video_id=video_id,
        )
        if duplicates:
            post_ids = sorted(int(item["id"]) for item in duplicates if isinstance(item.get("id"), int))
            raise VkWriteError(
                f"Video already appears in community wall posts: {post_ids}",
                method="wall.get",
            )
        response = self._call(
            "wall.post",
            params={
                "owner_id": -community_id,
                "from_group": True,
                "message": canonical_vk_text(message),
                "attachments": f"video{video_owner_id}_{video_id}",
                "guid": guid,
            },
        )
        post_id = response.get("post_id") if isinstance(response, dict) else response
        if not isinstance(post_id, int) or post_id <= 0:
            raise VkWriteError(f"wall.post returned an invalid post ID: {response!r}", method="wall.post")
        observed = self.read_post(community_id=community_id, post_id=post_id)
        if observed is None or not _post_has_video(observed, owner_id=video_owner_id, video_id=video_id):
            raise VkWriteError("wall.post was not visible with the expected video attachment", method="wall.getById")
        observed_message = canonical_vk_text(str(observed.get("text") or ""))
        if observed_message != canonical_vk_text(message):
            raise VkWriteError("wall.post message differs from the reviewed plan", method="wall.getById")
        return VkWallPostResult(
            owner_id=-community_id,
            post_id=post_id,
            message=observed_message,
            video_remote_id=f"{video_owner_id}_{video_id}",
        )


__all__ = [
    "VK_WALL_PLAN_SCHEMA",
    "VK_WALL_PLAN_VERSION",
    "VK_WALL_POLICY_VERSION",
    "VkWallPostResult",
    "VkWallWriter",
    "build_vk_wall_post_plan",
    "calculate_vk_wall_plan_sha256",
    "render_vk_wall_post",
    "validate_vk_wall_post_plan",
]
