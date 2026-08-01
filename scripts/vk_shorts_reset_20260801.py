from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

BASE_SCRIPT = Path(__file__).with_name("vk_shorts_reset.py")
SPEC = importlib.util.spec_from_file_location("vk_shorts_reset_base", BASE_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load base executor: {BASE_SCRIPT}")
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)

SOURCE_ID_RE = re.compile(r"YouTube\s+ID:\s*([A-Za-z0-9_-]{11})", re.IGNORECASE)
SHORT_URL_RE = re.compile(r"(?:youtube\.com/shorts/|youtu\.be/)([A-Za-z0-9_-]{11})", re.IGNORECASE)
PLAN_SCHEMA = "video-manager.vk-shorts-reset-20260801"
PLAN_VERSION = 2
OPERATION_ROOT_NAME = "vk-shorts-reset-20260801-v2"


def source_id(description: object) -> str | None:
    text = str(description or "")
    match = SOURCE_ID_RE.search(text)
    if match:
        return match.group(1)
    match = SHORT_URL_RE.search(text)
    return match.group(1) if match else None


def direct_video(post: dict[str, Any]) -> dict[str, Any] | None:
    if post.get("copy_history"):
        return None
    attachments = post.get("attachments")
    if not isinstance(attachments, list) or len(attachments) != 1:
        return None
    attachment = attachments[0]
    if not isinstance(attachment, dict) or attachment.get("type") != "video":
        return None
    video = attachment.get("video")
    return video if isinstance(video, dict) else None


def remote_id(video: dict[str, Any]) -> str | None:
    owner_id = video.get("owner_id")
    video_id = video.get("id")
    if not isinstance(owner_id, int) or not isinstance(video_id, int):
        return None
    return f"{owner_id}_{video_id}"


def operation_root(repo: Path) -> Path:
    return repo / "data" / OPERATION_ROOT_NAME


