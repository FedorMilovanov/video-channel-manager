from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterable
from urllib.parse import urlsplit

from video_channel_manager.editorial._project_profiles import resolve_project_key
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.http import HttpFailureKind
from video_channel_manager.platforms.vk.catalog import canonical_sha256, text_sha256
from video_channel_manager.platforms.vk.publishing import VK_PUBLICATION_PROFILES
from video_channel_manager.platforms.vk.text import render_vk_video_description
from video_channel_manager.platforms.vk.text_writer import canonical_vk_text
from video_channel_manager.platforms.vk.wall_safety import (
    VkWallDelta,
    VkWallDeltaStatus,
    VkWallPostFingerprint,
    VkWallSnapshot,
    VkWallSurface,
    build_wall_snapshot,
    compare_wall_snapshots,
)
from video_channel_manager.platforms.vk.writer import VkVideoWriter, VkWriteError

VK_WALL_PLAN_SCHEMA = "video-manager.vk-wall-post-plan"
VK_WALL_PLAN_VERSION = 2
VK_WALL_POLICY_VERSION = "vk-wall-postponed-v2"
_AMBIGUOUS_WALL_FAILURES = frozenset(
    {
        HttpFailureKind.TRANSPORT,
        HttpFailureKind.RATE_LIMIT,
        HttpFailureKind.TRANSIENT_HTTP,
        HttpFailureKind.PROVIDER_TRANSIENT,
        HttpFailureKind.INVALID_JSON,
        HttpFailureKind.INVALID_PAYLOAD,
    }
)


@dataclass(frozen=True, slots=True)
class VkWallPostResult:
    owner_id: int
    post_id: int
    message: str
    video_remote_id: str
    publish_date: int
    guid: str
    before_snapshot_sha256: str
    after_snapshot_sha256: str

    @property
    def remote_id(self) -> str:
        return f"{self.owner_id}_{self.post_id}"


class VkWallRecoveryRequired(VkWriteError):
    """A wall mutation may have been accepted and needs exact reconciliation."""


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


