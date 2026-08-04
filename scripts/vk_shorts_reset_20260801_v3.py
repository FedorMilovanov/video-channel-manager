from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

_WAVE6_RETIRED_EXECUTOR = True
if __name__ == "__main__":
    raise SystemExit(
        "This historical executor is retired by Wave 6. "
        "Use the versioned `video-manager wave` engine through the reviewed operator contract."
    )

V2_SCRIPT = Path(__file__).with_name("vk_shorts_reset_20260801.py")
SPEC = importlib.util.spec_from_file_location("vk_shorts_reset_v2", V2_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load V2 executor: {V2_SCRIPT}")
v2 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = v2
SPEC.loader.exec_module(v2)
base = v2.base

PLAN_SCHEMA = "video-manager.vk-shorts-reset-20260801-v3"
PLAN_VERSION = 3
OPERATION_ROOT_NAME = "vk-shorts-reset-20260801-v3"
ORIGINAL_UPLOAD_REPLACEMENT = base.upload_replacement


def operation_root(repo: Path) -> Path:
    return repo / "data" / OPERATION_ROOT_NAME


def write_jsonl(path: Path, rows: list[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(base.canonical_json(row) + "\n")


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
    row_by_remote = {f"{int(row['vk_owner_id'])}_{int(row['vk_video_id'])}": row for row in rows}
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
            row, state, video = v2.validate_post(post, row_by_remote, args.view_cutoff)
        except base.OperationError as exc:
            conflicts.append({"post_id": post_id, "reason": str(exc)})
            continue

        key = str(state["remote_id"])
        clip_backup.append(video)
        attachment_hash = hashlib.sha256(base.canonical_json(video).encode("utf-8")).hexdigest()
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
                "attachment_sha256": attachment_hash,
            }
        )

        if key in candidates_by_remote:
            candidates_by_remote[key]["wall_post_ids"].append(int(post_id))
            continue

        source_mode = "vk_remote"
        source_path = operation_root(repo) / "source-cache" / f"{row['youtube_id']}.mp4"
        source_sha256: str | None = None
        source_size: int | None = None
        try:
            local_media = base.resolve_media(repo, row)
        except base.OperationError:
            local_media = None
        if local_media is not None:
            actual_sha = base.sha256_file(local_media)
            expected_sha = str(row.get("local_sha256") or "")
            if expected_sha and actual_sha != expected_sha:
                conflicts.append(
                    {
                        "post_id": post_id,
                        "remote_id": key,
                        "youtube_id": row["youtube_id"],
                        "reason": "local source SHA mismatch",
                    }
                )
                continue
            source_mode = "local"
            source_path = local_media
            source_sha256 = actual_sha
            source_size = local_media.stat().st_size

        candidates_by_remote[key] = {
            "youtube_id": row["youtube_id"],
            "youtube_url": row["youtube_url"],
            "title": row["title"],
            "duration_seconds": row["duration_seconds"],
            "old_remote_id": key,
            "old_state": state,
            "source_mode": source_mode,
            "source_vk_url": f"https://vk.com/video{key}",
            "source_path": str(source_path.relative_to(repo)),
            "source_sha256": source_sha256,
            "source_size": source_size,
            "wall_post_ids": [int(post_id)],
        }

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
        "source_policy": "existing VK clip first; ledger YouTube URL only as fallback",
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
    token = f"SHORTS-RESET-V3-{plan_sha[:12]}-{len(wall_records)}-{len(candidates)}"
    summary = {
        "generated_at": base.utc_now(),
        "plan_sha256": plan_sha,
        "confirmation_token": token,
        "live_posts_after_boundary": len(posts),
        "wall_post_candidates": len(wall_records),
        "clip_replacement_candidates": len(candidates),
        "remote_source_candidates": sum(1 for item in candidates if item["source_mode"] == "vk_remote"),
        "local_source_candidates": sum(1 for item in candidates if item["source_mode"] == "local"),
        "conflicts": len(conflicts),
        "candidate_post_range": [wall_records[0]["post_id"], wall_records[-1]["post_id"]] if wall_records else None,
        "plan_path": str(plan_path),
    }
    base.write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\nPREPARE V3 COMPLETE: no remote writes were performed.")
    return 0


def downloader_command() -> list[str]:
    executable = shutil.which("yt-dlp")
    if executable:
        return [executable]
    if importlib.util.find_spec("yt_dlp") is not None:
        return [sys.executable, "-m", "yt_dlp"]
    raise base.OperationError("yt-dlp is required to recover the existing VK clips")


def probe_media(path: Path, expected_duration: object) -> dict[str, Any]:
    ffprobe = base.require_tool("ffprobe")
    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_type,width,height",
        "-of",
        "json",
        str(path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise base.OperationError(f"ffprobe failed for {path}: {completed.stderr[-1000:]}")
    payload = json.loads(completed.stdout)
    streams = payload.get("streams") if isinstance(payload, dict) else None
    video_streams = (
        [item for item in streams if isinstance(item, dict) and item.get("codec_type") == "video"]
        if isinstance(streams, list)
        else []
    )
    if not video_streams:
        raise base.OperationError(f"Downloaded source has no video stream: {path}")
    duration_raw = payload.get("format", {}).get("duration") if isinstance(payload.get("format"), dict) else None
    duration = float(duration_raw) if duration_raw is not None else None
    if isinstance(expected_duration, int) and duration is not None and abs(duration - expected_duration) > 4.0:
        raise base.OperationError(f"Downloaded duration mismatch: {duration:.2f} vs {expected_duration}")
    return {"duration": duration, "streams": video_streams}


def download_source(repo: Path, candidate: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    target = repo / str(candidate["source_path"])
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and target.stat().st_size > 0:
        probe = probe_media(target, candidate.get("duration_seconds"))
        return target, {"source_url": "cached", "probe": probe}

    command_prefix = downloader_command()
    urls = [str(candidate["source_vk_url"]), str(candidate["youtube_url"])]
    errors: list[str] = []
    temp_template = str(target.with_suffix(".%(ext)s"))
    for url in urls:
        for leftover in target.parent.glob(f"{target.stem}.*"):
            if leftover.is_file():
                leftover.unlink()
        command = [
            *command_prefix,
            "--no-playlist",
            "--no-progress",
            "--retries",
            "10",
            "--fragment-retries",
            "10",
            "--merge-output-format",
            "mp4",
            "--recode-video",
            "mp4",
            "-f",
            "bv*+ba/b",
            "-o",
            temp_template,
            url,
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        produced = sorted(target.parent.glob(f"{target.stem}*.mp4"), key=lambda item: item.stat().st_size, reverse=True)
        if completed.returncode == 0 and produced:
            if produced[0] != target:
                produced[0].replace(target)
            probe = probe_media(target, candidate.get("duration_seconds"))
            return target, {"source_url": url, "probe": probe, "yt_dlp_tail": completed.stdout[-1000:]}
        errors.append(f"{url}: {completed.stderr[-1200:]}")
    raise base.OperationError("Could not download source from VK or YouTube: " + " | ".join(errors))


def upload_replacement(
    gateway: Any,
    journal: Any,
    repo: Path,
    plan: dict[str, Any],
    candidate: dict[str, Any],
    *,
    wait_seconds: int,
    poll_seconds: int,
) -> str:
    runtime_candidate = dict(candidate)
    source_path = repo / str(candidate["source_path"])
    source_evidence: dict[str, Any]
    if candidate.get("source_mode") == "local":
        if not source_path.is_file():
            raise base.OperationError(f"Planned local source disappeared: {source_path}")
        source_evidence = {"source_url": "local", "probe": probe_media(source_path, candidate.get("duration_seconds"))}
    else:
        source_path, source_evidence = download_source(repo, candidate)
    source_sha = base.sha256_file(source_path)
    runtime_candidate["source_path"] = str(source_path.relative_to(repo))
    runtime_candidate["source_sha256"] = source_sha
    runtime_candidate["source_size"] = source_path.stat().st_size
    evidence_path = operation_root(repo) / "source-evidence" / f"{candidate['youtube_id']}.json"
    base.write_json(
        evidence_path,
        {
            "generated_at": base.utc_now(),
            "youtube_id": candidate["youtube_id"],
            "old_remote_id": candidate["old_remote_id"],
            "source_path": runtime_candidate["source_path"],
            "source_sha256": source_sha,
            "source_size": runtime_candidate["source_size"],
            **source_evidence,
        },
    )
    return ORIGINAL_UPLOAD_REPLACEMENT(
        gateway,
        journal,
        repo,
        plan,
        runtime_candidate,
        wait_seconds=wait_seconds,
        poll_seconds=poll_seconds,
    )


base.PLAN_SCHEMA = PLAN_SCHEMA
base.PLAN_VERSION = PLAN_VERSION
base.operation_root = operation_root
v2.operation_root = operation_root
base.command_prepare = command_prepare
base.upload_replacement = upload_replacement
base.verify_candidate_live = v2.verify_candidate_live
base.delete_old_video_once = v2.delete_old_video_once
base.delete_wall_post_once = v2.delete_wall_post_once
base.command_apply = v2.command_apply


if __name__ == "__main__":
    try:
        raise SystemExit(base.main())
    except (base.OperationError, base.UnknownOutcome) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
