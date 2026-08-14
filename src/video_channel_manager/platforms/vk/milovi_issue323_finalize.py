from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk import VkApiClient, VkTokenStore, local_vk_write_lock
from video_channel_manager.platforms.vk.milovi_daily_postponed_wall import load_or_create_daily_schedule
from video_channel_manager.platforms.vk.milovi_immediate_wall import MILOVI_COMMUNITY_ID, MILOVI_OWNER_ID
from video_channel_manager.platforms.vk.milovi_issue323_live_resume import (
    _Issue323RecoveryWriter,
    _LiveClipWriter,
    _ensure_clip_live,
    _native_clip_assessment,
    _resume_wall_baseline,
)
from video_channel_manager.platforms.vk.milovi_issue323_upload_wall_reconcile import (
    reconcile_issue323_upload_wall_effect,
)
from video_channel_manager.platforms.vk.milovi_promotion import (
    PUBLIC_PROMOTION_URLS,
    assert_internal_promotion_copy,
    public_clip_description,
    public_wall_message,
)
from video_channel_manager.platforms.vk.milovi_rollout_sources import (
    ROLL_OUT_IDS,
    SourceAsset,
    prepare_sources,
    write_json_atomic,
)
from video_channel_manager.platforms.vk.milovi_token_clip_rollout import (
    MiloviTokenRolloutBlocked,
    _ensure_wall,
    _has_provider_effect,
    _item,
    _load_journal,
    _media_artifacts,
    _parse_remote_id,
    _prove_target,
    _resolve_account,
    _result,
    _save,
    _upload_remote_id,
    clip_readiness,
)
from video_channel_manager.platforms.vk.upload_lifecycle import (
    UploadRecoveryRequired,
    UploadRejected,
    UploadStage,
    ensure_upload_record,
)
from video_channel_manager.platforms.vk.upload_media import execute_upload_operation
from video_channel_manager.platforms.vk.wall import VkWallWriter
from video_channel_manager.platforms.vk.wall_safety import DEFAULT_UPLOAD_WALL_POLICY, VkWallSnapshot, VkWallSurface

EXECUTION_CONFIRMATION = "ISSUE_323_FINALIZE_INTERNAL_PROMOTION_AND_CLEANUP_475"
FINALIZER_SCHEMA = "video-manager.milovi-issue-323-finalizer"
ANOMALY_SOURCE_ID = "o1WXIMupuws"
ANOMALY_CLIP_REMOTE_ID = "-68859909_456239232"
ANOMALY_POST_ID = 475
ANOMALY_WALL_REMOTE_ID = f"{MILOVI_OWNER_ID}_{ANOMALY_POST_ID}"
LEGACY_MARKER_PREFIX = "youtube.com/shorts/"


class MiloviFinalizerBlocked(MiloviTokenRolloutBlocked):
    pass


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _promote_asset(asset: SourceAsset) -> SourceAsset:
    description = public_clip_description(asset.title)
    wall_message = public_wall_message(asset.title)
    assert_internal_promotion_copy(description, title=asset.title)
    assert_internal_promotion_copy(wall_message, title=asset.title)
    return replace(asset, description=description, wall_message=wall_message)


def _promotion_plan(assets: list[SourceAsset]) -> dict[str, dict[str, str]]:
    return {
        asset.source_id: {
            "clip_description_sha256": _sha256_text(asset.description),
            "wall_message_sha256": _sha256_text(asset.wall_message),
        }
        for asset in assets
    }


def _new_finalizer_journal(assets: list[SourceAsset]) -> dict[str, Any]:
    return {
        "schema_name": FINALIZER_SCHEMA,
        "schema_version": 1,
        "community_id": MILOVI_COMMUNITY_ID,
        "owner_id": MILOVI_OWNER_ID,
        "anomaly_wall_remote_id": ANOMALY_WALL_REMOTE_ID,
        "anomaly_clip_remote_id": ANOMALY_CLIP_REMOTE_ID,
        "promotion_plan": _promotion_plan(assets),
        "cleanup_475": {"status": "pending"},
        "clip_description_edits": {source_id: {"status": "pending"} for source_id in ROLL_OUT_IDS},
        "wall_message_edits": {source_id: {"status": "pending"} for source_id in ROLL_OUT_IDS},
    }


def _load_finalizer_journal(path: Path, assets: list[SourceAsset]) -> dict[str, Any]:
    if not path.is_file():
        payload = _new_finalizer_journal(assets)
        write_json_atomic(path, payload)
        return payload
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise MiloviFinalizerBlocked("Finalizer journal is not a JSON object")
    expected = {
        "schema_name": FINALIZER_SCHEMA,
        "schema_version": 1,
        "community_id": MILOVI_COMMUNITY_ID,
        "owner_id": MILOVI_OWNER_ID,
        "anomaly_wall_remote_id": ANOMALY_WALL_REMOTE_ID,
        "anomaly_clip_remote_id": ANOMALY_CLIP_REMOTE_ID,
        "promotion_plan": _promotion_plan(assets),
    }
    mismatch = {key: (value, payload.get(key)) for key, value in expected.items() if payload.get(key) != value}
    if mismatch:
        raise MiloviFinalizerBlocked(f"Finalizer journal binding mismatch: {mismatch}")
    return payload