def _aware_utc(value: datetime, *, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(UTC)


def _future_publish_date(
    publish_at: datetime,
    *,
    now: datetime | None = None,
    minimum_future_seconds: int = 300,
) -> int:
    if minimum_future_seconds < 0:
        raise ValueError("minimum_future_seconds cannot be negative")
    scheduled = _aware_utc(publish_at, field="publish_at")
    current = _aware_utc(now or datetime.now(UTC), field="now")
    publish_date = int(scheduled.timestamp())
    if publish_date <= int(current.timestamp()) + minimum_future_seconds:
        raise ValueError("publish_at is not safely in the future")
    return publish_date


def render_vk_wall_post(
    *,
    project_key: str,
    headline: str,
    lead: str,
    paragraphs: Iterable[str],
    source_links: Iterable[tuple[str, str]],
    article_url: str | None = None,
    site_url: str | None = None,
    hashtags: Iterable[str] = (),
) -> str:
    profile = VK_PUBLICATION_PROFILES.get(project_key)
    if profile is None:
        raise ValueError("VK wall rendering requires an explicit registered project_key")
    normalized_headline = canonical_vk_text(headline)
    normalized_lead = canonical_vk_text(lead)
    if not normalized_headline or not normalized_lead:
        raise ValueError("VK wall headline and lead cannot be blank")

    selected_site_url = site_url if site_url is not None else profile.site_url
    route_url = (
        _absolute_http_url(article_url, "article_url")
        if article_url
        else _absolute_http_url(selected_site_url, "site_url")
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
    route_label = "📚 Полная статья" if article_url else "🌐 Проект"
    sections.append(f"{route_label}: {route_url}")
    if links:
        sections.append("Первоисточники:\n" + "\n".join(f"• {label}: {url}" for label, url in links))
    if normalized_tags:
        sections.append(" ".join(normalized_tags))
    message = _assert_plain_vk_message("\n\n".join(sections))

    if message.count(route_url) != 1:
        raise ValueError("The selected project route must occur exactly once in the wall message")
    return message


def calculate_vk_wall_plan_sha256(plan: dict[str, Any]) -> str:
    return canonical_sha256({key: value for key, value in plan.items() if key != "plan_sha256"})


def build_vk_wall_post_plan(
    target: AuditPackage,
    *,
    video_remote_id: str,
    message: str,
    source_links: list[dict[str, str]],
    publish_at: datetime,
    article_url: str | None = None,
    project_key: str | None = None,
    now: datetime | None = None,
    minimum_future_seconds: int = 300,
) -> dict[str, Any]:
    if target.channel.ref.platform.value != "vk":
        raise ValueError("VK wall plan target must be a VK AuditPackage")
    community_id = int(target.channel.ref.channel_id)
    resolved_project = resolve_project_key(
        {
            "project_key": project_key,
            "community_id": community_id,
            "owner_id": -community_id,
        }
    )
    if resolved_project is None:
        raise ValueError("VK wall plan project/community identity is unknown or inconsistent")
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
    publish_date = _future_publish_date(
        publish_at,
        now=now,
        minimum_future_seconds=minimum_future_seconds,
    )
    normalized_article_url = _absolute_http_url(article_url, "article_url") if article_url else None
    normalized_sources = []
    for item in source_links:
        label = canonical_vk_text(item.get("label", "")) or "Источник"
        url = _absolute_http_url(item.get("url", ""), "source link")
        normalized_sources.append({"label": label, "url": url, "kind": str(item.get("kind") or "source")})

    message_digest = text_sha256(normalized_message)
    guid_seed = f"{resolved_project}:{community_id}:{video_remote_id}:{publish_date}:{message_digest}"
    guid = "vcm-" + hashlib.sha256(guid_seed.encode("utf-8")).hexdigest()[:28]
    plan: dict[str, Any] = {
        "schema_name": VK_WALL_PLAN_SCHEMA,
        "schema_version": VK_WALL_PLAN_VERSION,
        "policy_version": VK_WALL_POLICY_VERSION,
        "project_key": resolved_project,
        "generated_at": datetime.now(UTC).isoformat(),
        "target_snapshot_id": str(target.snapshot_id),
        "target_community_id": community_id,
        "target_owner_id": -community_id,
        "video_remote_id": video_remote_id,
        "video_owner_id": owner_id,
        "video_id": video_id,
        "expected_video_title": canonical_vk_text(video.title),
        "expected_video_title_sha256": text_sha256(video.title),
        "expected_video_description": canonical_vk_text(video.description),
        "expected_video_description_sha256": text_sha256(video.description),
        "message": normalized_message,
        "message_sha256": message_digest,
        "attachment": f"video{video_remote_id}",
        "publication_mode": "postponed",
        "immediate_publication_authorized": False,
        "publish_date": publish_date,
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
    if type(community_id) is not int or community_id <= 0:
        raise ValueError("target_community_id must be a positive exact integer")
    if plan.get("target_owner_id") != -community_id:
        raise ValueError("VK wall plan target owner is inconsistent")
    resolved_project = resolve_project_key(
        {
            "project_key": plan.get("project_key"),
            "community_id": community_id,
            "owner_id": plan.get("target_owner_id"),
        }
    )
    if resolved_project is None or resolved_project != plan.get("project_key"):
        raise ValueError("VK wall plan project/community identity is inconsistent")
    owner_id, video_id = _parse_video_remote_id(str(plan.get("video_remote_id") or ""))
    if owner_id != -community_id or plan.get("video_owner_id") != owner_id or plan.get("video_id") != video_id:
        raise ValueError("VK wall plan video identity is inconsistent")
    if plan.get("attachment") != f"video{owner_id}_{video_id}":
        raise ValueError("VK wall plan attachment does not match the video identity")
    for field in ("expected_video_title", "expected_video_description", "message"):
        if plan.get(f"{field}_sha256") != text_sha256(str(plan.get(field) or "")):
            raise ValueError(f"VK wall plan hash mismatch: {field}")
    _assert_plain_vk_message(str(plan.get("message") or ""))
    if plan.get("publication_mode") != "postponed":
        raise ValueError("VK wall plan must use postponed publication mode")
    if type(plan.get("immediate_publication_authorized")) is not bool:
        raise ValueError("immediate_publication_authorized must be an exact boolean")
    if plan.get("immediate_publication_authorized") is not False:
        raise ValueError("Immediate wall publication is not authorized by the postponed plan")
    publish_date = plan.get("publish_date")
    if type(publish_date) is not int or publish_date <= 0:
        raise ValueError("VK wall plan publish_date must be a positive exact integer")
    if not isinstance(plan.get("guid"), str) or not plan["guid"].startswith("vcm-"):
        raise ValueError("VK wall plan guid is invalid")
    guid_seed = (
        f"{resolved_project}:{community_id}:{owner_id}_{video_id}:"
        f"{publish_date}:{plan['message_sha256']}"
    )
    expected_guid = "vcm-" + hashlib.sha256(guid_seed.encode("utf-8")).hexdigest()[:28]
    if plan.get("guid") != expected_guid:
        raise ValueError("VK wall plan guid does not match immutable operation identity")
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
    """VK wall reader/writer with complete two-surface evidence.

    The only supported write route is postponed publication. Immediate posting
    has no implicit fallback and requires a different reviewed authority type.
    """

    def _read_wall_surface(
        self,
        *,
        community_id: int,
        surface: VkWallSurface,
        max_posts: int,
    ) -> tuple[list[dict[str, Any]], int, bool]:
        if community_id <= 0 or max_posts <= 0:
            raise ValueError("community_id and max_posts must be positive")
        items: list[dict[str, Any]] = []
        pages = 0
        offset = 0
        expected_total: int | None = None
        complete = False
        while offset < max_posts:
            count = min(100, max_posts - offset)
            response = self._call(
                "wall.get",
                params={
                    "owner_id": -community_id,
                    "filter": surface.api_filter,
                    "count": count,
                    "offset": offset,
                },
                retry_transient=True,
            )
            pages += 1
            if not isinstance(response, dict) or not isinstance(response.get("items"), list):
                raise VkWriteError("wall.get returned an invalid response", method="wall.get")
            raw_total = response.get("count")
            if type(raw_total) is not int or raw_total < 0:
                raise VkWriteError("wall.get returned an invalid total count", method="wall.get")
            if expected_total is None:
                expected_total = raw_total
            elif expected_total != raw_total:
                return items, pages, False
            page_items = [item for item in response["items"] if isinstance(item, dict)]
            if len(page_items) != len(response["items"]):
                return items, pages, False
            if any(item.get("owner_id") != -community_id for item in page_items):
                raise VkWriteError("wall.get returned a post from another owner", method="wall.get")
            items.extend(page_items)
            offset += len(page_items)
            if offset >= raw_total:
                complete = True
                break
            if not page_items or len(page_items) < count:
                break
        if expected_total is None:
            complete = False
        elif len(items) >= expected_total:
            complete = True
        return items, pages, complete

    def capture_wall_snapshot(
        self,
        *,
        community_id: int,
        max_posts_per_surface: int = 10000,
    ) -> VkWallSnapshot:
        published, published_pages, published_complete = self._read_wall_surface(
            community_id=community_id,
            surface=VkWallSurface.PUBLISHED,
            max_posts=max_posts_per_surface,
        )
        postponed, postponed_pages, postponed_complete = self._read_wall_surface(
            community_id=community_id,
            surface=VkWallSurface.POSTPONED,
            max_posts=max_posts_per_surface,
        )
        return build_wall_snapshot(
            community_id=community_id,
            published_items=published,
            postponed_items=postponed,
            published_pages=published_pages,
            postponed_pages=postponed_pages,
            complete=published_complete and postponed_complete,
        )

    def find_video_posts(
        self,
        *,
        community_id: int,
        video_owner_id: int,
        video_id: int,
        max_posts_per_surface: int = 10000,
    ) -> list[dict[str, Any]]:
        if community_id <= 0 or video_owner_id == 0 or video_id <= 0 or max_posts_per_surface <= 0:
            raise ValueError("Invalid wall duplicate-scan parameters")
        matches: list[dict[str, Any]] = []
        for surface in VkWallSurface:
            items, _pages, complete = self._read_wall_surface(
                community_id=community_id,
                surface=surface,
                max_posts=max_posts_per_surface,
            )
            if not complete:
                raise VkWriteError(
                    f"wall.get {surface.value} scan is incomplete; duplicate state is unknown",
                    method="wall.get",
                )
            for item in items:
                if _post_has_video(item, owner_id=video_owner_id, video_id=video_id):
                    matches.append({**item, "_vcm_surface": surface.value})
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

    @staticmethod
    def _expected_post(
        snapshot: VkWallSnapshot,
        *,
        video_owner_id: int,
        video_id: int,
        message: str,
        publish_date: int,
        post_id: int | None,
    ) -> list[VkWallPostFingerprint]:
        attachment = f"video{video_owner_id}_{video_id}"
        message_digest = text_sha256(canonical_vk_text(message))
        return [
            post
            for post in snapshot.posts
            if post.surface is VkWallSurface.POSTPONED
            and post.publish_date == publish_date
            and post.text_sha256 == message_digest
            and attachment in post.attachments
            and (post_id is None or post.post_id == post_id)
        ]

    @staticmethod
    def _result_from_reconciliation(
        *,
        before: VkWallSnapshot,
        after: VkWallSnapshot,
        delta: VkWallDelta,
        matches: list[VkWallPostFingerprint],
        message: str,
        video_owner_id: int,
        video_id: int,
        publish_date: int,
        guid: str,
    ) -> VkWallPostResult:
        if delta.status is VkWallDeltaStatus.UNKNOWN_REQUIRES_RECONCILIATION:
            raise VkWallRecoveryRequired(
                f"VK wall postflight is incomplete: {delta.reasons}",
                method="wall.get",
                retryable=False,
            )
        if len(matches) != 1:
            raise VkWallRecoveryRequired(
                "VK wall outcome cannot be reconciled to exactly one postponed post",
                method="wall.get",
                retryable=False,
            )
        match = matches[0]
        expected_created = (f"postponed:{match.remote_id}",)
        if delta.created != expected_created or delta.removed or delta.changed:
            raise VkWallRecoveryRequired(
                "VK wall changed outside the one approved postponed post",
                method="wall.get",
                retryable=False,
            )
        return VkWallPostResult(
            owner_id=match.owner_id,
            post_id=match.post_id,
            message=canonical_vk_text(message),
            video_remote_id=f"{video_owner_id}_{video_id}",
            publish_date=publish_date,
            guid=guid,
            before_snapshot_sha256=before.snapshot_sha256,
            after_snapshot_sha256=after.snapshot_sha256,
        )

    def post_video(
        self,
        *,
        community_id: int,
        video_owner_id: int,
        video_id: int,
        message: str,
        guid: str,
        publish_at: datetime,
        now: datetime | None = None,
        minimum_future_seconds: int = 300,
        max_posts_per_surface: int = 10000,
    ) -> VkWallPostResult:
        if community_id <= 0 or video_owner_id != -community_id or video_id <= 0:
            raise ValueError("Wall post video identity must match the target community")
        normalized_message = _assert_plain_vk_message(message)
        if not normalized_message:
            raise ValueError("VK wall message cannot be blank")
        if not guid.startswith("vcm-"):
            raise ValueError("guid must be a deterministic vcm- identifier")
        publish_date = _future_publish_date(
            publish_at,
            now=now,
            minimum_future_seconds=minimum_future_seconds,
        )
        before = self.capture_wall_snapshot(
            community_id=community_id,
            max_posts_per_surface=max_posts_per_surface,
        )
        if not before.complete:
            raise VkWriteError("VK wall preflight snapshot is incomplete", method="wall.get")
        attachment = f"video{video_owner_id}_{video_id}"
        duplicates = [post for post in before.posts if attachment in post.attachments]
        if duplicates:
            locations = sorted(f"{post.surface.value}:{post.remote_id}" for post in duplicates)
            raise VkWriteError(
                f"Video already appears in published/postponed wall posts: {locations}",
                method="wall.get",
            )
        schedule_collisions = [
            post
            for post in before.posts
            if post.surface is VkWallSurface.POSTPONED and post.publish_date == publish_date
        ]
        if schedule_collisions:
            locations = sorted(post.remote_id for post in schedule_collisions)
            raise VkWriteError(
                f"Postponed wall schedule slot {publish_date} is already occupied: {locations}",
                method="wall.get",
            )

        try:
            response = self._call(
                "wall.post",
                params={
                    "owner_id": -community_id,
                    "from_group": True,
                    "message": normalized_message,
                    "attachments": attachment,
                    "publish_date": publish_date,
                    "guid": guid,
                },
            )
        except VkWriteError as exc:
            if exc.kind not in _AMBIGUOUS_WALL_FAILURES:
                raise
            after = self.capture_wall_snapshot(
                community_id=community_id,
                max_posts_per_surface=max_posts_per_surface,
            )
            delta = compare_wall_snapshots(before, after)
            matches = self._expected_post(
                after,
                video_owner_id=video_owner_id,
                video_id=video_id,
                message=normalized_message,
                publish_date=publish_date,
                post_id=None,
            )
            return self._result_from_reconciliation(
                before=before,
                after=after,
                delta=delta,
                matches=matches,
                message=normalized_message,
                video_owner_id=video_owner_id,
                video_id=video_id,
                publish_date=publish_date,
                guid=guid,
            )

        post_id = response.get("post_id") if isinstance(response, dict) else response
        if not isinstance(post_id, int) or post_id <= 0:
            raise VkWallRecoveryRequired(
                f"wall.post returned no usable post identity: {response!r}",
                method="wall.post",
                retryable=False,
            )
        after = self.capture_wall_snapshot(
            community_id=community_id,
            max_posts_per_surface=max_posts_per_surface,
        )
        delta = compare_wall_snapshots(before, after)
        matches = self._expected_post(
            after,
            video_owner_id=video_owner_id,
            video_id=video_id,
            message=normalized_message,
            publish_date=publish_date,
            post_id=post_id,
        )
        return self._result_from_reconciliation(
            before=before,
            after=after,
            delta=delta,
            matches=matches,
            message=normalized_message,
            video_owner_id=video_owner_id,
            video_id=video_id,
            publish_date=publish_date,
            guid=guid,
        )


__all__ = [
    "VK_WALL_PLAN_SCHEMA",
    "VK_WALL_PLAN_VERSION",
    "VK_WALL_POLICY_VERSION",
    "VkWallPostResult",
    "VkWallRecoveryRequired",
    "VkWallWriter",
    "build_vk_wall_post_plan",
    "calculate_vk_wall_plan_sha256",
    "render_vk_wall_post",
    "validate_vk_wall_post_plan",
]
