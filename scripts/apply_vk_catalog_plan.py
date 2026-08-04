#!/usr/bin/env python3
"""Dry-run or apply a reviewed VK catalog plan with locked live re-preflight."""

from __future__ import annotations

import argparse
import json
from collections import Counter
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.application.cross_platform import normalize_title
from video_channel_manager.config import get_settings
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk import VkApiClient, VkInventoryService, VkTokenStore
from video_channel_manager.platforms.vk.catalog import target_video_ids_sha256, validate_vk_catalog_plan
from video_channel_manager.platforms.vk.lock import local_vk_write_lock
from video_channel_manager.platforms.vk.text_writer import VkVideoTextWriter, canonical_vk_text
from video_channel_manager.platforms.vk.writer import VkWriteError

_WAVE6_RETIRED_EXECUTOR = True
if __name__ == "__main__":
    raise SystemExit(
        "This historical executor is retired by Wave 6. "
        "Use the versioned `video-manager wave` engine through the reviewed operator contract."
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--account", default="legendary-poet")
    parser.add_argument("--community", type=int, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-community", type=int)
    parser.add_argument("--confirm-ready", type=int)
    parser.add_argument("--confirm-plan-sha256")
    parser.add_argument("--confirm-video-coverage")
    parser.add_argument("--max-operations", type=int, default=500)
    parser.add_argument("--write-delay", type=float, default=2.0)
    parser.add_argument("--result-output", type=Path)
    return parser


def _load_plan(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read VK catalog plan {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("VK catalog plan must be a JSON object")
    validate_vk_catalog_plan(payload)
    return payload


def _atomic_write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _parse_remote_id(remote_id: str) -> tuple[int, int]:
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


def _is_system_collection(collection: Any) -> bool:
    raw_id = collection.metadata.get("id")
    return (
        collection.privacy_status == "system"
        or collection.ref.remote_id.startswith("-")
        or isinstance(raw_id, int)
        and raw_id < 0
        or bool(collection.metadata.get("is_system"))
    )


def _live_indexes(live: AuditPackage) -> tuple[dict[str, Any], dict[str, list[Any]], set[tuple[str, str]]]:
    videos = {item.ref.remote_id: item for item in live.videos}
    collections: dict[str, list[Any]] = {}
    for collection in live.collections:
        if _is_system_collection(collection):
            continue
        collections.setdefault(normalize_title(collection.title), []).append(collection)
    memberships = {
        (membership.collection_ref.remote_id, membership.video_ref.remote_id) for membership in live.memberships
    }
    return videos, collections, memberships


def _preflight(plan: dict[str, Any], live: AuditPackage) -> dict[str, Any]:
    coverage = target_video_ids_sha256(live)
    if coverage != plan["target_video_ids_sha256"]:
        raise ValueError(
            "Live VK video coverage differs from the reviewed plan. Create a fresh scan and rebuild the plan."
        )
    videos, collections, memberships = _live_indexes(live)
    states: list[dict[str, Any]] = []
    album_resolution: dict[str, str] = {}

    for operation in plan["album_operations"]:
        candidates = collections.get(operation["normalized_title"], [])
        if len(candidates) > 1:
            state = "conflict"
            detail = "multiple live albums have the planned normalized title"
        elif len(candidates) == 1:
            state = "already_applied"
            detail = candidates[0].ref.remote_id
            album_resolution[operation["source_collection_id"]] = candidates[0].ref.remote_id
        else:
            state = "ready"
            detail = "album absent"
        states.append({"operation_id": operation["operation_id"], "kind": "album", "state": state, "detail": detail})

    for operation in plan["placement_operations"]:
        target_video_id = operation["target_video_id"]
        if target_video_id not in videos:
            states.append(
                {
                    "operation_id": operation["operation_id"],
                    "kind": "placement",
                    "state": "conflict",
                    "detail": "target video is not visible",
                }
            )
            continue
        collection_id = operation.get("target_collection_id") or album_resolution.get(operation["source_collection_id"])
        if collection_id is None:
            normalized = normalize_title(operation["album_title"])
            candidates = collections.get(normalized, [])
            if len(candidates) == 1:
                collection_id = candidates[0].ref.remote_id
                album_resolution[operation["source_collection_id"]] = collection_id
            elif len(candidates) > 1:
                states.append(
                    {
                        "operation_id": operation["operation_id"],
                        "kind": "placement",
                        "state": "conflict",
                        "detail": "album title is ambiguous",
                    }
                )
                continue
        if collection_id is None:
            planned_album = any(
                item["source_collection_id"] == operation["source_collection_id"] for item in plan["album_operations"]
            )
            state = "ready" if planned_album else "conflict"
            detail = "ready after planned album creation" if planned_album else "target album is absent"
        elif (str(collection_id), target_video_id) in memberships:
            state = "already_applied"
            detail = str(collection_id)
        else:
            state = "ready"
            detail = str(collection_id)
        states.append(
            {
                "operation_id": operation["operation_id"],
                "kind": "placement",
                "state": state,
                "detail": detail,
            }
        )

    for operation in plan["text_operations"]:
        video = videos.get(operation["target_video_id"])
        if video is None:
            state = "conflict"
            detail = "target video is not visible"
        else:
            current_title = canonical_vk_text(video.title)
            current_description = canonical_vk_text(video.description)
            before = (
                current_title == operation["before_title"] and current_description == operation["before_description"]
            )
            after = current_title == operation["after_title"] and current_description == operation["after_description"]
            if after:
                state = "already_applied"
                detail = "live text equals reviewed after-state"
            elif before:
                state = "ready"
                detail = "live text equals reviewed before-state"
            else:
                state = "conflict"
                detail = "live text is neither reviewed before-state nor after-state"
        states.append({"operation_id": operation["operation_id"], "kind": "text", "state": state, "detail": detail})

    counts = Counter(item["state"] for item in states)
    return {
        "video_coverage_sha256": coverage,
        "states": states,
        "ready": counts["ready"],
        "already_applied": counts["already_applied"],
        "conflicts": counts["conflict"],
        "album_resolution": album_resolution,
    }


def _status_by_id(preflight: dict[str, Any]) -> dict[str, str]:
    return {item["operation_id"]: item["state"] for item in preflight["states"]}


def main() -> int:
    args = _parser().parse_args()
    if args.max_operations <= 0:
        raise SystemExit("--max-operations must be positive")
    if args.write_delay < 0:
        raise SystemExit("--write-delay cannot be negative")

    plan = _load_plan(args.plan)
    total_operations = int(plan["summary"]["total_operations"])
    if total_operations > args.max_operations:
        raise SystemExit(f"Plan has {total_operations} operations, above --max-operations {args.max_operations}.")
    if args.community != plan["target_community_id"]:
        raise SystemExit("--community differs from the reviewed plan target")

    settings = get_settings()
    store = VkTokenStore(settings.data_dir)
    reader = VkApiClient(token_store=store, account_alias=args.account, api_version=settings.vk_api_version)
    community = reader.get_community(str(args.community))
    if int(community.ref.channel_id) != args.community or not bool(community.metadata.get("managed_by_token")):
        raise SystemExit("The token does not manage the exact reviewed VK community.")

    print("Reading fresh live VK inventory…")
    live = VkInventoryService(reader).build_audit_package(args.community)
    preflight = _preflight(plan, live)
    print(
        "VK catalog preflight:\n"
        f"  plan: {plan['plan_sha256']}\n"
        f"  video coverage: {preflight['video_coverage_sha256']}\n"
        f"  ready: {preflight['ready']}\n"
        f"  already applied: {preflight['already_applied']}\n"
        f"  conflicts: {preflight['conflicts']}\n"
        f"  review-only excluded: {plan['summary']['review_only']}"
    )
    for item in preflight["states"]:
        print(f"  {item['state']:15} {item['operation_id']} — {item['detail']}")
    if preflight["conflicts"]:
        raise SystemExit("Conflicts must be resolved in a fresh reviewed plan before execution.")
    if not args.execute:
        print("Dry-run only. No VK mutation method was called.")
        print("Execute requires exact community, ready count, plan SHA-256 and video coverage SHA-256.")
        return 0

    confirmations = {
        "community": args.confirm_community == args.community,
        "ready": args.confirm_ready == preflight["ready"],
        "plan": args.confirm_plan_sha256 == plan["plan_sha256"],
        "coverage": args.confirm_video_coverage == preflight["video_coverage_sha256"],
    }
    failed = [name for name, valid in confirmations.items() if not valid]
    if failed:
        raise SystemExit(f"Execution confirmation mismatch: {', '.join(failed)}")

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    result_output = args.result_output or settings.data_dir / "reports" / f"vk-catalog-apply-{timestamp}.json"
    result: dict[str, Any] = {
        "schema_name": "video-manager.vk-catalog-apply-result",
        "schema_version": 1,
        "started_at": datetime.now(UTC).isoformat(),
        "plan_sha256": plan["plan_sha256"],
        "community_id": args.community,
        "status": "running",
        "operations": [],
    }
    _atomic_write(result_output, result)

    lock_path = settings.data_dir / "locks" / f"vk-{args.account}-{args.community}.lock"
    try:
        with local_vk_write_lock(
            lock_path,
            account=args.account,
            community_id=args.community,
            operation="apply-vk-catalog-plan",
        ):
            locked_live = VkInventoryService(reader).build_audit_package(args.community)
            locked_preflight = _preflight(plan, locked_live)
            if locked_preflight["conflicts"] or locked_preflight["ready"] != preflight["ready"]:
                raise RuntimeError("Locked re-preflight differs from the confirmed dry-run; no write was started.")
            states = _status_by_id(locked_preflight)
            writer = VkVideoTextWriter(
                token_store=store,
                account_alias=args.account,
                api_version=settings.vk_api_version,
            )
            album_resolution = dict(locked_preflight["album_resolution"])

            for operation in plan["album_operations"]:
                operation_id = operation["operation_id"]
                if states[operation_id] == "already_applied":
                    result["operations"].append({"operation_id": operation_id, "status": "already_applied"})
                    continue
                album_id = writer.create_album(community_id=args.community, title=operation["title"])
                album_resolution[operation["source_collection_id"]] = str(album_id)
                result["operations"].append(
                    {"operation_id": operation_id, "status": "created_and_verified", "album_id": album_id}
                )
                _atomic_write(result_output, result)
                if args.write_delay:
                    time.sleep(args.write_delay)

            for operation in plan["placement_operations"]:
                operation_id = operation["operation_id"]
                if states[operation_id] == "already_applied":
                    result["operations"].append({"operation_id": operation_id, "status": "already_applied"})
                    continue
                album_id_text = operation.get("target_collection_id") or album_resolution.get(
                    operation["source_collection_id"]
                )
                if album_id_text is None:
                    raise RuntimeError(f"Cannot resolve album for {operation_id}")
                owner_id, video_id = _parse_remote_id(operation["target_video_id"])
                added = writer.add_to_album(
                    community_id=args.community,
                    album_id=int(album_id_text),
                    owner_id=owner_id,
                    video_id=video_id,
                )
                result["operations"].append(
                    {
                        "operation_id": operation_id,
                        "status": "added_and_verified" if added else "already_applied",
                        "album_id": int(album_id_text),
                    }
                )
                _atomic_write(result_output, result)
                if added and args.write_delay:
                    time.sleep(args.write_delay)

            for operation in plan["text_operations"]:
                operation_id = operation["operation_id"]
                if states[operation_id] == "already_applied":
                    result["operations"].append({"operation_id": operation_id, "status": "already_applied"})
                    continue
                owner_id, video_id = _parse_remote_id(operation["target_video_id"])
                updated = writer.replace_text_if_current(
                    owner_id=owner_id,
                    video_id=video_id,
                    expected_title=operation["before_title"],
                    expected_description=operation["before_description"],
                    new_title=operation["after_title"],
                    new_description=operation["after_description"],
                )
                result["operations"].append(
                    {"operation_id": operation_id, "status": "updated_and_verified", "remote_id": updated.remote_id}
                )
                _atomic_write(result_output, result)
                if args.write_delay:
                    time.sleep(args.write_delay)

            final_live = VkInventoryService(reader).build_audit_package(args.community)
            final_preflight = _preflight(plan, final_live)
            if final_preflight["conflicts"] or final_preflight["ready"]:
                raise RuntimeError(
                    f"Final postflight failed: ready={final_preflight['ready']} conflicts={final_preflight['conflicts']}"
                )
            result["status"] = "completed"
            result["completed_at"] = datetime.now(UTC).isoformat()
            result["final_snapshot_id"] = str(final_live.snapshot_id)
            result["summary"] = {
                "operations": len(result["operations"]),
                "already_applied": final_preflight["already_applied"],
                "review_only_excluded": plan["summary"]["review_only"],
            }
            _atomic_write(result_output, result)
    except (ValueError, OSError, RuntimeError, VkWriteError, KeyboardInterrupt) as exc:
        result["status"] = "failed"
        result["failed_at"] = datetime.now(UTC).isoformat()
        result["error"] = f"{type(exc).__name__}: {exc}"
        _atomic_write(result_output, result)
        if isinstance(exc, KeyboardInterrupt):
            raise
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"VK catalog plan completed and postflight-verified. Result → {result_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