def _save_finalizer(path: Path, journal: dict[str, Any]) -> None:
    write_json_atomic(path, journal)


def _legacy_marker_ok(item: Mapping[str, Any], source_id: str) -> bool:
    marker = f"{LEGACY_MARKER_PREFIX}{source_id}".casefold()
    return marker in str(item.get("description") or "").casefold()


def _assert_native_clip(
    writer: VkWallWriter,
    asset: SourceAsset,
    remote_id: str,
    *,
    description_mode: str,
    preservation_only: bool = False,
    durable_verified: bool = False,
) -> dict[str, Any]:
    owner_id, video_id = _parse_remote_id(remote_id)
    raw = writer.read_video(owner_id=owner_id, video_id=video_id)
    if raw is None:
        raise MiloviFinalizerBlocked(f"VK Clip disappeared: {remote_id}")
    if raw.get("owner_id") != owner_id or raw.get("id") != video_id:
        raise MiloviFinalizerBlocked(f"VK Clip identity changed: {remote_id}")
    if preservation_only:
        return raw
    if durable_verified:
        if str(raw.get("type") or "") != "short_video":
            raise MiloviFinalizerBlocked(f"Durably verified VK Clip lost native short_video type: {remote_id}")
    else:
        assessment = _native_clip_assessment(
            raw,
            expected_owner_id=owner_id,
            expected_video_id=video_id,
            readiness=clip_readiness(asset),
        )
        if not assessment.ready:
            raise MiloviFinalizerBlocked(
                f"VK object {remote_id} is not a verified native short_video: {assessment.reasons}"
            )
    description = str(raw.get("description") or "").strip()
    if description_mode == "promoted":
        if description != asset.description.strip():
            raise MiloviFinalizerBlocked(f"VK Clip {remote_id} public description differs from promotion plan")
    elif description_mode == "legacy_or_promoted":
        if description != asset.description.strip() and not _legacy_marker_ok(raw, asset.source_id):
            raise MiloviFinalizerBlocked(f"VK Clip {remote_id} cannot be bound to source {asset.source_id}")
    else:
        raise ValueError(f"Unknown description_mode: {description_mode}")
    return raw


def _one_video_attachment(post: Mapping[str, Any]) -> tuple[int, int, Mapping[str, Any]]:
    """Return the exact single video while tolerating provider-projected non-video attachments."""

    attachments = post.get("attachments")
    if not isinstance(attachments, list):
        raise MiloviFinalizerBlocked("Wall post attachments are unavailable")
    videos: list[Mapping[str, Any]] = []
    for index, attachment in enumerate(attachments):
        if not isinstance(attachment, Mapping):
            raise MiloviFinalizerBlocked(f"Wall attachment {index} is not an object")
        if attachment.get("type") != "video":
            continue
        video = attachment.get("video")
        if not isinstance(video, Mapping):
            raise MiloviFinalizerBlocked("Wall video attachment has no expanded video object")
        videos.append(video)
    if len(videos) != 1:
        raise MiloviFinalizerBlocked(f"Wall post must contain exactly one video attachment; observed {len(videos)}")
    video = videos[0]
    owner_id = video.get("owner_id")
    video_id = video.get("id")
    if type(owner_id) is not int or type(video_id) is not int:
        raise MiloviFinalizerBlocked("Wall attachment identity is invalid")
    return owner_id, video_id, video


def _assert_wall475_absent(writer: VkWallWriter) -> str:
    """Verify absence read-only; destructive authority belongs only to phase 1."""

    post = writer.read_post(community_id=MILOVI_COMMUNITY_ID, post_id=ANOMALY_POST_ID)
    if post is None:
        return "wall.getById:none"
    if post.get("is_deleted") is True and post.get("owner_id") == MILOVI_OWNER_ID and post.get("id") == ANOMALY_POST_ID:
        return "wall.getById:is_deleted_true"
    raise MiloviFinalizerBlocked("Wall 475 is live or its tombstone identity changed; phase 2 has no delete authority")


def _cleanup_anomaly_475(
    *,
    writer: VkWallWriter,
    promoted_asset: SourceAsset,
    finalizer: dict[str, Any],
    finalizer_path: Path,
) -> None:
    """Adopt phase-1 cleanup read-only; never delete or replay wall 475 here."""

    state = finalizer["cleanup_475"]
    if state.get("status") != "verified_absent":
        raise MiloviFinalizerBlocked(
            "Wall 475 cleanup is not durably reconciled by phase 1; phase 2 has no delete authority"
        )
    absence_evidence = _assert_wall475_absent(writer)
    _assert_native_clip(
        writer,
        promoted_asset,
        ANOMALY_CLIP_REMOTE_ID,
        description_mode="legacy_or_promoted",
        preservation_only=True,
    )
    state.update(
        status="verified_absent",
        phase2_delete_authority=False,
        phase2_absence_evidence=absence_evidence,
        protected_clip_remote_id=ANOMALY_CLIP_REMOTE_ID,
        protected_clip_preserved=True,
    )
    _save_finalizer(finalizer_path, finalizer)


