from __future__ import annotations

import hashlib
import time
from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from video_channel_manager.platforms.vk.milovi_immediate_wall import MILOVI_COMMUNITY_ID, MILOVI_OWNER_ID
from video_channel_manager.platforms.vk.milovi_issue323_anomaly_state import ANOMALY_WALL_REMOTE_ID
from video_channel_manager.platforms.vk.milovi_issue323_live_resume import _native_clip_assessment
from video_channel_manager.platforms.vk.milovi_promotion import (
    assert_internal_promotion_copy,
    public_clip_description,
    public_wall_message,
)
from video_channel_manager.platforms.vk.milovi_rollout_sources import (
    ROLL_OUT_IDS,
    SourceAsset,
    build_description,
    build_wall_message,
)
from video_channel_manager.platforms.vk.milovi_token_clip_rollout import (
    MiloviTokenRolloutBlocked,
    _parse_remote_id,
    clip_readiness,
)
from video_channel_manager.platforms.vk.wall import VkWallWriter
from video_channel_manager.platforms.vk.wall_safety import VkWallSnapshot, VkWallSurface

_MIN_PROCESSING_COPY_PREFIX = 80


class MiloviIssue323ReadModelBlocked(MiloviTokenRolloutBlocked):
    """Exact Issue #323 provider evidence cannot be reduced to one safe read model."""


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _promote_asset(asset: SourceAsset) -> SourceAsset:
    """Build reviewed internal-promotion copy without granting provider mutation authority."""

    description = public_clip_description(asset.title)
    wall_message = public_wall_message(asset.title)
    assert_internal_promotion_copy(description, title=asset.title)
    assert_internal_promotion_copy(wall_message, title=asset.title)
    legacy_description = asset.legacy_description if asset.legacy_description is not None else asset.description
    legacy_wall_message = asset.legacy_wall_message if asset.legacy_wall_message is not None else asset.wall_message
    return replace(
        asset,
        description=description,
        wall_message=wall_message,
        legacy_description=legacy_description.strip(),
        legacy_wall_message=legacy_wall_message.strip(),
    )


def _legacy_clip_description(asset: SourceAsset) -> str:
    if asset.legacy_description is not None:
        return asset.legacy_description.strip()
    return build_description(asset.title, asset.source_id).strip()


def _legacy_wall_message(asset: SourceAsset) -> str:
    if asset.legacy_wall_message is not None:
        return asset.legacy_wall_message.strip()
    return build_wall_message(asset.title, asset.source_id).strip()


def _copy_state(*, current: str, legacy: str, promoted: str, source_id: str, field: str) -> str:
    if current == promoted:
        return "promoted"
    if current == legacy:
        return "legacy"
    raise MiloviIssue323ReadModelBlocked(
        f"{field} for {source_id} is neither exact reviewed legacy nor exact promoted copy"
    )


def _processing_copy_prefix(current: str) -> str | None:
    value = current.strip()
    if value.endswith("…"):
        prefix = value[:-1].rstrip()
    else:
        trailing_dots = len(value) - len(value.rstrip("."))
        if trailing_dots < 2:
            return None
        prefix = value[:-trailing_dots].rstrip()
    if len(prefix) < _MIN_PROCESSING_COPY_PREFIX:
        return None
    return prefix


def _clip_copy_state(
    *,
    current: str,
    legacy: str,
    promoted: str,
    source_id: str,
    field: str,
    provider_item: Mapping[str, Any],
) -> str:
    """Classify exact copy or one narrow VK processing-time truncation projection."""

    try:
        return _copy_state(
            current=current,
            legacy=legacy,
            promoted=promoted,
            source_id=source_id,
            field=field,
        )
    except MiloviIssue323ReadModelBlocked as exc:
        provider_busy = bool(provider_item.get("processing")) or bool(provider_item.get("converting"))
        if not provider_busy:
            raise
        prefix = _processing_copy_prefix(current)
        if prefix is None:
            raise
        if promoted.startswith(prefix):
            return "provider_processing_promoted_projection"
        if legacy.startswith(prefix):
            return "provider_processing_legacy_projection"
        raise exc


def _assert_native_clip(
    writer: VkWallWriter,
    asset: SourceAsset,
    remote_id: str,
    *,
    description_mode: str,
    preservation_only: bool = False,
    durable_verified: bool = False,
) -> dict[str, Any]:
    """Read and prove one exact native Clip; this function has no write capability."""

    owner_id, video_id = _parse_remote_id(remote_id)
    raw = writer.read_video(owner_id=owner_id, video_id=video_id)
    if raw is None:
        raise MiloviIssue323ReadModelBlocked(f"VK Clip disappeared: {remote_id}")
    if raw.get("owner_id") != owner_id or raw.get("id") != video_id:
        raise MiloviIssue323ReadModelBlocked(f"VK Clip identity changed: {remote_id}")
    if preservation_only:
        return raw
    if durable_verified:
        if str(raw.get("type") or "") != "short_video":
            raise MiloviIssue323ReadModelBlocked(f"Durably verified VK Clip lost native short_video type: {remote_id}")
    else:
        assessment = _native_clip_assessment(
            raw,
            expected_owner_id=owner_id,
            expected_video_id=video_id,
            readiness=clip_readiness(asset),
        )
        if not assessment.ready:
            raise MiloviIssue323ReadModelBlocked(
                f"VK object {remote_id} is not a verified native short_video: {assessment.reasons}"
            )
    description = str(raw.get("description") or "").strip()
    if description_mode == "promoted":
        if description != asset.description.strip():
            raise MiloviIssue323ReadModelBlocked(f"VK Clip {remote_id} public description differs from promotion plan")
    elif description_mode == "legacy_or_promoted":
        _clip_copy_state(
            current=description,
            legacy=_legacy_clip_description(asset),
            promoted=asset.description.strip(),
            source_id=asset.source_id,
            field="Clip description",
            provider_item=raw,
        )
    else:
        raise ValueError(f"Unknown description_mode: {description_mode}")
    return raw


