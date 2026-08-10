from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from video_channel_manager.editorial._project_profiles import PROJECT_KEYS, PROJECT_VK_COMMUNITY_IDS
from video_channel_manager.platforms.vk.client import VkApiClient, VkApiError

VK_OWNER_CLIPS_PROBE_SCHEMA = "vk-owner-clips-experimental-probe-v1"
VK_OWNER_CLIPS_PROBE_API_VERSION = "5.253"
VK_OWNER_CLIPS_PROBE_METHOD = "shortVideo.getOwnerVideos"
VK_OWNER_CLIPS_PROBE_PAGE_SIZE = 24


def _utc_iso(value: int | None = None) -> str:
    moment = datetime.now(UTC) if value is None else datetime.fromtimestamp(value, tz=UTC)
    return moment.isoformat().replace("+00:00", "Z")


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) else None


def _validate_identity(*, project_key: str, community_id: int, owner_id: int) -> str:
    normalized_project = project_key.strip()
    if normalized_project not in PROJECT_KEYS:
        raise ValueError(f"unknown project_key for VK owner Clips probe: {project_key}")
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
        raise ValueError(f"VK owner differs from canonical community identity for {normalized_project}: {owner_id}")
    return normalized_project


def _normalize_required_remote_ids(values: Sequence[str], *, owner_id: int) -> list[str]:
    normalized: list[str] = []
    expected_prefix = f"{owner_id}_"
    for raw in values:
        value = raw.strip()
        if not value:
            raise ValueError("required VK remote ID cannot be blank")
        if not value.startswith(expected_prefix):
            raise ValueError(f"required VK remote ID does not belong to exact owner {owner_id}: {value}")
        suffix = value[len(expected_prefix) :]
        if not suffix.isdigit() or int(suffix) <= 0:
            raise ValueError(f"invalid required VK remote ID: {value}")
        normalized.append(value)
    if len(set(normalized)) != len(normalized):
        raise ValueError("required VK remote IDs must be unique")
    return normalized


def _provider_error_payload(exc: VkApiError) -> dict[str, Any]:
    return {
        "method": exc.method,
        "code": exc.code,
        "retryable": exc.retryable,
        "kind": exc.kind.value if exc.kind is not None else None,
        "attempts": exc.attempts,
        "message": str(exc),
    }


def _video_payload(item: dict[str, Any]) -> dict[str, Any]:
    nested = item.get("video")
    return nested if isinstance(nested, dict) else item


def _serialize_candidate(item: dict[str, Any], *, owner_id: int) -> tuple[dict[str, Any] | None, str | None]:
    video = _video_payload(item)
    raw_owner_id = _int_or_none(video.get("owner_id"))
    raw_video_id = _int_or_none(video.get("id"))
    if raw_owner_id is None or raw_video_id is None or raw_video_id <= 0:
        return None, "missing_owner_or_video_id"
    if raw_owner_id != owner_id:
        raise VkApiError(
            f"VK {VK_OWNER_CLIPS_PROBE_METHOD} returned foreign owner {raw_owner_id}; expected exact owner {owner_id}",
            method=VK_OWNER_CLIPS_PROBE_METHOD,
        )

    remote_id = f"{raw_owner_id}_{raw_video_id}"
    raw_type = str(video.get("type") or "").strip()
    published_unix = _int_or_none(video.get("date"))
    is_native_clip = raw_type == "short_video"
    return (
        {
            "remote_id": remote_id,
            "owner_id": raw_owner_id,
            "video_id": raw_video_id,
            "type": raw_type or None,
            "is_native_clip": is_native_clip,
            "title": str(video.get("title") or remote_id),
            "description": str(video.get("description") or ""),
            "duration_seconds": _int_or_none(video.get("duration")),
            "published_at": _utc_iso(published_unix) if published_unix is not None else None,
            "width": _int_or_none(video.get("width")),
            "height": _int_or_none(video.get("height")),
            "views": _int_or_none(video.get("views")),
            "permalink": (
                f"https://vk.com/clip{remote_id}" if is_native_clip else f"https://vk.com/video{remote_id}"
            ),
            "raw": item,
        },
        None,
    )


