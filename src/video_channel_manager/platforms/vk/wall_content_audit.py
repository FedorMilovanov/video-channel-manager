from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

from video_channel_manager.platforms.vk.catalog import canonical_sha256
from video_channel_manager.platforms.vk.client import VkApiClient

_ALLOWED_WALL_FILTERS = frozenset({"owner", "postponed"})
_VIDEO_LINK_RE = re.compile(
    r"(?<!\w)(?:(?:https?://)?(?:www\.)?(?:vk\.com|vkvideo\.ru)/)?(?:video|clip)(-?\d+)_(\d+)",
    flags=re.IGNORECASE,
)


def _remote_video_id(owner_id: object, video_id: object) -> str | None:
    if not isinstance(owner_id, int) or not isinstance(video_id, int):
        return None
    if owner_id == 0 or video_id <= 0:
        return None
    return f"{owner_id}_{video_id}"


def _post_ref(post: dict[str, Any]) -> dict[str, Any]:
    owner_id = post.get("owner_id")
    post_id = post.get("id")
    reference: dict[str, Any] = {
        "owner_id": owner_id if isinstance(owner_id, int) else None,
        "post_id": post_id if isinstance(post_id, int) else None,
        "date": post.get("date") if isinstance(post.get("date"), int) else None,
    }
    if isinstance(owner_id, int) and isinstance(post_id, int):
        reference["url"] = f"https://vk.com/wall{owner_id}_{post_id}"
    return reference


def _walk_posts(post: dict[str, Any]) -> list[dict[str, Any]]:
    result = [post]
    copy_history = post.get("copy_history")
    if isinstance(copy_history, list):
        for item in copy_history:
            if isinstance(item, dict):
                result.extend(_walk_posts(item))
    return result


def extract_video_ids_from_post(post: dict[str, Any]) -> set[str]:
    """Extract VK video identities from attachments, text links, and repost history."""

    result: set[str] = set()
    for current in _walk_posts(post):
        message = str(current.get("text") or "")
        for match in _VIDEO_LINK_RE.finditer(message):
            result.add(f"{int(match.group(1))}_{int(match.group(2))}")

        attachments = current.get("attachments")
        if not isinstance(attachments, list):
            continue
        for attachment in attachments:
            if not isinstance(attachment, dict):
                continue
            attachment_type = str(attachment.get("type") or "")
            if attachment_type not in {"video", "clip"}:
                continue
            payload = attachment.get(attachment_type)
            if not isinstance(payload, dict) and attachment_type == "clip":
                payload = attachment.get("video")
            if not isinstance(payload, dict):
                continue
            remote_id = _remote_video_id(payload.get("owner_id"), payload.get("id"))
            if remote_id is not None:
                result.add(remote_id)
    return result


def fetch_wall_posts(
    client: VkApiClient,
    *,
    community_id: int,
    filter_name: str,
) -> list[dict[str, Any]]:
    """Read every owner or postponed wall post for one managed VK community."""

    if community_id <= 0:
        raise ValueError("VK community ID must be positive")
    if filter_name not in _ALLOWED_WALL_FILTERS:
        raise ValueError(f"Unsupported VK wall filter: {filter_name}")
    return client._list_offset(
        "wall.get",
        params={
            "owner_id": -community_id,
            "filter": filter_name,
            "extended": False,
        },
        page_size=100,
    )


def _index_posts(posts: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], set[str]]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    all_referenced: set[str] = set()
    for post in posts:
        reference = _post_ref(post)
        video_ids = extract_video_ids_from_post(post)
        all_referenced.update(video_ids)
        for video_id in sorted(video_ids):
            index[video_id].append(reference)
    return dict(index), all_referenced