def _needs_issue323_upload_wall_reconcile(record: Mapping[str, Any]) -> bool:
    try:
        stage = UploadStage(str(record.get("stage")))
    except ValueError:
        return False
    if stage is not UploadStage.UNKNOWN_REQUIRES_RECONCILIATION:
        return False
    wall_safety = record.get("wall_safety")
    delta = wall_safety.get("delta") if isinstance(wall_safety, Mapping) else None
    return isinstance(delta, Mapping) and delta.get("status") == "changed"


def _ensure_promoted_clip(
    asset: SourceAsset,
    artifact: Any,
    item: dict[str, Any],
    journal: dict[str, Any],
    journal_path: Path,
    writer: VkWallWriter,
    upload_writer: _LiveClipWriter,
    timeout: int,
) -> str:
    current = item.get("clip_remote_id")
    if isinstance(current, str) and current:
        _assert_native_clip(writer, asset, current, description_mode="promoted", durable_verified=True)
        return current

    raw_record = item.get("upload_record")
    record = dict(raw_record) if isinstance(raw_record, Mapping) else None
    readiness = clip_readiness(asset)
    record, _ = ensure_upload_record(
        record,
        source_snapshot_id=journal["source_snapshot_id"],
        community_id=MILOVI_COMMUNITY_ID,
        source_video_id=asset.source_id,
        source_title=asset.title,
        source_duration_seconds=asset.duration_seconds,
        published_title=asset.title,
        published_description=asset.description,
        readiness=readiness,
        wall_policy=DEFAULT_UPLOAD_WALL_POLICY,
    )
    item["upload_record"] = record
    _save(journal_path, journal)

    def persist() -> None:
        item["upload_record"] = record
        _save(journal_path, journal)

    def prepare_recovery(current_wall: VkWallSnapshot) -> tuple[VkWallSnapshot, _Issue323RecoveryWriter]:
        if not current_wall.complete:
            raise MiloviFinalizerBlocked("Complete wall snapshot unavailable during upload recovery")
        if _needs_issue323_upload_wall_reconcile(record):
            current_wall, wall_before = reconcile_issue323_upload_wall_effect(
                record=record,
                current_wall=current_wall,
                journal=journal,
                writer=writer,
                client=upload_writer.client,
                source_id=asset.source_id,
                persist=persist,
            )
        else:
            wall_before = _resume_wall_baseline(record, current_wall, journal=journal)
        raw_wall_safety = record.get("wall_safety")
        if not isinstance(raw_wall_safety, Mapping):
            raise UploadRecoveryRequired("Provider-dispatched promoted upload lost durable wall safety evidence")
        recovery = _Issue323RecoveryWriter(
            upload_writer,
            wall_safety=raw_wall_safety,
            journal=journal,
            source_id=asset.source_id,
        )
        record["issue323_recovery_wall_view"] = {
            "baseline_actual_snapshot_sha256": current_wall.snapshot_sha256,
            "historical_before_snapshot_sha256": wall_before.snapshot_sha256,
            "reservation_replay_authorized": False,
            "binary_retransmission_authorized": False,
        }
        persist()
        return wall_before, recovery

    current_wall = writer.capture_wall_snapshot(community_id=MILOVI_COMMUNITY_ID, max_posts_per_surface=10000)
    if not current_wall.complete:
        raise MiloviFinalizerBlocked("Complete wall baseline unavailable before upload/resume")
    had_provider_effect = _has_provider_effect(record)
    operation_writer: Any = upload_writer
    recovery_writer: _Issue323RecoveryWriter | None = None
    if had_provider_effect:
        wall_before, recovery_writer = prepare_recovery(current_wall)
        operation_writer = recovery_writer
    else:
        wall_before = current_wall
    journal["provider_write_attempted"] = True
    item["status"] = "upload_in_progress"
    _save(journal_path, journal)

    try:
        execute_upload_operation(
            record,
            writer=operation_writer,
            community_id=MILOVI_COMMUNITY_ID,
            title=asset.title,
            description=asset.description,
            media_path=None if had_provider_effect else Path(asset.media_path),
            media_artifact=None if had_provider_effect else artifact,
            readiness=readiness,
            processing_timeout=timeout,
            wall_before_snapshot=wall_before,
            persist=persist,
        )
    except UploadRecoveryRequired:
        if had_provider_effect or not _needs_issue323_upload_wall_reconcile(record):
            raise
        current_after = writer.capture_wall_snapshot(
            community_id=MILOVI_COMMUNITY_ID,
            max_posts_per_surface=10000,
        )
        wall_before, recovery_writer = prepare_recovery(current_after)
        operation_writer = recovery_writer
        had_provider_effect = True
        execute_upload_operation(
            record,
            writer=operation_writer,
            community_id=MILOVI_COMMUNITY_ID,
            title=asset.title,
            description=asset.description,
            media_path=None,
            media_artifact=None,
            readiness=readiness,
            processing_timeout=timeout,
            wall_before_snapshot=wall_before,
            persist=persist,
        )

    if recovery_writer is not None:
        evidence = record.get("issue323_recovery_wall_view")
        if isinstance(evidence, dict):
            evidence.update(
                postflight_actual_snapshot_sha256=recovery_writer.last_actual_snapshot_sha256,
                postflight_effective_snapshot_sha256=recovery_writer.last_effective_snapshot_sha256,
                postflight_historical_snapshot_sha256=recovery_writer.last_historical_snapshot_sha256,
                postflight_reversed_surface_ids=list(recovery_writer.last_reversed_surface_ids),
                postflight_exact_read_ids=list(recovery_writer.last_exact_read_ids),
            )
            persist()
    if UploadStage(str(record.get("stage"))) is not UploadStage.VERIFIED:
        raise MiloviFinalizerBlocked(f"Upload lifecycle did not verify {asset.source_id}")
    remote_id = _upload_remote_id(record)
    _assert_native_clip(writer, asset, remote_id, description_mode="promoted")
    item.update(
        status="clip_verified",
        clip_remote_id=remote_id,
        clip_origin="resumed_token_short_video_internal_promotion"
        if had_provider_effect
        else "new_token_short_video_internal_promotion",
    )
    _save(journal_path, journal)
    return remote_id