def build_vk_owner_clips_probe_snapshot(
    client: VkApiClient,
    *,
    project_key: str,
    community_id: int,
    owner_id: int,
    required_remote_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """Probe the VK Video owner Clips endpoint without mutating provider state.

    ``shortVideo.getOwnerVideos`` is observed in the VK Video web client but is
    not part of the public VK API 5.199 schema. The probe therefore records the
    endpoint response as experimental evidence and only recognizes a native
    Clip when the returned video object explicitly proves ``type=short_video``.
    """

    normalized_project = _validate_identity(
        project_key=project_key,
        community_id=community_id,
        owner_id=owner_id,
    )
    if client.api_version != VK_OWNER_CLIPS_PROBE_API_VERSION:
        raise ValueError(
            "VK owner Clips probe requires the exact observed web-client API version "
            f"{VK_OWNER_CLIPS_PROBE_API_VERSION}; got {client.api_version}"
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

    raw_items: list[dict[str, Any]] = []
    provider_reported_total: int | None = None
    provider_reported_offsets: list[int] = []
    offset = 0
    provider_error: dict[str, Any] | None = None
    pagination_complete = False

    for _ in range(100):
        try:
            response = client._call(
                VK_OWNER_CLIPS_PROBE_METHOD,
                params={
                    "owner_id": owner_id,
                    "offset": offset,
                    "count": VK_OWNER_CLIPS_PROBE_PAGE_SIZE,
                },
            )
        except VkApiError as exc:
            provider_error = _provider_error_payload(exc)
            break

        if not isinstance(response, dict):
            provider_error = {
                "method": VK_OWNER_CLIPS_PROBE_METHOD,
                "code": None,
                "retryable": False,
                "kind": "invalid_payload",
                "attempts": 1,
                "message": f"VK {VK_OWNER_CLIPS_PROBE_METHOD} returned a non-object response",
            }
            break

        count_value = _int_or_none(response.get("count"))
        if provider_reported_total is None and count_value is not None:
            provider_reported_total = count_value
        response_offset = _int_or_none(response.get("offset"))
        if response_offset is not None:
            provider_reported_offsets.append(response_offset)

        page_value = response.get("items")
        if not isinstance(page_value, list):
            provider_error = {
                "method": VK_OWNER_CLIPS_PROBE_METHOD,
                "code": None,
                "retryable": False,
                "kind": "invalid_payload",
                "attempts": 1,
                "message": f"VK {VK_OWNER_CLIPS_PROBE_METHOD} response has no list items field",
            }
            break
        page = [item for item in page_value if isinstance(item, dict)]
        raw_items.extend(page)

        if not page:
            pagination_complete = provider_reported_total in {None, len(raw_items)}
            break
        offset += len(page)
        if provider_reported_total is not None and offset >= provider_reported_total:
            pagination_complete = True
            break
        if provider_reported_total is None and len(page) < VK_OWNER_CLIPS_PROBE_PAGE_SIZE:
            pagination_complete = True
            break
    else:
        provider_error = {
            "method": VK_OWNER_CLIPS_PROBE_METHOD,
            "code": None,
            "retryable": False,
            "kind": "pagination_limit",
            "attempts": 100,
            "message": "VK owner Clips probe hit the 100-page safety limit",
        }

    candidates: list[dict[str, Any]] = []
    shape_noise: list[dict[str, Any]] = []
    seen_remote_ids: set[str] = set()
    for index, item in enumerate(raw_items):
        record, reason = _serialize_candidate(item, owner_id=owner_id)
        if record is None:
            shape_noise.append({"index": index, "reason": reason, "raw": item})
            continue
        remote_id = str(record["remote_id"])
        if remote_id in seen_remote_ids:
            raise VkApiError(
                f"VK {VK_OWNER_CLIPS_PROBE_METHOD} returned duplicate remote ID {remote_id}",
                method=VK_OWNER_CLIPS_PROBE_METHOD,
            )
        seen_remote_ids.add(remote_id)
        candidates.append(record)

    clips = [item for item in candidates if item["is_native_clip"] is True]
    type_counts = Counter(str(item["type"] or "<missing>") for item in candidates)
    candidate_remote_ids = {str(item["remote_id"]) for item in candidates}
    clip_remote_ids = {str(item["remote_id"]) for item in clips}
    required_found = [remote_id for remote_id in required if remote_id in clip_remote_ids]
    required_returned_non_clip = [
        remote_id for remote_id in required if remote_id in candidate_remote_ids and remote_id not in clip_remote_ids
    ]
    required_missing = [remote_id for remote_id in required if remote_id not in candidate_remote_ids]
    endpoint_ok = provider_error is None

    return {
        "schema": VK_OWNER_CLIPS_PROBE_SCHEMA,
        "generated_at": _utc_iso(),
        "project_key": normalized_project,
        "account_alias": client.account_alias,
        "api_version": client.api_version,
        "read_only": True,
        "provider_effect": "safe_read_only",
        "evidence_level": "experimental_vk_video_web_client_endpoint",
        "community": {
            "community_id": community_id,
            "owner_id": owner_id,
            "title": channel.title,
            "url": channel.url,
            "managed_by_token": True,
        },
        "request_contract": {
            "method": VK_OWNER_CLIPS_PROBE_METHOD,
            "owner_id": owner_id,
            "page_size": VK_OWNER_CLIPS_PROBE_PAGE_SIZE,
            "api_version": VK_OWNER_CLIPS_PROBE_API_VERSION,
            "public_vk_api_5_199_documented": False,
        },
        "provider_probe": {
            "status": "ok" if endpoint_ok else "error",
            "error": provider_error,
            "provider_reported_total": provider_reported_total,
            "provider_reported_offsets": provider_reported_offsets,
            "retrieved_raw_item_count": len(raw_items),
            "pagination_complete": pagination_complete,
        },
        "coverage": {
            "candidate_count": len(candidates),
            "clip_count": len(clips),
            "shape_noise_count": len(shape_noise),
            "returned_type_counts": dict(sorted(type_counts.items())),
            "all_normalized_items_exact_owner": True,
            "native_clip_identity_rule": "type=short_video",
            "required_remote_ids": required,
            "required_remote_ids_found_as_clips": required_found,
            "required_remote_ids_returned_non_clip": required_returned_non_clip,
            "required_remote_ids_missing_from_probe": required_missing,
            "surface_complete_claim": False,
        },
        "known_limitations": [
            "shortVideo.getOwnerVideos is observed in the VK Video web client but is not in the public VK API 5.199 schema.",
            "This first probe is evidence collection, not authorization for upload, edit, hide, delete, wall post, or scheduling.",
            "Only records explicitly proving type=short_video are classified as native Clips.",
            "Even a successful pagination pass must be reconciled against independently observed wall Clips before a complete-surface claim is made.",
        ],
        "clips": clips,
        "endpoint_candidates": candidates,
        "shape_noise": shape_noise,
    }


__all__ = [
    "VK_OWNER_CLIPS_PROBE_API_VERSION",
    "VK_OWNER_CLIPS_PROBE_METHOD",
    "VK_OWNER_CLIPS_PROBE_SCHEMA",
    "build_vk_owner_clips_probe_snapshot",
]
