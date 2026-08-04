from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from video_channel_manager.platforms.vk.store import VkTokenStore

_WAVE6_RETIRED_EXECUTOR = True
if __name__ == "__main__":
    raise SystemExit(
        "This historical executor is retired by Wave 6. "
        "Use the versioned `video-manager wave` engine through the reviewed operator contract."
    )

API_BASE = "https://api.vk.com/method"
API_VERSION = "5.199"
EXPECTED_PROJECT = "lord-god-strength"
EXPECTED_COMMUNITY = 60805374
EXPECTED_OWNER = -60805374
DEFAULT_BOUNDARY_POST = 12400
DEFAULT_VIEW_CUTOFF = 20
READ_RETRY_CODES = {6, 9, 10, 29}
PLAN_SCHEMA = "video-manager.vk-shorts-reset-plan"
PLAN_VERSION = 1


class OperationError(RuntimeError):
    pass


class UnknownOutcome(OperationError):
    pass


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def require_tool(name: str) -> str:
    value = shutil.which(name)
    if not value:
        raise OperationError(f"Required executable is missing from PATH: {name}")
    return value


def safe_title(value: str) -> str:
    return " ".join(value.split())[:128]


def parse_remote_id(remote_id: str) -> tuple[int, int]:
    try:
        owner_raw, video_raw = remote_id.split("_", 1)
        return int(owner_raw), int(video_raw)
    except (ValueError, AttributeError) as exc:
        raise OperationError(f"Invalid VK remote video ID: {remote_id}") from exc


