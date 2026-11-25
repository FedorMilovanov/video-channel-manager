#!/usr/bin/env python3
"""One-video, exact-state YouTube tag/license repair; no upload, delete, or retries."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.platforms.youtube import InstalledClientConfig, TokenStore, YouTubeDescriptionWriter
from video_channel_manager.platforms.youtube.write_lock import local_youtube_write_lock

PARTS = "snippet,status,contentDetails,localizations"


def digest(value: object) -> str:
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    )


def observed(raw: dict[str, Any]) -> dict[str, Any]:
    s = raw["snippet"]
    t = raw["status"]
    c = raw["contentDetails"]
    return {
        "video_id": raw["id"],
        "channel_id": s["channelId"],
        "title": s["title"],
        "description_sha256": digest(s.get("description", "")),
        "tags": list(s.get("tags", [])),
        "category_id": s["categoryId"],
        "default_language": s.get("defaultLanguage"),
        "default_audio_language": s.get("defaultAudioLanguage"),
        "privacy": t.get("privacyStatus"),
        "license": t.get("license"),
        "embeddable": t.get("embeddable"),
        "public_stats": t.get("publicStatsViewable"),
        "self_declared_kids": t.get("selfDeclaredMadeForKids"),
        "made_for_kids": t.get("madeForKids"),
        "upload_status": t.get("uploadStatus"),
        "publish_at": t.get("publishAt"),
        "has_custom_thumbnail": c.get("hasCustomThumbnail"),
        "duration": c.get("duration"),
        "localizations_sha256": digest(raw.get("localizations", {})),
    }


def validate_plan(plan: dict[str, Any]) -> None:
    if plan.get("schema") != "youtube-exact-metadata-repair-v1":
        raise ValueError("Wrong schema")
    before = plan["before"]
    after = plan["after"]
    if plan.get("account") != "fedor-milovanov":
        raise ValueError("Wrong account")
    if plan.get("channel_id") != "UCeSJsC6go2c9pdJCuUI1BYA":
        raise ValueError("Wrong owner channel")
    if before["channel_id"] != plan["channel_id"] or before["video_id"] != plan["video_id"]:
        raise ValueError("Source identity mismatch")
    if before["privacy"] != "public" or before["license"] != "creativeCommon":
        raise ValueError("Source is not expected public/CC state")
    if not isinstance(before["tags"], list) or not all(isinstance(tag, str) for tag in before["tags"]):
        raise ValueError("Source tags malformed")
    tags = after.get("tags")
    if not isinstance(tags, list) or len(tags) < 10 or len(tags) != len(set(tags)):
        raise ValueError("Proposed tags malformed")
    if any(not isinstance(v, str) or not v.strip() for v in tags):
        raise ValueError("Blank or nontext tag")
    if sum(len(v) for v in tags) > 400:
        raise ValueError("Too many tag characters")
    if any(x in " ".join(tags).casefold() for x in ("macarthur", "макартур", "shepherds conference")):
        raise ValueError("Cross-speaker tags not cleaned")
    if after.get("license") != "youtube" or after.get("tags") == before["tags"]:
        raise ValueError("No valid scoped fix")
    if plan.get("before_sha256") != digest(before) or plan.get("after_sha256") != digest(after):
        raise ValueError("Unsigned plan content")


def validate_live(plan: dict[str, Any], raw: dict[str, Any], *, after: bool = False) -> None:
    expected = dict(plan["before"])
    if after:
        expected["tags"] = plan["after"]["tags"]
        expected["license"] = plan["after"]["license"]
    current = observed(raw)
    differences = []
    for key, value in expected.items():
        actual = current.get(key)
        if key == "tags":
            # YouTube returns alphabetically normalized tag order after videos.update.
            # The complete distinct tag membership, not array order, is the invariant.
            same_tags = (
                isinstance(actual, list)
                and len(actual) == len(value)
                and len(actual) == len(set(actual))
                and set(actual) == set(value)
            )
            if not same_tags:
                differences.append(key)
        elif actual != value:
            differences.append(key)
    if differences:
        raise ValueError(f"Owner state mismatch ({'after' if after else 'before'}): {differences}")


def update_body(raw: dict[str, Any], *, tags: list[str], license: str) -> dict[str, Any]:
    s = raw["snippet"]
    t = raw["status"]
    new_snippet: dict[str, Any] = {
        "title": s["title"],
        "categoryId": s["categoryId"],
        "description": s["description"],
        "tags": tags,
    }
    for key in ("defaultLanguage", "defaultAudioLanguage"):
        if s.get(key):
            new_snippet[key] = s[key]
    status: dict[str, Any] = {"privacyStatus": t["privacyStatus"], "license": license}
    for key in ("embeddable", "publicStatsViewable", "selfDeclaredMadeForKids"):
        if key in t:
            status[key] = t[key]
    # Never include read-only madeForKids/uploadStatus in PUT; preserve only mutable fields.
    return {"id": raw["id"], "snippet": new_snippet, "status": status}


def exclusive_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def replace_json(path: Path, data: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        exclusive_json(temporary, data)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def execute(
    plan: dict[str, Any],
    writer: YouTubeDescriptionWriter,
    *,
    account: str,
    channel: str,
    execute_write: bool,
    backup_path: Path | None = None,
    receipt_path: Path | None = None,
) -> dict[str, Any]:
    validate_plan(plan)
    if account != plan["account"] or channel != plan["channel_id"]:
        raise ValueError("Account/channel argument mismatch")

    def read() -> dict[str, Any]:
        result = writer._request("GET", "videos", params={"part": PARTS, "id": plan["video_id"], "maxResults": 1})
        items = result.get("items", [])
        if len(items) != 1:
            raise ValueError("Expected precisely one owner video")
        return items[0]

    if not execute_write:
        live = read()
        validate_live(plan, live)
        return {"status": "dry_run_verified", "video_id": plan["video_id"], "provider_writes": 0}
    if backup_path is None or receipt_path is None:
        raise ValueError("Unique immutable backup and receipt paths required")
    if backup_path.resolve() == receipt_path.resolve() or backup_path.exists() or receipt_path.exists():
        raise ValueError("Existing or identical journals: refusing provider mutation")
    lock = Path(writer.token_store.data_dir) / "locks" / f"youtube-{account}-{channel}.lock"
    with local_youtube_write_lock(lock, account=account, channel_id=channel):
        live = read()
        validate_live(plan, live)
        backup = {
            "schema": "youtube-exact-metadata-backup-v1",
            "created": datetime.now(UTC).isoformat(),
            "source": live,
            "plan_sha256": digest(plan),
        }
        exclusive_json(backup_path, backup)
        receipt = {
            "schema": "youtube-exact-metadata-result-v1",
            "video_id": plan["video_id"],
            "source_plan_sha256": digest(plan),
            "backup": str(backup_path),
            "status": "attempting",
            "provider_writes_attempted": 0,
        }
        exclusive_json(receipt_path, receipt)
        # No replay after this point. Even a transport timeout is an ambiguous mutation.
        receipt["provider_writes_attempted"] = 1
        receipt["status"] = "pending_reconciliation"
        replace_json(receipt_path, receipt)
        try:
            writer._request(
                "PUT",
                "videos",
                params={"part": "snippet,status"},
                json_body=update_body(live, tags=plan["after"]["tags"], license=plan["after"]["license"]),
                require_write=True,
            )
            postflight = read()
            validate_live(plan, postflight, after=True)
        except BaseException as error:
            receipt["error_type"] = type(error).__name__
            receipt["status"] = "pending_reconciliation"
            replace_json(receipt_path, receipt)
            raise
        receipt["status"] = "completed_live_verified"
        receipt["verified_at"] = datetime.now(UTC).isoformat()
        receipt["observed_after_sha256"] = digest(observed(postflight))
        replace_json(receipt_path, receipt)
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
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    writer = YouTubeDescriptionWriter(
        client_config=InstalledClientConfig.from_file(args.client_secret),
        token_store=TokenStore(args.data_dir),
        account_alias=args.account,
    )
    result = execute(
        plan,
        writer,
        account=args.account,
        channel=args.confirm_channel,
        execute_write=args.execute,
        backup_path=args.backup,
        receipt_path=args.receipt,
    )
    print(json.dumps({k: v for k, v in result.items() if k != "source"}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
