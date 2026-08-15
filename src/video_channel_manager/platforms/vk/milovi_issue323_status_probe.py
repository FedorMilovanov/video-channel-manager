from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk import VkApiClient, VkTokenStore, local_vk_write_lock
from video_channel_manager.platforms.vk.lock import community_vk_write_lock_path
from video_channel_manager.platforms.vk.milovi_daily_postponed_wall import (
    _validate_schedule_payload,
)
from video_channel_manager.platforms.vk.milovi_immediate_wall import MILOVI_COMMUNITY_ID, MILOVI_OWNER_ID
from video_channel_manager.platforms.vk.milovi_issue323_finalize import (
    MiloviFinalizerBlocked,
    _assert_native_clip,
    _copy_state,
    _legacy_clip_description,
    _legacy_wall_message,
    _promote_asset,
    _read_exact_wall_incarnation,
    _resolve_wall_incarnation,
    _sha256_text,
)
from video_channel_manager.platforms.vk.milovi_rollout_sources import (
    PREPARED_SCHEMA,
    ROLL_OUT_IDS,
    SOURCE_SNAPSHOT_ID,
    SourceAsset,
    write_json_atomic,
)
from video_channel_manager.platforms.vk.milovi_token_clip_rollout import (
    MiloviTokenRolloutBlocked,
    _find_existing_clip,
    _has_provider_effect,
    _load_journal,
    _prove_target,
    _resolve_account,
    _upload_remote_id,
)
from video_channel_manager.platforms.vk.upload_lifecycle import UploadStage
from video_channel_manager.platforms.vk.wall import VkWallWriter
from video_channel_manager.platforms.vk.wall_safety import VkWallSnapshot, VkWallSurface

STATUS_SCHEMA = "video-manager.milovi-issue-323-readonly-status"
STATUS_VERSION = 1

ExistingClipLookup = Callable[[VkApiClient, SourceAsset], str | None]


class MiloviStatusProbeBlocked(MiloviTokenRolloutBlocked):
    pass


class _ReadOnlyVkProvider:
    """Expose only the provider reads needed by the Issue #323 status probe."""

    __slots__ = ("_delegate",)

    def __init__(self, delegate: VkWallWriter) -> None:
        self._delegate = delegate

    def read_video(self, *, owner_id: int, video_id: int) -> dict[str, Any] | None:
        return self._delegate.read_video(owner_id=owner_id, video_id=video_id)

    def read_post(self, *, community_id: int, post_id: int) -> dict[str, Any] | None:
        return self._delegate.read_post(community_id=community_id, post_id=post_id)

    def capture_wall_snapshot(self, *, community_id: int, max_posts_per_surface: int = 10000) -> VkWallSnapshot:
        return self._delegate.capture_wall_snapshot(
            community_id=community_id,
            max_posts_per_surface=max_posts_per_surface,
        )


