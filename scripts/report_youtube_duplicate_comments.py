from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.platforms.youtube.comments import comments_equivalent

_AUDIT_SCHEMA = "video-manager.youtube-comment-audit"
_DOSSIER_SCHEMA = "video-manager.youtube-duplicate-comment-dossier"


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


def _required_string(payload: dict[str, Any], key: str, *, context: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context}.{key} must be a non-empty string.")
    return value.strip()


def _plan_operations_by_video(plan: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    if plan is None:
        return {}
    operations = plan.get("operations")
    if not isinstance(operations, list) or not all(isinstance(item, dict) for item in operations):
        raise ValueError("Signed plan operations must be a list of objects.")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for operation in operations:
        video_id = _required_string(operation, "video_id", context="plan operation")
        grouped.setdefault(video_id, []).append(operation)
    return grouped


def _journal_comment_ids_by_video(journal: dict[str, Any] | None) -> dict[str, set[str]]:
    if journal is None:
        return {}
    attempts = journal.get("attempts")
    if not isinstance(attempts, dict):
        raise ValueError("Apply journal attempts must be an object.")
    grouped: dict[str, set[str]] = {}
    for operation_id, attempt in attempts.items():
        if not isinstance(attempt, dict):
            raise ValueError(f"Apply journal attempt {operation_id} must be an object.")
        if attempt.get("status") != "completed":
            continue
        video_id = _required_string(attempt, "video_id", context=f"journal attempt {operation_id}")
        comment_id = _required_string(attempt, "comment_id", context=f"journal attempt {operation_id}")
        grouped.setdefault(video_id, set()).add(comment_id)
    return grouped


def build_duplicate_dossier(
    audit: dict[str, Any],
    *,
    expected_channel: str,
    plan: dict[str, Any] | None = None,
    journal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if audit.get("schema_name") != _AUDIT_SCHEMA or audit.get("schema_version") != 1:
        raise ValueError("Unsupported YouTube comment audit schema.")
    if audit.get("channel_id") != expected_channel:
        raise ValueError("YouTube comment audit channel does not match the requested channel.")

    videos = audit.get("videos")
    if not isinstance(videos, list) or not all(isinstance(item, dict) for item in videos):
        raise ValueError("YouTube comment audit videos must be a list of objects.")

    plan_by_video = _plan_operations_by_video(plan)
    journal_ids_by_video = _journal_comment_ids_by_video(journal)
    duplicate_records: list[dict[str, Any]] = []

    for video in videos:
        video_id = _required_string(video, "video_id", context="audit video")
        raw_owned_count = video.get("owned_comment_count")
        if isinstance(raw_owned_count, bool) or not isinstance(raw_owned_count, int) or raw_owned_count < 0:
            raise ValueError(f"audit video {video_id}.owned_comment_count must be a non-negative integer.")
        if raw_owned_count <= 1:
            continue

        owned_comments = video.get("owned_comments")
        if not isinstance(owned_comments, list) or not all(isinstance(item, dict) for item in owned_comments):
            raise ValueError(f"audit video {video_id}.owned_comments must be a list of objects.")
        if len(owned_comments) != raw_owned_count:
            raise ValueError(f"audit video {video_id} owned comment list does not match owned_comment_count.")

        plan_operations = plan_by_video.get(video_id, [])
        expected_texts = [
            str(operation.get("comment_text") or "")
            for operation in plan_operations
            if isinstance(operation.get("comment_text"), str) and str(operation.get("comment_text")).strip()
        ]
        journal_comment_ids = journal_ids_by_video.get(video_id, set())

        comments: list[dict[str, Any]] = []
        for comment in owned_comments:
            comment_id = _required_string(comment, "comment_id", context=f"audit video {video_id} comment")
            text = comment.get("text")
            text_sha256 = comment.get("text_sha256")
            if not isinstance(text, str):
                raise ValueError(f"audit comment {comment_id}.text must be a string.")
            if not isinstance(text_sha256, str) or not text_sha256.startswith("sha256:"):
                raise ValueError(f"audit comment {comment_id}.text_sha256 must be a SHA-256 value.")
            comments.append(
                {
                    "comment_id": comment_id,
                    "thread_id": comment.get("thread_id"),
                    "text": text,
                    "text_sha256": text_sha256,
                    "published_at": comment.get("published_at"),
                    "updated_at": comment.get("updated_at"),
                    "moderation_status": comment.get("moderation_status"),
                    "is_completed_journal_comment": comment_id in journal_comment_ids,
                    "matches_signed_plan_text": any(comments_equivalent(text, expected) for expected in expected_texts),
                }
            )

        journal_matches = [item for item in comments if item["is_completed_journal_comment"]]
        plan_matches = [item for item in comments if item["matches_signed_plan_text"]]
        recommended_keep_comment_id: str | None = None
        recommendation_reason = "review_required"
        if len(journal_matches) == 1:
            recommended_keep_comment_id = str(journal_matches[0]["comment_id"])
            recommendation_reason = "unique_completed_journal_comment_id"
        elif len(plan_matches) == 1:
            recommended_keep_comment_id = str(plan_matches[0]["comment_id"])
            recommendation_reason = "unique_signed_plan_text_match"

        deletion_candidates = [
            str(item["comment_id"])
            for item in comments
            if recommended_keep_comment_id is not None and item["comment_id"] != recommended_keep_comment_id
        ]
        duplicate_records.append(
            {
                "video_id": video_id,
                "title": str(video.get("title") or video_id),
                "privacy_status": video.get("privacy_status"),
                "owned_comment_count": raw_owned_count,
                "comments": comments,
                "recommended_keep_comment_id": recommended_keep_comment_id,
                "recommendation_reason": recommendation_reason,
                "deletion_candidates": deletion_candidates,
                "destructive_action_authorized": False,
            }
        )

    return {
        "schema_name": _DOSSIER_SCHEMA,
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "read-only-analysis",
        "remote_writes": 0,
        "channel_id": expected_channel,
        "source_snapshot": audit.get("source_snapshot"),
        "duplicate_video_count": len(duplicate_records),
        "auto_recommendation_count": sum(
            1 for item in duplicate_records if item["recommended_keep_comment_id"] is not None
        ),
        "manual_review_count": sum(1 for item in duplicate_records if item["recommended_keep_comment_id"] is None),
        "duplicates": duplicate_records,
    }


def _write_markdown(path: Path, dossier: dict[str, Any]) -> None:
    lines = [
        "# YouTube duplicate channel-comment dossier",
        "",
        f"- Channel: `{dossier['channel_id']}`",
        f"- Duplicate videos: **{dossier['duplicate_video_count']}**",
        f"- Automatic keep recommendations: **{dossier['auto_recommendation_count']}**",
        f"- Manual reviews required: **{dossier['manual_review_count']}**",
        "- Remote writes: **0**",
        "",
    ]
    for item in dossier["duplicates"]:
        lines.extend(
            [
                f"## {item['title']}",
                "",
                f"- Video ID: `{item['video_id']}`",
                f"- Owned comments: **{item['owned_comment_count']}**",
                f"- Recommended keep: `{item['recommended_keep_comment_id'] or 'REVIEW REQUIRED'}`",
                f"- Reason: `{item['recommendation_reason']}`",
                "",
            ]
        )
        for comment in item["comments"]:
            lines.extend(
                [
                    f"### Comment `{comment['comment_id']}`",
                    "",
                    f"- Text SHA-256: `{comment['text_sha256']}`",
                    f"- Published: `{comment['published_at']}`",
                    f"- Updated: `{comment['updated_at']}`",
                    f"- Moderation: `{comment['moderation_status']}`",
                    f"- Completed journal ID: `{comment['is_completed_journal_comment']}`",
                    f"- Signed-plan text match: `{comment['matches_signed_plan_text']}`",
                    "",
                    "```text",
                    comment["text"],
                    "```",
                    "",
                ]
            )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a no-write dossier for videos with multiple channel-authored top-level comments."
    )
    parser.add_argument("audit", type=Path)
    parser.add_argument("--channel", required=True)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--journal", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        audit_path = args.audit.resolve()
        audit = _read_json(audit_path)
        plan = _read_json(args.plan.resolve()) if args.plan is not None else None
        journal = _read_json(args.journal.resolve()) if args.journal is not None else None
        dossier = build_duplicate_dossier(
            audit,
            expected_channel=args.channel,
            plan=plan,
            journal=journal,
        )
        output = args.output
        if output is None:
            output = audit_path.with_name(audit_path.stem + "-duplicate-dossier.json")
        output = output.resolve()
        _write_json(output, dossier)
        markdown = output.with_suffix(".md")
        _write_markdown(markdown, dossier)
        print("YouTube duplicate-comment dossier completed:")
        print(f"  duplicate videos: {dossier['duplicate_video_count']}")
        print(f"  automatic keep recommendations: {dossier['auto_recommendation_count']}")
        print(f"  manual reviews required: {dossier['manual_review_count']}")
        print("  remote writes: 0")
        print(f"JSON → {output}")
        print(f"Markdown → {markdown}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