def _find_rollout_wall_raw(writer: VkWallWriter, post_id: int) -> tuple[VkWallSurface, dict[str, Any]] | None:
    matches: list[tuple[VkWallSurface, dict[str, Any]]] = []
    for surface in (VkWallSurface.PUBLISHED, VkWallSurface.POSTPONED):
        items, _pages, complete = writer._read_wall_surface(
            community_id=MILOVI_COMMUNITY_ID,
            surface=surface,
            max_posts=10000,
        )
        if not complete:
            raise MiloviFinalizerBlocked(f"{surface.value} wall scan is incomplete")
        matches.extend(
            (surface, item) for item in items if item.get("id") == post_id and item.get("owner_id") == MILOVI_OWNER_ID
        )
    if len(matches) > 1:
        raise MiloviFinalizerBlocked(f"Wall post {post_id} appears on multiple surfaces")
    return matches[0] if matches else None


def _assert_post_shape(post: Mapping[str, Any], *, clip_remote_id: str, publish_date: int) -> None:
    owner_id, video_id = _parse_remote_id(clip_remote_id)
    if post.get("owner_id") != MILOVI_OWNER_ID or post.get("date") != publish_date:
        raise MiloviFinalizerBlocked("Wall identity/date changed")
    attachment_owner, attachment_video, _expanded = _one_video_attachment(post)
    if (attachment_owner, attachment_video) != (owner_id, video_id):
        raise MiloviFinalizerBlocked("Wall attachment changed")


