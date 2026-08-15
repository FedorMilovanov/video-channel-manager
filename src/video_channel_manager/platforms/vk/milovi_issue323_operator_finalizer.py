from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from video_channel_manager.platforms.vk import milovi_issue323_finalize as base


def _operator_description_ok(value: str, *, source_id: str) -> str:
    description = value.strip()
    if not description:
        raise base.MiloviFinalizerBlocked(f"Operator Clip description is empty: {source_id}")
    folded = description.casefold()
    if "youtube.com" in folded or "youtu.be" in folded:
        raise base.MiloviFinalizerBlocked(
            f"Operator Clip description still contains a public YouTube link: {source_id}"
        )
    return description


def _clip_copy_state(
    *,
    raw: Mapping[str, Any],
    asset: base.SourceAsset,
) -> tuple[str, str]:
    description = str(raw.get("description") or "").strip()
    try:
        state = base._clip_copy_state(
            current=description,
            legacy=base._legacy_clip_description(asset),
            promoted=asset.description.strip(),
            source_id=asset.source_id,
            field="Clip description",
            provider_item=raw,
        )
    except base.MiloviFinalizerBlocked:
        if bool(raw.get("processing")) or bool(raw.get("converting")):
            raise
        _operator_description_ok(description, source_id=asset.source_id)
        state = "operator_preserved"
    return state, description


def _assert_durable_clip(
    writer: base.VkWallWriter,
    asset: base.SourceAsset,
    remote_id: str,
) -> tuple[dict[str, Any], str, str]:
    owner_id, video_id = base._parse_remote_id(remote_id)
    raw = writer.read_video(owner_id=owner_id, video_id=video_id)
    if raw is None:
        raise base.MiloviFinalizerBlocked(f"VK Clip disappeared: {remote_id}")
    if raw.get("owner_id") != owner_id or raw.get("id") != video_id:
        raise base.MiloviFinalizerBlocked(f"VK Clip identity changed: {remote_id}")
    if str(raw.get("type") or "") != "short_video":
        raise base.MiloviFinalizerBlocked(f"Durably verified VK Clip lost native short_video type: {remote_id}")
    state, description = _clip_copy_state(raw=raw, asset=asset)
    return raw, state, description


def _verified_upload_remote_id(item: Mapping[str, Any]) -> str | None:
    raw_record = item.get("upload_record")
    if not isinstance(raw_record, Mapping):
        return None
    try:
        stage = base.UploadStage(str(raw_record.get("stage")))
    except ValueError:
        return None
    if stage is not base.UploadStage.VERIFIED or not base._has_provider_effect(raw_record):
        return None
    return base._upload_remote_id(raw_record)


def _ensure_promoted_clip(
    asset: base.SourceAsset,
    artifact: Any,
    item: dict[str, Any],
    journal: dict[str, Any],
    journal_path: Path,
    writer: base.VkWallWriter,
    upload_writer: Any,
    timeout: int,
) -> str:
    current = item.get("clip_remote_id")
    if isinstance(current, str) and current:
        _assert_durable_clip(writer, asset, current)
        return current

    verified_remote_id = _verified_upload_remote_id(item)
    if verified_remote_id is not None:
        _assert_durable_clip(writer, asset, verified_remote_id)
        item.update(
            status="clip_verified",
            clip_remote_id=verified_remote_id,
            clip_origin="resumed_verified_short_video_without_reupload",
        )
        base._save(journal_path, journal)
        return verified_remote_id

    # The base path remains the sole uploader for records with no durable provider effect.
    return base._ensure_promoted_clip(
        asset,
        artifact,
        item,
        journal,
        journal_path,
        writer,
        upload_writer,
        timeout,
    )


