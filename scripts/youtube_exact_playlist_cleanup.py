#!/usr/bin/env python3
"""One-shot, owner-verified cleanup of three obsolete Paul Washer playlist memberships.

Deletes playlist ENTRIES, never videos. No retries of ambiguous mutations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.platforms.youtube import InstalledClientConfig, TokenStore
from video_channel_manager.platforms.youtube.write_lock import local_youtube_write_lock
from video_channel_manager.youtube_release_provider import YouTubeReleaseProvider

OWNER = "UCeSJsC6go2c9pdJCuUI1BYA"
ACCOUNT = "fedor-milovanov"
OLD = "5bQDzxVM40g"
NEW = "Ba-1IHVz3H8"
PLAYLISTS = {
    "PLu2Bhoh2caiWr9lsuVokJkv4O7qyyecpB",
    "PLu2Bhoh2caiVGVGu9UzgOpizYeANtHpE4",
    "PLu2Bhoh2caiWQC9Jf4fpB5ydX-8VnM-AV",
}


def canonical_hash(value: object) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(body).hexdigest()


def validate_plan(plan: dict[str, Any]) -> None:
    if (
        plan.get("schema") != "youtube-washer-exact-playlist-cleanup-v1"
        or plan.get("owner") != OWNER
        or plan.get("account") != ACCOUNT
        or plan.get("obsolete_video_id") != OLD
        or plan.get("protected_video_id") != NEW
    ):
        raise ValueError("Wrong owner/account/exact video identity")
    rows = plan.get("memberships")
    if not isinstance(rows, list) or len(rows) != 3:
        raise ValueError("Expected exactly three obsolete playlist entries")
    if {r.get("playlist_id") for r in rows} != PLAYLISTS:
        raise ValueError("Playlist identity mismatch")
    obsolete = [r.get("old_membership_id") for r in rows]
    protected = [r.get("new_membership_id") for r in rows]
    if (
        any(not isinstance(x, str) or not x.strip() for x in obsolete + protected)
        or len(set(obsolete + protected)) != 6
    ):
        raise ValueError("Membership IDs are blank or duplicate")
    if plan.get("plan_sha256") != canonical_hash({k: v for k, v in plan.items() if k != "plan_sha256"}):
        raise ValueError("Plan digest mismatch")


def _items(provider: YouTubeReleaseProvider, ids: list[str]) -> list[dict[str, Any]]:
    response = provider._safe_request(
        "GET",
        f"{provider.api_base_url}/playlistItems",
        resource="playlistItems.read-exact",
        params={"part": "snippet,contentDetails", "id": ",".join(ids), "maxResults": 50},
    )
    payload = response.json()
    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("Invalid playlistItems response")
    return items


def _confirm_membership(item: dict[str, Any], *, membership_id: str, playlist_id: str, video_id: str) -> None:
    snippet = item.get("snippet") or {}
    details = item.get("contentDetails") or {}
    actual_video = details.get("videoId") or (snippet.get("resourceId") or {}).get("videoId")
    if (
        item.get("id") != membership_id
        or snippet.get("playlistId") != playlist_id
        or snippet.get("channelId") != OWNER
        or actual_video != video_id
    ):
        raise ValueError(f"Playlist entry identity mismatch: {membership_id}")


def _video_invariants(provider: YouTubeReleaseProvider) -> dict[str, dict[str, Any]]:
    result = {}
    for video_id, visibility in ((OLD, "unlisted"), (NEW, "public")):
        raw = provider.read_video(video_id)
        snippet, status, details = raw.get("snippet", {}), raw.get("status", {}), raw.get("contentDetails", {})
        if raw.get("id") != video_id or snippet.get("channelId") != OWNER or status.get("privacyStatus") != visibility:
            raise ValueError("Owner video identity or privacy changed; do not delete playlist entries")
        result[video_id] = {
            "title": snippet.get("title"),
            "description_sha256": canonical_hash(snippet.get("description", "")),
            "status": status.get("privacyStatus"),
            "license": status.get("license"),
            "duration": details.get("duration"),
            "has_custom_thumbnail": details.get("hasCustomThumbnail"),
        }
    return result


def preflight(plan: dict[str, Any], provider: YouTubeReleaseProvider) -> dict[str, Any]:
    validate_plan(plan)
    videos = _video_invariants(provider)
    rows = plan["memberships"]
    expected_ids = [r[key] for r in rows for key in ("old_membership_id", "new_membership_id")]
    actual = _items(provider, expected_ids)
    by_id = {x.get("id"): x for x in actual}
    if len(actual) != 6 or len(by_id) != 6:
        raise ValueError("Owner has unexpected playlist memberships; no mutation")
    for row in rows:
        for id_key, video_id in (("old_membership_id", OLD), ("new_membership_id", NEW)):
            membership = row[id_key]
            _confirm_membership(
                by_id[membership], membership_id=membership, playlist_id=row["playlist_id"], video_id=video_id
            )
    return {"video_invariants": videos, "owner_memberships": actual}


def _write_new(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def _update_json(path: Path, payload: dict[str, Any]) -> None:
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        _write_new(temp, payload)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def execute(
    plan: dict[str, Any],
    provider: YouTubeReleaseProvider,
    *,
    execute_write: bool,
    backup_path: Path | None = None,
    receipt_path: Path | None = None,
) -> dict[str, Any]:
    validate_plan(plan)
    if not execute_write:
        result = preflight(plan, provider)
        return {"status": "dry_run_ready", "verified_entries": len(result["owner_memberships"]), "mutations": 0}
    if backup_path is None or receipt_path is None:
        raise ValueError("Backup and receipt are required")
    if backup_path.resolve() == receipt_path.resolve() or backup_path.exists() or receipt_path.exists():
        raise ValueError("Existing, duplicated or ambiguous journals: refuse mutation")
    lock = Path(provider.token_store.data_dir) / "locks" / f"youtube-{ACCOUNT}-{OWNER}.lock"
    with local_youtube_write_lock(lock, account=ACCOUNT, channel_id=OWNER):
        owner = preflight(plan, provider)
        _write_new(
            backup_path,
            {
                "schema": "youtube-washer-playlist-backup-v1",
                "created": datetime.now(UTC).isoformat(),
                "plan_sha256": plan["plan_sha256"],
                "original": owner,
            },
        )
        receipt = {
            "schema": "youtube-washer-playlist-receipt-v1",
            "account": ACCOUNT,
            "owner": OWNER,
            "source_plan_sha256": plan["plan_sha256"],
            "backup_path": str(backup_path),
            "status": "started",
            "attempted": [],
            "verified_removed": [],
        }
        _write_new(receipt_path, receipt)
        for row in plan["memberships"]:
            old_id, new_id = row["old_membership_id"], row["new_membership_id"]
            before = _items(provider, [old_id, new_id])
            by_id = {x.get("id"): x for x in before}
            if set(by_id) != {old_id, new_id}:
                raise ValueError("Playlist membership drift before deletion")
            _confirm_membership(by_id[old_id], membership_id=old_id, playlist_id=row["playlist_id"], video_id=OLD)
            _confirm_membership(by_id[new_id], membership_id=new_id, playlist_id=row["playlist_id"], video_id=NEW)
            receipt["status"] = "pending_reconciliation"
            receipt["attempted"].append({"playlist_id": row["playlist_id"], "old_membership_id": old_id})
            _update_json(receipt_path, receipt)
            # Mutate once, never replay on 5xx / timeouts or unexpected 204 response.
            response, failed = provider._mutation_request(
                "DELETE",
                f"{provider.api_base_url}/playlistItems",
                resource="playlistItems.delete.exact-washer-old",
                params={"id": old_id},
            )
            if failed is not None:
                raise RuntimeError(f"Playlist delete requires reconciliation: {failed.provider_effect}")
            if response is None or response.status_code != 204:
                raise RuntimeError("Unexpected delete response; reconcile before any other mutation")
            # Read-only eventual-consistency checks; no additional mutation calls.
            clean = False
            for delay in (0.0, 0.5, 1.0, 2.0):
                if delay:
                    time.sleep(delay)
                after_items = _items(provider, [old_id, new_id])
                by_id_after = {x.get("id"): x for x in after_items}
                if old_id not in by_id_after and new_id in by_id_after:
                    _confirm_membership(
                        by_id_after[new_id], membership_id=new_id, playlist_id=row["playlist_id"], video_id=NEW
                    )
                    clean = True
                    break
            if not clean:
                raise RuntimeError("Playlist removal not verified; no subsequent deletions")
            receipt["verified_removed"].append({"playlist_id": row["playlist_id"], "old_membership_id": old_id})
            _update_json(receipt_path, receipt)
        final_videos = _video_invariants(provider)
        if final_videos != owner["video_invariants"]:
            raise ValueError("Video identity/status changed during playlist cleanup; manual investigation")
        receipt["status"] = "completed_live_verified"
        receipt["provider_deletes_verified"] = 3
        receipt["finished"] = datetime.now(UTC).isoformat()
        _update_json(receipt_path, receipt)
        return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--account", required=True)
    parser.add_argument("--confirm-channel", required=True)
    parser.add_argument("--client-secret", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.account != ACCOUNT or args.confirm_channel != OWNER:
        raise ValueError("Incorrect account/channel CLI arguments")
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    provider = YouTubeReleaseProvider(
        client_config=InstalledClientConfig.from_file(args.client_secret),
        token_store=TokenStore(args.data_dir),
        account_alias=args.account,
    )
    result = execute(plan, provider, execute_write=args.execute, backup_path=args.backup, receipt_path=args.receipt)
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