def _video_payload(video: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    ref = video.get("ref")
    if not isinstance(ref, dict):
        raise ValueError("VK video record has no ref object")
    remote_id = str(ref.get("remote_id") or "").strip()
    if not remote_id:
        raise ValueError("VK video record has no remote_id")
    metadata = video.get("metadata")
    return remote_id, metadata if isinstance(metadata, dict) else {}


def build_wall_content_audit(
    *,
    community_id: int,
    videos: list[dict[str, Any]],
    published_posts: list[dict[str, Any]],
    postponed_posts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare the complete VK video inventory with published and scheduled wall posts."""

    published_index, published_referenced = _index_posts(published_posts)
    postponed_index, postponed_referenced = _index_posts(postponed_posts)

    video_ids: list[str] = []
    records: list[dict[str, Any]] = []
    for video in videos:
        remote_id, metadata = _video_payload(video)
        video_ids.append(remote_id)
        published_refs = published_index.get(remote_id, [])
        postponed_refs = postponed_index.get(remote_id, [])
        wall_post_id = metadata.get("wall_post_id") if isinstance(metadata.get("wall_post_id"), int) else None

        if published_refs and postponed_refs:
            state = "published_and_scheduled_conflict"
        elif postponed_refs:
            state = "scheduled"
        elif published_refs:
            state = "published"
        elif wall_post_id is not None:
            state = "wall_marker_only_review"
        else:
            state = "unposted"

        records.append(
            {
                "video_id": remote_id,
                "title": str(video.get("title") or remote_id),
                "published_at": video.get("published_at"),
                "duration_seconds": video.get("duration_seconds"),
                "is_short_video": bool(metadata.get("is_short_video")),
                "views": metadata.get("views") if isinstance(metadata.get("views"), int) else None,
                "wall_post_id_marker": wall_post_id,
                "state": state,
                "published_post_refs": published_refs,
                "postponed_post_refs": postponed_refs,
                "video_url": str(metadata.get("share_url") or metadata.get("permalink") or ""),
            }
        )

    duplicates = sorted(item for item, count in Counter(video_ids).items() if count > 1)
    if duplicates:
        raise ValueError(f"Duplicate VK video identities in inventory: {duplicates[:5]}")

    known_video_ids = set(video_ids)
    state_counts = Counter(str(item["state"]) for item in records)
    records.sort(key=lambda item: (str(item.get("published_at") or ""), str(item["video_id"])), reverse=True)

    duplicate_references = [
        {
            "video_id": video_id,
            "published_posts": published_index.get(video_id, []),
            "postponed_posts": postponed_index.get(video_id, []),
        }
        for video_id in sorted(known_video_ids)
        if len(published_index.get(video_id, [])) > 1
        or len(postponed_index.get(video_id, [])) > 1
        or (video_id in published_index and video_id in postponed_index)
    ]

    audit: dict[str, Any] = {
        "schema_name": "video-manager.vk-wall-content-audit",
        "schema_version": 1,
        "community_id": community_id,
        "read_only": True,
        "summary": {
            "videos": len(records),
            "published_wall_posts": len(published_posts),
            "postponed_wall_posts": len(postponed_posts),
            "published_videos": state_counts["published"],
            "scheduled_videos": state_counts["scheduled"],
            "unposted_videos": state_counts["unposted"],
            "wall_marker_only_review": state_counts["wall_marker_only_review"],
            "published_and_scheduled_conflicts": state_counts["published_and_scheduled_conflict"],
            "duplicate_post_references": len(duplicate_references),
        },
        "videos": records,
        "duplicate_post_references": duplicate_references,
        "unknown_published_video_ids": sorted(published_referenced - known_video_ids),
        "unknown_postponed_video_ids": sorted(postponed_referenced - known_video_ids),
    }
    audit["status"] = (
        "review_required"
        if duplicate_references
        or state_counts["wall_marker_only_review"]
        or state_counts["published_and_scheduled_conflict"]
        else "completed"
    )
    audit["audit_sha256"] = canonical_sha256({key: value for key, value in audit.items() if key != "audit_sha256"})
    return audit


def render_wall_content_audit_markdown(audit: dict[str, Any]) -> str:
    summary = audit["summary"]
    lines = [
        "# VK wall content audit",
        "",
        f"- Status: `{audit['status']}`",
        f"- Audit: `{audit['audit_sha256']}`",
        f"- Community: `{audit['community_id']}`",
        f"- Videos: **{summary['videos']}**",
        f"- Published posts scanned: **{summary['published_wall_posts']}**",
        f"- Postponed posts scanned: **{summary['postponed_wall_posts']}**",
        f"- Videos already published: **{summary['published_videos']}**",
        f"- Videos already scheduled: **{summary['scheduled_videos']}**",
        f"- Confirmed unposted videos: **{summary['unposted_videos']}**",
        f"- Marker-only records requiring review: **{summary['wall_marker_only_review']}**",
        f"- Published/scheduled conflicts: **{summary['published_and_scheduled_conflicts']}**",
        "",
        "## Confirmed unposted videos",
        "",
    ]
    unposted = [item for item in audit["videos"] if item["state"] == "unposted"]
    if not unposted:
        lines.append("- None")
    for item in unposted:
        kind = "short" if item["is_short_video"] else "full"
        lines.append(f"- `{item['video_id']}` · {kind} · {item['title']}")

    review = [item for item in audit["videos"] if item["state"].endswith("review") or "conflict" in item["state"]]
    if review:
        lines.extend(["", "## Manual review", ""])
        for item in review:
            lines.append(f"- `{item['video_id']}` · `{item['state']}` · {item['title']}")

    return "\n".join(lines).rstrip() + "\n"


__all__ = [
    "build_wall_content_audit",
    "extract_video_ids_from_post",
    "fetch_wall_posts",
    "render_wall_content_audit_markdown",
]