def _one_video_attachment(post: Mapping[str, Any]) -> tuple[int, int, Mapping[str, Any]]:
    """Return the exact single video while tolerating provider-projected non-video attachments."""

    attachments = post.get("attachments")
    if not isinstance(attachments, list):
        raise MiloviIssue323ReadModelBlocked("Wall post attachments are unavailable")
    videos: list[Mapping[str, Any]] = []
    for index, attachment in enumerate(attachments):
        if not isinstance(attachment, Mapping):
            raise MiloviIssue323ReadModelBlocked(f"Wall attachment {index} is not an object")
        if attachment.get("type") != "video":
            continue
        video = attachment.get("video")
        if not isinstance(video, Mapping):
            raise MiloviIssue323ReadModelBlocked("Wall video attachment has no expanded video object")
        videos.append(video)
    if len(videos) != 1:
        raise MiloviIssue323ReadModelBlocked(
            f"Wall post must contain exactly one video attachment; observed {len(videos)}"
        )
    video = videos[0]
    owner_id = video.get("owner_id")
    video_id = video.get("id")
    if type(owner_id) is not int or type(video_id) is not int:
        raise MiloviIssue323ReadModelBlocked("Wall attachment identity is invalid")
    return owner_id, video_id, video


def _assert_post_shape(post: Mapping[str, Any], *, clip_remote_id: str, publish_date: int) -> None:
    owner_id, video_id = _parse_remote_id(clip_remote_id)
    if post.get("owner_id") != MILOVI_OWNER_ID or post.get("date") != publish_date:
        raise MiloviIssue323ReadModelBlocked("Wall identity/date changed")
    attachment_owner, attachment_video, _expanded = _one_video_attachment(post)
    if (attachment_owner, attachment_video) != (owner_id, video_id):
        raise MiloviIssue323ReadModelBlocked("Wall attachment changed")


def _journaled_wall_ids(journal: Mapping[str, Any]) -> set[str]:
    items = journal.get("items")
    if not isinstance(items, Mapping):
        raise MiloviIssue323ReadModelBlocked("Issue #323 journal has no item map for wall resolution")
    result: set[str] = set()
    for source_id in ROLL_OUT_IDS:
        raw = items.get(source_id)
        if not isinstance(raw, Mapping):
            continue
        remote_id = raw.get("wall_remote_id")
        if not isinstance(remote_id, str) or not remote_id:
            continue
        owner_id, post_id = _parse_remote_id(remote_id)
        if owner_id != MILOVI_OWNER_ID or post_id <= 0:
            raise MiloviIssue323ReadModelBlocked(f"Journaled wall ID left Milovi: {source_id}")
        if remote_id in result:
            raise MiloviIssue323ReadModelBlocked(f"Journaled wall ID is reused by multiple sources: {remote_id}")
        result.add(remote_id)
    return result


def _read_exact_wall_incarnation(
    writer: VkWallWriter,
    *,
    remote_id: str,
    clip_remote_id: str,
    publish_date: int,
) -> dict[str, Any]:
    owner_id, post_id = _parse_remote_id(remote_id)
    raw = writer.read_post(community_id=MILOVI_COMMUNITY_ID, post_id=post_id)
    if raw is None or raw.get("is_deleted") is True:
        raise MiloviIssue323ReadModelBlocked(f"Resolved wall incarnation is not live: {remote_id}")
    if raw.get("owner_id") != owner_id or raw.get("id") != post_id:
        raise MiloviIssue323ReadModelBlocked(f"Resolved wall incarnation changed identity: {remote_id}")
    _assert_post_shape(raw, clip_remote_id=clip_remote_id, publish_date=publish_date)
    return dict(raw)