def _journaled_wall_ids(journal: Mapping[str, Any]) -> set[str]:
    items = journal.get("items")
    if not isinstance(items, Mapping):
        raise MiloviFinalizerBlocked("Issue #323 journal has no item map for finalizer wall resolution")
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
            raise MiloviFinalizerBlocked(f"Journaled wall ID left Milovi: {source_id}")
        if remote_id in result:
            raise MiloviFinalizerBlocked(f"Journaled wall ID is reused by multiple sources: {remote_id}")
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
        raise MiloviFinalizerBlocked(f"Resolved wall incarnation is not live: {remote_id}")
    if raw.get("owner_id") != owner_id or raw.get("id") != post_id:
        raise MiloviFinalizerBlocked(f"Resolved wall incarnation changed identity: {remote_id}")
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
    """Resolve the one live provider incarnation of an Issue #323 logical wall mapping."""

    if not snapshot.complete:
        raise MiloviFinalizerBlocked("Complete wall snapshot is required for finalizer wall resolution")
    owner_id, post_id = _parse_remote_id(wall_remote_id)
    if owner_id != MILOVI_OWNER_ID or post_id <= 0:
        raise MiloviFinalizerBlocked("Wall remote ID is outside Milovi")
    expected_attachment = f"video{clip_remote_id}"
    logical_candidates = [
        post
        for post in snapshot.posts
        if post.owner_id == owner_id and post.publish_date == publish_date and expected_attachment in post.attachments
    ]
    old_matches = [post for post in snapshot.posts if post.remote_id == wall_remote_id]
    if len(old_matches) > 1:
        raise MiloviFinalizerBlocked(f"Journaled wall ID appears on multiple surfaces: {wall_remote_id}")
    observed_now = int(time.time()) if now_epoch is None else now_epoch

    if old_matches:
        current = old_matches[0]
        if len(logical_candidates) != 1 or logical_candidates[0].remote_id != wall_remote_id:
            raise MiloviFinalizerBlocked(f"Logical wall mapping is duplicated for {wall_remote_id}")
        if current.publish_date != publish_date or expected_attachment not in current.attachments:
            raise MiloviFinalizerBlocked(f"Journaled wall mapping changed binding: {wall_remote_id}")
        if current.surface is VkWallSurface.PUBLISHED and observed_now + 60 < publish_date:
            raise MiloviFinalizerBlocked(f"Wall post published before its scheduled slot: {wall_remote_id}")
        raw = _read_exact_wall_incarnation(
            writer,
            remote_id=wall_remote_id,
            clip_remote_id=clip_remote_id,
            publish_date=publish_date,
        )
        return wall_remote_id, current.surface, raw, "journaled_id"

    if observed_now + 60 < publish_date:
        raise MiloviFinalizerBlocked(f"Wall mapping disappeared before its frozen slot: {wall_remote_id}")

    exact_old = writer.read_post(community_id=MILOVI_COMMUNITY_ID, post_id=post_id)
    if exact_old is not None and exact_old.get("is_deleted") is not True:
        if exact_old.get("owner_id") != owner_id or exact_old.get("id") != post_id:
            raise MiloviFinalizerBlocked(f"Journaled wall exact read changed identity: {wall_remote_id}")
        _assert_post_shape(exact_old, clip_remote_id=clip_remote_id, publish_date=publish_date)
        if logical_candidates:
            candidate_ids = sorted(post.remote_id for post in logical_candidates)
            raise MiloviFinalizerBlocked(
                f"Journaled wall exact read is live but aggregate snapshot also has logical candidates: {candidate_ids}"
            )
        return wall_remote_id, VkWallSurface.PUBLISHED, dict(exact_old), "exact_old_id"

    if exact_old is not None:
        if exact_old.get("is_deleted") is not True:
            raise MiloviFinalizerBlocked(f"Journaled wall exact read has ambiguous state: {wall_remote_id}")
        if exact_old.get("owner_id") != owner_id or exact_old.get("id") != post_id:
            raise MiloviFinalizerBlocked(f"Journaled wall tombstone changed identity: {wall_remote_id}")
        tombstone_date = exact_old.get("date")
        if type(tombstone_date) is int and tombstone_date != publish_date:
            raise MiloviFinalizerBlocked(
                f"Journaled wall tombstone date changed: {wall_remote_id}: {tombstone_date} != {publish_date}"
            )

    successors = [
        post
        for post in logical_candidates
        if post.surface is VkWallSurface.PUBLISHED and post.remote_id != wall_remote_id
    ]
    if not successors:
        raise MiloviFinalizerBlocked(f"No published successor exists for due wall mapping: {wall_remote_id}")
    if len(successors) != 1:
        successor_ids = sorted(post.remote_id for post in successors)
        raise MiloviFinalizerBlocked(f"Published successor is ambiguous for {wall_remote_id}: {successor_ids}")
    successor = successors[0]
    if successor.remote_id in _journaled_wall_ids(journal):
        raise MiloviFinalizerBlocked(
            f"Published successor collides with another journaled wall ID: {wall_remote_id} -> {successor.remote_id}"
        )
    if successor.remote_id == ANOMALY_WALL_REMOTE_ID:
        raise MiloviFinalizerBlocked("Published successor unexpectedly reused anomaly wall 475")
    raw = _read_exact_wall_incarnation(
        writer,
        remote_id=successor.remote_id,
        clip_remote_id=clip_remote_id,
        publish_date=publish_date,
    )
    return successor.remote_id, VkWallSurface.PUBLISHED, raw, "published_successor"


def _edit_clip_description(
    *,
    writer: VkWallWriter,
    client: VkApiClient,
    asset: SourceAsset,
    remote_id: str,
    operation: dict[str, Any],
    finalizer: dict[str, Any],
    finalizer_path: Path,
) -> None:
    raw = _assert_native_clip(
        writer,
        asset,
        remote_id,
        description_mode="legacy_or_promoted",
        durable_verified=True,
    )
    if str(raw.get("description") or "").strip() == asset.description.strip():
        operation.update(status="verified", remote_id=remote_id)
        _save_finalizer(finalizer_path, finalizer)
        return
    if not _legacy_marker_ok(raw, asset.source_id):
        raise MiloviFinalizerBlocked(f"Refusing description edit: {remote_id} lost legacy source binding")
    owner_id, video_id = _parse_remote_id(remote_id)
    before_title = str(raw.get("title") or "")
    operation.update(status="edit_intent", remote_id=remote_id)
    _save_finalizer(finalizer_path, finalizer)
    _prove_target(client)
    try:
        writer._call("video.edit", params={"owner_id": owner_id, "video_id": video_id, "desc": asset.description})
    except Exception:
        observed = writer.read_video(owner_id=owner_id, video_id=video_id)
        if (
            not isinstance(observed, Mapping)
            or str(observed.get("description") or "").strip() != asset.description.strip()
        ):
            raise
    after = _assert_native_clip(
        writer,
        asset,
        remote_id,
        description_mode="promoted",
        durable_verified=True,
    )
    after_title = str(after.get("title") or "")
    if before_title and after_title and after_title != before_title:
        raise MiloviFinalizerBlocked(f"video.edit unexpectedly changed title for {remote_id}")
    operation.update(status="verified", remote_id=remote_id)
    _save_finalizer(finalizer_path, finalizer)