def _complete_child(
    source_id: str,
    *,
    legacy_assets: dict[str, base.SourceAsset],
    promoted_assets: dict[str, base.SourceAsset],
    artifacts: dict[str, Any],
    journal: dict[str, Any],
    journal_path: Path,
    slots: Mapping[str, Any],
    writer: base.VkWallWriter,
    upload_writer: Any,
    client: base.VkApiClient,
    verify_timeout_seconds: int,
) -> None:
    item = base._item(journal, source_id)
    if item.get("status") == "wall_verified":
        return
    asset = promoted_assets[source_id]
    if source_id == base.ANOMALY_SOURCE_ID and item.get("status") != "clip_verified":
        clip_id = base._ensure_clip_live(
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
        if clip_id != base.ANOMALY_CLIP_REMOTE_ID:
            raise base.MiloviFinalizerBlocked("Eighth reconciliation returned another Clip")
    elif item.get("status") == "clip_verified":
        clip_id = str(item.get("clip_remote_id") or "")
        if not clip_id:
            raise base.MiloviFinalizerBlocked(f"clip_verified item lost remote ID: {source_id}")
        _assert_durable_clip(writer, asset, clip_id)
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
    if source_id == base.ANOMALY_SOURCE_ID and clip_id != base.ANOMALY_CLIP_REMOTE_ID:
        raise base.MiloviFinalizerBlocked("Eighth Clip identity changed")
    base._ensure_wall(asset, clip_id, slots[source_id], item, journal, journal_path, writer, client)


def _promotion_preflight(
    *,
    writer: base.VkWallWriter,
    assets: list[base.SourceAsset],
    journal: dict[str, Any],
    now_epoch: int | None = None,
) -> dict[str, Any]:
    base._assert_wall475_absent(writer)
    snapshot = writer.capture_wall_snapshot(community_id=base.MILOVI_COMMUNITY_ID, max_posts_per_surface=10000)
    if not snapshot.complete:
        raise base.MiloviFinalizerBlocked("Promotion preflight wall snapshot is incomplete")
    observed_now = int(base.time.time()) if now_epoch is None else now_epoch
    current_wall_ids: set[str] = set()
    evidence: list[dict[str, Any]] = []
    for asset in assets:
        item = base._item(journal, asset.source_id)
        clip_remote_id = str(item.get("clip_remote_id") or "")
        wall_remote_id = str(item.get("wall_remote_id") or "")
        publish_date = item.get("publish_date")
        if item.get("status") != "wall_verified" or not clip_remote_id or not wall_remote_id or type(publish_date) is not int:
            raise base.MiloviFinalizerBlocked(f"Promotion preflight durable mapping is incomplete: {asset.source_id}")

        _raw_clip, clip_state, clip_description = _assert_durable_clip(writer, asset, clip_remote_id)
        if clip_state.startswith("provider_processing_"):
            raise base.MiloviFinalizerBlocked(
                f"Promotion preflight requires exact Clip copy, not processing projection: {asset.source_id}"
            )
        current_remote_id, surface, post, resolution_mode = base._resolve_wall_incarnation(
            writer=writer,
            snapshot=snapshot,
            journal=journal,
            wall_remote_id=wall_remote_id,
            clip_remote_id=clip_remote_id,
            publish_date=publish_date,
            now_epoch=observed_now,
        )
        if current_remote_id in current_wall_ids:
            raise base.MiloviFinalizerBlocked(f"Promotion preflight current wall incarnation is reused: {current_remote_id}")
        current_wall_ids.add(current_remote_id)
        wall_text = str(post.get("text") or "").strip()
        wall_state = base._copy_state(
            current=wall_text,
            legacy=base._legacy_wall_message(asset),
            promoted=asset.wall_message.strip(),
            source_id=asset.source_id,
            field="Wall message",
        )
        evidence.append(
            {
                "source_id": asset.source_id,
                "clip_remote_id": clip_remote_id,
                "clip_copy_state": clip_state,
                "clip_description_sha256": base._sha256_text(clip_description),
                "wall_remote_id": wall_remote_id,
                "current_wall_remote_id": current_remote_id,
                "wall_resolution_mode": resolution_mode,
                "wall_surface": surface.value,
                "wall_copy_state": wall_state,
                "wall_message_sha256": base._sha256_text(wall_text),
                "publish_date": publish_date,
            }
        )
    if tuple(row["source_id"] for row in evidence) != base.ROLL_OUT_IDS:
        raise base.MiloviFinalizerBlocked("Promotion preflight source order differs from exact Issue #323 allowlist")
    return {
        "status": "verified",
        "provider_write_authorized_by_preflight": False,
        "wall_snapshot_sha256": snapshot.snapshot_sha256,
        "items": evidence,
    }


def _preflight_clip_sha(finalizer: Mapping[str, Any], source_id: str) -> str:
    preflight = finalizer.get("promotion_preflight")
    rows = preflight.get("items") if isinstance(preflight, Mapping) else None
    if not isinstance(rows, list):
        raise base.MiloviFinalizerBlocked("Promotion preflight evidence is missing")
    matches = [row for row in rows if isinstance(row, Mapping) and row.get("source_id") == source_id]
    if len(matches) != 1:
        raise base.MiloviFinalizerBlocked(f"Promotion preflight evidence is ambiguous: {source_id}")
    digest = matches[0].get("clip_description_sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        raise base.MiloviFinalizerBlocked(f"Promotion preflight Clip digest is invalid: {source_id}")
    return digest


def _edit_clip_description(
    *,
    writer: base.VkWallWriter,
    client: base.VkApiClient,
    asset: base.SourceAsset,
    remote_id: str,
    operation: dict[str, Any],
    finalizer: dict[str, Any],
    finalizer_path: Path,
) -> None:
    _raw, state, current_description = _assert_durable_clip(writer, asset, remote_id)
    current_sha = base._sha256_text(current_description)
    if current_sha != _preflight_clip_sha(finalizer, asset.source_id):
        raise base.MiloviFinalizerBlocked(f"Clip description changed after promotion preflight: {remote_id}")

    if state == "operator_preserved":
        if operation.get("dispatch_started") is True or str(operation.get("status") or "pending") in {
            "edit_dispatch_started",
            "unknown_requires_reconciliation",
        }:
            raise base.MiloviFinalizerBlocked(
                f"Cannot adopt operator copy while a video.edit dispatch is unresolved: {remote_id}"
            )
        operation.update(
            status="preserved_operator",
            remote_id=remote_id,
            description_sha256=current_sha,
            provider_write_dispatched=False,
        )
        base._save_finalizer(finalizer_path, finalizer)
        return
    if state == "promoted":
        operation.update(
            status="verified",
            remote_id=remote_id,
            description_sha256=current_sha,
            dispatch_started=bool(operation.get("dispatch_started", False)),
        )
        base._save_finalizer(finalizer_path, finalizer)
        return
    if state != "legacy":
        raise base.MiloviFinalizerBlocked(f"Clip copy is not stable enough to promote: {remote_id}: {state}")
    base._edit_clip_description(
        writer=writer,
        client=client,
        asset=asset,
        remote_id=remote_id,
        operation=operation,
        finalizer=finalizer,
        finalizer_path=finalizer_path,
    )


def _final_postflight(
    writer: base.VkWallWriter,
    assets: list[base.SourceAsset],
    journal: dict[str, Any],
    finalizer: Mapping[str, Any],
    *,
    now_epoch: int | None = None,
) -> list[dict[str, Any]]:
    base._assert_wall475_absent(writer)
    snapshot = writer.capture_wall_snapshot(community_id=base.MILOVI_COMMUNITY_ID, max_posts_per_surface=10000)
    if not snapshot.complete:
        raise base.MiloviFinalizerBlocked("Final wall snapshot is incomplete")
    observed_now = int(base.time.time()) if now_epoch is None else now_epoch
    evidence: list[dict[str, Any]] = []
    current_wall_ids: set[str] = set()
    clip_ops = finalizer.get("clip_description_edits")
    if not isinstance(clip_ops, Mapping):
        raise base.MiloviFinalizerBlocked("Finalizer Clip operation map is missing")

    for asset in assets:
        item = base._item(journal, asset.source_id)
        clip_remote_id = str(item.get("clip_remote_id") or "")
        wall_remote_id = str(item.get("wall_remote_id") or "")
        publish_date = item.get("publish_date")
        if item.get("status") != "wall_verified" or not clip_remote_id or not wall_remote_id or type(publish_date) is not int:
            raise base.MiloviFinalizerBlocked(f"Final durable mapping is incomplete: {asset.source_id}")

        _raw_clip, clip_state, clip_description = _assert_durable_clip(writer, asset, clip_remote_id)
        clip_sha = base._sha256_text(clip_description)
        clip_op = clip_ops.get(asset.source_id)
        if clip_state == "operator_preserved":
            if not isinstance(clip_op, Mapping) or clip_op.get("status") != "preserved_operator":
                raise base.MiloviFinalizerBlocked(f"Operator Clip copy lost durable preservation evidence: {asset.source_id}")
            if clip_op.get("remote_id") != clip_remote_id or clip_op.get("description_sha256") != clip_sha:
                raise base.MiloviFinalizerBlocked(f"Operator Clip copy changed after preservation: {asset.source_id}")
        elif clip_state != "promoted":
            raise base.MiloviFinalizerBlocked(f"Final Clip copy is neither promoted nor operator-preserved: {asset.source_id}")

        actual_remote_id, raw_surface, raw_post, resolution_mode = base._resolve_wall_incarnation(
            writer=writer,
            snapshot=snapshot,
            journal=journal,
            wall_remote_id=wall_remote_id,
            clip_remote_id=clip_remote_id,
            publish_date=publish_date,
            now_epoch=observed_now,
        )
        if actual_remote_id in current_wall_ids:
            raise base.MiloviFinalizerBlocked(f"Final wall incarnation is reused by multiple sources: {actual_remote_id}")
        current_wall_ids.add(actual_remote_id)
        if str(raw_post.get("text") or "").strip() != asset.wall_message.strip():
            raise base.MiloviFinalizerBlocked(f"Final wall public copy differs for {asset.source_id}")
        evidence.append(
            {
                "source_id": asset.source_id,
                "clip_remote_id": clip_remote_id,
                "clip_copy_state": clip_state,
                "wall_remote_id": wall_remote_id,
                "current_wall_remote_id": actual_remote_id,
                "wall_resolution_mode": resolution_mode,
                "publish_date": publish_date,
                "wall_surface": raw_surface.value,
                "clip_description_sha256": clip_sha,
                "wall_message_sha256": base._sha256_text(asset.wall_message),
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
    if confirmation != base.EXECUTION_CONFIRMATION:
        raise base.MiloviFinalizerBlocked(f"Exact confirmation required: {base.EXECUTION_CONFIRMATION}")
    if verify_timeout_seconds < 60:
        raise base.MiloviFinalizerBlocked("verify_timeout_seconds must be >=60")

    journal = base._load_journal(journal_path)
    if journal.get("canary_verified") is not True:
        raise base.MiloviFinalizerBlocked("Issue #323 canary is not durably verified")
    legacy_list = base.prepare_sources(work_dir)
    promoted_list = [base._promote_asset(asset) for asset in legacy_list]
    legacy_assets = {asset.source_id: asset for asset in legacy_list}
    promoted_assets = {asset.source_id: asset for asset in promoted_list}
    artifacts = base._media_artifacts(legacy_list)
    finalizer = base._load_finalizer_journal(finalizer_journal_path, promoted_list)

    settings = base.get_settings()
    store = base.VkTokenStore(settings.data_dir)
    alias, client = base._resolve_account(store, settings.vk_api_version)
    writer = base.VkWallWriter(token_store=store, account_alias=alias, api_version=settings.vk_api_version)
    upload_writer = base._LiveClipWriter(writer, client)
    lock_path = settings.data_dir / "locks" / f"vk-{base.MILOVI_COMMUNITY_ID}-issue-323-finalizer.lock"

    try:
        with base.local_vk_write_lock(
            lock_path,
            account=alias,
            community_id=base.MILOVI_COMMUNITY_ID,
            operation="milovi-issue-323-finalize-operator-copy-safe",
        ):
            base._prove_target(client)
            slots = base.load_or_create_daily_schedule(schedule_path, writer=writer)
            if tuple(slots) != base.ROLL_OUT_IDS:
                raise base.MiloviFinalizerBlocked("Issue #323 schedule differs from exact source order")

            anomaly_item = base._item(journal, base.ANOMALY_SOURCE_ID)
            anomaly_record = anomaly_item.get("upload_record")
            reservation = anomaly_record.get("reservation") if isinstance(anomaly_record, Mapping) else None
            if not isinstance(reservation, Mapping) or reservation.get("remote_id") != base.ANOMALY_CLIP_REMOTE_ID:
                raise base.MiloviFinalizerBlocked("Eighth durable reservation is not exact Clip 456239232")

            base._cleanup_anomaly_475(
                writer=writer,
                promoted_asset=promoted_assets[base.ANOMALY_SOURCE_ID],
                finalizer=finalizer,
                finalizer_path=finalizer_journal_path,
            )

            for source_id in base.ROLL_OUT_IDS[base.ROLL_OUT_IDS.index(base.ANOMALY_SOURCE_ID) :]:
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
                base.write_json_atomic(rollout_output_path, base._result(journal, "in_progress"))

            incomplete = [
                source_id
                for source_id in base.ROLL_OUT_IDS
                if base._item(journal, source_id).get("status") != "wall_verified"
            ]
            if incomplete:
                raise base.MiloviFinalizerBlocked(f"Rollout child completion is incomplete: {incomplete}")

            finalizer["promotion_preflight"] = _promotion_preflight(
                writer=writer,
                assets=promoted_list,
                journal=journal,
            )
            base._save_finalizer(finalizer_journal_path, finalizer)

            for asset in promoted_list:
                item = base._item(journal, asset.source_id)
                clip_remote_id = str(item.get("clip_remote_id") or "")
                wall_remote_id = str(item.get("wall_remote_id") or "")
                publish_date = item.get("publish_date")
                if not clip_remote_id or not wall_remote_id or type(publish_date) is not int:
                    raise base.MiloviFinalizerBlocked(f"Cannot promote incomplete durable mapping: {asset.source_id}")
                _edit_clip_description(
                    writer=writer,
                    client=client,
                    asset=asset,
                    remote_id=clip_remote_id,
                    operation=finalizer["clip_description_edits"][asset.source_id],
                    finalizer=finalizer,
                    finalizer_path=finalizer_journal_path,
                )
                base._edit_wall_message(
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

            evidence = _final_postflight(writer, promoted_list, journal, finalizer)
            rollout_payload = base._result(journal, "batch_verified")
            rollout_payload["public_promotion"] = {
                "youtube_public_links": False,
                "canonical_urls": list(base.PUBLIC_PROMOTION_URLS),
                "operator_clip_descriptions_preserved": True,
            }
            base.write_json_atomic(rollout_output_path, rollout_payload)
            payload = {
                "schema_name": base.FINALIZER_SCHEMA,
                "schema_version": 1,
                "status": "final_verified",
                "project_key": "milovi-cake",
                "community_id": base.MILOVI_COMMUNITY_ID,
                "owner_id": base.MILOVI_OWNER_ID,
                "browser_used": False,
                "anomaly_cleanup": {"wall_remote_id": base.ANOMALY_WALL_REMOTE_ID, "status": "verified_absent"},
                "promotion_preflight": finalizer["promotion_preflight"],
                "youtube_public_links": False,
                "operator_clip_descriptions_preserved": True,
                "canonical_promotion_urls": list(base.PUBLIC_PROMOTION_URLS),
                "items": evidence,
            }
            base.write_json_atomic(output_path, payload)
            return payload
    except Exception as exc:
        base.write_json_atomic(
            output_path,
            {
                "schema_name": base.FINALIZER_SCHEMA,
                "schema_version": 1,
                "status": "blocked",
                "project_key": "milovi-cake",
                "community_id": base.MILOVI_COMMUNITY_ID,
                "owner_id": base.MILOVI_OWNER_ID,
                "browser_used": False,
                "error": {"type": type(exc).__name__, "message": str(exc)},
            },
        )
        raise


__all__ = ["run_issue_323_finalizer"]