def write_jsonl(path: Path, rows: list[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(base.canonical_json(row) + "\n")


def state_from_attachment(video: dict[str, Any]) -> dict[str, Any]:
    state = base.video_state(video)
    state["youtube_id"] = source_id(video.get("description"))
    state["wall_post_id"] = video.get("wall_post_id")
    return state


def validate_post(
    post: dict[str, Any],
    row_by_remote: dict[str, dict[str, Any]],
    cutoff: int,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    post_id = post.get("id")
    if not isinstance(post_id, int) or post_id <= base.DEFAULT_BOUNDARY_POST:
        raise base.OperationError("post is outside the approved boundary")
    video = direct_video(post)
    if video is None:
        raise base.OperationError("post is not a simple one-video post")
    key = remote_id(video)
    if key is None or key not in row_by_remote:
        raise base.OperationError(f"video is not linked to the reviewed Shorts ledger: {key}")
    row = row_by_remote[key]
    state = state_from_attachment(video)
    if state["owner_id"] != base.EXPECTED_OWNER:
        raise base.OperationError(f"wrong video owner: {state['owner_id']}")
    if state["type"] != "short_video":
        raise base.OperationError(f"attachment is not short_video: {state['type']}")
    if state["youtube_id"] != row["youtube_id"]:
        raise base.OperationError(
            f"YouTube ID mismatch: attachment={state['youtube_id']} ledger={row['youtube_id']}"
        )
    views = state["views"]
    if not isinstance(views, int):
        raise base.OperationError("view count is unavailable")
    if views >= cutoff:
        raise base.OperationError(f"outside this operation's candidate filter: views={views}")
    actual_duration = state["duration"]
    expected_duration = row.get("duration_seconds")
    if (
        isinstance(actual_duration, int)
        and isinstance(expected_duration, int)
        and abs(actual_duration - expected_duration) > 2
    ):
        raise base.OperationError(
            f"duration mismatch: VK={actual_duration} YouTube={expected_duration}"
        )
    return row, state, video


def command_prepare(args: Any) -> int:
    repo = args.repo.resolve()
    if args.community != base.EXPECTED_COMMUNITY:
        raise base.OperationError("Wrong VK community")
    if args.boundary_post != base.DEFAULT_BOUNDARY_POST or args.view_cutoff != base.DEFAULT_VIEW_CUTOFF:
        raise base.OperationError("This dated operation has fixed boundary/candidate parameters")

    gateway = base.load_token_and_gateway(repo, args.account, args.community)
    rows = [
        row
        for row in base.load_legacy_rows(repo)
        if row.get("classification") == "confirmed_missing" and int(row.get("upload_attempted") or 0) == 1
    ]
    row_by_remote = {
        f"{int(row['vk_owner_id'])}_{int(row['vk_video_id'])}": row
        for row in rows
    }
    posts = gateway.wall_posts_after(base.EXPECTED_OWNER, args.boundary_post)

    wall_records: list[dict[str, Any]] = []
    candidates_by_remote: dict[str, dict[str, Any]] = {}
    conflicts: list[dict[str, Any]] = []
    wall_backup: list[object] = []
    clip_backup: list[object] = []

    for post in sorted(posts, key=lambda item: int(item.get("id") or 0)):
        wall_backup.append(post)
        post_id = post.get("id")
        try:
            row, state, video = validate_post(post, row_by_remote, args.view_cutoff)
        except base.OperationError as exc:
            conflicts.append({"post_id": post_id, "reason": str(exc)})
            continue

        key = str(state["remote_id"])
        clip_backup.append(video)
        wall_records.append(
            {
                "post_id": int(post_id),
                "owner_id": base.EXPECTED_OWNER,
                "remote_id": key,
                "youtube_id": row["youtube_id"],
                "date": post.get("date"),
                "text": str(post.get("text") or ""),
                "comments": post.get("comments"),
                "likes": post.get("likes"),
                "reposts": post.get("reposts"),
                "views": post.get("views"),
                "attachment_state": state,
                "attachment_sha256": hashlib.sha256(
                    base.canonical_json(video).encode("utf-8")
                ).hexdigest(),
            }
        )

        try:
            media = base.resolve_media(repo, row)
            actual_sha = base.sha256_file(media)
            expected_sha = str(row.get("local_sha256") or "")
            if expected_sha and actual_sha != expected_sha:
                raise base.OperationError(f"source SHA mismatch: {actual_sha} != {expected_sha}")
        except base.OperationError as exc:
            conflicts.append(
                {
                    "post_id": post_id,
                    "remote_id": key,
                    "youtube_id": row["youtube_id"],
                    "reason": str(exc),
                    "wall_cleanup_still_eligible": True,
                }
            )
            continue

        candidate = candidates_by_remote.get(key)
        if candidate is None:
            candidate = {
                "youtube_id": row["youtube_id"],
                "youtube_url": row["youtube_url"],
                "title": row["title"],
                "duration_seconds": row["duration_seconds"],
                "old_remote_id": key,
                "old_state": state,
                "source_path": str(media.relative_to(repo)),
                "source_sha256": actual_sha,
                "source_size": media.stat().st_size,
                "wall_post_ids": [],
            }
            candidates_by_remote[key] = candidate
        candidate["wall_post_ids"].append(int(post_id))

    wall_records.sort(key=lambda item: item["post_id"])
    candidates = sorted(
        candidates_by_remote.values(),
        key=lambda item: (min(item["wall_post_ids"]), item["youtube_id"]),
    )
    plan = {
        "schema_name": PLAN_SCHEMA,
        "schema_version": PLAN_VERSION,
        "generated_at": base.utc_now(),
        "project_key": base.EXPECTED_PROJECT,
        "account_alias": args.account,
        "community_id": args.community,
        "owner_id": base.EXPECTED_OWNER,
        "boundary_post_id": args.boundary_post,
        "operation_specific_filter": {"view_count_below": args.view_cutoff},
        "processing_flag_note": (
            "For this dated operation, processing=1 on a wall attachment does not override the same "
            "attachment's exact type=short_video, VK ID, source YouTube ID, duration, dimensions, and views."
        ),
        "wall_posts": wall_records,
        "clip_candidates": candidates,
        "excluded": [],
        "conflicts": conflicts,
    }
    root = operation_root(repo)
    root.mkdir(parents=True, exist_ok=True)
    plan_path, sha_path, summary_path = base.plan_paths(repo)
    base.write_json(plan_path, plan)
    plan_sha = base.sha256_file(plan_path)
    sha_path.write_text(f"{plan_sha}  plan.json\n", encoding="utf-8")
    write_jsonl(root / "wall-backup.jsonl", wall_backup)
    write_jsonl(root / "clip-attachment-backup.jsonl", clip_backup)
    token = f"SHORTS-RESET-V2-{plan_sha[:12]}-{len(wall_records)}-{len(candidates)}"
    summary = {
        "generated_at": base.utc_now(),
        "plan_sha256": plan_sha,
        "confirmation_token": token,
        "live_posts_after_boundary": len(posts),
        "wall_post_candidates": len(wall_records),
        "clip_replacement_candidates": len(candidates),
        "conflicts": len(conflicts),
        "candidate_post_range": (
            [wall_records[0]["post_id"], wall_records[-1]["post_id"]]
            if wall_records
            else None
        ),
        "plan_path": str(plan_path),
    }
    base.write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\nPREPARE V2 COMPLETE: no remote writes were performed.")
    return 0


def verify_candidate_live(gateway: Any, candidate: dict[str, Any], cutoff: int) -> dict[str, Any]:
    expected_remote = str(candidate["old_remote_id"])
    expected_youtube = str(candidate["youtube_id"])
    reason = "no linked wall post is available"
    for post_id in candidate.get("wall_post_ids", []):
        post = gateway.wall_post(base.EXPECTED_OWNER, int(post_id))
        if post is None:
            reason = f"wall post {post_id} is absent"
            continue
        video = direct_video(post)
        if video is None:
            reason = f"wall post {post_id} is no longer a simple video post"
            continue
        state = state_from_attachment(video)
        if state["remote_id"] != expected_remote:
            reason = f"wall post {post_id} points to {state['remote_id']}"
            continue
        if state["type"] != "short_video":
            reason = f"wall post {post_id} type is {state['type']}"
            continue
        if state["youtube_id"] != expected_youtube:
            reason = f"wall post {post_id} YouTube ID is {state['youtube_id']}"
            continue
        if not isinstance(state["views"], int) or state["views"] >= cutoff:
            reason = f"wall post {post_id} views={state['views']}"
            continue
        return state
    raise base.OperationError(f"Old clip cannot be revalidated: {reason}")


def delete_old_video_once(
    gateway: Any,
    journal: Any,
    plan: dict[str, Any],
    candidate: dict[str, Any],
    new_remote_id: str,
) -> None:
    youtube_id = str(candidate["youtube_id"])
    old_remote_id = str(candidate["old_remote_id"])
    action_key = f"delete-video:{old_remote_id}"
    existing = journal.get(action_key)
    if existing:
        if existing["status"] == "accepted":
            return
        if existing["status"] == "unknown":
            raise base.OperationError(f"Previous video.delete outcome is unknown: {old_remote_id}")
        raise base.OperationError(f"Unexpected previous video.delete status: {existing['status']}")

    replacement = gateway.exact_video(new_remote_id)
    if replacement is None:
        raise base.OperationError(f"Verified replacement disappeared: {new_remote_id}")
    replacement_state = base.video_state(replacement)
    if (
        replacement_state["type"] != "video"
        or replacement_state["processing"]
        or replacement_state["converting"]
    ):
        raise base.OperationError(f"Replacement is not final type=video: {replacement_state}")

    request = {
        "community_id": int(plan["community_id"]),
        "old_remote_id": old_remote_id,
        "new_remote_id": new_remote_id,
    }
    journal.upsert(
        action_key,
        "delete_video",
        "started",
        source_id=youtube_id,
        old_remote_id=old_remote_id,
        new_remote_id=new_remote_id,
        request=request,
    )
    try:
        response = gateway.delete_video_once(int(plan["community_id"]), old_remote_id)
    except base.UnknownOutcome as exc:
        journal.upsert(
            action_key,
            "delete_video",
            "unknown",
            source_id=youtube_id,
            old_remote_id=old_remote_id,
            new_remote_id=new_remote_id,
            error=str(exc),
        )
        raise
    journal.upsert(
        action_key,
        "delete_video",
        "accepted",
        source_id=youtube_id,
        old_remote_id=old_remote_id,
        new_remote_id=new_remote_id,
        response=response,
    )


def delete_wall_post_once(
    gateway: Any,
    journal: Any,
    plan: dict[str, Any],
    post: dict[str, Any],
) -> None:
    post_id = int(post["post_id"])
    action_key = f"delete-wall:{post_id}"
    existing = journal.get(action_key)
    if existing:
        if existing["status"] in {"verified_absent", "already_absent"}:
            return
        if existing["status"] in {"sent", "unknown"}:
            if gateway.wall_post(base.EXPECTED_OWNER, post_id) is None:
                journal.upsert(
                    action_key,
                    "delete_wall",
                    "verified_absent",
                    old_remote_id=post["remote_id"],
                )
                return
            raise base.OperationError(
                f"Previous wall.delete outcome is unresolved; refusing to resend: {post_id}"
            )

    live = gateway.wall_post(base.EXPECTED_OWNER, post_id)
    if live is None:
        journal.upsert(
            action_key,
            "delete_wall",
            "already_absent",
            old_remote_id=post["remote_id"],
        )
        return
    video = direct_video(live)
    key = remote_id(video) if video is not None else None
    if key != post["remote_id"] or post_id <= int(plan["boundary_post_id"]):
        raise base.OperationError(f"Wall post changed since plan: {post_id}")
    if video is None or video.get("type") != "short_video":
        raise base.OperationError(f"Wall post is no longer a simple short_video post: {post_id}")
    if source_id(video.get("description")) != post["youtube_id"]:
        raise base.OperationError(f"Wall post YouTube identity changed: {post_id}")

    request = {"owner_id": base.EXPECTED_OWNER, "post_id": post_id, "remote_id": key}
    journal.upsert(action_key, "delete_wall", "started", old_remote_id=key, request=request)
    try:
        response = gateway.delete_wall_post_once(base.EXPECTED_OWNER, post_id)
    except base.UnknownOutcome as exc:
        journal.upsert(action_key, "delete_wall", "unknown", old_remote_id=key, error=str(exc))
        raise
    journal.upsert(action_key, "delete_wall", "sent", old_remote_id=key, response=response)
    time.sleep(1.0)
    if gateway.wall_post(base.EXPECTED_OWNER, post_id) is None:
        journal.upsert(
            action_key,
            "delete_wall",
            "verified_absent",
            old_remote_id=key,
            response=response,
        )
    else:
        raise base.OperationError(f"wall.delete was sent once but post is still visible: {post_id}")


def command_apply(args: Any) -> int:
    repo = args.repo.resolve()
    plan, plan_sha, summary = base.load_verified_plan(repo)
    base.verify_confirmation(summary, args.confirm)
    if not args.execute:
        raise base.OperationError("Apply requires --execute")
    if base.os.environ.get("VCM_ALLOW_UPLOAD_OPERATIONS") != "1":
        raise base.OperationError("Apply requires VCM_ALLOW_UPLOAD_OPERATIONS=1")
    if base.os.environ.get("VCM_ALLOW_DESTRUCTIVE_OPERATIONS") != "1":
        raise base.OperationError("Apply requires VCM_ALLOW_DESTRUCTIVE_OPERATIONS=1")

    candidates = plan.get("clip_candidates")
    wall_posts = plan.get("wall_posts")
    if not isinstance(candidates, list) or not isinstance(wall_posts, list):
        raise base.OperationError("Invalid V2 plan candidate lists")
    canary_path = operation_root(repo) / "canary-result.json"
    if not canary_path.is_file():
        raise base.OperationError("Canary result is missing. Run Canary first.")
    canary = base.read_json(canary_path)
    if canary.get("plan_sha256") != plan_sha or canary.get("status") != "verified_type_video":
        raise base.OperationError("Canary result does not match the current V2 plan")

    gateway = base.load_token_and_gateway(repo, str(plan["account_alias"]), int(plan["community_id"]))
    cutoff = int(plan["operation_specific_filter"]["view_count_below"])
    wall_by_id = {int(post["post_id"]): post for post in wall_posts if isinstance(post, dict)}
    journal = base.open_journal(repo, plan_sha)
    try:
        for index, candidate in enumerate(candidates, start=1):
            print(
                f"REPLACE {index}/{len(candidates)} youtube_id={candidate['youtube_id']}",
                flush=True,
            )
            prior_delete = journal.get(f"delete-video:{candidate['old_remote_id']}")
            if prior_delete is None:
                verify_candidate_live(gateway, candidate, cutoff)
            new_remote_id = base.upload_replacement(
                gateway,
                journal,
                repo,
                plan,
                candidate,
                wait_seconds=args.wait_seconds,
                poll_seconds=args.poll_seconds,
            )
            delete_old_video_once(gateway, journal, plan, candidate, new_remote_id)
            for post_id in candidate.get("wall_post_ids", []):
                record = wall_by_id.get(int(post_id))
                if record is not None:
                    delete_wall_post_once(gateway, journal, plan, record)
            print(
                f"REPLACED old={candidate['old_remote_id']} new={new_remote_id}",
                flush=True,
            )

        candidate_post_ids = {
            int(post_id)
            for candidate in candidates
            for post_id in candidate.get("wall_post_ids", [])
        }
        for post_id, record in sorted(wall_by_id.items()):
            if post_id not in candidate_post_ids:
                delete_wall_post_once(gateway, journal, plan, record)
                print(f"WALL REMOVED post_id={post_id}", flush=True)

        remaining = base.wall_id_set(gateway, int(plan["boundary_post_id"]))
        remaining_planned = sorted(set(wall_by_id) & remaining)
        boundary_present = gateway.wall_post(base.EXPECTED_OWNER, base.DEFAULT_BOUNDARY_POST) is not None
        result = {
            "generated_at": base.utc_now(),
            "plan_sha256": plan_sha,
            "journal_counts": journal.counts(),
            "wall_candidates": len(wall_posts),
            "clip_candidates": len(candidates),
            "remaining_planned_wall_posts": remaining_planned,
            "boundary_post_12400_present": boundary_present,
        }
        base.write_json(operation_root(repo) / "apply-result.json", result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if remaining_planned:
            raise base.OperationError(f"Some planned wall posts remain: {remaining_planned}")
        if not boundary_present:
            raise base.OperationError("Protected boundary post 12400 is missing")
        return 0
    finally:
        journal.close()


base.PLAN_SCHEMA = PLAN_SCHEMA
base.PLAN_VERSION = PLAN_VERSION
base.operation_root = operation_root
base.command_prepare = command_prepare
base.verify_candidate_live = verify_candidate_live
base.delete_old_video_once = delete_old_video_once
base.delete_wall_post_once = delete_wall_post_once
base.command_apply = command_apply


if __name__ == "__main__":
    try:
        raise SystemExit(base.main())
    except (base.OperationError, base.UnknownOutcome) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