def _edit_wall_message(
    *,
    writer: VkWallWriter,
    client: VkApiClient,
    asset: SourceAsset,
    journal: Mapping[str, Any],
    wall_remote_id: str,
    clip_remote_id: str,
    publish_date: int,
    operation: dict[str, Any],
    finalizer: dict[str, Any],
    finalizer_path: Path,
) -> None:
    before_snapshot = writer.capture_wall_snapshot(community_id=MILOVI_COMMUNITY_ID, max_posts_per_surface=10000)
    actual_remote_id, surface, post, resolution_mode = _resolve_wall_incarnation(
        writer=writer,
        snapshot=before_snapshot,
        journal=journal,
        wall_remote_id=wall_remote_id,
        clip_remote_id=clip_remote_id,
        publish_date=publish_date,
    )
    if str(post.get("text") or "").strip() == asset.wall_message.strip():
        operation.update(
            status="verified",
            journal_remote_id=wall_remote_id,
            remote_id=actual_remote_id,
            surface=surface.value,
            resolution_mode=resolution_mode,
        )
        _save_finalizer(finalizer_path, finalizer)
        return
    _actual_owner, actual_post_id = _parse_remote_id(actual_remote_id)
    operation.update(
        status="edit_intent",
        journal_remote_id=wall_remote_id,
        remote_id=actual_remote_id,
        surface=surface.value,
        resolution_mode=resolution_mode,
    )
    _save_finalizer(finalizer_path, finalizer)
    _prove_target(client)
    params: dict[str, str | int | bool] = {
        "owner_id": MILOVI_OWNER_ID,
        "post_id": actual_post_id,
        "message": asset.wall_message,
        "attachments": f"video{clip_remote_id}",
    }
    if surface is VkWallSurface.POSTPONED:
        params["publish_date"] = publish_date
    try:
        writer._call("wall.edit", params=params)
    except Exception:
        observed_snapshot = writer.capture_wall_snapshot(
            community_id=MILOVI_COMMUNITY_ID,
            max_posts_per_surface=10000,
        )
        _observed_id, _observed_surface, observed, _observed_mode = _resolve_wall_incarnation(
            writer=writer,
            snapshot=observed_snapshot,
            journal=journal,
            wall_remote_id=wall_remote_id,
            clip_remote_id=clip_remote_id,
            publish_date=publish_date,
        )
        if str(observed.get("text") or "").strip() != asset.wall_message.strip():
            raise
    after_snapshot = writer.capture_wall_snapshot(community_id=MILOVI_COMMUNITY_ID, max_posts_per_surface=10000)
    after_remote_id, after_surface, after, after_mode = _resolve_wall_incarnation(
        writer=writer,
        snapshot=after_snapshot,
        journal=journal,
        wall_remote_id=wall_remote_id,
        clip_remote_id=clip_remote_id,
        publish_date=publish_date,
    )
    if str(after.get("text") or "").strip() != asset.wall_message.strip():
        raise MiloviFinalizerBlocked(f"Wall message failed verification: {wall_remote_id}")
    operation.update(
        status="verified",
        journal_remote_id=wall_remote_id,
        remote_id=after_remote_id,
        surface=after_surface.value,
        resolution_mode=after_mode,
    )
    _save_finalizer(finalizer_path, finalizer)


def _final_postflight(
    writer: VkWallWriter,
    assets: list[SourceAsset],
    journal: dict[str, Any],
    *,
    now_epoch: int | None = None,
) -> list[dict[str, Any]]:
    _assert_wall475_absent(writer)
    snapshot = writer.capture_wall_snapshot(community_id=MILOVI_COMMUNITY_ID, max_posts_per_surface=10000)
    if not snapshot.complete:
        raise MiloviFinalizerBlocked("Final wall snapshot is incomplete")
    observed_now = int(time.time()) if now_epoch is None else now_epoch
    evidence: list[dict[str, Any]] = []
    current_wall_ids: set[str] = set()
    for asset in assets:
        item = _item(journal, asset.source_id)
        clip_remote_id = str(item.get("clip_remote_id") or "")
        wall_remote_id = str(item.get("wall_remote_id") or "")
        publish_date = item.get("publish_date")
        if (
            item.get("status") != "wall_verified"
            or not clip_remote_id
            or not wall_remote_id
            or type(publish_date) is not int
        ):
            raise MiloviFinalizerBlocked(f"Final durable mapping is incomplete: {asset.source_id}")
        _assert_native_clip(
            writer,
            asset,
            clip_remote_id,
            description_mode="promoted",
            durable_verified=True,
        )
        actual_remote_id, raw_surface, raw_post, resolution_mode = _resolve_wall_incarnation(
            writer=writer,
            snapshot=snapshot,
            journal=journal,
            wall_remote_id=wall_remote_id,
            clip_remote_id=clip_remote_id,
            publish_date=publish_date,
            now_epoch=observed_now,
        )
        if actual_remote_id in current_wall_ids:
            raise MiloviFinalizerBlocked(f"Final wall incarnation is reused by multiple sources: {actual_remote_id}")
        current_wall_ids.add(actual_remote_id)
        if str(raw_post.get("text") or "").strip() != asset.wall_message.strip():
            raise MiloviFinalizerBlocked(f"Final wall public copy differs for {asset.source_id}")
        evidence.append(
            {
                "source_id": asset.source_id,
                "clip_remote_id": clip_remote_id,
                "wall_remote_id": wall_remote_id,
                "current_wall_remote_id": actual_remote_id,
                "wall_resolution_mode": resolution_mode,
                "publish_date": publish_date,
                "wall_surface": raw_surface.value,
                "clip_description_sha256": _sha256_text(asset.description),
                "wall_message_sha256": _sha256_text(asset.wall_message),
            }
        )
    return evidence


