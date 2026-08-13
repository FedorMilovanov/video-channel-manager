from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk import VkApiClient, VkTokenStore, local_vk_write_lock
from video_channel_manager.platforms.vk.milovi_immediate_wall import MILOVI_COMMUNITY_ID, MILOVI_OWNER_ID
from video_channel_manager.platforms.vk.milovi_issue323_live_resume import (
    _LiveClipWriter,
    _native_clip_assessment,
    _resume_wall_baseline,
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
    CANARY_SOURCE_ID,
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
from video_channel_manager.platforms.vk.wall_safety import DEFAULT_UPLOAD_WALL_POLICY, VkWallSurface
from video_channel_manager.platforms.vk.milovi_daily_postponed_wall import load_or_create_daily_schedule

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
    expected_plan = _promotion_plan(assets)
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
        "promotion_plan": expected_plan,
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
) -> dict[str, Any]:
    owner_id, video_id = _parse_remote_id(remote_id)
    raw = writer.read_video(owner_id=owner_id, video_id=video_id)
    if raw is None:
        raise MiloviFinalizerBlocked(f"VK Clip disappeared: {remote_id}")
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
    if description_mode == "legacy_or_promoted":
        if not _legacy_marker_ok(raw, asset.source_id) and description != asset.description.strip():
            raise MiloviFinalizerBlocked(f"VK Clip {remote_id} cannot be bound to source {asset.source_id}")
    elif description_mode == "promoted":
        if description != asset.description.strip():
            raise MiloviFinalizerBlocked(f"VK Clip {remote_id} public description differs from promotion plan")
    else:
        raise ValueError(f"Unknown description_mode: {description_mode}")
    return raw


def _one_video_attachment(post: Mapping[str, Any]) -> tuple[int, int, Mapping[str, Any]]:
    attachments = post.get("attachments")
    if not isinstance(attachments, list) or len(attachments) != 1:
        raise MiloviFinalizerBlocked("Anomaly wall post must contain exactly one attachment")
    attachment = attachments[0]
    if not isinstance(attachment, Mapping) or attachment.get("type") != "video":
        raise MiloviFinalizerBlocked("Anomaly wall post attachment is not exactly one video")
    video = attachment.get("video")
    if not isinstance(video, Mapping):
        raise MiloviFinalizerBlocked("Anomaly wall post has no expanded video attachment")
    owner_id = video.get("owner_id")
    video_id = video.get("id")
    if type(owner_id) is not int or type(video_id) is not int:
        raise MiloviFinalizerBlocked("Anomaly wall attachment identity is invalid")
    return owner_id, video_id, video


def _validate_anomaly_post(post: Mapping[str, Any], legacy_asset: SourceAsset) -> None:
    if post.get("owner_id") != MILOVI_OWNER_ID or post.get("id") != ANOMALY_POST_ID:
        raise MiloviFinalizerBlocked("Wall 475 identity differs from exact Issue #323 anomaly")
    if str(post.get("text") or "").strip():
        raise MiloviFinalizerBlocked("Wall 475 is no longer the empty-text anomaly authorized for deletion")
    owner_id, video_id, expanded = _one_video_attachment(post)
    expected_owner, expected_video = _parse_remote_id(ANOMALY_CLIP_REMOTE_ID)
    if owner_id != expected_owner or video_id != expected_video:
        raise MiloviFinalizerBlocked("Wall 475 no longer attaches exact Clip 456239232")
    observed_type = str(expanded.get("type") or "")
    if observed_type and observed_type != "short_video":
        raise MiloviFinalizerBlocked("Wall 475 attachment is no longer a native short_video")
    if not _legacy_marker_ok(expanded, legacy_asset.source_id):
        raise MiloviFinalizerBlocked("Wall 475 attachment lost exact legacy source marker")


