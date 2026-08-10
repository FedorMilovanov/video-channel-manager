from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from video_channel_manager.editorial._project_profiles import PROJECT_KEYS, PROJECT_VK_COMMUNITY_IDS
from video_channel_manager.platforms.vk.client import VkApiClient, VkApiError

VK_CLIPS_AUDIT_SCHEMA = "vk-clips-readonly-audit-v1"


def _utc_iso(value: int | None = None) -> str:
    moment = datetime.now(UTC) if value is None else datetime.fromtimestamp(value, tz=UTC)
    return moment.isoformat().replace("+00:00", "Z")


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) else None


def _normalize_required_remote_ids(values: Sequence[str], *, owner_id: int) -> list[str]:
    normalized: list[str] = []
    expected_prefix = f"{owner_id}_"
    for raw in values:
        value = raw.strip()
        if not value:
            raise ValueError("required VK remote ID cannot be blank")
        if not value.startswith(expected_prefix):
            raise ValueError(
                f"required VK remote ID does not belong to exact owner {owner_id}: {value}"
            )
        suffix = value[len(expected_prefix) :]
        if not suffix.isdigit() or int(suffix) <= 0:
            raise ValueError(f"invalid required VK remote ID: {value}")
        normalized.append(value)
    if len(set(normalized)) != len(normalized):
        raise ValueError("required VK remote IDs must be unique")
    return normalized


def build_vk_clips_audit_snapshot(
    client: VkApiClient,
    *,
    project_key: str,
    community_id: int,
    owner_id: int,
    required_remote_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """Build one exact, mutation-free VK Clips surface snapshot.

    The project/community/owner contract is validated locally before the first
    provider call. The provider response is then required to prove the same
    community, management access, exact owner on every object, and
    ``type=short_video`` on every returned item.
    """

    normalized_project = project_key.strip()
    if normalized_project not in PROJECT_KEYS:
        raise ValueError(f"unknown project_key for VK Clips scan: {project_key}")
    if isinstance(community_id, bool) or not isinstance(community_id, int) or community_id <= 0:
        raise ValueError(f"VK community_id must be a positive integer: {community_id}")
    if isinstance(owner_id, bool) or not isinstance(owner_id, int) or owner_id >= 0:
        raise ValueError(f"VK owner_id must be a negative integer: {owner_id}")

    expected_communities = PROJECT_VK_COMMUNITY_IDS.get(normalized_project, frozenset())
    if community_id not in expected_communities:
        raise ValueError(
            f"VK community differs from canonical project identity for {normalized_project}: {community_id}"
        )
    if owner_id != -community_id:
        raise ValueError(
            f"VK owner differs from canonical community identity for {normalized_project}: {owner_id}"
        )

    required = _normalize_required_remote_ids(required_remote_ids, owner_id=owner_id)

    channel = client.get_community(community_id)
    returned_community_id = int(channel.ref.channel_id)
    returned_owner_id = channel.metadata.get("owner_id")
    managed_by_token = bool(channel.metadata.get("managed_by_token"))
    if returned_community_id != community_id:
        raise VkApiError(
            f"VK groups.getById resolved a different community: expected {community_id}, got {returned_community_id}",
            method="groups.getById",
        )
    if returned_owner_id != owner_id:
        raise VkApiError(
            f"VK groups.getById resolved a different owner: expected {owner_id}, got {returned_owner_id}",
            method="groups.getById",
        )
    if not managed_by_token:
        raise VkApiError(
            f"VK token did not prove management access for exact community {community_id}",
            method="groups.getById",
        )

    items = client._list_offset(
        "video.search",
        params={
            "owner_id": owner_id,
            "filters": "short",
            "sort": 0,
            "extended": False,
        },
        page_size=200,
    )

    clips: list[dict[str, Any]] = []
    seen_remote_ids: set[str] = set()
    for item in items:
        raw_owner_id = _int_or_none(item.get("owner_id"))
        raw_video_id = _int_or_none(item.get("id"))
        raw_type = str(item.get("type") or "").strip()
        if raw_owner_id != owner_id:
            raise VkApiError(
                f"VK video.search returned foreign owner {raw_owner_id}; expected exact owner {owner_id}",
                method="video.search",
            )
        if raw_video_id is None or raw_video_id <= 0:
            raise VkApiError("VK video.search returned an invalid video ID", method="video.search")
        if raw_type != "short_video":
            raise VkApiError(
                f"VK video.search short filter returned non-Clip type {raw_type or '<missing>'}",
                method="video.search",
            )

        remote_id = f"{raw_owner_id}_{raw_video_id}"
        if remote_id in seen_remote_ids:
            raise VkApiError(
                f"VK video.search returned duplicate Clip remote ID {remote_id}",
                method="video.search",
            )
        seen_remote_ids.add(remote_id)

        published_unix = _int_or_none(item.get("date"))
        clips.append(
            {
                "remote_id": remote_id,
                "owner_id": raw_owner_id,
                "video_id": raw_video_id,
                "type": raw_type,
                "title": str(item.get("title") or remote_id),
                "description": str(item.get("description") or ""),
                "duration_seconds": _int_or_none(item.get("duration")),
                "published_at": _utc_iso(published_unix) if published_unix is not None else None,
                "width": _int_or_none(item.get("width")),
                "height": _int_or_none(item.get("height")),
                "views": _int_or_none(item.get("views")),
                "permalink": f"https://vk.com/clip{remote_id}",
                "raw": item,
            }
        )

    missing_required = [remote_id for remote_id in required if remote_id not in seen_remote_ids]
    if missing_required:
        raise VkApiError(
            "VK Clips scan did not contain required coverage probe(s): " + ", ".join(missing_required),
            method="video.search",
        )

    return {
        "schema": VK_CLIPS_AUDIT_SCHEMA,
        "generated_at": _utc_iso(),
        "project_key": normalized_project,
        "account_alias": client.account_alias,
        "api_version": client.api_version,
        "read_only": True,
        "provider_effect": "safe_read_only",
        "community": {
            "community_id": community_id,
            "owner_id": owner_id,
            "title": channel.title,
            "url": channel.url,
            "managed_by_token": True,
        },
        "request_contract": {
            "method": "video.search",
            "owner_id": owner_id,
            "filters": ["short"],
            "sort": 0,
            "extended": False,
            "page_size": 200,
        },
        "coverage": {
            "clip_count": len(clips),
            "all_items_exact_owner": True,
            "all_items_short_video": True,
            "required_remote_ids": required,
            "required_remote_ids_found": required,
        },
        "clips": clips,
    }


__all__ = ["VK_CLIPS_AUDIT_SCHEMA", "build_vk_clips_audit_snapshot"]
