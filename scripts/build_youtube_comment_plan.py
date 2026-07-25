from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.config import get_settings
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.youtube.comment_plan import (
    CommentOperation,
    build_comment_plan,
    make_comment_operation,
    validate_comment_plan,
    video_id_set_sha256,
)
from video_channel_manager.platforms.youtube.comments import comments_equivalent

_CONTENT_SCHEMA = "video-manager.youtube-comment-content"
_AUDIT_SCHEMA = "video-manager.youtube-comment-audit"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _load_content_records(content_dir: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for path in sorted(content_dir.rglob("*.json")):
        payload = _read_json(path)
        if payload.get("schema_name") != _CONTENT_SCHEMA:
            continue
        if payload.get("schema_version") != 1:
            raise ValueError(f"Unsupported comment content schema in {path}")
        video_id = str(payload.get("video_id") or "").strip()
        if not video_id:
            raise ValueError(f"Comment content has no video_id: {path}")
        if video_id in records:
            raise ValueError(f"Duplicate approved content for video {video_id}: {path}")
        payload["_path"] = str(path)
        records[video_id] = payload
    return records


def _report_markdown(
    *,
    plan: dict[str, Any],
    already_applied: list[dict[str, str]],
    review_only: list[dict[str, str]],
    unused_content: list[dict[str, str]],
) -> str:
    lines = [
        "# YouTube comment plan build report",
        "",
        f"- Channel: `{plan['channel_id']}`",
        f"- Source snapshot: `{plan['source_snapshot']}`",
        f"- Plan SHA-256: `{plan['plan_sha256']}`",
        f"- Operations: **{len(plan['operations'])}**",
        f"- Already applied: **{len(already_applied)}**",
        f"- Review-only: **{len(review_only)}**",
        f"- Unused content records: **{len(unused_content)}**",
        "",
    ]
    for heading, rows in (
        ("Operations", plan["operations"]),
        ("Already applied", already_applied),
        ("Review-only", review_only),
        ("Unused content", unused_content),
    ):
        lines.extend([f"## {heading}", ""])
        if not rows:
            lines.extend(["None.", ""])
            continue
        for item in rows:
            lines.append(
                f"- `{item.get('video_id', '')}` — {item.get('video_title') or item.get('title') or ''}"
                + (f" — {item.get('reason')}" if item.get("reason") else "")
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a self-validating plan from human-approved YouTube comments.")
    parser.add_argument("snapshot", type=Path, help="YouTube AuditPackage JSON")
    parser.add_argument("audit", type=Path, help="JSON produced by audit_youtube_comments.py")
    parser.add_argument("--content-dir", type=Path, default=Path("content/youtube-comments"))
    parser.add_argument("--account", default="legendary-poet")
    parser.add_argument("--include-updates", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        package = AuditPackage.model_validate_json(args.snapshot.read_text(encoding="utf-8"))
        audit = _read_json(args.audit)
        content = _load_content_records(args.content_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot load inputs: {exc}", file=sys.stderr)
        return 2

    channel_id = package.channel.ref.channel_id
    public_videos = [item for item in package.videos if (item.privacy_status or "").lower() == "public"]
    video_by_id = {item.ref.remote_id: item for item in public_videos}
    expected_inventory_sha = video_id_set_sha256(list(video_by_id))
    if audit.get("schema_name") != _AUDIT_SCHEMA or audit.get("schema_version") != 1:
        print("ERROR: unsupported YouTube comment audit schema.", file=sys.stderr)
        return 2
    if audit.get("channel_id") != channel_id:
        print("ERROR: audit channel does not match the snapshot channel.", file=sys.stderr)
        return 2
    if audit.get("source_snapshot") != str(package.snapshot_id):
        print("ERROR: audit source snapshot does not match the supplied AuditPackage.", file=sys.stderr)
        return 2
    if audit.get("inventory_video_ids_sha256") != expected_inventory_sha:
        print("ERROR: audit inventory hash does not match the current public-video set.", file=sys.stderr)
        return 2

    audit_videos = audit.get("videos")
    if not isinstance(audit_videos, list):
        print("ERROR: audit videos must be a list.", file=sys.stderr)
        return 2
    audit_by_id = {
        str(item.get("video_id") or ""): item for item in audit_videos if isinstance(item, dict) and item.get("video_id")
    }
    if set(audit_by_id) != set(video_by_id):
        print("ERROR: audit does not cover exactly the current public-video set.", file=sys.stderr)
        return 2

    operations: list[CommentOperation] = []
    already_applied: list[dict[str, str]] = []
    review_only: list[dict[str, str]] = []
    used_content: set[str] = set()

    for video_id, record in sorted(content.items()):
        if record.get("status") != "approved":
            continue
        used_content.add(video_id)
        video = video_by_id.get(video_id)
        if video is None:
            review_only.append(
                {"video_id": video_id, "video_title": str(record.get("video_title") or ""), "reason": "not public or absent"}
            )
            continue
        if record.get("channel_id") != channel_id:
            review_only.append(
                {"video_id": video_id, "video_title": video.title, "reason": "content channel mismatch"}
            )
            continue
        source_ids = record.get("source_ids")
        if not isinstance(source_ids, list):
            review_only.append({"video_id": video_id, "video_title": video.title, "reason": "source_ids missing"})
            continue
        comment_text = str(record.get("comment_text") or "")
        reviewed_at = str(record.get("reviewed_at") or "").strip()
        if not reviewed_at:
            review_only.append({"video_id": video_id, "video_title": video.title, "reason": "reviewed_at missing"})
            continue

        live = audit_by_id[video_id]
        status = str(live.get("status") or "")
        owned_comments = live.get("owned_comments")
        owned = [item for item in owned_comments if isinstance(item, dict)] if isinstance(owned_comments, list) else []
        if status in {"missing", "foreign_only"} and not owned:
            try:
                operations.append(
                    make_comment_operation(
                        action="create",
                        channel_id=channel_id,
                        video_id=video_id,
                        video_title=video.title,
                        comment_text=comment_text,
                        source_ids=[str(item) for item in source_ids],
                        reviewed_at=reviewed_at,
                    )
                )
            except ValueError as exc:
                review_only.append({"video_id": video_id, "video_title": video.title, "reason": str(exc)})
            continue
        if status == "owned_present" and len(owned) == 1:
            existing_text = str(owned[0].get("text") or "")
            if comments_equivalent(existing_text, comment_text):
                already_applied.append({"video_id": video_id, "video_title": video.title, "reason": "identical"})
                continue
            if args.include_updates:
                try:
                    operations.append(
                        make_comment_operation(
                            action="update",
                            channel_id=channel_id,
                            video_id=video_id,
                            video_title=video.title,
                            comment_text=comment_text,
                            source_ids=[str(item) for item in source_ids],
                            reviewed_at=reviewed_at,
                            expected_comment_id=str(owned[0].get("comment_id") or ""),
                            expected_comment_text=existing_text,
                        )
                    )
                except ValueError as exc:
                    review_only.append({"video_id": video_id, "video_title": video.title, "reason": str(exc)})
            else:
                review_only.append(
                    {"video_id": video_id, "video_title": video.title, "reason": "different owned comment; updates disabled"}
                )
            continue
        review_only.append(
            {
                "video_id": video_id,
                "video_title": video.title,
                "reason": f"audit status {status}; owned comments {len(owned)}",
            }
        )

    unused_content = [
        {
            "video_id": video_id,
            "video_title": str(record.get("video_title") or video_id),
            "reason": "record is not approved",
        }
        for video_id, record in sorted(content.items())
        if video_id not in used_content
    ]
    plan = build_comment_plan(
        account_alias=args.account,
        channel_id=channel_id,
        source_snapshot=str(package.snapshot_id),
        source_snapshot_generated_at=package.generated_at.isoformat(),
        inventory_video_ids=list(video_by_id),
        operations=operations,
        mode="reviewed-create-and-update" if args.include_updates else "reviewed-missing-only",
    )
    validation_errors = validate_comment_plan(plan)
    if validation_errors:
        print("ERROR: generated plan failed self-validation:", file=sys.stderr)
        for error in validation_errors:
            print(f"  - {error}", file=sys.stderr)
        return 2

    settings = get_settings()
    if args.output is None:
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        args.output = settings.data_dir / "reports" / f"youtube-comment-plan-{channel_id}-{timestamp}.json"
    _write_json(args.output, plan)
    report_path = args.output.with_suffix(".md")
    report_path.write_text(
        _report_markdown(
            plan=plan,
            already_applied=already_applied,
            review_only=review_only,
            unused_content=unused_content,
        ),
        encoding="utf-8",
    )

    print("YouTube comment plan built:")
    print(f"  operations: {len(operations)}")
    print(f"  already applied: {len(already_applied)}")
    print(f"  review-only: {len(review_only)}")
    print(f"  plan SHA-256: {plan['plan_sha256']}")
    print(f"JSON → {args.output}")
    print(f"Markdown → {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
