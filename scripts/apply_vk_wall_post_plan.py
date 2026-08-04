#!/usr/bin/env python3
"""Dry-run or publish exactly one reviewed VK wall post with duplicate protection."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk import VkApiClient, VkTokenStore
from video_channel_manager.platforms.vk.lock import local_vk_write_lock
from video_channel_manager.platforms.vk.text_writer import canonical_vk_text
from video_channel_manager.platforms.vk.wall import VkWallWriter, validate_vk_wall_post_plan
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
    parser.add_argument("--confirm-video")
    parser.add_argument("--confirm-plan-sha256")
    parser.add_argument("--confirm-message-sha256")
    parser.add_argument("--confirm-duplicate-count", type=int)
    parser.add_argument("--max-wall-scan", type=int, default=500)
    parser.add_argument("--result-output", type=Path)
    return parser


def _load_plan(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read VK wall post plan {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("VK wall post plan must be a JSON object")
    validate_vk_wall_post_plan(payload)
    return payload


def _atomic_write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _live_preflight(plan: dict[str, Any], writer: VkWallWriter, max_wall_scan: int) -> dict[str, Any]:
    video = writer.read_video(owner_id=plan["video_owner_id"], video_id=plan["video_id"])
    if video is None:
        raise ValueError(f"VK video {plan['video_remote_id']} is not visible")
    title = canonical_vk_text(str(video.get("title") or ""))
    description = canonical_vk_text(str(video.get("description") or ""))
    if title != plan["expected_video_title"]:
        raise ValueError("Live VK video title differs from the reviewed wall plan")
    if description != plan["expected_video_description"]:
        raise ValueError("Live VK video description differs from the reviewed wall plan")
    duplicates = writer.find_video_posts(
        community_id=plan["target_community_id"],
        video_owner_id=plan["video_owner_id"],
        video_id=plan["video_id"],
        max_posts=max_wall_scan,
    )
    return {
        "title": title,
        "description": description,
        "duplicate_count": len(duplicates),
        "duplicate_post_ids": sorted(item["id"] for item in duplicates if isinstance(item.get("id"), int)),
    }


def main() -> int:
    args = _parser().parse_args()
    if args.max_wall_scan <= 0:
        raise SystemExit("--max-wall-scan must be positive")
    plan = _load_plan(args.plan)
    if args.community != plan["target_community_id"]:
        raise SystemExit("--community differs from the reviewed wall plan target")

    settings = get_settings()
    store = VkTokenStore(settings.data_dir)
    reader = VkApiClient(token_store=store, account_alias=args.account, api_version=settings.vk_api_version)
    community = reader.get_community(str(args.community))
    if int(community.ref.channel_id) != args.community or not bool(community.metadata.get("managed_by_token")):
        raise SystemExit("The token does not manage the exact reviewed VK community")
    writer = VkWallWriter(token_store=store, account_alias=args.account, api_version=settings.vk_api_version)

    preflight = _live_preflight(plan, writer, args.max_wall_scan)
    print(
        "VK wall post preflight:\n"
        f"  community: {args.community} — {community.title}\n"
        f"  video: {plan['video_remote_id']}\n"
        f"  title: {preflight['title']}\n"
        f"  duplicate posts found: {preflight['duplicate_count']}\n"
        f"  message sha256: {plan['message_sha256']}\n"
        f"  plan sha256: {plan['plan_sha256']}\n"
        f"  guid: {plan['guid']}"
    )
    if preflight["duplicate_post_ids"]:
        print(f"  duplicate post IDs: {preflight['duplicate_post_ids']}")
    if preflight["duplicate_count"]:
        raise SystemExit("The video is already present on the scanned community wall; publication is blocked.")
    if not args.execute:
        print("Dry-run only. wall.post was not called.")
        print("Execute requires exact community, video ID, plan/message SHA-256 and duplicate count 0.")
        return 0

    confirmations = {
        "community": args.confirm_community == args.community,
        "video": args.confirm_video == plan["video_remote_id"],
        "plan": args.confirm_plan_sha256 == plan["plan_sha256"],
        "message": args.confirm_message_sha256 == plan["message_sha256"],
        "duplicates": args.confirm_duplicate_count == preflight["duplicate_count"] == 0,
    }
    failed = [name for name, valid in confirmations.items() if not valid]
    if failed:
        raise SystemExit(f"Execution confirmation mismatch: {', '.join(failed)}")

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    result_output = args.result_output or settings.data_dir / "reports" / f"vk-wall-post-{timestamp}.json"
    result: dict[str, Any] = {
        "schema_name": "video-manager.vk-wall-post-result",
        "schema_version": 1,
        "started_at": datetime.now(UTC).isoformat(),
        "community_id": args.community,
        "video_remote_id": plan["video_remote_id"],
        "plan_sha256": plan["plan_sha256"],
        "message_sha256": plan["message_sha256"],
        "guid": plan["guid"],
        "status": "running",
    }
    _atomic_write(result_output, result)

    lock_path = settings.data_dir / "locks" / f"vk-{args.account}-{args.community}.lock"
    try:
        with local_vk_write_lock(
            lock_path,
            account=args.account,
            community_id=args.community,
            operation="publish-reviewed-vk-wall-post",
        ):
            locked_preflight = _live_preflight(plan, writer, args.max_wall_scan)
            if locked_preflight["duplicate_count"] != 0:
                raise RuntimeError("A duplicate appeared after lock acquisition; wall.post was not called")
            published = writer.post_video(
                community_id=args.community,
                video_owner_id=plan["video_owner_id"],
                video_id=plan["video_id"],
                message=plan["message"],
                guid=plan["guid"],
            )
            result.update(
                {
                    "status": "completed",
                    "completed_at": datetime.now(UTC).isoformat(),
                    "wall_post_remote_id": published.remote_id,
                    "wall_post_id": published.post_id,
                    "wall_url": f"https://vk.com/wall{published.remote_id}",
                }
            )
            _atomic_write(result_output, result)
    except (ValueError, OSError, RuntimeError, VkWriteError, KeyboardInterrupt) as exc:
        result["status"] = "failed"
        result["failed_at"] = datetime.now(UTC).isoformat()
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["recovery"] = (
            "Do not blindly retry wall.post. Re-run dry-run first: it reconciles the wall by the exact video attachment."
        )
        _atomic_write(result_output, result)
        if isinstance(exc, KeyboardInterrupt):
            raise
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"VK wall post published and verified. Result → {result_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
