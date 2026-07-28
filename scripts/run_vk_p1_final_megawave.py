#!/usr/bin/env python3
"""Run the final all-in-one VK P1 migration and create one verified handoff ZIP."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import sys
import time
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk import VkApiClient, VkInventoryService, VkTokenStore
from video_channel_manager.platforms.vk.editorial_final_megawave import (
    build_final_megawave_plan,
    verify_final_megawave_plan,
)
from video_channel_manager.platforms.vk.editorial_writer import VkEditorialWriter
from video_channel_manager.platforms.vk.lock import local_vk_write_lock
from video_channel_manager.platforms.vk.text_writer import canonical_vk_text
from verify_vk_reviewed_correction_pushkin_cloud_apply_bundle import (
    verify_bundle as verify_pushkin_cloud_apply,
)

_REQUIRED_COUNTS = {
    "target_videos": 42,
    "descriptions_to_update": 42,
    "titles_to_update": 3,
    "albums_to_rename": 3,
    "placements_to_add": 32,
    "total_operations": 77,
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-apply-bundle", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--account", default="legendary-poet")
    parser.add_argument("--community", type=int, default=235216998)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--write-delay", type=float, default=1.0)
    parser.add_argument("--output-dir", type=Path)
    return parser


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _json_bytes(raw: bytes, *, name: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot decode JSON {name}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {name}")
    return payload


def _sha256_bytes(raw: bytes) -> str:
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _extract_verified_source(
    source_apply: Path,
    policy: dict[str, Any],
) -> tuple[dict[str, Any], bytes, dict[str, Any]]:
    expected_sha = str(policy.get("source_apply_bundle_sha256") or "")
    actual_sha = _sha256_file(source_apply)
    if actual_sha != expected_sha:
        raise ValueError(f"Source apply SHA differs: expected {expected_sha}, actual {actual_sha}")

    source_verification = verify_pushkin_cloud_apply(source_apply)
    if source_verification.get("status") != "verified_completed":
        raise ValueError("Pushkin Cloud source apply is not independently verified")

    with zipfile.ZipFile(source_apply) as archive:
        names = [entry.filename for entry in archive.infolist()]
        if len(names) != len(set(names)):
            raise ValueError("Source apply ZIP contains duplicate entries")
        source_snapshot = _json_bytes(archive.read("04-final-vk-snapshot.json"), name="04-final-vk-snapshot.json")
        review_bundle = archive.read("source-review-bundle.zip")
    return source_snapshot, review_bundle, source_verification


def _verify_review_bundle(
    raw_bundle: bytes,
    policy: dict[str, Any],
    source_snapshot: dict[str, Any],
) -> dict[str, Any]:
    expected_sha = str(policy.get("source_review_bundle_sha256") or "")
    actual_sha = _sha256_bytes(raw_bundle)
    if actual_sha != expected_sha:
        raise ValueError(f"Source review bundle SHA differs: expected {expected_sha}, actual {actual_sha}")

    with zipfile.ZipFile(io.BytesIO(raw_bundle)) as archive:
        names = [entry.filename for entry in archive.infolist()]
        if len(names) != len(set(names)):
            raise ValueError("Source review bundle contains duplicate entries")
        manifest = _json_bytes(archive.read("manifest.json"), name="manifest.json")
        queue = _json_bytes(archive.read("review-queue.json"), name="review-queue.json")
        for item in manifest.get("files", []):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "")
            content = archive.read(name)
            if len(content) != int(item.get("size_bytes", -1)):
                raise ValueError(f"Source review size mismatch: {name}")
            if _sha256_bytes(content) != str(item.get("sha256") or ""):
                raise ValueError(f"Source review SHA mismatch: {name}")

    if manifest.get("status") != "review_only_completed" or int(manifest.get("remote_writes", -1)) != 0:
        raise ValueError("Source review manifest is not completed review-only")
    if queue.get("mode") != "review_only" or int(queue.get("remote_writes", -1)) != 0:
        raise ValueError("Source review queue is not review-only")

    source_videos = {
        str(item["ref"]["remote_id"]): item
        for item in source_snapshot.get("videos", [])
        if isinstance(item, dict)
    }
    target_ids = {str(item["video_id"]) for item in policy.get("targets", []) if isinstance(item, dict)}
    seen: set[str] = set()
    for unit in queue.get("research_units", []):
        if not isinstance(unit, dict):
            continue
        for item in unit.get("videos", []):
            if not isinstance(item, dict):
                continue
            remote_id = str(item.get("video_id") or "")
            if remote_id not in target_ids:
                continue
            if unit.get("priority") != "P1":
                raise ValueError(f"Final megawave target is not active P1: {remote_id}")
            source_video = source_videos.get(remote_id)
            if source_video is None:
                raise ValueError(f"Final megawave target is absent from source snapshot: {remote_id}")
            if canonical_vk_text(str(unit.get("description") or "")) != canonical_vk_text(
                str(source_video.get("description") or "")
            ):
                raise ValueError(f"Review queue description differs from source snapshot: {remote_id}")
            seen.add(remote_id)
    missing = sorted(target_ids - seen)
    if missing:
        raise ValueError(f"Final megawave targets missing from active P1 queue: {missing}")
    return {
        "status": "verified",
        "bundle_sha256": actual_sha,
        "active_p1_targets": len(seen),
        "remote_writes": 0,
    }


def _snapshot_dict(audit: Any) -> dict[str, Any]:
    payload = audit.model_dump(mode="json")
    if not isinstance(payload, dict):
        raise ValueError("VK audit package did not serialize to an object")
    return payload


def _video_map(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item["ref"]["remote_id"]): item for item in snapshot.get("videos", [])}


def _collection_map(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item["ref"]["remote_id"]): item for item in snapshot.get("collections", [])}


def _membership_pairs(snapshot: dict[str, Any]) -> set[tuple[str, str]]:
    return {
        (str(item["collection_ref"]["remote_id"]), str(item["video_ref"]["remote_id"]))
        for item in snapshot.get("memberships", [])
    }


def _parse_remote_id(remote_id: str) -> tuple[int, int]:
    owner_text, separator, video_text = remote_id.partition("_")
    if not separator:
        raise ValueError(f"Invalid VK video ID: {remote_id}")
    owner_id = int(owner_text)
    video_id = int(video_text)
    if owner_id == 0 or video_id <= 0:
        raise ValueError(f"Invalid VK video ID: {remote_id}")
    return owner_id, video_id


def _preflight(source: dict[str, Any], live: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    source_videos = _video_map(source)
    live_videos = _video_map(live)
    source_collections = _collection_map(source)
    live_collections = _collection_map(live)
    source_memberships = _membership_pairs(source)
    live_memberships = _membership_pairs(live)
    planned_additions = {
        (str(item["target_collection_id"]), str(item["target_video_id"]))
        for item in plan.get("placement_operations", [])
    }

    global_conflicts: list[str] = []
    if set(source_videos) != set(live_videos):
        global_conflicts.append("video inventory differs from verified source")
    if set(source_collections) != set(live_collections):
        global_conflicts.append("collection inventory differs from verified source")
    missing_memberships = sorted(source_memberships - live_memberships)
    unexpected_memberships = sorted(live_memberships - source_memberships - planned_additions)
    if missing_memberships:
        global_conflicts.append(f"source memberships removed: {missing_memberships[:5]}")
    if unexpected_memberships:
        global_conflicts.append(f"unexpected memberships added: {unexpected_memberships[:5]}")

    states: list[dict[str, Any]] = []
    for operation in plan.get("video_text_operations", []):
        remote_id = str(operation["target_video_id"])
        video = live_videos.get(remote_id)
        if video is None:
            state, detail = "conflict", "target video is absent"
        else:
            title = canonical_vk_text(str(video.get("title") or ""))
            description = canonical_vk_text(str(video.get("description") or ""))
            before = title == operation["before_title"] and description == operation["before_description"]
            after = title == operation["after_title"] and description == operation["after_description"]
            if after:
                state, detail = "already_applied", "live text equals final after-state"
            elif before:
                state, detail = "ready", "live text equals verified source state"
            else:
                state, detail = "conflict", "live text is neither before-state nor after-state"
        states.append({"operation_id": operation["operation_id"], "kind": "video_text", "state": state, "detail": detail})

    for operation in plan.get("album_title_operations", []):
        collection_id = str(operation["target_collection_id"])
        collection = live_collections.get(collection_id)
        if collection is None:
            state, detail = "conflict", "target album is absent"
        else:
            title = canonical_vk_text(str(collection.get("title") or ""))
            if title == operation["after_title"]:
                state, detail = "already_applied", "live album title equals final after-state"
            elif title == operation["before_title"]:
                state, detail = "ready", "live album title equals verified source state"
            else:
                state, detail = "conflict", "live album title is neither before-state nor after-state"
        states.append({"operation_id": operation["operation_id"], "kind": "album_title", "state": state, "detail": detail})

    for operation in plan.get("placement_operations", []):
        pair = (str(operation["target_collection_id"]), str(operation["target_video_id"]))
        if pair in live_memberships:
            state, detail = "already_applied", "video is already present in the final VK playlist"
        else:
            state, detail = "ready", "expected VK playlist membership is absent"
        states.append({"operation_id": operation["operation_id"], "kind": "placement_add", "state": state, "detail": detail})

    counts = Counter(item["state"] for item in states)
    return {
        "status": "conflict" if global_conflicts or counts["conflict"] else "ready",
        "global_conflicts": global_conflicts,
        "states": states,
        "ready": counts["ready"],
        "already_applied": counts["already_applied"],
        "conflicts": counts["conflict"] + len(global_conflicts),
        "source_memberships": len(source_memberships),
        "live_memberships": len(live_memberships),
        "planned_additions": len(planned_additions),
    }


def _state_by_id(preflight: dict[str, Any]) -> dict[str, str]:
    return {str(item["operation_id"]): str(item["state"]) for item in preflight["states"]}


def _verify_final_state(source: dict[str, Any], final: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    source_videos = _video_map(source)
    final_videos = _video_map(final)
    source_collections = _collection_map(source)
    final_collections = _collection_map(final)
    source_memberships = _membership_pairs(source)
    expected_additions = {
        (str(item["target_collection_id"]), str(item["target_video_id"]))
        for item in plan.get("placement_operations", [])
    }
    expected_memberships = source_memberships | expected_additions
    final_memberships = _membership_pairs(final)

    if set(source_videos) != set(final_videos) or len(final_videos) != 111:
        raise ValueError("Final video inventory differs from the verified 111-video source")
    if set(source_collections) != set(final_collections) or len(final_collections) != 17:
        raise ValueError("Final collection inventory differs from the verified 17-collection source")

    video_operations = {str(item["target_video_id"]): item for item in plan["video_text_operations"]}
    for remote_id, before in source_videos.items():
        after = final_videos[remote_id]
        operation = video_operations.get(remote_id)
        if operation is None:
            if canonical_vk_text(str(before.get("title") or "")) != canonical_vk_text(str(after.get("title") or "")):
                raise ValueError(f"Non-target title changed: {remote_id}")
            if canonical_vk_text(str(before.get("description") or "")) != canonical_vk_text(str(after.get("description") or "")):
                raise ValueError(f"Non-target description changed: {remote_id}")
        else:
            if canonical_vk_text(str(after.get("title") or "")) != operation["after_title"]:
                raise ValueError(f"Final target title differs from plan: {remote_id}")
            if canonical_vk_text(str(after.get("description") or "")) != operation["after_description"]:
                raise ValueError(f"Final target description differs from plan: {remote_id}")

    album_operations = {str(item["target_collection_id"]): item for item in plan["album_title_operations"]}
    for collection_id, before in source_collections.items():
        after = final_collections[collection_id]
        operation = album_operations.get(collection_id)
        expected_title = operation["after_title"] if operation else canonical_vk_text(str(before.get("title") or ""))
        if canonical_vk_text(str(after.get("title") or "")) != expected_title:
            raise ValueError(f"Final album title differs from plan: {collection_id}")
        if before.get("metadata", {}).get("share_url") != after.get("metadata", {}).get("share_url"):
            raise ValueError(f"VK playlist share URL changed unexpectedly: {collection_id}")

    if final_memberships != expected_memberships:
        missing = sorted(expected_memberships - final_memberships)
        extra = sorted(final_memberships - expected_memberships)
        raise ValueError(f"Final memberships differ: missing={missing[:5]} extra={extra[:5]}")

    return {
        "status": "verified_completed",
        "plan_sha256": plan["plan_sha256"],
        "videos": 111,
        "collections": 17,
        "source_memberships": len(source_memberships),
        "added_memberships": len(expected_additions),
        "final_memberships": len(final_memberships),
        "target_descriptions_verified": 42,
        "target_titles_changed": int(plan["summary"]["titles_to_update"]),
        "album_titles_changed": int(plan["summary"]["albums_to_rename"]),
        "non_target_videos_verified_unchanged": 69,
        "playlist_share_urls_unchanged": True,
    }


def _plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# VK P1 final all-in-one megawave",
        "",
        f"- Decision set: `{plan['decision_set_id']}`",
        f"- Plan: `{plan['plan_sha256']}`",
        f"- Target descriptions: **{plan['summary']['descriptions_to_update']}**",
        f"- Title corrections: **{plan['summary']['titles_to_update']}**",
        f"- Album title normalizations: **{plan['summary']['albums_to_rename']}**",
        f"- Missing VK playlist placements: **{plan['summary']['placements_to_add']}**",
        f"- Total guarded operations: **{plan['summary']['total_operations']}**",
        "",
        "## Video text operations",
        "",
    ]
    for operation in plan["video_text_operations"]:
        lines.extend([
            f"### {operation['after_title']}",
            "",
            f"- Video: `{operation['target_video_id']}`",
            f"- Title changed: `{operation['title_changed']}`",
            f"- Description: `{operation['before_description_sha256']}` → `{operation['after_description_sha256']}`",
            f"- Poem blocks preserved: `{operation['metadata']['poem_blocks_preserved']}`",
            f"- VK playlists: {', '.join(operation['metadata']['playlist_urls'])}",
            "",
        ])
    lines.extend(["## Playlist placements", ""])
    for operation in plan["placement_operations"]:
        lines.append(f"- `{operation['target_video_id']}` → album `{operation['target_collection_id']}`")
    return "\n".join(lines).rstrip() + "\n"


def _write_manifest(bundle_dir: Path, metadata: dict[str, Any]) -> None:
    files = []
    for path in sorted(bundle_dir.iterdir(), key=lambda value: value.name):
        if not path.is_file() or path.name == "manifest.json":
            continue
        files.append({"name": path.name, "size_bytes": path.stat().st_size, "sha256": _sha256_file(path)})
    _atomic_json(bundle_dir / "manifest.json", {**metadata, "files": files})


def _package(bundle_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(bundle_dir.iterdir(), key=lambda value: value.name):
            if path.is_file():
                archive.write(path, arcname=path.name)


def run(args: argparse.Namespace) -> Path:
    if not args.execute:
        raise ValueError("The final megawave requires the explicit --execute flag")
    if args.write_delay < 0:
        raise ValueError("--write-delay cannot be negative")

    policy = _load_json(args.policy)
    if int(policy.get("target_community_id", 0)) != args.community:
        raise ValueError("--community differs from the final megawave policy")

    settings = get_settings()
    output_dir = args.output_dir or settings.data_dir / "handoffs"
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    bundle_name = f"vk-p1-final-megawave-apply-{stamp}"
    bundle_dir = output_dir / bundle_name
    zip_path = output_dir / f"{bundle_name}.zip"
    bundle_dir.mkdir(parents=True, exist_ok=False)

    status = "started"
    error: str | None = None
    plan: dict[str, Any] | None = None
    preflight: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    verification: dict[str, Any] | None = None

    try:
        source_apply = args.source_apply_bundle.resolve(strict=True)
        source_snapshot, review_bundle_raw, source_verification = _extract_verified_source(source_apply, policy)
        review_verification = _verify_review_bundle(review_bundle_raw, policy, source_snapshot)
        plan = build_final_megawave_plan(source_snapshot, policy)
        verify_final_megawave_plan(source_snapshot, policy, plan)
        for key, expected in _REQUIRED_COUNTS.items():
            actual = int(plan["summary"].get(key, -1))
            if actual != expected:
                raise ValueError(f"Final megawave {key} differs: expected {expected}, actual {actual}")

        _atomic_json(bundle_dir / "00-source-vk-snapshot.json", source_snapshot)
        _atomic_json(bundle_dir / "01-plan.json", plan)
        (bundle_dir / "02-plan-review.md").write_text(_plan_markdown(plan), encoding="utf-8")
        _atomic_json(bundle_dir / "03-source-apply-verification.json", source_verification)
        _atomic_json(bundle_dir / "04-source-review-verification.json", review_verification)
        shutil.copy2(args.policy, bundle_dir / "final-megawave-policy.json")
        shutil.copy2(source_apply, bundle_dir / "source-pushkin-cloud-apply.zip")
        (bundle_dir / "source-review-bundle.zip").write_bytes(review_bundle_raw)

        store = VkTokenStore(settings.data_dir)
        reader = VkApiClient(token_store=store, account_alias=args.account, api_version=settings.vk_api_version)
        community = reader.get_community(str(args.community))
        if int(community.ref.channel_id) != args.community or not bool(community.metadata.get("managed_by_token")):
            raise ValueError("The VK token does not manage the exact final megawave community")

        live = _snapshot_dict(VkInventoryService(reader).build_audit_package(args.community))
        preflight = _preflight(source_snapshot, live, plan)
        _atomic_json(bundle_dir / "05-preflight.json", preflight)
        print(
            "VK P1 FINAL MEGAWAVE PREFLIGHT\n"
            f"  plan: {plan['plan_sha256']}\n"
            f"  total operations: {plan['summary']['total_operations']}\n"
            f"  ready: {preflight['ready']}\n"
            f"  already applied: {preflight['already_applied']}\n"
            f"  conflicts: {preflight['conflicts']}"
        )
        if preflight["conflicts"]:
            raise ValueError(f"Final megawave preflight conflicts: {preflight['global_conflicts']}")

        lock_path = settings.data_dir / "locks" / f"vk-{args.account}-{args.community}.lock"
        with local_vk_write_lock(lock_path, account=args.account, community_id=args.community, operation="apply-vk-p1-final-megawave"):
            locked_live = _snapshot_dict(VkInventoryService(reader).build_audit_package(args.community))
            locked_preflight = _preflight(source_snapshot, locked_live, plan)
            if locked_preflight["conflicts"] or locked_preflight["ready"] != preflight["ready"] or locked_preflight["already_applied"] != preflight["already_applied"]:
                raise RuntimeError("Locked re-preflight differs from confirmed final megawave preflight")
            states = _state_by_id(locked_preflight)
            writer = VkEditorialWriter(token_store=store, account_alias=args.account, api_version=settings.vk_api_version)
            result = {
                "schema_name": "video-manager.vk-p1-final-megawave-result",
                "schema_version": 1,
                "status": "running",
                "started_at": datetime.now(UTC).isoformat(),
                "plan_sha256": plan["plan_sha256"],
                "community_id": args.community,
                "operations": [],
            }
            _atomic_json(bundle_dir / "06-result.json", result)

            for operation in plan["video_text_operations"]:
                operation_id = str(operation["operation_id"])
                if states[operation_id] == "already_applied":
                    item = {"operation_id": operation_id, "kind": "video_text", "status": "already_applied"}
                else:
                    owner_id, video_id = _parse_remote_id(str(operation["target_video_id"]))
                    updated = writer.replace_text_if_current(
                        owner_id=owner_id,
                        video_id=video_id,
                        expected_title=str(operation["before_title"]),
                        expected_description=str(operation["before_description"]),
                        new_title=str(operation["after_title"]),
                        new_description=str(operation["after_description"]),
                    )
                    item = {"operation_id": operation_id, "kind": "video_text", "status": "updated_and_verified", "remote_id": updated.remote_id}
                result["operations"].append(item)
                _atomic_json(bundle_dir / "06-result.json", result)
                if args.write_delay:
                    time.sleep(args.write_delay)

            for operation in plan["album_title_operations"]:
                operation_id = str(operation["operation_id"])
                if states[operation_id] == "already_applied":
                    item = {"operation_id": operation_id, "kind": "album_title", "status": "already_applied"}
                else:
                    writer.rename_album(community_id=args.community, album_id=int(operation["target_collection_id"]), title=str(operation["after_title"]))
                    item = {"operation_id": operation_id, "kind": "album_title", "status": "updated_pending_postflight", "album_id": int(operation["target_collection_id"])}
                result["operations"].append(item)
                _atomic_json(bundle_dir / "06-result.json", result)
                if args.write_delay:
                    time.sleep(args.write_delay)

            for operation in plan["placement_operations"]:
                operation_id = str(operation["operation_id"])
                if states[operation_id] == "already_applied":
                    item = {"operation_id": operation_id, "kind": "placement_add", "status": "already_applied"}
                else:
                    owner_id, video_id = _parse_remote_id(str(operation["target_video_id"]))
                    changed = writer.add_to_album(
                        community_id=args.community,
                        album_id=int(operation["target_collection_id"]),
                        owner_id=owner_id,
                        video_id=video_id,
                    )
                    item = {
                        "operation_id": operation_id,
                        "kind": "placement_add",
                        "status": "updated_and_verified" if changed else "already_applied",
                        "album_id": int(operation["target_collection_id"]),
                        "video_id": str(operation["target_video_id"]),
                    }
                result["operations"].append(item)
                _atomic_json(bundle_dir / "06-result.json", result)
                if args.write_delay:
                    time.sleep(args.write_delay)

            final_snapshot = _snapshot_dict(VkInventoryService(reader).build_audit_package(args.community))
            _atomic_json(bundle_dir / "07-final-vk-snapshot.json", final_snapshot)
            verification = _verify_final_state(source_snapshot, final_snapshot, plan)
            _atomic_json(bundle_dir / "08-independent-verification.json", verification)
            result["status"] = "completed"
            result["completed_at"] = datetime.now(UTC).isoformat()
            result["operation_statuses"] = dict(Counter(str(item["status"]) for item in result["operations"]))
            _atomic_json(bundle_dir / "06-result.json", result)

        status = "completed"
        readme = (
            "VK P1 FINAL ALL-IN-ONE MEGAWAVE — APPLY\n\n"
            f"Status: {status}\n"
            f"Decision set: {policy['decision_set_id']}\n"
            f"Plan: {plan['plan_sha256']}\n"
            "Descriptions rewritten: 42\n"
            "Misleading titles corrected: 3\n"
            "Album titles normalized: 3\n"
            "Missing VK playlist memberships added: 32\n"
            "Total guarded operations: 77\n\n"
            "All target descriptions now use VK-native playlist links, the canonical https://thelegendarypoet.ru site links, canonical project channels, standardized hashtags, full-version links for short videos, and rights notices for modern copyrighted works.\n"
        )
        (bundle_dir / "README.txt").write_text(readme, encoding="utf-8")
    except Exception as exc:
        status = "failed"
        error = str(exc)
        _atomic_json(bundle_dir / "ERROR.json", {"status": status, "error": error, "created_at": datetime.now(UTC).isoformat()})
    finally:
        manifest_metadata = {
            "schema_name": "video-manager.vk-p1-final-megawave-handoff",
            "schema_version": 1,
            "created_at": datetime.now(UTC).isoformat(),
            "status": status,
            "mode": "apply",
            "decision_set_id": str(policy.get("decision_set_id") or ""),
            "community_id": args.community,
            "plan_sha256": plan.get("plan_sha256") if plan else None,
            "ready": preflight.get("ready") if preflight else None,
            "already_applied": preflight.get("already_applied") if preflight else None,
            "conflicts": preflight.get("conflicts") if preflight else None,
            "verification_status": verification.get("status") if verification else None,
            "error": error,
        }
        _write_manifest(bundle_dir, manifest_metadata)
        _package(bundle_dir, zip_path)
        shutil.rmtree(bundle_dir, ignore_errors=True)

    print(zip_path)
    if status != "completed":
        raise RuntimeError(error or "Final megawave failed")
    return zip_path


def main() -> int:
    args = _parser().parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, OSError, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        raise SystemExit(2) from exc