class VkGateway:
    def __init__(self, token: str, *, version: str = API_VERSION) -> None:
        self.token = token
        self.version = version

    def _once(self, method: str, params: dict[str, object]) -> object:
        payload = {"access_token": self.token, "v": self.version, **params}
        try:
            with httpx.Client(timeout=httpx.Timeout(90.0), follow_redirects=True) as client:
                response = client.get(f"{API_BASE}/{method}", params=payload)
        except httpx.HTTPError as exc:
            raise UnknownOutcome(f"VK transport outcome is unknown for {method}: {exc}") from exc
        try:
            body = response.json()
        except ValueError as exc:
            raise UnknownOutcome(f"VK returned invalid JSON for {method}: {response.text[:500]}") from exc
        if not isinstance(body, dict):
            raise UnknownOutcome(f"VK returned a non-object for {method}")
        error = body.get("error")
        if isinstance(error, dict):
            code = error.get("error_code")
            message = error.get("error_msg")
            raise OperationError(f"VK API {code} in {method}: {message}")
        if "response" not in body:
            raise UnknownOutcome(f"VK response has no response field for {method}")
        return body["response"]

    def read(self, method: str, params: dict[str, object], *, attempts: int = 8) -> object:
        delay = 1.0
        for attempt in range(1, attempts + 1):
            try:
                return self._once(method, params)
            except OperationError as exc:
                text = str(exc)
                code = None
                if text.startswith("VK API "):
                    try:
                        code = int(text.split()[2])
                    except (ValueError, IndexError):
                        code = None
                if code not in READ_RETRY_CODES or attempt >= attempts:
                    raise
            except UnknownOutcome:
                if attempt >= attempts:
                    raise
            time.sleep(delay)
            delay = min(delay * 2, 30.0)
        raise AssertionError("unreachable")

    def write_once(self, method: str, params: dict[str, object]) -> object:
        return self._once(method, params)

    def community(self, community_id: int) -> dict[str, Any]:
        response = self.read("groups.getById", {"group_id": community_id, "fields": "screen_name,is_admin"})
        groups: object
        if isinstance(response, dict):
            groups = response.get("groups")
        else:
            groups = response
        if not isinstance(groups, list) or not groups or not isinstance(groups[0], dict):
            raise OperationError(f"Cannot resolve VK community {community_id}")
        return groups[0]

    def exact_videos(self, remote_ids: list[str]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        unique_ids = sorted(set(remote_ids))
        for start in range(0, len(unique_ids), 100):
            batch = unique_ids[start : start + 100]
            response = self.read("video.get", {"videos": ",".join(batch), "extended": 0})
            items = response.get("items") if isinstance(response, dict) else None
            if not isinstance(items, list):
                raise OperationError("video.get exact response has no items list")
            for raw in items:
                if not isinstance(raw, dict):
                    continue
                owner_id = raw.get("owner_id")
                video_id = raw.get("id")
                if isinstance(owner_id, int) and isinstance(video_id, int):
                    result[f"{owner_id}_{video_id}"] = raw
            time.sleep(0.35)
        return result

    def exact_video(self, remote_id: str) -> dict[str, Any] | None:
        return self.exact_videos([remote_id]).get(remote_id)

    def wall_posts_after(self, owner_id: int, boundary_post: int) -> list[dict[str, Any]]:
        page_size = 100
        offset = 0
        found: list[dict[str, Any]] = []
        stop = False
        while not stop:
            response = self.read(
                "wall.get",
                {"owner_id": owner_id, "filter": "owner", "count": page_size, "offset": offset, "extended": 0},
            )
            items = response.get("items") if isinstance(response, dict) else None
            posts = [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []
            if not posts:
                break
            for post in posts:
                post_id = post.get("id")
                if not isinstance(post_id, int):
                    continue
                if post_id <= boundary_post:
                    stop = True
                    continue
                found.append(post)
            offset += len(posts)
            if len(posts) < page_size:
                break
            time.sleep(0.35)
        return found

    def wall_post(self, owner_id: int, post_id: int) -> dict[str, Any] | None:
        response = self.read("wall.getById", {"posts": f"{owner_id}_{post_id}", "extended": 0})
        items: object
        if isinstance(response, dict):
            items = response.get("items")
        else:
            items = response
        if not isinstance(items, list):
            return None
        for item in items:
            if isinstance(item, dict) and item.get("id") == post_id and item.get("owner_id") == owner_id:
                return item
        return None

    def reserve_video(self, community_id: int, title: str, description: str) -> dict[str, Any]:
        response = self.write_once(
            "video.save",
            {
                "group_id": community_id,
                "name": safe_title(title),
                "description": description[:5000],
                "is_private": 0,
                "wallpost": 0,
                "no_comments": 0,
                "repeat": 0,
                "auto_publish": 0,
            },
        )
        if not isinstance(response, dict):
            raise UnknownOutcome("video.save returned a non-object")
        upload_url = str(response.get("upload_url") or "").strip()
        video_id = response.get("video_id", response.get("vid", response.get("id")))
        owner_id = response.get("owner_id")
        if not upload_url or not isinstance(video_id, int):
            raise UnknownOutcome(f"video.save response lacks upload_url/video_id: {canonical_json(response)}")
        return {
            **response,
            "upload_url": upload_url,
            "video_id": video_id,
            "owner_id": int(owner_id) if isinstance(owner_id, int) else -community_id,
        }

    def upload_file_once(self, upload_url: str, media_path: Path) -> dict[str, Any]:
        mime = mimetypes.guess_type(media_path.name)[0] or "video/mp4"
        try:
            with media_path.open("rb") as handle:
                files = {"video_file": (media_path.name, handle, mime)}
                timeout = httpx.Timeout(connect=60.0, read=7200.0, write=7200.0, pool=60.0)
                with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                    response = client.post(upload_url, files=files)
        except httpx.HTTPError as exc:
            raise UnknownOutcome(f"Upload-server outcome is unknown: {exc}") from exc
        if response.status_code >= 400:
            raise OperationError(f"Upload server HTTP {response.status_code}: {response.text[:1000]}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise UnknownOutcome(f"Upload server returned invalid JSON: {response.text[:1000]}") from exc
        if not isinstance(payload, dict):
            raise UnknownOutcome("Upload server returned a non-object")
        if payload.get("error"):
            raise OperationError(f"Upload server error: {canonical_json(payload)}")
        return payload

    def delete_video_once(self, community_id: int, remote_id: str) -> object:
        owner_id, video_id = parse_remote_id(remote_id)
        return self.write_once(
            "video.delete",
            {"owner_id": owner_id, "target_id": -community_id, "video_id": video_id},
        )

    def delete_wall_post_once(self, owner_id: int, post_id: int) -> object:
        return self.write_once("wall.delete", {"owner_id": owner_id, "post_id": post_id})


class Journal:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS actions (
                action_key TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                source_id TEXT,
                old_remote_id TEXT,
                new_remote_id TEXT,
                request_json TEXT,
                response_json TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def set_meta(self, key: str, value: str) -> None:
        self.db.execute(
            "INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self.db.commit()

    def get(self, action_key: str) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM actions WHERE action_key=?", (action_key,)).fetchone()

    def upsert(
        self,
        action_key: str,
        kind: str,
        status: str,
        *,
        source_id: str | None = None,
        old_remote_id: str | None = None,
        new_remote_id: str | None = None,
        request: object | None = None,
        response: object | None = None,
        error: str | None = None,
    ) -> None:
        now = utc_now()
        self.db.execute(
            """
            INSERT INTO actions(
                action_key,kind,status,source_id,old_remote_id,new_remote_id,
                request_json,response_json,error,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(action_key) DO UPDATE SET
                status=excluded.status,
                new_remote_id=COALESCE(excluded.new_remote_id,actions.new_remote_id),
                request_json=COALESCE(excluded.request_json,actions.request_json),
                response_json=COALESCE(excluded.response_json,actions.response_json),
                error=excluded.error,
                updated_at=excluded.updated_at
            """,
            (
                action_key,
                kind,
                status,
                source_id,
                old_remote_id,
                new_remote_id,
                canonical_json(request) if request is not None else None,
                canonical_json(response) if response is not None else None,
                error,
                now,
                now,
            ),
        )
        self.db.commit()

    def counts(self) -> dict[str, int]:
        rows = self.db.execute("SELECT kind,status,COUNT(*) AS n FROM actions GROUP BY kind,status").fetchall()
        return {f"{row['kind']}:{row['status']}": int(row["n"]) for row in rows}


def load_legacy_rows(repo: Path) -> list[dict[str, Any]]:
    ledger = repo / "data" / "vk-upload" / "verified-shorts" / "shorts-upload-ledger.db"
    if not ledger.is_file():
        raise OperationError(f"Shorts ledger not found: {ledger}")
    with sqlite3.connect(ledger) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(
            """
            SELECT youtube_id,title,youtube_url,duration_seconds,classification,status,
                   local_path,local_sha256,local_size,vk_owner_id,vk_video_id,
                   upload_attempted,last_error
            FROM operations
            WHERE vk_owner_id IS NOT NULL AND vk_video_id IS NOT NULL
            ORDER BY youtube_id
            """
        ).fetchall()
    if not rows:
        raise OperationError("Shorts ledger has no exact uploaded VK IDs")
    return [dict(row) for row in rows]


def resolve_media(repo: Path, row: dict[str, Any]) -> Path:
    youtube_id = str(row["youtube_id"])
    canonical = repo / "data" / "vk-upload" / "verified-shorts" / "media" / f"{youtube_id}.mp4"
    if canonical.is_file():
        return canonical
    raw = row.get("local_path")
    if isinstance(raw, str) and raw:
        candidate = Path(raw)
        if candidate.is_file():
            return candidate
    raise OperationError(f"Local source MP4 is missing for YouTube ID {youtube_id}: {canonical}")


def video_state(raw: dict[str, Any]) -> dict[str, Any]:
    processing = bool(raw.get("processing") or raw.get("is_processing"))
    converting = bool(raw.get("converting") or raw.get("is_converting"))
    return {
        "remote_id": f"{raw.get('owner_id')}_{raw.get('id')}",
        "owner_id": raw.get("owner_id"),
        "video_id": raw.get("id"),
        "title": str(raw.get("title") or ""),
        "description": str(raw.get("description") or ""),
        "duration": raw.get("duration"),
        "type": raw.get("type"),
        "views": raw.get("views"),
        "processing": processing,
        "converting": converting,
        "width": raw.get("width"),
        "height": raw.get("height"),
        "date": raw.get("date"),
    }


def direct_video_attachment(post: dict[str, Any]) -> str | None:
    if post.get("copy_history"):
        return None
    attachments = post.get("attachments")
    if not isinstance(attachments, list) or len(attachments) != 1:
        return None
    attachment = attachments[0]
    if not isinstance(attachment, dict) or attachment.get("type") != "video":
        return None
    video = attachment.get("video")
    if not isinstance(video, dict):
        return None
    owner_id = video.get("owner_id")
    video_id = video.get("id")
    if not isinstance(owner_id, int) or not isinstance(video_id, int):
        return None
    return f"{owner_id}_{video_id}"


def operation_root(repo: Path) -> Path:
    return repo / "data" / "vk-shorts-reset-20260801"


def load_token_and_gateway(repo: Path, account: str, community: int) -> VkGateway:
    data_dir = repo / "data"
    token = VkTokenStore(data_dir).load_token(account)
    if token.is_expired():
        raise OperationError(f"Stored VK token is expired: {account}")
    gateway = VkGateway(token.access_token)
    community_data = gateway.community(community)
    if int(community_data.get("id") or 0) != community:
        raise OperationError(f"Resolved wrong community: {community_data}")
    if not bool(community_data.get("is_admin")):
        raise OperationError("Stored VK token is not an administrator of the target community")
    return gateway


def plan_paths(repo: Path) -> tuple[Path, Path, Path]:
    root = operation_root(repo)
    return root / "plan.json", root / "plan.sha256", root / "plan-summary.json"


def load_verified_plan(repo: Path) -> tuple[dict[str, Any], str, dict[str, Any]]:
    plan_path, sha_path, summary_path = plan_paths(repo)
    if not plan_path.is_file() or not sha_path.is_file() or not summary_path.is_file():
        raise OperationError("Plan files are missing. Run Prepare first.")
    expected_sha = sha_path.read_text(encoding="utf-8").strip().split()[0].lower()
    actual_sha = sha256_file(plan_path)
    if actual_sha != expected_sha:
        raise OperationError(f"Plan SHA-256 mismatch: {actual_sha} != {expected_sha}")
    plan = read_json(plan_path)
    summary = read_json(summary_path)
    if not isinstance(plan, dict) or plan.get("schema_name") != PLAN_SCHEMA:
        raise OperationError("Invalid Shorts reset plan")
    if summary.get("plan_sha256") != actual_sha:
        raise OperationError("Plan summary does not match plan SHA-256")
    return plan, actual_sha, summary


def command_prepare(args: argparse.Namespace) -> int:
    repo = args.repo.resolve()
    if args.community != EXPECTED_COMMUNITY:
        raise OperationError(f"Community mismatch: {args.community} != {EXPECTED_COMMUNITY}")
    if args.boundary_post != DEFAULT_BOUNDARY_POST:
        raise OperationError(f"Boundary mismatch: {args.boundary_post} != {DEFAULT_BOUNDARY_POST}")
    gateway = load_token_and_gateway(repo, args.account, args.community)
    rows = load_legacy_rows(repo)
    remote_ids = [f"{int(row['vk_owner_id'])}_{int(row['vk_video_id'])}" for row in rows]
    live = gateway.exact_videos(remote_ids)
    posts = gateway.wall_posts_after(EXPECTED_OWNER, args.boundary_post)
    post_records: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    tracked = set(remote_ids)
    for post in posts:
        post_id = post.get("id")
        remote_id = direct_video_attachment(post)
        if not isinstance(post_id, int):
            continue
        if remote_id is None:
            conflicts.append({"kind": "wall_not_simple_video", "post_id": post_id})
            continue
        raw_video = live.get(remote_id)
        if remote_id not in tracked or raw_video is None:
            conflicts.append({"kind": "wall_video_not_in_shorts_ledger", "post_id": post_id, "remote_id": remote_id})
            continue
        state = video_state(raw_video)
        if state["type"] != "short_video" or state["processing"] or state["converting"]:
            conflicts.append(
                {"kind": "wall_video_not_final_short", "post_id": post_id, "remote_id": remote_id, "state": state}
            )
            continue
        post_records.append(
            {
                "post_id": post_id,
                "owner_id": EXPECTED_OWNER,
                "remote_id": remote_id,
                "date": post.get("date"),
                "text": str(post.get("text") or ""),
                "comments": post.get("comments"),
                "likes": post.get("likes"),
                "reposts": post.get("reposts"),
                "views": post.get("views"),
            }
        )

    candidates: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for row in rows:
        remote_id = f"{int(row['vk_owner_id'])}_{int(row['vk_video_id'])}"
        raw = live.get(remote_id)
        if raw is None:
            excluded.append({"youtube_id": row["youtube_id"], "remote_id": remote_id, "reason": "not_visible"})
            continue
        state = video_state(raw)
        views = state["views"]
        if state["type"] != "short_video":
            excluded.append(
                {"youtube_id": row["youtube_id"], "remote_id": remote_id, "reason": "not_short_video", "state": state}
            )
            continue
        if state["processing"] or state["converting"]:
            excluded.append(
                {"youtube_id": row["youtube_id"], "remote_id": remote_id, "reason": "processing", "state": state}
            )
            continue
        if not isinstance(views, int):
            excluded.append(
                {"youtube_id": row["youtube_id"], "remote_id": remote_id, "reason": "views_unknown", "state": state}
            )
            continue
        if views >= args.view_cutoff:
            excluded.append(
                {
                    "youtube_id": row["youtube_id"],
                    "remote_id": remote_id,
                    "reason": "outside_current_operation_filter",
                    "views": views,
                }
            )
            continue
        try:
            media = resolve_media(repo, row)
        except OperationError as exc:
            excluded.append(
                {
                    "youtube_id": row["youtube_id"],
                    "remote_id": remote_id,
                    "reason": "local_media_missing",
                    "error": str(exc),
                }
            )
            continue
        expected_media_sha = str(row.get("local_sha256") or "")
        actual_media_sha = sha256_file(media)
        if expected_media_sha and actual_media_sha != expected_media_sha:
            excluded.append(
                {
                    "youtube_id": row["youtube_id"],
                    "remote_id": remote_id,
                    "reason": "local_media_sha_mismatch",
                    "expected": expected_media_sha,
                    "actual": actual_media_sha,
                }
            )
            continue
        candidates.append(
            {
                "youtube_id": row["youtube_id"],
                "youtube_url": row["youtube_url"],
                "title": row["title"],
                "duration_seconds": row["duration_seconds"],
                "old_remote_id": remote_id,
                "old_state": state,
                "source_path": str(media.relative_to(repo)),
                "source_sha256": actual_media_sha,
                "source_size": media.stat().st_size,
                "wall_post_ids": sorted(
                    record["post_id"] for record in post_records if record["remote_id"] == remote_id
                ),
            }
        )

    plan = {
        "schema_name": PLAN_SCHEMA,
        "schema_version": PLAN_VERSION,
        "generated_at": utc_now(),
        "project_key": EXPECTED_PROJECT,
        "account_alias": args.account,
        "community_id": args.community,
        "owner_id": EXPECTED_OWNER,
        "boundary_post_id": args.boundary_post,
        "operation_specific_filter": {"view_count_below": args.view_cutoff},
        "wall_posts": sorted(post_records, key=lambda item: item["post_id"]),
        "clip_candidates": sorted(candidates, key=lambda item: (item["old_state"]["views"], item["youtube_id"])),
        "excluded": excluded,
        "conflicts": conflicts,
    }
    root = operation_root(repo)
    root.mkdir(parents=True, exist_ok=True)
    plan_path, sha_path, summary_path = plan_paths(repo)
    write_json(plan_path, plan)
    plan_sha = sha256_file(plan_path)
    sha_path.write_text(f"{plan_sha}  plan.json\n", encoding="utf-8")
    token = f"SHORTS-RESET-{plan_sha[:12]}-{len(post_records)}-{len(candidates)}"
    summary = {
        "generated_at": utc_now(),
        "plan_sha256": plan_sha,
        "confirmation_token": token,
        "wall_post_candidates": len(post_records),
        "clip_replacement_candidates": len(candidates),
        "excluded": len(excluded),
        "conflicts": len(conflicts),
        "plan_path": str(plan_path),
    }
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\nPREPARE COMPLETE: no remote writes were performed.")
    return 0


def verify_confirmation(summary: dict[str, Any], provided: str) -> None:
    expected = str(summary.get("confirmation_token") or "")
    if not expected or provided != expected:
        raise OperationError("Exact confirmation token mismatch")


def create_16x9(source: Path, target: Path) -> Path:
    ffmpeg = require_tool("ffmpeg")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        return target
    filter_graph = (
        "[0:v]split=2[bgsrc][fgsrc];"
        "[bgsrc]scale=1280:720:force_original_aspect_ratio=increase,"
        "crop=1280:720,boxblur=20:10[bg];"
        "[fgsrc]scale=1280:720:force_original_aspect_ratio=decrease[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=1,format=yuv420p[v]"
    )
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(source),
        "-filter_complex",
        filter_graph,
        "-map",
        "[v]",
        "-map",
        "0:a:0?",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "20",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-movflags",
        "+faststart",
        "-shortest",
        str(target),
    ]
    result = subprocess.run(command, check=False)
    if result.returncode != 0 or not target.is_file():
        raise OperationError(f"ffmpeg failed for {source}")
    return target


def wall_id_set(gateway: VkGateway, boundary: int) -> set[int]:
    return {
        int(post["id"])
        for post in gateway.wall_posts_after(EXPECTED_OWNER, boundary)
        if isinstance(post.get("id"), int)
    }


def wait_for_final_video(gateway: VkGateway, remote_id: str, wait_seconds: int, poll_seconds: int) -> dict[str, Any]:
    deadline = time.monotonic() + max(wait_seconds, 0)
    last: dict[str, Any] | None = None
    while True:
        raw = gateway.exact_video(remote_id)
        if raw is not None:
            last = video_state(raw)
            print(
                f"CHECK {remote_id}: type={last['type']} processing={last['processing']} "
                f"converting={last['converting']} views={last['views']}",
                flush=True,
            )
            if not last["processing"] and not last["converting"] and last["type"] in {"video", "short_video"}:
                return last
        if time.monotonic() >= deadline:
            if last is None:
                raise OperationError(f"New VK object did not become visible: {remote_id}")
            return last
        time.sleep(max(poll_seconds, 1))


def upload_replacement(
    gateway: VkGateway,
    journal: Journal,
    repo: Path,
    plan: dict[str, Any],
    candidate: dict[str, Any],
    *,
    wait_seconds: int,
    poll_seconds: int,
) -> str:
    youtube_id = str(candidate["youtube_id"])
    old_remote_id = str(candidate["old_remote_id"])
    action_key = f"upload:{youtube_id}"
    existing = journal.get(action_key)
    new_remote_id: str | None = str(existing["new_remote_id"]) if existing and existing["new_remote_id"] else None
    if existing and existing["status"] == "unknown":
        raise OperationError(f"Upload outcome is unknown for {youtube_id}; refusing to retry")
    if new_remote_id:
        final = wait_for_final_video(gateway, new_remote_id, wait_seconds, poll_seconds)
        if final["type"] != "video" or final["processing"] or final["converting"]:
            raise OperationError(f"Existing replacement is not final type=video: {new_remote_id} {final}")
        journal.upsert(
            action_key,
            "upload",
            "verified",
            source_id=youtube_id,
            old_remote_id=old_remote_id,
            new_remote_id=new_remote_id,
            response=final,
        )
        return new_remote_id

    source = repo / str(candidate["source_path"])
    if not source.is_file():
        raise OperationError(f"Source file missing: {source}")
    if sha256_file(source) != candidate["source_sha256"]:
        raise OperationError(f"Source SHA-256 drift for {youtube_id}")
    target = operation_root(repo) / "media-16x9" / f"{youtube_id}-16x9.mp4"
    create_16x9(source, target)
    description = str(candidate["old_state"].get("description") or "")
    before_wall = wall_id_set(gateway, int(plan["boundary_post_id"]))
    reserve_request = {
        "community_id": int(plan["community_id"]),
        "title": candidate["title"],
        "source_sha256": candidate["source_sha256"],
        "wallpost": 0,
        "auto_publish": 0,
        "repeat": 0,
    }
    journal.upsert(
        action_key,
        "upload",
        "reserve_started",
        source_id=youtube_id,
        old_remote_id=old_remote_id,
        request=reserve_request,
    )
    try:
        reserve = gateway.reserve_video(int(plan["community_id"]), str(candidate["title"]), description)
    except UnknownOutcome as exc:
        journal.upsert(
            action_key,
            "upload",
            "unknown",
            source_id=youtube_id,
            old_remote_id=old_remote_id,
            request=reserve_request,
            error=str(exc),
        )
        raise
    new_remote_id = f"{int(reserve['owner_id'])}_{int(reserve['video_id'])}"
    journal.upsert(
        action_key,
        "upload",
        "reserved",
        source_id=youtube_id,
        old_remote_id=old_remote_id,
        new_remote_id=new_remote_id,
        request=reserve_request,
        response={key: value for key, value in reserve.items() if key != "upload_url"},
    )
    try:
        upload_response = gateway.upload_file_once(str(reserve["upload_url"]), target)
    except UnknownOutcome as exc:
        journal.upsert(
            action_key,
            "upload",
            "unknown",
            source_id=youtube_id,
            old_remote_id=old_remote_id,
            new_remote_id=new_remote_id,
            error=str(exc),
        )
        raise
    journal.upsert(
        action_key,
        "upload",
        "uploaded",
        source_id=youtube_id,
        old_remote_id=old_remote_id,
        new_remote_id=new_remote_id,
        response=upload_response,
    )
    final = wait_for_final_video(gateway, new_remote_id, wait_seconds, poll_seconds)
    after_wall = wall_id_set(gateway, int(plan["boundary_post_id"]))
    unexpected = sorted(after_wall - before_wall)
    if unexpected:
        journal.upsert(
            action_key,
            "upload",
            "blocked_unexpected_wall_post",
            source_id=youtube_id,
            old_remote_id=old_remote_id,
            new_remote_id=new_remote_id,
            response={"final": final, "unexpected_wall_post_ids": unexpected},
        )
        raise OperationError(f"Unexpected VK wall posts appeared after upload: {unexpected}")
    if final["type"] != "video" or final["processing"] or final["converting"]:
        journal.upsert(
            action_key,
            "upload",
            "wrong_type",
            source_id=youtube_id,
            old_remote_id=old_remote_id,
            new_remote_id=new_remote_id,
            response=final,
        )
        raise OperationError(f"Replacement did not become ordinary type=video: {new_remote_id} {final}")
    journal.upsert(
        action_key,
        "upload",
        "verified",
        source_id=youtube_id,
        old_remote_id=old_remote_id,
        new_remote_id=new_remote_id,
        response=final,
    )
    return new_remote_id


def verify_candidate_live(gateway: VkGateway, candidate: dict[str, Any], cutoff: int) -> dict[str, Any]:
    old_remote_id = str(candidate["old_remote_id"])
    raw = gateway.exact_video(old_remote_id)
    if raw is None:
        raise OperationError(f"Old clip is no longer visible: {old_remote_id}")
    state = video_state(raw)
    if state["type"] != "short_video" or state["processing"] or state["converting"]:
        raise OperationError(f"Old object is no longer a final short_video: {old_remote_id} {state}")
    if not isinstance(state["views"], int) or state["views"] >= cutoff:
        raise OperationError(
            f"Old clip no longer matches this operation's plan: {old_remote_id} views={state['views']}"
        )
    return state


def delete_old_video_once(
    gateway: VkGateway,
    journal: Journal,
    plan: dict[str, Any],
    candidate: dict[str, Any],
    new_remote_id: str,
) -> None:
    youtube_id = str(candidate["youtube_id"])
    old_remote_id = str(candidate["old_remote_id"])
    action_key = f"delete-video:{old_remote_id}"
    existing = journal.get(action_key)
    if existing:
        if existing["status"] == "verified_absent":
            return
        if existing["status"] in {"sent", "unknown"}:
            if gateway.exact_video(old_remote_id) is None:
                journal.upsert(
                    action_key,
                    "delete_video",
                    "verified_absent",
                    source_id=youtube_id,
                    old_remote_id=old_remote_id,
                    new_remote_id=new_remote_id,
                )
                return
            raise OperationError(f"Previous video.delete outcome is unresolved; refusing to resend: {old_remote_id}")
    if gateway.exact_video(new_remote_id) is None:
        raise OperationError(f"Verified replacement disappeared before deletion: {new_remote_id}")
    request = {
        "community_id": plan["community_id"],
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
    except UnknownOutcome as exc:
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
        "sent",
        source_id=youtube_id,
        old_remote_id=old_remote_id,
        new_remote_id=new_remote_id,
        response=response,
    )
    time.sleep(1.0)
    if gateway.exact_video(old_remote_id) is None:
        journal.upsert(
            action_key,
            "delete_video",
            "verified_absent",
            source_id=youtube_id,
            old_remote_id=old_remote_id,
            new_remote_id=new_remote_id,
            response=response,
        )
    else:
        raise OperationError(f"video.delete was sent once but old object is still visible: {old_remote_id}")


def delete_wall_post_once(
    gateway: VkGateway,
    journal: Journal,
    plan: dict[str, Any],
    post: dict[str, Any],
) -> None:
    post_id = int(post["post_id"])
    action_key = f"delete-wall:{post_id}"
    existing = journal.get(action_key)
    if existing:
        if existing["status"] == "verified_absent":
            return
        if existing["status"] in {"sent", "unknown"}:
            if gateway.wall_post(EXPECTED_OWNER, post_id) is None:
                journal.upsert(action_key, "delete_wall", "verified_absent", old_remote_id=post["remote_id"])
                return
            raise OperationError(f"Previous wall.delete outcome is unresolved; refusing to resend: {post_id}")
    live_post = gateway.wall_post(EXPECTED_OWNER, post_id)
    if live_post is None:
        journal.upsert(action_key, "delete_wall", "verified_absent", old_remote_id=post["remote_id"])
        return
    remote_id = direct_video_attachment(live_post)
    if remote_id != post["remote_id"] or post_id <= int(plan["boundary_post_id"]):
        raise OperationError(f"Wall post changed since plan: {post_id}")
    raw = gateway.exact_video(remote_id)
    if raw is None or video_state(raw)["type"] != "short_video":
        raise OperationError(f"Wall post no longer points to a final short_video: {post_id} {remote_id}")
    request = {"owner_id": EXPECTED_OWNER, "post_id": post_id, "remote_id": remote_id}
    journal.upsert(action_key, "delete_wall", "started", old_remote_id=remote_id, request=request)
    try:
        response = gateway.delete_wall_post_once(EXPECTED_OWNER, post_id)
    except UnknownOutcome as exc:
        journal.upsert(action_key, "delete_wall", "unknown", old_remote_id=remote_id, error=str(exc))
        raise
    journal.upsert(action_key, "delete_wall", "sent", old_remote_id=remote_id, response=response)
    time.sleep(0.8)
    if gateway.wall_post(EXPECTED_OWNER, post_id) is None:
        journal.upsert(action_key, "delete_wall", "verified_absent", old_remote_id=remote_id, response=response)
    else:
        raise OperationError(f"wall.delete was sent once but post is still visible: {post_id}")


def open_journal(repo: Path, plan_sha: str) -> Journal:
    journal = Journal(operation_root(repo) / "operation-ledger.db")
    journal.set_meta("plan_sha256", plan_sha)
    journal.set_meta("project_key", EXPECTED_PROJECT)
    journal.set_meta("community_id", str(EXPECTED_COMMUNITY))
    return journal


def command_canary(args: argparse.Namespace) -> int:
    repo = args.repo.resolve()
    plan, plan_sha, summary = load_verified_plan(repo)
    verify_confirmation(summary, args.confirm)
    if not args.execute or os.environ.get("VCM_ALLOW_UPLOAD_OPERATIONS") != "1":
        raise OperationError("Canary requires --execute and VCM_ALLOW_UPLOAD_OPERATIONS=1")
    candidates = plan.get("clip_candidates")
    if not isinstance(candidates, list) or not candidates:
        print("No clip replacement candidates. Canary is not needed.")
        return 0
    gateway = load_token_and_gateway(repo, str(plan["account_alias"]), int(plan["community_id"]))
    cutoff = int(plan["operation_specific_filter"]["view_count_below"])
    candidate = candidates[0]
    verify_candidate_live(gateway, candidate, cutoff)
    journal = open_journal(repo, plan_sha)
    try:
        new_remote_id = upload_replacement(
            gateway,
            journal,
            repo,
            plan,
            candidate,
            wait_seconds=args.wait_seconds,
            poll_seconds=args.poll_seconds,
        )
        result = {
            "generated_at": utc_now(),
            "plan_sha256": plan_sha,
            "youtube_id": candidate["youtube_id"],
            "old_remote_id": candidate["old_remote_id"],
            "new_remote_id": new_remote_id,
            "status": "verified_type_video",
        }
        write_json(operation_root(repo) / "canary-result.json", result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("CANARY VERIFIED. The old clip has not been deleted.")
        return 0
    finally:
        journal.close()


def command_apply(args: argparse.Namespace) -> int:
    repo = args.repo.resolve()
    plan, plan_sha, summary = load_verified_plan(repo)
    verify_confirmation(summary, args.confirm)
    if not args.execute:
        raise OperationError("Apply requires --execute")
    if os.environ.get("VCM_ALLOW_UPLOAD_OPERATIONS") != "1":
        raise OperationError("Apply requires VCM_ALLOW_UPLOAD_OPERATIONS=1")
    if os.environ.get("VCM_ALLOW_DESTRUCTIVE_OPERATIONS") != "1":
        raise OperationError("Apply requires VCM_ALLOW_DESTRUCTIVE_OPERATIONS=1")
    gateway = load_token_and_gateway(repo, str(plan["account_alias"]), int(plan["community_id"]))
    cutoff = int(plan["operation_specific_filter"]["view_count_below"])
    candidates = plan.get("clip_candidates")
    wall_posts = plan.get("wall_posts")
    if not isinstance(candidates, list) or not isinstance(wall_posts, list):
        raise OperationError("Invalid plan candidate lists")
    journal = open_journal(repo, plan_sha)
    try:
        if candidates:
            canary_path = operation_root(repo) / "canary-result.json"
            if not canary_path.is_file():
                raise OperationError("Canary result is missing. Run Canary first.")
            canary = read_json(canary_path)
            if canary.get("plan_sha256") != plan_sha or canary.get("status") != "verified_type_video":
                raise OperationError("Canary result does not match the current plan")

        for post in wall_posts:
            if not isinstance(post, dict):
                continue
            delete_wall_post_once(gateway, journal, plan, post)
            print(f"WALL REMOVED post_id={post['post_id']}", flush=True)

        for index, candidate in enumerate(candidates, start=1):
            if not isinstance(candidate, dict):
                continue
            print(f"REPLACE {index}/{len(candidates)} youtube_id={candidate['youtube_id']}", flush=True)
            try:
                verify_candidate_live(gateway, candidate, cutoff)
            except OperationError as exc:
                journal.upsert(
                    f"skip:{candidate['youtube_id']}",
                    "skip",
                    "live_drift",
                    source_id=str(candidate["youtube_id"]),
                    old_remote_id=str(candidate["old_remote_id"]),
                    error=str(exc),
                )
                print(f"SKIP LIVE DRIFT: {exc}", flush=True)
                continue
            new_remote_id = upload_replacement(
                gateway,
                journal,
                repo,
                plan,
                candidate,
                wait_seconds=args.wait_seconds,
                poll_seconds=args.poll_seconds,
            )
            delete_old_video_once(gateway, journal, plan, candidate, new_remote_id)
            print(f"REPLACED old={candidate['old_remote_id']} new={new_remote_id}", flush=True)

        final = {
            "generated_at": utc_now(),
            "plan_sha256": plan_sha,
            "journal_counts": journal.counts(),
            "wall_candidates": len(wall_posts),
            "clip_candidates": len(candidates),
        }
        write_json(operation_root(repo) / "apply-result.json", final)
        print(json.dumps(final, ensure_ascii=False, indent=2))
        return 0
    finally:
        journal.close()


def command_status(args: argparse.Namespace) -> int:
    repo = args.repo.resolve()
    root = operation_root(repo)
    output: dict[str, Any] = {"root": str(root)}
    for name in ["plan-summary.json", "canary-result.json", "apply-result.json"]:
        path = root / name
        if path.is_file():
            output[name] = read_json(path)
    journal_path = root / "operation-ledger.db"
    if journal_path.is_file():
        journal = Journal(journal_path)
        try:
            output["journal_counts"] = journal.counts()
        finally:
            journal.close()
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="One-time guarded VK Shorts wall cleanup and ordinary-video replacement."
    )
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--account", default="legendary-poet")
    parser.add_argument("--community", type=int, default=EXPECTED_COMMUNITY)
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare", help="Read-only live audit and immutable plan.")
    prepare.add_argument("--boundary-post", type=int, default=DEFAULT_BOUNDARY_POST)
    prepare.add_argument("--view-cutoff", type=int, default=DEFAULT_VIEW_CUTOFF)
    prepare.set_defaults(func=command_prepare)

    canary = sub.add_parser("canary", help="Upload and verify one 16:9 ordinary-video canary.")
    canary.add_argument("--confirm", required=True)
    canary.add_argument("--execute", action="store_true")
    canary.add_argument("--wait-seconds", type=int, default=1800)
    canary.add_argument("--poll-seconds", type=int, default=20)
    canary.set_defaults(func=command_canary)

    apply_cmd = sub.add_parser(
        "apply",
        help="Delete planned Shorts wall posts, replace eligible clips, and delete old clips.",
    )
    apply_cmd.add_argument("--confirm", required=True)
    apply_cmd.add_argument("--execute", action="store_true")
    apply_cmd.add_argument("--wait-seconds", type=int, default=1800)
    apply_cmd.add_argument("--poll-seconds", type=int, default=20)
    apply_cmd.set_defaults(func=command_apply)

    status = sub.add_parser("status", help="Show resumable operation state.")
    status.set_defaults(func=command_status)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except (OperationError, UnknownOutcome, sqlite3.Error, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
