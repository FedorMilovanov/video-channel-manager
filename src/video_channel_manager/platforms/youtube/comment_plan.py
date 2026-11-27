from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, Literal, NotRequired, TypedDict

from video_channel_manager.platforms.youtube.comments import (
    canonicalize_comment_text,
    comment_text_sha256,
    validate_comment_text,
)

SCHEMA_NAME = "video-manager.youtube-comment-plan"
SCHEMA_VERSION = 1
CommentAction = Literal["create", "update", "reply"]


class CommentOperation(TypedDict):
    operation_id: str
    action: CommentAction
    channel_id: str
    video_id: str
    video_title: str
    comment_text: str
    comment_sha256: str
    expected_comment_id: str | None
    expected_comment_text: str | None
    expected_comment_sha256: str | None
    expected_owned_comments: NotRequired[dict[str, str]]
    expected_parent_author_channel_id: NotRequired[str]
    source_ids: list[str]
    review_status: Literal["approved"]
    reviewed_at: str


def _canonical_json(payload: object) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(payload: object) -> str:
    return f"sha256:{hashlib.sha256(_canonical_json(payload)).hexdigest()}"


def video_id_set_sha256(video_ids: list[str]) -> str:
    normalized = sorted({item.strip() for item in video_ids if item.strip()})
    return _sha256(normalized)


def _valid_owner_comment_map(value: object, *, allow_empty: bool = False) -> bool:
    return (
        isinstance(value, dict)
        and (allow_empty or bool(value))
        and all(
            isinstance(key, str)
            and bool(key.strip())
            and isinstance(digest, str)
            and re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is not None
            for key, digest in value.items()
        )
    )


def operation_id_for(
    *,
    action: CommentAction,
    channel_id: str,
    video_id: str,
    comment_sha256: str,
    expected_comment_id: str | None,
    expected_comment_sha256: str | None,
    expected_owned_comments: dict[str, str] | None = None,
    expected_parent_author_channel_id: str | None = None,
) -> str:
    identity: dict[str, Any] = {
        "action": action,
        "channel_id": channel_id,
        "video_id": video_id,
        "comment_sha256": comment_sha256,
        "expected_comment_id": expected_comment_id,
        "expected_comment_sha256": expected_comment_sha256,
    }
    if expected_owned_comments is not None:
        identity["expected_owned_comments"] = expected_owned_comments
    if expected_parent_author_channel_id is not None:
        identity["expected_parent_author_channel_id"] = expected_parent_author_channel_id
    return _sha256(identity).removeprefix("sha256:")[:24]


def make_comment_operation(
    *,
    action: CommentAction,
    channel_id: str,
    video_id: str,
    video_title: str,
    comment_text: str,
    source_ids: list[str],
    reviewed_at: str,
    expected_comment_id: str | None = None,
    expected_comment_text: str | None = None,
    expected_owned_comments: dict[str, str] | None = None,
    expected_parent_author_channel_id: str | None = None,
) -> CommentOperation:
    normalized = validate_comment_text(comment_text)
    # The before-state can contain the very formatting error being repaired.
    expected_normalized = (
        canonicalize_comment_text(expected_comment_text) if expected_comment_text is not None else None
    )
    if action == "create" and (expected_comment_id is not None or expected_normalized is not None):
        raise ValueError("Create operations cannot declare an expected existing comment.")
    if action in {"update", "reply"} and (not expected_comment_id or not expected_normalized):
        raise ValueError("Update/reply operations require expected_comment_id and expected_comment_text.")
    if action == "reply":
        if (
            not expected_parent_author_channel_id
            or not expected_parent_author_channel_id.strip()
            or expected_owned_comments is None
        ):
            raise ValueError("Reply requires reviewed parent author and explicit owner reply map.")
    elif expected_parent_author_channel_id is not None:
        raise ValueError("Parent author belongs only to a reply operation.")
    if expected_owned_comments is not None and not _valid_owner_comment_map(
        expected_owned_comments, allow_empty=action in {"create", "reply"}
    ):
        raise ValueError("Reviewed comment requires an exact owner comment ID/hash map.")
    cleaned_sources = sorted({item.strip() for item in source_ids if item.strip()})
    if not cleaned_sources:
        raise ValueError("Approved comment operations require at least one source_id or editorial-rule ID.")
    comment_sha = comment_text_sha256(normalized)
    expected_sha = comment_text_sha256(expected_normalized) if expected_normalized is not None else None
    if (
        action == "update"
        and expected_owned_comments is not None
        and (expected_comment_id is None or expected_owned_comments.get(expected_comment_id) != expected_sha)
    ):
        raise ValueError("Reviewed update must bind the target comment's exact before digest.")
    if action == "reply" and (
        expected_owned_comments is None
        or expected_comment_id in expected_owned_comments
        or comment_sha in expected_owned_comments.values()
    ):
        raise ValueError("Reply requires a distinct text and a map of replies, not the parent itself.")
    operation_id = operation_id_for(
        action=action,
        channel_id=channel_id,
        video_id=video_id,
        comment_sha256=comment_sha,
        expected_comment_id=expected_comment_id,
        expected_comment_sha256=expected_sha,
        expected_owned_comments=expected_owned_comments,
        expected_parent_author_channel_id=expected_parent_author_channel_id,
    )
    operation: CommentOperation = {
        "operation_id": operation_id,
        "action": action,
        "channel_id": channel_id,
        "video_id": video_id,
        "video_title": video_title.strip() or video_id,
        "comment_text": normalized,
        "comment_sha256": comment_sha,
        "expected_comment_id": expected_comment_id,
        "expected_comment_text": expected_normalized,
        "expected_comment_sha256": expected_sha,
        "source_ids": cleaned_sources,
        "review_status": "approved",
        "reviewed_at": reviewed_at,
    }
    if expected_owned_comments is not None:
        operation["expected_owned_comments"] = dict(expected_owned_comments)
    if expected_parent_author_channel_id is not None:
        operation["expected_parent_author_channel_id"] = expected_parent_author_channel_id
    return operation