def _cleanup_anomaly_475(
    *,
    writer: VkWallWriter,
    client: VkApiClient,
    legacy_asset: SourceAsset,
    promoted_asset: SourceAsset,
    finalizer: dict[str, Any],
    finalizer_path: Path,
) -> None:
    state = finalizer["cleanup_475"]
    post = writer.read_post(community_id=MILOVI_COMMUNITY_ID, post_id=ANOMALY_POST_ID)
    if post is None:
        _assert_native_clip(writer, promoted_asset, ANOMALY_CLIP_REMOTE_ID, description_mode="legacy_or_promoted")
        state.update(status="verified_absent")
        _save_finalizer(finalizer_path, finalizer)
        return

    _validate_anomaly_post(post, legacy_asset)
    _assert_native_clip(writer, promoted_asset, ANOMALY_CLIP_REMOTE_ID, description_mode="legacy_or_promoted")
    state.update(status="delete_intent", predelete_post_sha256=_sha256_text(json.dumps(post, sort_keys=True, ensure_ascii=False)))
    _save_finalizer(finalizer_path, finalizer)
    _prove_target(client)
    try:
        writer._call(
            "wall.delete",
            params={"owner_id": MILOVI_OWNER_ID, "post_id": ANOMALY_POST_ID},
        )
    except Exception:
        if writer.read_post(community_id=MILOVI_COMMUNITY_ID, post_id=ANOMALY_POST_ID) is not None:
            raise
    if writer.read_post(community_id=MILOVI_COMMUNITY_ID, post_id=ANOMALY_POST_ID) is not None:
        raise MiloviFinalizerBlocked("Exact anomaly wall 475 still exists after delete response")
    _assert_native_clip(writer, promoted_asset, ANOMALY_CLIP_REMOTE_ID, description_mode="legacy_or_promoted")
    state.update(status="verified_absent")
    _save_finalizer(finalizer_path, finalizer)


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
        _assert_native_clip(writer, asset, current, description_mode="promoted")
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

    current_wall = writer.capture_wall_snapshot(community_id=MILOVI_COMMUNITY_ID, max_posts_per_surface=10000)
    if not current_wall.complete:
        raise MiloviFinalizerBlocked("Complete wall baseline unavailable before upload/resume")
    wall_before = _resume_wall_baseline(record, current_wall) if _has_provider_effect(record) else current_wall

    journal["provider_write_attempted"] = True
    item["status"] = "upload_in_progress"
    _save(journal_path, journal)
    execute_upload_operation(
        record,
        writer=upload_writer,
        community_id=MILOVI_COMMUNITY_ID,
        title=asset.title,
        description=asset.description,
        media_path=Path(asset.media_path),
        media_artifact=artifact,
        readiness=readiness,
        processing_timeout=timeout,
        wall_before_snapshot=wall_before,
        persist=persist,
    )
    if UploadStage(str(record.get("stage"))) is not UploadStage.VERIFIED:
        raise MiloviFinalizerBlocked(f"Upload lifecycle did not verify {asset.source_id}")
    remote_id = _upload_remote_id(record)
    _assert_native_clip(writer, asset, remote_id, description_mode="promoted")
    item.update(status="clip_verified", clip_remote_id=remote_id, clip_origin="new_token_short_video_internal_promotion")
    _save(journal_path, journal)
    return remote_id


def _find_postponed_raw(writer: VkWallWriter, post_id: int) -> dict[str, Any] | None:
    items, _pages, complete = writer._read_wall_surface(
        community_id=MILOVI_COMMUNITY_ID,
        surface=VkWallSurface.POSTPONED,
        max_posts=10000,
    )
    if not complete:
        raise MiloviFinalizerBlocked("Postponed wall scan is incomplete")
    matches = [item for item in items if item.get("id") == post_id and item.get("owner_id") == MILOVI_OWNER_ID]
    if len(matches) > 1:
        raise MiloviFinalizerBlocked(f"Postponed wall post {post_id} is duplicated in readback")
    return matches[0] if matches else None