def _complete_child(
    source_id: str,
    *,
    legacy_assets: dict[str, SourceAsset],
    promoted_assets: dict[str, SourceAsset],
    artifacts: dict[str, Any],
    journal: dict[str, Any],
    journal_path: Path,
    slots: Mapping[str, Any],
    writer: VkWallWriter,
    upload_writer: _LiveClipWriter,
    client: VkApiClient,
    verify_timeout_seconds: int,
) -> None:
    item = _item(journal, source_id)
    if item.get("status") == "wall_verified":
        return
    asset = promoted_assets[source_id]
    if source_id == ANOMALY_SOURCE_ID and item.get("status") != "clip_verified":
        clip_id = _ensure_clip_live(
            legacy_assets[source_id],
            artifacts[source_id],
            item,
            journal,
            journal_path,
            writer,
            upload_writer,
            client,
            verify_timeout_seconds,
        )
        if clip_id != ANOMALY_CLIP_REMOTE_ID:
            raise MiloviFinalizerBlocked("Eighth reconciliation returned another Clip")
    elif item.get("status") == "clip_verified":
        clip_id = str(item.get("clip_remote_id") or "")
        if not clip_id:
            raise MiloviFinalizerBlocked(f"clip_verified item lost remote ID: {source_id}")
        mode = "legacy_or_promoted" if source_id == ANOMALY_SOURCE_ID else "promoted"
        _assert_native_clip(
            writer,
            asset,
            clip_id,
            description_mode=mode,
            durable_verified=True,
        )
    else:
        clip_id = _ensure_promoted_clip(
            asset,
            artifacts[source_id],
            item,
            journal,
            journal_path,
            writer,
            upload_writer,
            verify_timeout_seconds,
        )
    if source_id == ANOMALY_SOURCE_ID and clip_id != ANOMALY_CLIP_REMOTE_ID:
        raise MiloviFinalizerBlocked("Eighth Clip identity changed")
    _ensure_wall(asset, clip_id, slots[source_id], item, journal, journal_path, writer, client)