def _plan_without_digest(payload: dict[str, Any]) -> dict[str, Any]:
    copy = deepcopy(payload)
    copy.pop("plan_sha256", None)
    return copy


def seal_comment_plan(payload: dict[str, Any]) -> dict[str, Any]:
    plan = deepcopy(payload)
    operations = plan.get("operations")
    if not isinstance(operations, list):
        raise ValueError("Comment plan operations must be a list.")
    operation_ids = [str(item.get("operation_id") or "") for item in operations if isinstance(item, dict)]
    plan["operation_set_sha256"] = _sha256(sorted(operation_ids))
    plan["counts"] = dict(
        sorted(Counter(str(item.get("action")) for item in operations if isinstance(item, dict)).items())
    )
    plan["plan_sha256"] = _sha256(_plan_without_digest(plan))
    return plan


def build_comment_plan(
    *,
    account_alias: str,
    channel_id: str,
    source_snapshot: str,
    source_snapshot_generated_at: str,
    inventory_video_ids: list[str],
    operations: list[CommentOperation],
    mode: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_name": SCHEMA_NAME,
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "account_alias": account_alias,
        "channel_id": channel_id,
        "source_snapshot": source_snapshot,
        "source_snapshot_generated_at": source_snapshot_generated_at,
        "mode": mode,
        "inventory_video_count": len(set(inventory_video_ids)),
        "inventory_video_ids_sha256": video_id_set_sha256(inventory_video_ids),
        "operations": operations,
    }
    return seal_comment_plan(payload)