def _assert_post_shape(post: Mapping[str, Any], *, clip_remote_id: str, publish_date: int) -> None:
    owner_id, video_id = _parse_remote_id(clip_remote_id)
    if post.get("owner_id") != MILOVI_OWNER_ID:
        raise MiloviFinalizerBlocked("Post owner differs from Milovi")
    if post.get("date") != publish_date:
        raise MiloviFinalizerBlocked("Postponed publish_date changed")
    attachment_owner, attachment_video, _expanded = _one_video_attachment(post)
    if attachment_owner != owner_id or attachment_video != video_id:
        raise MiloviFinalizerBlocked("Postponed wall attachment changed")


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
    raw = _assert_native_clip(writer, asset, remote_id, description_mode="legacy_or_promoted")
    if str(raw.get("description") or "").strip() == asset.description.strip():
        operation.update(status="verified")
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
        writer._call(
            "video.edit",
            params={"owner_id": owner_id, "video_id": video_id, "desc": asset.description},
        )
    except Exception:
        observed = writer.read_video(owner_id=owner_id, video_id=video_id)
        if not isinstance(observed, Mapping) or str(observed.get("description") or "").strip() != asset.description.strip():
            raise
    after = _assert_native_clip(writer, asset, remote_id, description_mode="promoted")
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
    wall_remote_id: str,
    clip_remote_id: str,
    publish_date: int,
    operation: dict[str, Any],
    finalizer: dict[str, Any],
    finalizer_path: Path,
) -> None:
    owner_id, post_id = _parse_remote_id(wall_remote_id)
    if owner_id != MILOVI_OWNER_ID:
        raise MiloviFinalizerBlocked("Wall remote ID is outside Milovi")
    post = _find_postponed_raw(writer, post_id)
    if post is None:
        raise MiloviFinalizerBlocked(f"Postponed wall post disappeared: {wall_remote_id}")
    _assert_post_shape(post, clip_remote_id=clip_remote_id, publish_date=publish_date)
    if str(post.get("text") or "").strip() == asset.wall_message.strip():
        operation.update(status="verified", remote_id=wall_remote_id)
        _save_finalizer(finalizer_path, finalizer)
        return
    operation.update(status="edit_intent", remote_id=wall_remote_id)
    _save_finalizer(finalizer_path, finalizer)
    _prove_target(client)
    try:
        writer._call(
            "wall.edit",
            params={
                "owner_id": MILOVI_OWNER_ID,
                "post_id": post_id,
                "message": asset.wall_message,
                "attachments": f"video{clip_remote_id}",
                "publish_date": publish_date,
            },
        )
    except Exception:
        observed = _find_postponed_raw(writer, post_id)
        if not isinstance(observed, Mapping) or str(observed.get("text") or "").strip() != asset.wall_message.strip():
            raise
    after = _find_postponed_raw(writer, post_id)
    if after is None:
        raise MiloviFinalizerBlocked(f"Postponed wall post disappeared after edit: {wall_remote_id}")
    _assert_post_shape(after, clip_remote_id=clip_remote_id, publish_date=publish_date)
    if str(after.get("text") or "").strip() != asset.wall_message.strip():
        raise MiloviFinalizerBlocked(f"Postponed wall message failed verification: {wall_remote_id}")
    operation.update(status="verified", remote_id=wall_remote_id)
    _save_finalizer(finalizer_path, finalizer)