def run_issue_323_finalizer(
    *,
    confirmation: str,
    output_path: Path,
    rollout_output_path: Path,
    journal_path: Path,
    finalizer_journal_path: Path,
    schedule_path: Path,
    work_dir: Path,
    verify_timeout_seconds: int = 7200,
) -> dict[str, Any]:
    if confirmation != EXECUTION_CONFIRMATION:
        raise MiloviFinalizerBlocked(f"Exact confirmation required: {EXECUTION_CONFIRMATION}")
    if verify_timeout_seconds < 60:
        raise MiloviFinalizerBlocked("verify_timeout_seconds must be >=60")

    journal = _load_journal(journal_path)
    if journal.get("canary_verified") is not True:
        raise MiloviFinalizerBlocked("Issue #323 canary is not durably verified")
    legacy_list = prepare_sources(work_dir)
    promoted_list = [_promote_asset(asset) for asset in legacy_list]
    legacy_assets = {asset.source_id: asset for asset in legacy_list}
    promoted_assets = {asset.source_id: asset for asset in promoted_list}
    artifacts = _media_artifacts(legacy_list)
    finalizer = _load_finalizer_journal(finalizer_journal_path, promoted_list)

    settings = get_settings()
    store = VkTokenStore(settings.data_dir)
    alias, client = _resolve_account(store, settings.vk_api_version)
    writer = VkWallWriter(token_store=store, account_alias=alias, api_version=settings.vk_api_version)
    upload_writer = _LiveClipWriter(writer, client)
    lock_path = settings.data_dir / "locks" / f"vk-{MILOVI_COMMUNITY_ID}-issue-323-finalizer.lock"

    try:
        with local_vk_write_lock(
            lock_path,
            account=alias,
            community_id=MILOVI_COMMUNITY_ID,
            operation="milovi-issue-323-finalize-internal-promotion",
        ):
            _prove_target(client)
            slots = load_or_create_daily_schedule(schedule_path, writer=writer)
            if tuple(slots) != ROLL_OUT_IDS:
                raise MiloviFinalizerBlocked("Issue #323 schedule differs from exact source order")

            anomaly_item = _item(journal, ANOMALY_SOURCE_ID)
            anomaly_record = anomaly_item.get("upload_record")
            reservation = anomaly_record.get("reservation") if isinstance(anomaly_record, Mapping) else None
            if not isinstance(reservation, Mapping) or reservation.get("remote_id") != ANOMALY_CLIP_REMOTE_ID:
                raise MiloviFinalizerBlocked("Eighth durable reservation is not exact Clip 456239232")

            _cleanup_anomaly_475(
                writer=writer,
                promoted_asset=promoted_assets[ANOMALY_SOURCE_ID],
                finalizer=finalizer,
                finalizer_path=finalizer_journal_path,
            )

            for source_id in ROLL_OUT_IDS[ROLL_OUT_IDS.index(ANOMALY_SOURCE_ID) :]:
                _complete_child(
                    source_id,
                    legacy_assets=legacy_assets,
                    promoted_assets=promoted_assets,
                    artifacts=artifacts,
                    journal=journal,
                    journal_path=journal_path,
                    slots=slots,
                    writer=writer,
                    upload_writer=upload_writer,
                    client=client,
                    verify_timeout_seconds=verify_timeout_seconds,
                )
                write_json_atomic(rollout_output_path, _result(journal, "in_progress"))

            incomplete = [
                source_id for source_id in ROLL_OUT_IDS if _item(journal, source_id).get("status") != "wall_verified"
            ]
            if incomplete:
                raise MiloviFinalizerBlocked(f"Rollout child completion is incomplete: {incomplete}")

            for asset in promoted_list:
                item = _item(journal, asset.source_id)
                clip_remote_id = str(item.get("clip_remote_id") or "")
                wall_remote_id = str(item.get("wall_remote_id") or "")
                publish_date = item.get("publish_date")
                if not clip_remote_id or not wall_remote_id or type(publish_date) is not int:
                    raise MiloviFinalizerBlocked(f"Cannot promote incomplete durable mapping: {asset.source_id}")
                _edit_clip_description(
                    writer=writer,
                    client=client,
                    asset=asset,
                    remote_id=clip_remote_id,
                    operation=finalizer["clip_description_edits"][asset.source_id],
                    finalizer=finalizer,
                    finalizer_path=finalizer_journal_path,
                )
                _edit_wall_message(
                    writer=writer,
                    client=client,
                    asset=asset,
                    journal=journal,
                    wall_remote_id=wall_remote_id,
                    clip_remote_id=clip_remote_id,
                    publish_date=publish_date,
                    operation=finalizer["wall_message_edits"][asset.source_id],
                    finalizer=finalizer,
                    finalizer_path=finalizer_journal_path,
                )

            evidence = _final_postflight(writer, promoted_list, journal)
            rollout_payload = _result(journal, "batch_verified")
            rollout_payload["public_promotion"] = {
                "youtube_public_links": False,
                "canonical_urls": list(PUBLIC_PROMOTION_URLS),
            }
            write_json_atomic(rollout_output_path, rollout_payload)
            payload = {
                "schema_name": FINALIZER_SCHEMA,
                "schema_version": 1,
                "status": "final_verified",
                "project_key": "milovi-cake",
                "community_id": MILOVI_COMMUNITY_ID,
                "owner_id": MILOVI_OWNER_ID,
                "browser_used": False,
                "anomaly_cleanup": {"wall_remote_id": ANOMALY_WALL_REMOTE_ID, "status": "verified_absent"},
                "youtube_public_links": False,
                "canonical_promotion_urls": list(PUBLIC_PROMOTION_URLS),
                "items": evidence,
            }
            write_json_atomic(output_path, payload)
            return payload
    except Exception as exc:
        write_json_atomic(
            output_path,
            {
                "schema_name": FINALIZER_SCHEMA,
                "schema_version": 1,
                "status": "blocked",
                "project_key": "milovi-cake",
                "community_id": MILOVI_COMMUNITY_ID,
                "owner_id": MILOVI_OWNER_ID,
                "browser_used": False,
                "error": {"type": type(exc).__name__, "message": str(exc)},
            },
        )
        raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Finish Milovi Issue #323 with internal promotion and exact wall-475 cleanup"
    )
    parser.add_argument("--execute", required=True)
    parser.add_argument("--output", type=Path, default=Path("operator-output/milovi-cake-issue-323-finalizer.json"))
    parser.add_argument(
        "--rollout-output",
        type=Path,
        default=Path("operator-output/milovi-cake-issue-323-token-daily-rollout.json"),
    )
    parser.add_argument(
        "--journal",
        type=Path,
        default=Path("data/vk/milovi-cake/issue-323-token-daily-rollout-journal.json"),
    )
    parser.add_argument(
        "--finalizer-journal",
        type=Path,
        default=Path("data/vk/milovi-cake/issue-323-finalizer-journal.json"),
    )
    parser.add_argument(
        "--schedule",
        type=Path,
        default=Path("data/vk/milovi-cake/issue-323-daily-wall-schedule.json"),
    )
    parser.add_argument("--work-dir", type=Path, default=Path("operator-output/milovi-cake-issue-323-work"))
    parser.add_argument("--verify-timeout", type=int, default=7200)
    args = parser.parse_args()
    result = run_issue_323_finalizer(
        confirmation=args.execute,
        output_path=args.output,
        rollout_output_path=args.rollout_output,
        journal_path=args.journal,
        finalizer_journal_path=args.finalizer_journal,
        schedule_path=args.schedule,
        work_dir=args.work_dir,
        verify_timeout_seconds=args.verify_timeout,
    )
    print(f"Milovi #323 finalizer: {result['status']} | browser={result['browser_used']} | result={args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (MiloviFinalizerBlocked, UploadRecoveryRequired, UploadRejected, OSError, ValueError) as exc:
        print(f"STOP: {type(exc).__name__}: {exc}")
        raise SystemExit(3) from exc


__all__ = [
    "ANOMALY_CLIP_REMOTE_ID",
    "ANOMALY_POST_ID",
    "ANOMALY_SOURCE_ID",
    "EXECUTION_CONFIRMATION",
    "FINALIZER_SCHEMA",
    "_promote_asset",
    "run_issue_323_finalizer",
]