def validate_comment_plan(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_name") != SCHEMA_NAME:
        errors.append(f"schema_name must be {SCHEMA_NAME}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    channel_id = str(payload.get("channel_id") or "").strip()
    source_snapshot = str(payload.get("source_snapshot") or "").strip()
    if not channel_id:
        errors.append("channel_id cannot be blank")
    if not source_snapshot:
        errors.append("source_snapshot cannot be blank")

    operations = payload.get("operations")
    if not isinstance(operations, list):
        errors.append("operations must be a list")
        return errors
    if len(operations) > 500:
        errors.append("operations exceed the hard safety cap of 500")
    mode = payload.get("mode")
    exact_modes = (
        "reviewed-first-comment",
        "reviewed-additional-comment",
        "reviewed-comment-update",
        "reviewed-comment-reply",
    )
    if mode in exact_modes and len(operations) != 1:
        errors.append("reviewed comment plan must contain exactly one operation")

    operation_ids: list[str] = []
    video_ids: list[str] = []
    for index, raw in enumerate(operations):
        prefix = f"operations[{index}]"
        if not isinstance(raw, dict):
            errors.append(f"{prefix} must be an object")
            continue
        action = str(raw.get("action") or "")
        if action not in {"create", "update", "reply"}:
            errors.append(f"{prefix}.action must be create, update or reply")
            continue
        raw_channel = str(raw.get("channel_id") or "").strip()
        video_id = str(raw.get("video_id") or "").strip()
        if raw_channel != channel_id:
            errors.append(f"{prefix}.channel_id does not match plan channel")
        if not video_id:
            errors.append(f"{prefix}.video_id cannot be blank")
        comment_text = str(raw.get("comment_text") or "")
        try:
            normalized = validate_comment_text(comment_text)
        except ValueError as exc:
            errors.append(f"{prefix}.comment_text: {exc}")
            normalized = comment_text
        comment_sha = comment_text_sha256(normalized)
        if raw.get("comment_sha256") != comment_sha:
            errors.append(f"{prefix}.comment_sha256 mismatch")
        expected_id = str(raw.get("expected_comment_id") or "").strip() or None
        expected_text_raw = raw.get("expected_comment_text")
        expected_text = str(expected_text_raw) if expected_text_raw is not None else None
        expected_sha = comment_text_sha256(expected_text) if expected_text is not None else None
        if raw.get("expected_comment_sha256") != expected_sha:
            errors.append(f"{prefix}.expected_comment_sha256 mismatch")
        if action == "create" and (expected_id is not None or expected_text is not None):
            errors.append(f"{prefix}: create cannot include expected existing comment data")
        if action in {"update", "reply"} and (expected_id is None or expected_text is None):
            errors.append(f"{prefix}: update/reply requires exact existing comment ID and text")
        owned_map = raw.get("expected_owned_comments")
        if "expected_owned_comments" in raw and not _valid_owner_comment_map(
            owned_map, allow_empty=mode in {"reviewed-first-comment", "reviewed-comment-reply"}
        ):
            errors.append(f"{prefix}.expected_owned_comments requires an exact owner ID/hash map")
        if "expected_owned_comments" in raw and mode not in exact_modes:
            errors.append(f"{prefix}: additional create requires reviewed-additional-comment mode")
        if mode == "reviewed-first-comment" and (action != "create" or owned_map != {} or len(operations) != 1):
            errors.append(f"{prefix}: first comment plan requires one create and an explicit empty owner map")
        if mode == "reviewed-additional-comment" and (
            action != "create" or not _valid_owner_comment_map(owned_map) or len(operations) != 1
        ):
            errors.append(f"{prefix}: additional comment plan must bind one exact reviewed addition")
        if mode == "reviewed-comment-update" and (
            action != "update"
            or not _valid_owner_comment_map(owned_map)
            or not isinstance(owned_map, dict)
            or not expected_id
            or not expected_text
            or owned_map.get(expected_id) != expected_sha
            or comment_sha == expected_sha
            or any(digest == comment_sha for cid, digest in owned_map.items() if cid != expected_id)
        ):
            errors.append(
                f"{prefix}: update requires one exact target, distinct new text and complete reviewed owner map"
            )
        parent_author = raw.get("expected_parent_author_channel_id")
        if action == "reply" or mode == "reviewed-comment-reply":
            if (
                action != "reply"
                or mode != "reviewed-comment-reply"
                or not isinstance(parent_author, str)
                or not parent_author.strip()
                or not expected_id
                or not expected_text
                or not _valid_owner_comment_map(owned_map, allow_empty=True)
                or not isinstance(owned_map, dict)
                or expected_id in owned_map
                or comment_sha in owned_map.values()
                or len(operations) != 1
            ):
                errors.append(
                    f"{prefix}: reviewed reply requires an exact parent, distinct text and explicit owner reply map"
                )
        elif "expected_parent_author_channel_id" in raw:
            errors.append(f"{prefix}: parent author is only valid for a reply")
        source_ids = raw.get("source_ids")
        if not isinstance(source_ids, list) or not source_ids or not all(str(item).strip() for item in source_ids):
            errors.append(f"{prefix}.source_ids must contain at least one nonblank ID")
        if raw.get("review_status") != "approved":
            errors.append(f"{prefix}.review_status must be approved")
        expected_operation_id = operation_id_for(
            action=action,  # type: ignore[arg-type]
            channel_id=raw_channel,
            video_id=video_id,
            comment_sha256=comment_sha,
            expected_comment_id=expected_id,
            expected_comment_sha256=expected_sha,
            expected_owned_comments=owned_map if isinstance(owned_map, dict) else None,
            expected_parent_author_channel_id=parent_author if isinstance(parent_author, str) else None,
        )
        operation_id = str(raw.get("operation_id") or "")
        if operation_id != expected_operation_id:
            errors.append(f"{prefix}.operation_id mismatch")
        operation_ids.append(operation_id)
        video_ids.append(video_id)

    duplicate_operations = [item for item, count in Counter(operation_ids).items() if item and count > 1]
    duplicate_videos = [item for item, count in Counter(video_ids).items() if item and count > 1]
    if duplicate_operations:
        errors.append(f"duplicate operation IDs: {', '.join(sorted(duplicate_operations))}")
    if duplicate_videos:
        errors.append(f"multiple operations target the same video: {', '.join(sorted(duplicate_videos))}")

    expected_set_sha = _sha256(sorted(operation_ids))
    if payload.get("operation_set_sha256") != expected_set_sha:
        errors.append("operation_set_sha256 mismatch")
    expected_counts = dict(
        sorted(Counter(str(item.get("action")) for item in operations if isinstance(item, dict)).items())
    )
    if payload.get("counts") != expected_counts:
        errors.append("counts mismatch")
    expected_plan_sha = _sha256(_plan_without_digest(payload))
    if payload.get("plan_sha256") != expected_plan_sha:
        errors.append("plan_sha256 mismatch")
    return errors


__all__ = [
    "CommentAction",
    "CommentOperation",
    "SCHEMA_NAME",
    "SCHEMA_VERSION",
    "build_comment_plan",
    "make_comment_operation",
    "operation_id_for",
    "seal_comment_plan",
    "validate_comment_plan",
    "video_id_set_sha256",
]
