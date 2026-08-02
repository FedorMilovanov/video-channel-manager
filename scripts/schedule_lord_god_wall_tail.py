#!/usr/bin/env python3
"""Plan or schedule the exact 26-video theological VK wall queue.

Read-only by default. ``--execute`` schedules only postponed posts, two per day
at 09:00 and 19:00 Europe/Moscow. No edit, delete, or immediate-post method is
implemented here.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import time
import zlib
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk import VkApiClient, VkApiError, VkTokenStore
from video_channel_manager.platforms.vk.lock import local_vk_write_lock
from video_channel_manager.platforms.vk.wall_content_audit import (
    extract_video_ids_from_post,
    fetch_wall_posts,
)

PROJECT_KEY = "lord-god-strength"
COMMUNITY_ID = 60805374
OWNER_ID = -60805374
ACCOUNT_ALIAS = "legendary-poet"  # Shared credential name, not project identity.
YOUTUBE_CHANNEL_ID = "UCeSJsC6go2c9pdJCuUI1BYA"
DECISION_SET_ID = "lord-god-wall-tail-202608"
EXPECTED_POLICY_SHA256 = "sha256:2f9e4de476ad7267b6f8423b7e23bd89173964af9d31641d3698a051c82041c5"
POLICY_DIR = Path("content/policies/lord-god-wall-tail-202608")
MOSCOW = ZoneInfo("Europe/Moscow")


def now_iso() -> str:
    return datetime.now(UTC).astimezone().isoformat()


def canonical_text(value: object) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def canonical_sha(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def message_sha(value: object) -> str:
    return f"sha256:{hashlib.sha256(canonical_text(value).encode()).hexdigest()}"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def read_json(path: Path, fallback: object) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else fallback


def load_policy(repo: Path) -> dict[str, Any]:
    files = sorted((repo / POLICY_DIR).glob("part-*.b85"))
    if len(files) != 4:
        raise RuntimeError(f"Expected four immutable policy parts, found {len(files)}")
    encoded = "".join(path.read_text(encoding="ascii").strip() for path in files)
    value = json.loads(zlib.decompress(base64.b85decode(encoded.encode("ascii"))).decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Policy root must be an object")
    return value


def validate_policy(policy: dict[str, Any]) -> None:
    expected = {
        "schema_name": "video-manager.vk-lord-god-wall-tail-policy",
        "schema_version": 1,
        "decision_set_id": DECISION_SET_ID,
        "project_key": PROJECT_KEY,
        "youtube_channel_id": YOUTUBE_CHANNEL_ID,
        "vk_community_id": COMMUNITY_ID,
        "vk_owner_id": OWNER_ID,
    }
    for key, value in expected.items():
        if policy.get(key) != value:
            raise ValueError(f"Policy identity mismatch: {key}")
    actual = canonical_sha({key: value for key, value in policy.items() if key != "policy_sha256"})
    if policy.get("policy_sha256") != actual or actual != EXPECTED_POLICY_SHA256:
        raise ValueError("Immutable policy digest mismatch")
    operations = policy.get("operations")
    if not isinstance(operations, list) or len(operations) != 26:
        raise ValueError("Policy must contain exactly 26 operations")
    seen_videos: set[str] = set()
    seen_dates: set[int] = set()
    previous_date = 0
    for index, operation in enumerate(operations, start=1):
        if not isinstance(operation, dict) or operation.get("ordinal") != index:
            raise ValueError(f"Invalid operation ordinal: {index}")
        video_id = str(operation.get("video_id") or "")
        attachment = str(operation.get("attachment") or "")
        text = canonical_text(operation.get("message"))
        publish_date = operation.get("publish_date")
        publish_at = datetime.fromisoformat(str(operation.get("publish_at") or ""))
        if not video_id.startswith(f"{OWNER_ID}_") or attachment != f"video{video_id}":
            raise ValueError(f"Wrong video identity: {index}")
        if operation.get("mode") != "postponed" or not text or len(text) > 4096:
            raise ValueError(f"Invalid postponed message: {index}")
        if operation.get("message_sha256") != message_sha(text):
            raise ValueError(f"Message digest mismatch: {index}")
        if not isinstance(publish_date, int) or int(publish_at.timestamp()) != publish_date:
            raise ValueError(f"Schedule mismatch: {index}")
        if publish_at.astimezone(MOSCOW).hour not in {9, 19}:
            raise ValueError(f"Unexpected hour: {index}")
        if video_id in seen_videos or publish_date in seen_dates or publish_date <= previous_date:
            raise ValueError("Duplicate or unordered operation")
        seen_videos.add(video_id)
        seen_dates.add(publish_date)
        previous_date = publish_date


def post_ref(post: dict[str, Any], queue: str) -> dict[str, Any]:
    owner_id, post_id = post.get("owner_id"), post.get("id")
    return {
        "queue": queue,
        "owner_id": owner_id if isinstance(owner_id, int) else None,
        "post_id": post_id if isinstance(post_id, int) else None,
        "date": post.get("date") if isinstance(post.get("date"), int) else None,
        "message": canonical_text(post.get("text")),
        "url": f"https://vk.ru/wall{owner_id}_{post_id}" if isinstance(owner_id, int) and isinstance(post_id, int) else None,
    }


def wall_snapshot(client: VkApiClient) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return (
        fetch_wall_posts(client, community_id=COMMUNITY_ID, filter_name="owner"),
        fetch_wall_posts(client, community_id=COMMUNITY_ID, filter_name="postponed"),
    )


def wall_index(published: list[dict[str, Any]], postponed: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for queue, posts in (("published", published), ("postponed", postponed)):
        for post in posts:
            ref = post_ref(post, queue)
            for video_id in extract_video_ids_from_post(post):
                result[video_id].append(ref)
    return dict(result)


def exact_video(client: VkApiClient, remote_id: str) -> dict[str, Any] | None:
    response = client._call("video.get", params={"videos": remote_id, "extended": False, "count": 1})
    items = response.get("items") if isinstance(response, dict) else None
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict) and f"{item.get('owner_id')}_{item.get('id')}" == remote_id:
            return item
    return None


def preflight(
    policy: dict[str, Any],
    client: VkApiClient,
    published: list[dict[str, Any]],
    postponed: list[dict[str, Any]],
    journal: dict[str, Any],
    *,
    minimum_future_seconds: int = 300,
) -> dict[str, Any]:
    index = wall_index(published, postponed)
    journal_ops = journal.get("operations") if isinstance(journal.get("operations"), dict) else {}
    current = int(datetime.now(UTC).timestamp())
    states: list[dict[str, Any]] = []
    conflicts: list[str] = []
    for operation in policy["operations"]:
        op_id = str(operation["operation_id"])
        video_id = str(operation["video_id"])
        expected_text = canonical_text(operation["message"])
        refs = index.get(video_id, [])
        exact = [ref for ref in refs if ref["message"] == expected_text and (ref["queue"] == "published" or ref["date"] == operation["publish_date"])]
        live = exact_video(client, video_id)
        previous = journal_ops.get(op_id)
        previous_status = previous.get("status") if isinstance(previous, dict) else None
        if live is None or live.get("type") != "video" or int(live.get("duration") or 0) <= 0:
            state, detail = "conflict", "target is not a playable ordinary VK video"
        elif len(exact) == 1 and len(refs) == 1:
            state, detail = "already_applied", "one exact wall post exists"
        elif refs:
            state, detail = "conflict", "target already has a different or duplicate wall post"
        elif previous_status == "unknown":
            state, detail = "conflict", "previous wall.post result is unknown"
        elif int(operation["publish_date"]) <= current + minimum_future_seconds:
            state, detail = "conflict", "approved time is no longer safely in the future"
        else:
            state, detail = "ready", "playable video is absent from both wall queues"
        if state == "conflict":
            conflicts.append(f"{op_id}: {detail}")
        states.append({
            "operation_id": op_id,
            "ordinal": operation["ordinal"],
            "video_id": video_id,
            "video_title": operation["video_title"],
            "publish_at": operation["publish_at"],
            "state": state,
            "detail": detail,
            "references": refs,
        })
        time.sleep(0.1)
    counts = Counter(item["state"] for item in states)
    return {
        "schema_name": "video-manager.vk-lord-god-wall-tail-preflight",
        "schema_version": 1,
        "generated_at": now_iso(),
        "policy_sha256": policy["policy_sha256"],
        "published_wall_posts": len(published),
        "postponed_wall_posts": len(postponed),
        "total_operations": len(states),
        "ready": counts["ready"],
        "already_applied": counts["already_applied"],
        "conflicts": counts["conflict"],
        "global_conflicts": conflicts,
        "states": states,
    }


def state_fingerprint(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"operation_id": item["operation_id"], "state": item["state"], "references": item["references"]}
        for item in report["states"]
    ]


def post_once(client: VkApiClient, operation: dict[str, Any]) -> object:
    token = client.token_store.load_token(client.account_alias)
    if token.is_expired():
        raise RuntimeError("Stored VK token is expired")
    return client._call_once("wall.post", {
        "access_token": token.access_token,
        "v": client.api_version,
        "owner_id": str(OWNER_ID),
        "from_group": "1",
        "message": str(operation["message"]),
        "attachments": str(operation["attachment"]),
        "publish_date": str(operation["publish_date"]),
        "guid": str(operation["operation_id"]),
    })


def post_id(response: object) -> int:
    if isinstance(response, int) and response > 0:
        return response
    if isinstance(response, dict) and isinstance(response.get("post_id"), int) and response["post_id"] > 0:
        return int(response["post_id"])
    raise RuntimeError(f"wall.post returned no positive post ID: {response!r}")


def review_markdown(policy: dict[str, Any], report: dict[str, Any]) -> str:
    states = {item["operation_id"]: item["state"] for item in report["states"]}
    lines = [
        "# Господь Бог — Сила Моя: 26 отложенных публикаций",
        "",
        "- Ритм: 09:00 и 19:00 по Москве.",
        f"- Период: {policy['summary']['first_publish_at']} — {policy['summary']['last_publish_at']}.",
        f"- Готово: {report['ready']}; уже стоит точно: {report['already_applied']}; конфликты: {report['conflicts']}.",
        "",
        "| № | Время | Видео | Статус |",
        "|---:|---|---|---|",
    ]
    for operation in policy["operations"]:
        lines.append(f"| {operation['ordinal']} | {operation['publish_at']} | {operation['video_title']} | `{states[operation['operation_id']]}` |")
    return "\n".join(lines) + "\n"


def run(repo: Path, *, execute: bool) -> int:
    repo = repo.resolve()
    out = repo / "data" / "vk-wall" / DECISION_SET_ID
    out.mkdir(parents=True, exist_ok=True)
    policy = load_policy(repo)
    validate_policy(policy)
    write_json(out / "plan.json", policy)

    settings = get_settings()
    store = VkTokenStore(settings.data_dir)
    client = VkApiClient(token_store=store, account_alias=ACCOUNT_ALIAS, api_version=settings.vk_api_version)
    community = client.get_community(COMMUNITY_ID)
    if community.ref.remote_id != str(COMMUNITY_ID) or not community.metadata.get("managed_by_token"):
        raise RuntimeError("Stored token does not manage VK community 60805374")

    journal_path = out / "journal.json"
    journal = read_json(journal_path, {
        "schema_name": "video-manager.vk-lord-god-wall-tail-journal",
        "schema_version": 1,
        "decision_set_id": DECISION_SET_ID,
        "policy_sha256": policy["policy_sha256"],
        "operations": {},
    })
    if not isinstance(journal, dict) or journal.get("decision_set_id") != DECISION_SET_ID or journal.get("policy_sha256") != policy["policy_sha256"]:
        raise RuntimeError("Local journal belongs to another immutable plan")

    published, postponed = wall_snapshot(client)
    report = preflight(policy, client, published, postponed, journal)
    write_json(out / "preflight.json", report)
    (out / "plan-review.md").write_text(review_markdown(policy, report), encoding="utf-8")
    print(json.dumps({
        "mode": "apply" if execute else "plan",
        "policy_sha256": policy["policy_sha256"],
        "operations": report["total_operations"],
        "ready": report["ready"],
        "already_applied": report["already_applied"],
        "conflicts": report["conflicts"],
        "first_publish_at": policy["summary"]["first_publish_at"],
        "last_publish_at": policy["summary"]["last_publish_at"],
        "plan_review": str(out / "plan-review.md"),
    }, ensure_ascii=False, indent=2))
    if report["conflicts"]:
        raise RuntimeError("Wall queue blocked: " + "; ".join(report["global_conflicts"]))
    if not execute:
        print("READ-ONLY PLAN COMPLETE. No VK writes were sent.")
        return 0
    if os.environ.get("VCM_ALLOW_WALL_POSTS") != "1":
        raise RuntimeError("Execution requires VCM_ALLOW_WALL_POSTS=1")

    result_path = out / "result.json"
    result: dict[str, Any] = {
        "schema_name": "video-manager.vk-lord-god-wall-tail-result",
        "schema_version": 1,
        "status": "running",
        "policy_sha256": policy["policy_sha256"],
        "started_at": now_iso(),
        "operations": [],
    }
    write_json(result_path, result)
    lock_path = settings.data_dir / "locks" / f"vk-wall-{COMMUNITY_ID}.lock"
    with local_vk_write_lock(lock_path, account=ACCOUNT_ALIAS, community_id=COMMUNITY_ID, operation=DECISION_SET_ID):
        locked_published, locked_postponed = wall_snapshot(client)
        locked = preflight(policy, client, locked_published, locked_postponed, journal)
        if locked["conflicts"] or state_fingerprint(locked) != state_fingerprint(report):
            raise RuntimeError("Locked preflight differs from reviewed preflight")
        states = {item["operation_id"]: item["state"] for item in locked["states"]}
        journal_ops = journal.get("operations")
        if not isinstance(journal_ops, dict):
            raise RuntimeError("Invalid journal operations map")
        for operation in policy["operations"]:
            op_id = str(operation["operation_id"])
            if states[op_id] == "already_applied":
                result["operations"].append({"operation_id": op_id, "status": "already_applied"})
                write_json(result_path, result)
                continue
            journal_ops[op_id] = {
                "status": "intent",
                "video_id": operation["video_id"],
                "publish_date": operation["publish_date"],
                "message_sha256": operation["message_sha256"],
                "intent_at": now_iso(),
            }
            journal["updated_at"] = now_iso()
            write_json(journal_path, journal)
            try:
                response = post_once(client, operation)
            except Exception as exc:
                journal_ops[op_id].update({"status": "unknown", "error": f"{type(exc).__name__}: {exc}", "updated_at": now_iso()})
                journal["updated_at"] = now_iso()
                write_json(journal_path, journal)
                result.update({"status": "stopped_unknown", "error": f"{op_id}: {type(exc).__name__}: {exc}", "stopped_at": now_iso()})
                write_json(result_path, result)
                raise RuntimeError(f"wall.post outcome is unknown for {op_id}; do not retry blindly") from exc
            accepted_id = post_id(response)
            journal_ops[op_id].update({"status": "accepted", "post_id": accepted_id, "accepted_at": now_iso()})
            journal["updated_at"] = now_iso()
            write_json(journal_path, journal)
            result["operations"].append({"operation_id": op_id, "post_id": accepted_id, "status": "scheduled_pending_postflight"})
            write_json(result_path, result)
            time.sleep(0.8)

        final_published, final_postponed = wall_snapshot(client)
        final = preflight(policy, client, final_published, final_postponed, journal, minimum_future_seconds=0)
        write_json(out / "postflight.json", final)
        if final["conflicts"] or final["ready"] or final["already_applied"] != 26:
            raise RuntimeError("Postflight did not verify all 26 exact postponed posts")
        for operation in policy["operations"]:
            item = journal_ops.get(operation["operation_id"])
            if isinstance(item, dict):
                item.update({"status": "verified", "verified_at": now_iso()})
        journal["updated_at"] = now_iso()
        write_json(journal_path, journal)
        result.update({
            "status": "completed",
            "completed_at": now_iso(),
            "verified_operations": 26,
            "verified_postponed": 26,
            "conflicts": 0,
            "first_publish_at": policy["summary"]["first_publish_at"],
            "last_publish_at": policy["summary"]["last_publish_at"],
        })
        write_json(result_path, result)
    print(json.dumps({
        "status": "completed",
        "verified_operations": 26,
        "first_publish_at": result["first_publish_at"],
        "last_publish_at": result["last_publish_at"],
        "result_path": str(result_path),
    }, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    return run(args.repo, execute=args.execute)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, VkApiError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        raise SystemExit(2) from exc