def _load_prepared_assets(path: Path) -> list[SourceAsset]:
    """Load reviewed metadata only; never probe media bytes or call YouTube."""

    if not path.is_file():
        raise MiloviStatusProbeBlocked(f"Prepared-source manifest is missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise MiloviStatusProbeBlocked("Prepared-source manifest is unreadable") from exc
    if not isinstance(payload, Mapping):
        raise MiloviStatusProbeBlocked("Prepared-source manifest is not a JSON object")
    if (
        payload.get("schema_name") != PREPARED_SCHEMA
        or payload.get("schema_version") != 1
        or payload.get("source_snapshot_id") != SOURCE_SNAPSHOT_ID
    ):
        raise MiloviStatusProbeBlocked("Prepared-source manifest differs from exact Issue #323 provenance")
    raw_assets = payload.get("assets")
    if not isinstance(raw_assets, list) or any(not isinstance(item, Mapping) for item in raw_assets):
        raise MiloviStatusProbeBlocked("Prepared-source manifest assets are malformed")
    try:
        assets = [SourceAsset(**dict(item)) for item in raw_assets]
    except (TypeError, ValueError) as exc:
        raise MiloviStatusProbeBlocked("Prepared-source manifest contains an invalid asset") from exc
    if tuple(asset.source_id for asset in assets) != ROLL_OUT_IDS:
        raise MiloviStatusProbeBlocked("Prepared-source manifest allowlist/order differs from exact Issue #323")
    return assets


def _load_schedule_read_only(path: Path) -> dict[str, datetime]:
    if not path.is_file():
        raise MiloviStatusProbeBlocked(f"Frozen Issue #323 schedule is missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise MiloviStatusProbeBlocked("Frozen Issue #323 schedule is unreadable") from exc
    if not isinstance(payload, Mapping):
        raise MiloviStatusProbeBlocked("Frozen Issue #323 schedule is not a JSON object")
    try:
        return _validate_schedule_payload(payload)
    except (RuntimeError, ValueError) as exc:
        raise MiloviStatusProbeBlocked("Frozen Issue #323 schedule binding is invalid") from exc


def _upload_state(item: Mapping[str, Any]) -> tuple[str | None, bool, str | None]:
    raw_record = item.get("upload_record")
    if not isinstance(raw_record, Mapping):
        return None, False, None
    try:
        stage = UploadStage(str(raw_record.get("stage")))
    except ValueError as exc:
        raise MiloviStatusProbeBlocked(f"Upload record has an invalid stage: {raw_record.get('stage')!r}") from exc
    provider_effect = _has_provider_effect(raw_record)
    remote_id: str | None = None
    if provider_effect:
        try:
            remote_id = _upload_remote_id(raw_record)
        except MiloviTokenRolloutBlocked:
            remote_id = None
    return stage.value, provider_effect, remote_id


def _durable_clip_candidate(item: Mapping[str, Any]) -> tuple[str | None, str | None, str | None, bool]:
    stage, provider_effect, upload_remote_id = _upload_state(item)
    raw_clip = item.get("clip_remote_id")
    if isinstance(raw_clip, str) and raw_clip:
        if upload_remote_id is not None and upload_remote_id != raw_clip:
            raise MiloviStatusProbeBlocked(
                f"Journal clip_remote_id {raw_clip} differs from upload reservation {upload_remote_id}"
            )
        return raw_clip, "journal", stage, provider_effect
    if upload_remote_id is not None:
        return upload_remote_id, "upload_record", stage, provider_effect
    return None, None, stage, provider_effect


def _resolve_unjournaled_wall(
    *,
    provider: _ReadOnlyVkProvider,
    snapshot: VkWallSnapshot,
    clip_remote_id: str,
    publish_date: int,
    now_epoch: int,
) -> tuple[str, VkWallSurface, dict[str, Any], str] | None:
    expected_attachment = f"video{clip_remote_id}"
    matches = [post for post in snapshot.posts if expected_attachment in post.attachments]
    if len(matches) > 1:
        ids = sorted(post.remote_id for post in matches)
        raise MiloviStatusProbeBlocked(f"Clip {clip_remote_id} appears in multiple wall mappings: {ids}")
    if not matches:
        return None
    match = matches[0]
    if match.publish_date != publish_date:
        raise MiloviStatusProbeBlocked(
            f"Clip {clip_remote_id} wall date changed: {match.publish_date} != frozen {publish_date}"
        )
    if match.surface is VkWallSurface.PUBLISHED and now_epoch + 60 < publish_date:
        raise MiloviStatusProbeBlocked(f"Clip {clip_remote_id} wall mapping published before its frozen slot")
    raw = _read_exact_wall_incarnation(
        cast(VkWallWriter, provider),
        remote_id=match.remote_id,
        clip_remote_id=clip_remote_id,
        publish_date=publish_date,
    )
    return match.remote_id, match.surface, raw, "unjournaled_exact_mapping"


def _safe_next_action(
    *,
    durable_status: str,
    upload_stage: str | None,
    provider_effect: bool,
    clip_remote_id: str | None,
    clip_origin: str | None,
    wall_remote_id: str | None,
    clip_copy_state: str | None,
    wall_copy_state: str | None,
) -> str:
    if wall_remote_id is not None:
        if durable_status != "wall_verified":
            return "reconcile_existing_wall_without_repost"
        if clip_copy_state == "promoted" and wall_copy_state == "promoted":
            return "phase_a_complete_promoted"
        return "phase_a_complete_promotion_pending"
    if clip_remote_id is not None:
        if provider_effect and upload_stage == UploadStage.VERIFIED.value and clip_origin == "upload_record":
            return "resume_from_verified_clip_without_reupload_then_wall"
        if durable_status == "clip_verified":
            return "resume_wall_only_without_reupload"
        if clip_origin == "inventory":
            return "adopt_existing_clip_without_reupload_then_wall"
        if provider_effect:
            return "reconcile_provider_effect_without_reupload_then_wall"
        return "resume_wall_without_reupload"
    if provider_effect:
        return "reconcile_provider_effect_without_replay"
    return "eligible_for_single_upload_after_executor_existing_clip_preflight"


def _probe_batch(
    *,
    assets: list[SourceAsset],
    journal: dict[str, Any],
    slots: Mapping[str, datetime],
    provider: _ReadOnlyVkProvider,
    client: VkApiClient,
    snapshot: VkWallSnapshot,
    existing_clip_lookup: ExistingClipLookup = _find_existing_clip,
    now_epoch: int | None = None,
) -> dict[str, Any]:
    if tuple(asset.source_id for asset in assets) != ROLL_OUT_IDS or tuple(slots) != ROLL_OUT_IDS:
        raise MiloviStatusProbeBlocked("Probe inputs differ from exact Issue #323 order")
    if not snapshot.complete or snapshot.community_id != MILOVI_COMMUNITY_ID:
        raise MiloviStatusProbeBlocked("Complete exact Milovi wall snapshot is required")

    observed_now = int(time.time()) if now_epoch is None else now_epoch
    legacy_assets = {asset.source_id: asset for asset in assets}
    promoted_assets = {asset.source_id: _promote_asset(asset) for asset in assets}
    raw_items = journal.get("items")
    if not isinstance(raw_items, Mapping):
        raise MiloviStatusProbeBlocked("Issue #323 journal item map is missing")

    evidence: list[dict[str, Any]] = []
    blockers: list[dict[str, str]] = []
    for index, source_id in enumerate(ROLL_OUT_IDS, start=1):
        raw_item = raw_items.get(source_id)
        if not isinstance(raw_item, Mapping):
            raise MiloviStatusProbeBlocked(f"Issue #323 journal item is invalid: {source_id}")
        item = dict(raw_item)
        durable_status = str(item.get("status") or "")
        if durable_status not in {
            "pending",
            "upload_in_progress",
            "clip_verified",
            "wall_intent",
            "wall_may_exist",
            "wall_verified",
        }:
            raise MiloviStatusProbeBlocked(f"Unexpected durable status for {source_id}: {durable_status!r}")

        asset = promoted_assets[source_id]
        legacy_asset = legacy_assets[source_id]
        expected_publish_date = int(slots[source_id].timestamp())
        observed_publish_date = item.get("publish_date")
        if type(observed_publish_date) is int and observed_publish_date != expected_publish_date:
            raise MiloviStatusProbeBlocked(
                f"Journal publish_date differs from frozen schedule for {source_id}: "
                f"{observed_publish_date} != {expected_publish_date}"
            )

        row: dict[str, Any] = {
            "index": index,
            "source_id": source_id,
            "durable_status": durable_status,
            "frozen_publish_at": slots[source_id].isoformat(),
            "frozen_publish_date": expected_publish_date,
            "clip_remote_id": None,
            "clip_identity_origin": None,
            "clip_copy_state": None,
            "clip_description_sha256": None,
            "upload_stage": None,
            "provider_effect_durable": False,
            "wall_remote_id": item.get("wall_remote_id"),
            "current_wall_remote_id": None,
            "wall_resolution_mode": None,
            "wall_surface": None,
            "wall_copy_state": None,
            "wall_message_sha256": None,
            "safe_next_action": None,
            "reupload_authorized_by_probe": False,
            "repost_authorized_by_probe": False,
            "stop_reason": None,
        }

        try:
            clip_remote_id, clip_origin, upload_stage, provider_effect = _durable_clip_candidate(item)
            row["upload_stage"] = upload_stage
            row["provider_effect_durable"] = provider_effect

            if clip_remote_id is None and not provider_effect:
                clip_remote_id = existing_clip_lookup(client, legacy_asset)
                if clip_remote_id is not None:
                    clip_origin = "inventory"

            clip_copy_state: str | None = None
            if clip_remote_id is not None:
                durable_verified = durable_status in {"clip_verified", "wall_verified"} or (
                    upload_stage == UploadStage.VERIFIED.value
                )
                raw_clip = _assert_native_clip(
                    cast(VkWallWriter, provider),
                    asset,
                    clip_remote_id,
                    description_mode="legacy_or_promoted",
                    durable_verified=durable_verified,
                )
                current_description = str(raw_clip.get("description") or "").strip()
                clip_copy_state = _copy_state(
                    current=current_description,
                    legacy=_legacy_clip_description(asset),
                    promoted=asset.description.strip(),
                    source_id=source_id,
                    field="Clip description",
                )
                row.update(
                    clip_remote_id=clip_remote_id,
                    clip_identity_origin=clip_origin,
                    clip_copy_state=clip_copy_state,
                    clip_description_sha256=_sha256_text(current_description),
                )

            journal_wall_remote_id = item.get("wall_remote_id")
            if durable_status == "wall_verified" and not (
                isinstance(journal_wall_remote_id, str) and journal_wall_remote_id
            ):
                raise MiloviStatusProbeBlocked(f"wall_verified item lost wall_remote_id: {source_id}")

            resolved_wall: tuple[str, VkWallSurface, dict[str, Any], str] | None = None
            if clip_remote_id is not None:
                if isinstance(journal_wall_remote_id, str) and journal_wall_remote_id:
                    resolved_wall = _resolve_wall_incarnation(
                        writer=cast(VkWallWriter, provider),
                        snapshot=snapshot,
                        journal=journal,
                        wall_remote_id=journal_wall_remote_id,
                        clip_remote_id=clip_remote_id,
                        publish_date=expected_publish_date,
                        now_epoch=observed_now,
                    )
                else:
                    resolved_wall = _resolve_unjournaled_wall(
                        provider=provider,
                        snapshot=snapshot,
                        clip_remote_id=clip_remote_id,
                        publish_date=expected_publish_date,
                        now_epoch=observed_now,
                    )

            wall_copy_state: str | None = None
            current_wall_remote_id: str | None = None
            if resolved_wall is not None:
                current_wall_remote_id, surface, raw_post, resolution_mode = resolved_wall
                current_message = str(raw_post.get("text") or "").strip()
                wall_copy_state = _copy_state(
                    current=current_message,
                    legacy=_legacy_wall_message(asset),
                    promoted=asset.wall_message.strip(),
                    source_id=source_id,
                    field="Wall message",
                )
                row.update(
                    current_wall_remote_id=current_wall_remote_id,
                    wall_resolution_mode=resolution_mode,
                    wall_surface=surface.value,
                    wall_copy_state=wall_copy_state,
                    wall_message_sha256=_sha256_text(current_message),
                )

            row["safe_next_action"] = _safe_next_action(
                durable_status=durable_status,
                upload_stage=upload_stage,
                provider_effect=provider_effect,
                clip_remote_id=clip_remote_id,
                clip_origin=clip_origin,
                wall_remote_id=current_wall_remote_id,
                clip_copy_state=clip_copy_state,
                wall_copy_state=wall_copy_state,
            )
        except (MiloviStatusProbeBlocked, MiloviFinalizerBlocked, MiloviTokenRolloutBlocked) as exc:
            row["safe_next_action"] = "stop_conflict"
            row["stop_reason"] = str(exc)
            blockers.append({"source_id": source_id, "reason": str(exc)})

        evidence.append(row)

    phase_a_complete = all(
        item["durable_status"] == "wall_verified" and item["current_wall_remote_id"] is not None for item in evidence
    )
    first_action = next(
        (
            item
            for item in evidence
            if item["safe_next_action"] not in {"phase_a_complete_promoted", "phase_a_complete_promotion_pending"}
        ),
        None,
    )
    protected_no_reupload = [
        item["source_id"]
        for item in evidence
        if item["clip_remote_id"] is not None or item["provider_effect_durable"] is True
    ]
    return {
        "schema_name": STATUS_SCHEMA,
        "schema_version": STATUS_VERSION,
        "status": "blocked" if blockers else "verified_read_only",
        "project_key": "milovi-cake",
        "community_id": MILOVI_COMMUNITY_ID,
        "owner_id": MILOVI_OWNER_ID,
        "source_snapshot_id": SOURCE_SNAPSHOT_ID,
        "provider_mutation_authorized": False,
        "journal_mutation_authorized": False,
        "media_download_authorized": False,
        "youtube_access_authorized": False,
        "wall_snapshot_sha256": snapshot.snapshot_sha256,
        "phase_a_complete": phase_a_complete,
        "first_action_source_id": first_action["source_id"] if first_action is not None else None,
        "first_safe_next_action": first_action["safe_next_action"] if first_action is not None else None,
        "protected_no_reupload_source_ids": protected_no_reupload,
        "blockers": blockers,
        "items": evidence,
    }


def run_issue_323_status_probe(
    *,
    output_path: Path,
    journal_path: Path,
    schedule_path: Path,
    prepared_manifest_path: Path,
) -> dict[str, Any]:
    """Reconcile Issue #323 live state without granting any provider mutation method."""

    if not journal_path.is_file():
        raise MiloviStatusProbeBlocked(f"Issue #323 durable journal is missing: {journal_path}")
    journal = _load_journal(journal_path)
    assets = _load_prepared_assets(prepared_manifest_path)
    slots = _load_schedule_read_only(schedule_path)

    settings = get_settings()
    store = VkTokenStore(settings.data_dir)
    alias, client = _resolve_account(store, settings.vk_api_version)
    delegate = VkWallWriter(token_store=store, account_alias=alias, api_version=settings.vk_api_version)
    provider = _ReadOnlyVkProvider(delegate)
    lock_path = community_vk_write_lock_path(settings.data_dir, community_id=MILOVI_COMMUNITY_ID)

    with local_vk_write_lock(
        lock_path,
        account=alias,
        community_id=MILOVI_COMMUNITY_ID,
        operation="milovi-issue-323-readonly-status-probe",
    ):
        _prove_target(client)
        snapshot = provider.capture_wall_snapshot(
            community_id=MILOVI_COMMUNITY_ID,
            max_posts_per_surface=10000,
        )
        payload = _probe_batch(
            assets=assets,
            journal=journal,
            slots=slots,
            provider=provider,
            client=client,
            snapshot=snapshot,
        )

    payload["captured_at"] = datetime.now(UTC).isoformat()
    payload["account_alias"] = alias
    write_json_atomic(output_path, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only live status reconciliation for Milovi Issue #323")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("operator-output/milovi-cake-issue-323-readonly-status.json"),
    )
    parser.add_argument(
        "--journal",
        type=Path,
        default=Path("data/vk/milovi-cake/issue-323-token-daily-rollout-journal.json"),
    )
    parser.add_argument(
        "--schedule",
        type=Path,
        default=Path("data/vk/milovi-cake/issue-323-daily-wall-schedule.json"),
    )
    parser.add_argument(
        "--prepared-manifest",
        type=Path,
        default=Path("operator-output/milovi-cake-issue-323-work/prepared-sources.json"),
    )
    args = parser.parse_args()
    result = run_issue_323_status_probe(
        output_path=args.output,
        journal_path=args.journal,
        schedule_path=args.schedule,
        prepared_manifest_path=args.prepared_manifest,
    )
    print(
        "Milovi #323 read-only status: "
        f"{result['status']} | next={result['first_action_source_id']}:{result['first_safe_next_action']} "
        f"| result={args.output}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (MiloviStatusProbeBlocked, MiloviTokenRolloutBlocked, MiloviFinalizerBlocked, OSError, ValueError) as exc:
        print(f"STOP: {type(exc).__name__}: {exc}")
        raise SystemExit(3) from exc


__all__ = [
    "STATUS_SCHEMA",
    "MiloviStatusProbeBlocked",
    "run_issue_323_status_probe",
]