def _resolve_wall_incarnation(
    *,
    writer: VkWallWriter,
    snapshot: VkWallSnapshot,
    journal: Mapping[str, Any],
    wall_remote_id: str,
    clip_remote_id: str,
    publish_date: int,
    now_epoch: int | None = None,
) -> tuple[str, VkWallSurface, dict[str, Any], str]:
    """Resolve one live provider incarnation of an Issue #323 logical wall mapping."""

    if not snapshot.complete:
        raise MiloviIssue323ReadModelBlocked("Complete wall snapshot is required for wall resolution")
    owner_id, post_id = _parse_remote_id(wall_remote_id)
    if owner_id != MILOVI_OWNER_ID or post_id <= 0:
        raise MiloviIssue323ReadModelBlocked("Wall remote ID is outside Milovi")
    expected_attachment = f"video{clip_remote_id}"
    logical_candidates = [
        post
        for post in snapshot.posts
        if post.owner_id == owner_id and post.publish_date == publish_date and expected_attachment in post.attachments
    ]
    old_matches = [post for post in snapshot.posts if post.remote_id == wall_remote_id]
    if len(old_matches) > 1:
        raise MiloviIssue323ReadModelBlocked(f"Journaled wall ID appears on multiple surfaces: {wall_remote_id}")
    observed_now = int(time.time()) if now_epoch is None else now_epoch

    if old_matches:
        current = old_matches[0]
        if len(logical_candidates) != 1 or logical_candidates[0].remote_id != wall_remote_id:
            raise MiloviIssue323ReadModelBlocked(f"Logical wall mapping is duplicated for {wall_remote_id}")
        if current.publish_date != publish_date or expected_attachment not in current.attachments:
            raise MiloviIssue323ReadModelBlocked(f"Journaled wall mapping changed binding: {wall_remote_id}")
        if current.surface is VkWallSurface.PUBLISHED and observed_now + 60 < publish_date:
            raise MiloviIssue323ReadModelBlocked(f"Wall post published before its scheduled slot: {wall_remote_id}")
        raw = _read_exact_wall_incarnation(
            writer,
            remote_id=wall_remote_id,
            clip_remote_id=clip_remote_id,
            publish_date=publish_date,
        )
        return wall_remote_id, current.surface, raw, "journaled_id"

    if observed_now + 60 < publish_date:
        raise MiloviIssue323ReadModelBlocked(f"Wall mapping disappeared before its frozen slot: {wall_remote_id}")

    exact_old = writer.read_post(community_id=MILOVI_COMMUNITY_ID, post_id=post_id)
    if exact_old is not None and exact_old.get("is_deleted") is not True:
        if exact_old.get("owner_id") != owner_id or exact_old.get("id") != post_id:
            raise MiloviIssue323ReadModelBlocked(f"Journaled wall exact read changed identity: {wall_remote_id}")
        _assert_post_shape(exact_old, clip_remote_id=clip_remote_id, publish_date=publish_date)
        if logical_candidates:
            candidate_ids = sorted(post.remote_id for post in logical_candidates)
            raise MiloviIssue323ReadModelBlocked(
                f"Journaled wall exact read is live but aggregate snapshot also has logical candidates: {candidate_ids}"
            )
        return wall_remote_id, VkWallSurface.PUBLISHED, dict(exact_old), "exact_old_id"

    if exact_old is not None:
        if exact_old.get("is_deleted") is not True:
            raise MiloviIssue323ReadModelBlocked(f"Journaled wall exact read has ambiguous state: {wall_remote_id}")
        if exact_old.get("owner_id") != owner_id or exact_old.get("id") != post_id:
            raise MiloviIssue323ReadModelBlocked(f"Journaled wall tombstone changed identity: {wall_remote_id}")
        tombstone_date = exact_old.get("date")
        if type(tombstone_date) is int and tombstone_date != publish_date:
            raise MiloviIssue323ReadModelBlocked(
                f"Journaled wall tombstone date changed: {wall_remote_id}: {tombstone_date} != {publish_date}"
            )

    successors = [
        post
        for post in logical_candidates
        if post.surface is VkWallSurface.PUBLISHED and post.remote_id != wall_remote_id
    ]
    if not successors:
        raise MiloviIssue323ReadModelBlocked(f"No published successor exists for due wall mapping: {wall_remote_id}")
    if len(successors) != 1:
        successor_ids = sorted(post.remote_id for post in successors)
        raise MiloviIssue323ReadModelBlocked(f"Published successor is ambiguous for {wall_remote_id}: {successor_ids}")
    successor = successors[0]
    if successor.remote_id in _journaled_wall_ids(journal):
        raise MiloviIssue323ReadModelBlocked(
            f"Published successor collides with another journaled wall ID: {wall_remote_id} -> {successor.remote_id}"
        )
    if successor.remote_id == ANOMALY_WALL_REMOTE_ID:
        raise MiloviIssue323ReadModelBlocked("Published successor unexpectedly reused anomaly wall 475")
    raw = _read_exact_wall_incarnation(
        writer,
        remote_id=successor.remote_id,
        clip_remote_id=clip_remote_id,
        publish_date=publish_date,
    )
    return successor.remote_id, VkWallSurface.PUBLISHED, raw, "published_successor"


__all__ = [
    "MiloviIssue323ReadModelBlocked",
    "_assert_native_clip",
    "_clip_copy_state",
    "_copy_state",
    "_legacy_clip_description",
    "_legacy_wall_message",
    "_one_video_attachment",
    "_promote_asset",
    "_read_exact_wall_incarnation",
    "_resolve_wall_incarnation",
    "_sha256_text",
]
