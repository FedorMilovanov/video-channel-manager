from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.config import get_settings
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.youtube.comments import (
    YouTubeCommentError,
    YouTubeCommentWriter,
    YouTubeCommentsDisabledError,
)
from video_channel_manager.platforms.youtube.models import InstalledClientConfig
from video_channel_manager.platforms.youtube.store import TokenStore


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# YouTube comment audit",
        "",
        f"- Channel: `{payload['channel_id']}`",
        f"- Source snapshot: `{payload['source_snapshot']}`",
        f"- Generated: `{payload['generated_at']}`",
        "",
        "## Summary",
        "",
    ]
    counts = payload.get("counts", {})
    if isinstance(counts, dict):
        for key, value in sorted(counts.items()):
            lines.append(f"- {key}: **{value}**")
    lines.extend(["", "## Videos", ""])
    for item in payload.get("videos", []):
        if not isinstance(item, dict):
            continue
        lines.append(f"### {item.get('title') or item.get('video_id')}")
        lines.append("")
        lines.append(f"- Video: `https://www.youtube.com/watch?v={item.get('video_id')}`")
        lines.append(f"- Status: `{item.get('status')}`")
        lines.append(f"- Total top-level comments: `{item.get('top_level_comment_count')}`")
        lines.append(f"- Channel-authored comments: `{item.get('owned_comment_count')}`")
        error = str(item.get("error") or "").strip()
        if error:
            lines.append(f"- Error: `{error}`")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _inventory_sha256(video_ids: list[str]) -> str:
    encoded = json.dumps(sorted(set(video_ids)), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Read every live YouTube video's top-level comments without writing.")
    parser.add_argument("snapshot", type=Path, help="YouTube AuditPackage JSON")
    parser.add_argument("--account", default="legendary-poet")
    parser.add_argument("--channel", default="", help="Exact channel ID; defaults to the snapshot channel")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--include-nonpublic", action="store_true")
    args = parser.parse_args()

    try:
        package = AuditPackage.model_validate_json(args.snapshot.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"ERROR: cannot read AuditPackage: {exc}", file=sys.stderr)
        return 2

    channel_id = args.channel.strip() or package.channel.ref.channel_id
    if channel_id != package.channel.ref.channel_id:
        print(
            f"ERROR: snapshot channel is {package.channel.ref.channel_id}, not requested {channel_id}.",
            file=sys.stderr,
        )
        return 2

    settings = get_settings()
    try:
        config = InstalledClientConfig.from_file(settings.youtube_client_secret_file)
        store = TokenStore(settings.data_dir)
        writer = YouTubeCommentWriter(client_config=config, token_store=store, account_alias=args.account)
    except (OSError, ValueError) as exc:
        print(f"ERROR: YouTube configuration: {exc}", file=sys.stderr)
        return 2

    candidates = [
        video for video in package.videos if args.include_nonpublic or (video.privacy_status or "").lower() == "public"
    ]
    results: list[dict[str, Any]] = []
    for index, video in enumerate(candidates, start=1):
        video_id = video.ref.remote_id
        print(f"[{index}/{len(candidates)}] Reading comments — {video.title}")
        try:
            comments = writer.list_top_level_comments(video_id)
        except YouTubeCommentsDisabledError as exc:
            results.append(
                {
                    "video_id": video_id,
                    "title": video.title,
                    "privacy_status": video.privacy_status,
                    "status": "comments_disabled",
                    "top_level_comment_count": 0,
                    "owned_comment_count": 0,
                    "owned_comments": [],
                    "error": str(exc),
                }
            )
            continue
        except YouTubeCommentError as exc:
            results.append(
                {
                    "video_id": video_id,
                    "title": video.title,
                    "privacy_status": video.privacy_status,
                    "status": "error",
                    "top_level_comment_count": 0,
                    "owned_comment_count": 0,
                    "owned_comments": [],
                    "error": str(exc),
                }
            )
            continue

        owned = [item for item in comments if item.author_channel_id == channel_id]
        if owned:
            status = "owned_present"
        elif comments:
            status = "foreign_only"
        else:
            status = "missing"
        results.append(
            {
                "video_id": video_id,
                "title": video.title,
                "privacy_status": video.privacy_status,
                "status": status,
                "top_level_comment_count": len(comments),
                "owned_comment_count": len(owned),
                "owned_comments": [
                    {
                        "thread_id": item.thread_id,
                        "comment_id": item.comment_id,
                        "text": item.text,
                        "text_sha256": item.text_sha256,
                        "published_at": item.published_at.isoformat() if item.published_at else None,
                        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
                        "moderation_status": item.moderation_status,
                    }
                    for item in owned
                ],
                "error": None,
            }
        )

    payload: dict[str, Any] = {
        "schema_name": "video-manager.youtube-comment-audit",
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "account_alias": args.account,
        "channel_id": channel_id,
        "source_snapshot": str(package.snapshot_id),
        "source_snapshot_generated_at": package.generated_at.isoformat(),
        "inventory_video_count": len(candidates),
        "inventory_video_ids_sha256": _inventory_sha256([item.ref.remote_id for item in candidates]),
        "counts": dict(sorted(Counter(str(item["status"]) for item in results).items())),
        "videos": results,
    }

    if args.output is None:
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        args.output = settings.data_dir / "reports" / f"youtube-comment-audit-{channel_id}-{timestamp}.json"
    _write_json(args.output, payload)
    report_path = args.output.with_suffix(".md")
    _write_markdown(report_path, payload)

    print("YouTube comment audit completed:")
    for status, count in payload["counts"].items():
        print(f"  {status}: {count}")
    print(f"JSON → {args.output}")
    print(f"Markdown → {report_path}")
    return 0 if not payload["counts"].get("error") else 1


if __name__ == "__main__":
    raise SystemExit(main())
