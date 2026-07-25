from __future__ import annotations

import hashlib
import json
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, Literal, TypedDict

from video_channel_manager.platforms.youtube.comments import comment_text_sha256, validate_comment_text

SCHEMA_NAME = "video-manager.youtube-comment-plan"
SCHEMA_VERSION = 1
CommentAction = Literal["create", "update"]


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


def operation_id_for(
    *,
    action: CommentAction,
    channel_id: str,
    video_id: str,
    comment_sha256: str,
    expected_comment_id: str | None,
    expected_comment_sha256: str | None,
) -> str:
    digest = _sha256(
        {
            "action": action,
            "channel_id": channel_id,
            "video_id": video_id,
            "comment_sha256": comment_sha256,
            "expected_comment_id": expected_comment_id,
            "expected_comment_sha256": expected_comment_sha256,
        }
    )
    return digest.removeprefix("sha256:")[:24]


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
) -> CommentOperation:
    normalized = validate_comment_text(comment_text)
    expected_normalized = validate_comment_text(expected_comment_text) if expected_comment_text is not None else None
    if action == "create" and (expected_comment_id is not None or expected_normalized is not None):
        raise ValueError("Create operations cannot declare an expected existing comment.")
    if action == "update" and (not expected_comment_id or expected_normalized is None):
        raise ValueError("Update operations require expected_comment_id and expected_comment_text.")
    cleaned_sources = sorted({item.strip() for item in source_ids if item.strip()})
    if not cleaned_sources:
        raise ValueError("Approved comment operations require at least one source_id or editorial-rule ID.")
    comment_sha = comment_text_sha256(normalized)
    expected_sha = comment_text_sha256(expected_normalized) if expected_normalized is not None else None
    operation_id = operation_id_for(
        action=action,
        channel_id=channel_id,
        video_id=video_id,
        comment_sha256=comment_sha,
        expected_comment_id=expected_comment_id,
        expected_comment_sha256=expected_sha,
    )
    return {
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
    plan["counts"] = dict(sorted(Counter(str(item.get("action")) for item in operations if isinstance(item, dict)).items()))
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

    operation_ids: list[str] = []
    video_ids: list[str] = []
    for index, raw in enumerate(operations):
        prefix = f"operations[{index}]"
        if not isinstance(raw, dict):
            errors.append(f"{prefix} must be an object")
            continue
        action = str(raw.get("action") or "")
        if action not in {"create", "update"}:
            errors.append(f"{prefix}.action must be create or update")
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
        if action == "update" and (expected_id is None or expected_text is None):
            errors.append(f"{prefix}: update requires exact existing comment ID and text")
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
    expected_counts = dict(sorted(Counter(str(item.get("action")) for item in operations if isinstance(item, dict)).items()))
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