def _final_postflight(
    *,
    writer: VkWallWriter,
    assets: list[SourceAsset],
    journal: dict[str, Any],
) -> list[dict[str, Any]]:
    if writer.read_post(community_id=MILOVI_COMMUNITY_ID, post_id=ANOMALY_POST_ID) is not None:
        raise MiloviFinalizerBlocked("Anomaly wall 475 reappeared")
    snapshot = writer.capture_wall_snapshot(community_id=MILOVI_COMMUNITY_ID, max_posts_per_surface=10000)
    if not snapshot.complete:
        raise MiloviFinalizerBlocked("Final wall snapshot is incomplete")
    evidence: list[dict[str, Any]] = []
    for asset in assets:
        item = _item(journal, asset.source_id)
        if item.get("status") != "wall_verified":
            raise MiloviFinalizerBlocked(f"Final item is not wall_verified: {asset.source_id}")
        clip_remote_id = str(item.get("clip_remote_id") or "")
        wall_remote_id = str(item.get("wall_remote_id") or "")
        publish_date = item.get("publish_date")
        if not clip_remote_id or not wall_remote_id or type(publish_date) is not int:
            raise MiloviFinalizerBlocked(f"Final durable mapping is incomplete: {asset.source_id}")
        _assert_native_clip(writer, asset, clip_remote_id, description_mode="promoted")
        owner_id, video_id = _parse_remote_id(clip_remote_id)
        attachment = f"video{owner_id}_{video_id}"
        matches = [post for post in snapshot.posts if attachment in post.attachments]
        published = [post for post in matches if post.surface is VkWallSurface.PUBLISHED]
        postponed = [post for post in matches if post.surface is VkWallSurface.POSTPONED]
        if published:
            raise MiloviFinalizerBlocked(f"Immediate rollout wall post remains for {asset.source_id}: {published}")
        if len(postponed) != 1 or postponed[0].remote_id != wall_remote_id or postponed[0].publish_date != publish_date:
            raise MiloviFinalizerBlocked(f"Postponed mapping differs for {asset.source_id}")
        _owner, post_id = _parse_remote_id(wall_remote_id)
        raw_post = _find_postponed_raw(writer, post_id)
        if raw_post is None or str(raw_post.get("text") or "").strip() != asset.wall_message.strip():
            raise MiloviFinalizerBlocked(f"Final wall public copy differs for {asset.source_id}")
        evidence.append(
            {
                "source_id": asset.source_id,
                "clip_remote_id": clip_remote_id,
                "wall_remote_id": wall_remote_id,
                "publish_date": publish_date,
                "clip_description_sha256": _sha256_text(asset.description),
                "wall_message_sha256": _sha256_text(asset.wall_message),
            }
        )
    return evidence


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
    legacy_assets = prepare_sources(work_dir)
    promoted_assets = [_promote_asset(asset) for asset in legacy_assets]
    legacy_by_id = {asset.source_id: asset for asset in legacy_assets}
    promoted_by_id = {asset.source_id: asset for asset in promoted_assets}
    artifacts = _media_artifacts(legacy_assets)
    finalizer = _load_finalizer_journal(finalizer_journal_path, promoted_assets)

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
                client=client,
                legacy_asset=legacy_by_id[ANOMALY_SOURCE_ID],
                promoted_asset=promoted_by_id[ANOMALY_SOURCE_ID],
                finalizer=finalizer,
                finalizer_path=finalizer_journal_path,
            )

            if anomaly_item.get("status") != "wall_verified":
                if anomaly_item.get("status") != "clip_verified":
                    from video_channel_manager.platforms.vk.milovi_issue323_live_resume import _ensure_clip_live

                    clip_id = _ensure_clip_live(
                        legacy_by_id[ANOMALY_SOURCE_ID],
                        artifacts[ANOMALY_SOURCE_ID],
                        anomaly_item,
                        journal,
                        journal_path,
                        writer,
                        upload_writer,
                        client,
                        verify_timeout_seconds,
                    )
                    if clip_id != ANOMALY_CLIP_REMOTE_ID:
                        raise MiloviFinalizerBlocked("Eighth reconciliation returned another Clip")
                else:
                    clip_id = str(anomaly_item.get("clip_remote_id") or "")
                    if clip_id != ANOMALY_CLIP_REMOTE_ID:
                        raise MiloviFinalizerBlocked("Eighth clip_verified state is bound to another Clip")
                _ensure_wall(
                    promoted_by_id[ANOMALY_SOURCE_ID],
                    clip_id,
                    slots[ANOMALY_SOURCE_ID],
                    anomaly_item,
                    journal,
                    journal_path,
                    writer,
                    client,
                )

            start = ROLL_OUT_IDS.index(ANOMALY_SOURCE_ID) + 1
            for source_id in ROLL_OUT_IDS[start:]:
                item = _item(journal, source_id)
                asset = promoted_by_id[source_id]
                if item.get("status") == "wall_verified":
                    continue
                if item.get("status") == "clip_verified":
                    clip_id = str(item.get("clip_remote_id") or "")
                    if not clip_id:
                        raise MiloviFinalizerBlocked(f"clip_verified item lost remote ID: {source_id}")
                    _assert_native_clip(writer, asset, clip_id, description_mode="promoted")
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
                _ensure_wall(
                    asset,
                    clip_id,
                    slots[source_id],
                    item,
                    journal,
                    journal_path,
                    writer,
                    client,
                )
                write_json_atomic(rollout_output_path, _result(journal, "in_progress"))

            incomplete = [source_id for source_id in ROLL_OUT_IDS if _item(journal, source_id).get("status") != "wall_verified"]
            if incomplete:
                raise MiloviFinalizerBlocked(f"Rollout child completion is incomplete: {incomplete}")

            for asset in promoted_assets:
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
                    wall_remote_id=wall_remote_id,
                    clip_remote_id=clip_remote_id,
                    publish_date=publish_date,
                    operation=finalizer["wall_message_edits"][asset.source_id],
                    finalizer=finalizer,
                    finalizer_path=finalizer_journal_path,
                )

            evidence = _final_postflight(writer=writer, assets=promoted_assets, journal=journal)
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
        blocked = {
            "schema_name": FINALIZER_SCHEMA,
            "schema_version": 1,
            "status": "blocked",
            "project_key": "milovi-cake",
            "community_id": MILOVI_COMMUNITY_ID,
            "owner_id": MILOVI_OWNER_ID,
            "browser_used": False,
            "error": {"type": type(exc).__name__, "message": str(exc)},
        }
        write_json_atomic(output_path, blocked)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Finish Milovi Issue #323 with internal promotion and exact wall-475 cleanup")
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
