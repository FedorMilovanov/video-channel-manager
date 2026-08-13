from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk import VkTokenStore
from video_channel_manager.platforms.vk.milovi_immediate_wall import MILOVI_COMMUNITY_ID, MILOVI_OWNER_ID
from video_channel_manager.platforms.vk.milovi_rollout_sources import ROLL_OUT_IDS, write_json_atomic
from video_channel_manager.platforms.vk.milovi_token_clip_rollout import (
    CANARY_SOURCE_ID,
    MiloviTokenRolloutBlocked,
    _load_journal,
    _prove_target,
    _resolve_account,
)
from video_channel_manager.platforms.vk.upload_lifecycle import (
    UploadStage,
    VkUploadReadiness,
    assess_vk_upload_readiness,
)
from video_channel_manager.platforms.vk.wall import VkWallWriter
from video_channel_manager.platforms.vk.wall_safety import (
    VkWallDeltaStatus,
    VkWallSnapshot,
    compare_wall_snapshots,
)

EXECUTION_CONFIRMATION = "ISSUE_323_RECONCILE_CANARY_456239225"
EXPECTED_REMOTE_ID = "-68859909_456239225"
RESULT_SCHEMA = "video-manager.milovi-issue-323-canary-reconciliation"


def _canonical_sha256(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _mapping(value: object, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MiloviTokenRolloutBlocked(f"Canary journal field {field!r} is missing or invalid")
    return value


def _readiness(record: Mapping[str, Any]) -> VkUploadReadiness:
    raw = _mapping(record.get("readiness"), field="readiness")
    allowed = raw.get("allowed_types")
    if not isinstance(allowed, list) or tuple(allowed) != ("short_video",):
        raise MiloviTokenRolloutBlocked("Canary journal no longer requires exact short_video readiness")
    expected_title = str(raw.get("expected_title") or "")
    minimum_duration = raw.get("minimum_duration_seconds")
    require_playable = raw.get("require_playable")
    if type(minimum_duration) is not int or type(require_playable) is not bool:
        raise MiloviTokenRolloutBlocked("Canary journal readiness fields are invalid")
    return VkUploadReadiness(
        expected_title=expected_title,
        minimum_duration_seconds=minimum_duration,
        allowed_types=("short_video",),
        require_playable=require_playable,
    )


def normalize_current_wall_to_historical_capture(
    current: VkWallSnapshot,
    wall_safety: Mapping[str, Any],
) -> VkWallSnapshot:
    """Recompute the historical baseline digest using current exact wall content.

    VkWallSnapshot includes captured_at in its self-digest. A fresh read-only
    snapshot therefore cannot equal a historical digest even when every post is
    identical. Replacing only captured_at with the journaled historical value
    lets the stored digest prove whether the current posts/page counts are
    exactly the original pre-upload baseline.
    """

    captured_at = str(wall_safety.get("before_captured_at") or "")
    if not captured_at:
        raise MiloviTokenRolloutBlocked("Canary upload has no historical wall capture timestamp")
    normalized = VkWallSnapshot(
        community_id=current.community_id,
        captured_at=captured_at,
        complete=current.complete,
        published_pages=current.published_pages,
        postponed_pages=current.postponed_pages,
        posts=current.posts,
    )
    expected_sha = str(wall_safety.get("before_snapshot_sha256") or "")
    if normalized.snapshot_sha256 != expected_sha:
        raise MiloviTokenRolloutBlocked(
            "Current Milovi wall is not byte-equivalent to the journaled pre-upload baseline; "
            "canary wall-side-effect reconciliation remains unresolved"
        )
    if current.published_pages != wall_safety.get("before_published_pages"):
        raise MiloviTokenRolloutBlocked("Published wall page count changed since canary upload")
    if current.postponed_pages != wall_safety.get("before_postponed_pages"):
        raise MiloviTokenRolloutBlocked("Postponed wall page count changed since canary upload")
    return normalized


def _bound_canary(journal: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    items = _mapping(journal.get("items"), field="items")
    raw_item = items.get(CANARY_SOURCE_ID)
    if not isinstance(raw_item, dict):
        raise MiloviTokenRolloutBlocked("Exact canary journal item is missing")
    item = raw_item
    raw_record = item.get("upload_record")
    if not isinstance(raw_record, dict):
        raise MiloviTokenRolloutBlocked("Canary has no durable upload record")
    record = raw_record
    if record.get("schema_name") != "video-manager.vk-upload-operation":
        raise MiloviTokenRolloutBlocked("Canary upload record schema changed")
    if record.get("source_video_id") != CANARY_SOURCE_ID or record.get("community_id") != MILOVI_COMMUNITY_ID:
        raise MiloviTokenRolloutBlocked("Canary upload record identity changed")
    reservation = _mapping(record.get("reservation"), field="reservation")
    if reservation.get("owner_id") != MILOVI_OWNER_ID or reservation.get("remote_id") != EXPECTED_REMOTE_ID:
        raise MiloviTokenRolloutBlocked("Canary reservation differs from exact live provider effect")
    if reservation.get("video_id") != 456239225:
        raise MiloviTokenRolloutBlocked("Canary VK video ID differs from exact live provider effect")
    return item, record


def reconcile_canary(*, journal_path: Path, output_path: Path) -> dict[str, Any]:
    journal = _load_journal(journal_path)
    if journal.get("provider_write_attempted") is not True:
        raise MiloviTokenRolloutBlocked("Canary reconciliation requires the already-dispatched exact provider effect")
    if journal.get("canary_verified") is not False:
        raise MiloviTokenRolloutBlocked("Canary wall verification is already complete; this reconciler must not run")
    item, record = _bound_canary(journal)
    remaining = [
        str(_mapping(journal["items"].get(source_id), field=source_id).get("status") or "")
        for source_id in ROLL_OUT_IDS[1:]
    ]
    if any(status != "pending" for status in remaining):
        raise MiloviTokenRolloutBlocked("Remaining 11 items are no longer all pending; exact incident scope changed")

    stage = UploadStage(str(record.get("stage")))
    if stage not in {UploadStage.PROCESSING, UploadStage.VERIFIED}:
        raise MiloviTokenRolloutBlocked(f"Canary upload stage is {stage.value!r}, expected processing/verified")

    settings = get_settings()
    store = VkTokenStore(settings.data_dir)
    alias, client = _resolve_account(store, settings.vk_api_version)
    _prove_target(client)
    writer = VkWallWriter(token_store=store, account_alias=alias, api_version=settings.vk_api_version)

    remote = writer.read_video(owner_id=MILOVI_OWNER_ID, video_id=456239225)
    if remote is None:
        raise MiloviTokenRolloutBlocked(f"Exact canary {EXPECTED_REMOTE_ID} is not visible in read-only VK readback")
    readiness = _readiness(record)
    assessment = assess_vk_upload_readiness(
        remote,
        expected_owner_id=MILOVI_OWNER_ID,
        expected_video_id=456239225,
        readiness=readiness,
    )
    marker = f"youtube.com/shorts/{CANARY_SOURCE_ID}".casefold()
    description_marker_ok = marker in str(remote.get("description") or "").casefold()

    result: dict[str, Any] = {
        "schema_name": RESULT_SCHEMA,
        "schema_version": 1,
        "project_key": "milovi-cake",
        "community_id": MILOVI_COMMUNITY_ID,
        "owner_id": MILOVI_OWNER_ID,
        "source_id": CANARY_SOURCE_ID,
        "remote_id": EXPECTED_REMOTE_ID,
        "provider_mutation_performed": False,
        "assessment": assessment.as_dict(),
        "description_marker_ok": description_marker_ok,
    }
    if not assessment.ready or not description_marker_ok:
        result["status"] = "not_ready_read_only"
        write_json_atomic(output_path, result)
        reasons = list(assessment.reasons)
        if not description_marker_ok:
            reasons.append("source_marker_missing")
        raise MiloviTokenRolloutBlocked(f"Exact canary is not fully ready for reconciliation: {reasons}")

    wall_safety = _mapping(record.get("wall_safety"), field="wall_safety")
    current_wall = writer.capture_wall_snapshot(community_id=MILOVI_COMMUNITY_ID, max_posts_per_surface=10000)
    if not current_wall.complete:
        raise MiloviTokenRolloutBlocked("Current Milovi wall snapshot is incomplete")
    historical_baseline = normalize_current_wall_to_historical_capture(current_wall, wall_safety)
    delta = compare_wall_snapshots(historical_baseline, current_wall)
    if delta.status is not VkWallDeltaStatus.CLEAN:
        raise MiloviTokenRolloutBlocked(f"Canary wall reconciliation is not clean: {delta.status.value}")

    now = _utc_now()
    mutable_wall = record.get("wall_safety")
    if not isinstance(mutable_wall, dict):
        raise MiloviTokenRolloutBlocked("Canary wall_safety record is not mutable")
    mutable_wall.update(
        {
            "after_snapshot_sha256": current_wall.snapshot_sha256,
            "after_captured_at": current_wall.captured_at,
            "after_published_pages": current_wall.published_pages,
            "after_postponed_pages": current_wall.postponed_pages,
            "delta": delta.as_dict(),
        }
    )
    record["verification"] = {
        "verified_at": now,
        "assessment": assessment.as_dict(),
        "item_sha256": _canonical_sha256(dict(remote)),
        "wall_before_snapshot_sha256": historical_baseline.snapshot_sha256,
        "wall_after_snapshot_sha256": current_wall.snapshot_sha256,
        "wall_delta_status": delta.status.value,
        "reconciliation": "exact_processing_remote_readback",
    }
    if stage is UploadStage.PROCESSING:
        transitions = record.get("transitions")
        if not isinstance(transitions, list):
            raise MiloviTokenRolloutBlocked("Canary transition ledger is invalid")
        transitions.append(
            {
                "from": UploadStage.PROCESSING.value,
                "to": UploadStage.VERIFIED.value,
                "at": now,
                "evidence": {
                    "assessment": assessment.as_dict(),
                    "wall_delta": delta.as_dict(),
                    "reconciliation": "exact_processing_remote_readback",
                },
            }
        )
        record["stage"] = UploadStage.VERIFIED.value
        record["updated_at"] = now
    record["last_error"] = None
    item.update(
        {
            "status": "clip_verified",
            "clip_remote_id": EXPECTED_REMOTE_ID,
            "clip_origin": "reconciled_exact_processing_remote",
        }
    )
    write_json_atomic(journal_path, journal)
    result.update(
        {
            "status": "canary_clip_verified_local_reconciliation",
            "journal_updated": True,
            "upload_stage": UploadStage.VERIFIED.value,
            "canary_verified": False,
            "next_operation": "postponed_wall_then_remaining_11",
        }
    )
    write_json_atomic(output_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only VK reconciliation for the exact Milovi #323 canary")
    parser.add_argument("--execute", required=True)
    parser.add_argument(
        "--journal",
        type=Path,
        default=Path("data/vk/milovi-cake/issue-323-token-daily-rollout-journal.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("operator-output/milovi-cake-issue-323-canary-reconciliation.json"),
    )
    args = parser.parse_args()
    if args.execute != EXECUTION_CONFIRMATION:
        raise MiloviTokenRolloutBlocked(f"Exact confirmation required: {EXECUTION_CONFIRMATION}")
    result = reconcile_canary(journal_path=args.journal, output_path=args.output)
    print(f"Milovi #323 canary: {result['status']} | remote={EXPECTED_REMOTE_ID} | provider_mutation=false")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (MiloviTokenRolloutBlocked, OSError, ValueError) as exc:
        print(f"STOP: {type(exc).__name__}: {exc}")
        raise SystemExit(3) from exc


__all__ = [
    "EXECUTION_CONFIRMATION",
    "EXPECTED_REMOTE_ID",
    "normalize_current_wall_to_historical_capture",
    "reconcile_canary",
]
