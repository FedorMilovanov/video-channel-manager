from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

_WAVE6_RETIRED_EXECUTOR = True
if __name__ == "__main__":
    raise SystemExit(
        "This historical executor is retired by Wave 6. "
        "Use the versioned `video-manager wave` engine through the reviewed operator contract."
    )

V3_SCRIPT = Path(__file__).with_name("vk_shorts_reset_20260801_v3.py")
SPEC = importlib.util.spec_from_file_location("vk_shorts_reset_v3", V3_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load V3 executor: {V3_SCRIPT}")
v3 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = v3
SPEC.loader.exec_module(v3)
base = v3.base

ORIGINAL_VIDEO_STATE = base.video_state
ORIGINAL_COMMAND_CANARY = base.command_canary


def video_state(raw: dict[str, Any]) -> dict[str, Any]:
    """Treat a usable ordinary 1280x720 video as ready despite VK's stale flag."""
    state = ORIGINAL_VIDEO_STATE(raw)
    state["processing_api"] = state["processing"]
    state["converting_api"] = state["converting"]
    ready = (
        state["type"] == "video"
        and state["width"] == 1280
        and state["height"] == 720
        and isinstance(state["duration"], int)
        and state["duration"] > 0
        and not state["converting"]
    )
    if ready:
        state["processing"] = False
        state["readiness"] = "ordinary_video_1280x720"
    return state


def existing_replacement(
    gateway: Any,
    journal: Any,
    candidate: dict[str, Any],
) -> tuple[str, dict[str, Any]] | None:
    youtube_id = str(candidate["youtube_id"])
    old_remote_id = str(candidate["old_remote_id"])
    row = journal.get(f"upload:{youtube_id}")
    if row is None or not row["new_remote_id"]:
        return None
    new_remote_id = str(row["new_remote_id"])
    raw = gateway.exact_video(new_remote_id)
    if raw is None:
        return None
    state = video_state(raw)
    if state["type"] != "video" or state["processing"] or state["converting"]:
        return None
    journal.upsert(
        f"upload:{youtube_id}",
        "upload",
        "verified",
        source_id=youtube_id,
        old_remote_id=old_remote_id,
        new_remote_id=new_remote_id,
        response=state,
    )
    return new_remote_id, state


def write_canary_result(
    repo: Path,
    plan_sha: str,
    candidate: dict[str, Any],
    new_remote_id: str,
    state: dict[str, Any],
) -> None:
    result = {
        "generated_at": base.utc_now(),
        "plan_sha256": plan_sha,
        "youtube_id": candidate["youtube_id"],
        "old_remote_id": candidate["old_remote_id"],
        "new_remote_id": new_remote_id,
        "status": "verified_type_video",
        "verification": state,
    }
    base.write_json(v3.operation_root(repo) / "canary-result.json", result)
    print(f"CANARY REUSED: {new_remote_id} is an ordinary playable 1280x720 video.", flush=True)


def command_canary(args: Any) -> int:
    repo = args.repo.resolve()
    plan, plan_sha, summary = base.load_verified_plan(repo)
    base.verify_confirmation(summary, args.confirm)
    candidates = plan.get("clip_candidates")
    if isinstance(candidates, list) and candidates:
        gateway = base.load_token_and_gateway(
            repo,
            str(plan["account_alias"]),
            int(plan["community_id"]),
        )
        journal = base.open_journal(repo, plan_sha)
        try:
            found = existing_replacement(gateway, journal, candidates[0])
            if found is not None:
                new_remote_id, state = found
                write_canary_result(repo, plan_sha, candidates[0], new_remote_id, state)
                return 0
        finally:
            journal.close()
    return ORIGINAL_COMMAND_CANARY(args)


def tolerant_delete_wall_post_once(
    gateway: Any,
    journal: Any,
    plan: dict[str, Any],
    post: dict[str, Any],
) -> None:
    post_id = int(post["post_id"])
    planned_remote_id = str(post["remote_id"])
    action_key = f"delete-wall:{post_id}"
    existing = journal.get(action_key)
    if existing:
        status = str(existing["status"])
        if status in {"accepted", "verified_absent", "already_absent"}:
            return
        if status == "sent":
            journal.upsert(
                action_key,
                "delete_wall",
                "accepted",
                old_remote_id=planned_remote_id,
                response={"resumed_from": "sent", "note": "VK wall cache may still expose the post"},
            )
            return
        if status == "unknown":
            if gateway.wall_post(base.EXPECTED_OWNER, post_id) is None:
                journal.upsert(
                    action_key,
                    "delete_wall",
                    "verified_absent",
                    old_remote_id=planned_remote_id,
                )
                return
            raise base.OperationError(f"Previous wall.delete outcome is unknown; refusing to resend: {post_id}")

    if post_id <= int(plan["boundary_post_id"]):
        raise base.OperationError(f"Protected wall post cannot be deleted: {post_id}")

    live = gateway.wall_post(base.EXPECTED_OWNER, post_id)
    if live is None:
        journal.upsert(
            action_key,
            "delete_wall",
            "already_absent",
            old_remote_id=planned_remote_id,
        )
        return

    video = v3.v2.direct_video(live)
    live_remote_id = v3.v2.remote_id(video) if video is not None else None
    original_attachment_matches = live_remote_id == planned_remote_id
    old_delete = journal.get(f"delete-video:{planned_remote_id}")
    old_video_was_deleted = old_delete is not None and old_delete["status"] == "accepted"

    if not original_attachment_matches and not old_video_was_deleted:
        raise base.OperationError(f"Wall post changed before its planned video was deleted: {post_id}")

    request = {
        "owner_id": base.EXPECTED_OWNER,
        "post_id": post_id,
        "planned_remote_id": planned_remote_id,
        "live_remote_id": live_remote_id,
        "old_video_was_deleted": old_video_was_deleted,
    }
    journal.upsert(
        action_key,
        "delete_wall",
        "started",
        old_remote_id=planned_remote_id,
        request=request,
    )
    try:
        response = gateway.delete_wall_post_once(base.EXPECTED_OWNER, post_id)
    except base.UnknownOutcome as exc:
        journal.upsert(
            action_key,
            "delete_wall",
            "unknown",
            old_remote_id=planned_remote_id,
            error=str(exc),
        )
        raise
    if response != 1:
        journal.upsert(
            action_key,
            "delete_wall",
            "rejected",
            old_remote_id=planned_remote_id,
            response=response,
            error="VK wall.delete did not return success",
        )
        raise base.OperationError(f"VK rejected wall.delete for post {post_id}: {response!r}")
    journal.upsert(
        action_key,
        "delete_wall",
        "accepted",
        old_remote_id=planned_remote_id,
        response=response,
    )


def ensure_canary_for_apply(args: Any) -> None:
    repo = args.repo.resolve()
    plan, plan_sha, _summary = base.load_verified_plan(repo)
    candidates = plan.get("clip_candidates")
    if not isinstance(candidates, list) or not candidates:
        return
    canary_path = v3.operation_root(repo) / "canary-result.json"
    if canary_path.is_file():
        canary = base.read_json(canary_path)
        if canary.get("plan_sha256") == plan_sha and canary.get("status") == "verified_type_video":
            return
    gateway = base.load_token_and_gateway(
        repo,
        str(plan["account_alias"]),
        int(plan["community_id"]),
    )
    journal = base.open_journal(repo, plan_sha)
    try:
        found = existing_replacement(gateway, journal, candidates[0])
        if found is None:
            return
        new_remote_id, state = found
        write_canary_result(repo, plan_sha, candidates[0], new_remote_id, state)
    finally:
        journal.close()


def command_apply(args: Any) -> int:
    ensure_canary_for_apply(args)
    repo = args.repo.resolve()
    plan, plan_sha, summary = base.load_verified_plan(repo)
    base.verify_confirmation(summary, args.confirm)
    if not args.execute:
        raise base.OperationError("Apply requires --execute")
    if os.environ.get("VCM_ALLOW_UPLOAD_OPERATIONS") != "1":
        raise base.OperationError("Apply requires VCM_ALLOW_UPLOAD_OPERATIONS=1")
    if os.environ.get("VCM_ALLOW_DESTRUCTIVE_OPERATIONS") != "1":
        raise base.OperationError("Apply requires VCM_ALLOW_DESTRUCTIVE_OPERATIONS=1")

    candidates = plan.get("clip_candidates")
    wall_posts = plan.get("wall_posts")
    if not isinstance(candidates, list) or not isinstance(wall_posts, list):
        raise base.OperationError("Invalid V3 plan candidate lists")
    canary_path = v3.operation_root(repo) / "canary-result.json"
    if not canary_path.is_file():
        raise base.OperationError("Canary result is missing")
    canary = base.read_json(canary_path)
    if canary.get("plan_sha256") != plan_sha or canary.get("status") != "verified_type_video":
        raise base.OperationError("Canary result does not match the current V3 plan")

    gateway = base.load_token_and_gateway(
        repo,
        str(plan["account_alias"]),
        int(plan["community_id"]),
    )
    cutoff = int(plan["operation_specific_filter"]["view_count_below"])
    wall_by_id = {int(post["post_id"]): post for post in wall_posts if isinstance(post, dict)}
    journal = base.open_journal(repo, plan_sha)
    try:
        for index, candidate in enumerate(candidates, start=1):
            if not isinstance(candidate, dict):
                continue
            print(f"REPLACE {index}/{len(candidates)} youtube_id={candidate['youtube_id']}", flush=True)
            prior_delete = journal.get(f"delete-video:{candidate['old_remote_id']}")
            if prior_delete is None:
                v3.v2.verify_candidate_live(gateway, candidate, cutoff)
            new_remote_id = base.upload_replacement(
                gateway,
                journal,
                repo,
                plan,
                candidate,
                wait_seconds=args.wait_seconds,
                poll_seconds=args.poll_seconds,
            )
            v3.v2.delete_old_video_once(gateway, journal, plan, candidate, new_remote_id)
            for post_id in candidate.get("wall_post_ids", []):
                record = wall_by_id.get(int(post_id))
                if record is not None:
                    tolerant_delete_wall_post_once(gateway, journal, plan, record)
            print(f"REPLACED old={candidate['old_remote_id']} new={new_remote_id}", flush=True)

        remaining_live = base.wall_id_set(gateway, int(plan["boundary_post_id"]))
        remaining_planned = sorted(set(wall_by_id) & remaining_live)
        accepted_pending_cache: list[int] = []
        unresolved: list[int] = []
        for post_id in remaining_planned:
            row = journal.get(f"delete-wall:{post_id}")
            if row is not None and row["status"] in {"accepted", "sent", "verified_absent", "already_absent"}:
                accepted_pending_cache.append(post_id)
            else:
                unresolved.append(post_id)

        boundary_present = gateway.wall_post(base.EXPECTED_OWNER, base.DEFAULT_BOUNDARY_POST) is not None
        result = {
            "generated_at": base.utc_now(),
            "plan_sha256": plan_sha,
            "journal_counts": journal.counts(),
            "wall_candidates": len(wall_posts),
            "clip_candidates": len(candidates),
            "remaining_planned_wall_posts": remaining_planned,
            "accepted_pending_wall_cache": accepted_pending_cache,
            "unresolved_wall_posts": unresolved,
            "boundary_post_12400_present": boundary_present,
        }
        base.write_json(v3.operation_root(repo) / "apply-result.json", result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if unresolved:
            raise base.OperationError(f"Unresolved planned wall posts: {unresolved}")
        if not boundary_present:
            raise base.OperationError("Protected boundary post 12400 is missing")
        return 0
    finally:
        journal.close()


base.video_state = video_state
v3.v2.base.video_state = video_state
base.command_canary = command_canary
base.command_apply = command_apply
base.delete_wall_post_once = tolerant_delete_wall_post_once
v3.v2.delete_wall_post_once = tolerant_delete_wall_post_once


if __name__ == "__main__":
    try:
        raise SystemExit(base.main())
    except (base.OperationError, base.UnknownOutcome) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
