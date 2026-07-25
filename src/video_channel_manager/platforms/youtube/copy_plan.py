from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any

COPY_PLAN_SCHEMA_NAME = "video-manager.youtube-copy-fix-plan"
COPY_PLAN_SCHEMA_VERSION = 3


def sha256_text(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def calculate_copy_plan_sha256(plan: dict[str, Any]) -> str:
    return canonical_sha256({key: value for key, value in plan.items() if key != "plan_sha256"})


def finalize_copy_plan(plan: dict[str, Any], *, checked_video_ids: list[str]) -> dict[str, Any]:
    """Add complete coverage and self-digest fields, then validate the plan."""

    normalized_ids = sorted(checked_video_ids)
    if len(normalized_ids) != len(set(normalized_ids)):
        raise ValueError("checked_video_ids must be unique")
    plan["schema_name"] = COPY_PLAN_SCHEMA_NAME
    plan["schema_version"] = COPY_PLAN_SCHEMA_VERSION
    plan["checked_video_ids"] = normalized_ids
    plan["checked_video_ids_sha256"] = canonical_sha256(normalized_ids)
    plan["plan_sha256"] = calculate_copy_plan_sha256(plan)
    validate_copy_plan(plan)
    return plan


def _required_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"YouTube copy plan field {field} must be a nonblank string.")
    return value


def validate_copy_plan(plan: dict[str, Any]) -> None:
    """Validate schema, target identity, operation hashes, coverage, and self-digest."""

    if plan.get("schema_name") != COPY_PLAN_SCHEMA_NAME:
        raise ValueError(f"Expected schema_name {COPY_PLAN_SCHEMA_NAME}.")
    if plan.get("schema_version") != COPY_PLAN_SCHEMA_VERSION:
        raise ValueError(f"Expected schema_version {COPY_PLAN_SCHEMA_VERSION}.")
    ruleset = _required_string(plan.get("ruleset"), "ruleset")
    target_channel_id = _required_string(plan.get("target_channel_id"), "target_channel_id")
    _required_string(plan.get("source_audit_sha256"), "source_audit_sha256")
    checked_hash = _required_string(plan.get("checked_video_ids_sha256"), "checked_video_ids_sha256")

    checked_video_ids = plan.get("checked_video_ids")
    if not isinstance(checked_video_ids, list) or not all(
        isinstance(video_id, str) and video_id.strip() for video_id in checked_video_ids
    ):
        raise ValueError("YouTube copy plan checked_video_ids must be a list of nonblank strings.")
    if checked_video_ids != sorted(checked_video_ids):
        raise ValueError("YouTube copy plan checked_video_ids must be sorted.")
    if len(checked_video_ids) != len(set(checked_video_ids)):
        raise ValueError("YouTube copy plan checked_video_ids contains duplicates.")
    if checked_hash != canonical_sha256(checked_video_ids):
        raise ValueError("YouTube copy plan checked_video_ids_sha256 does not match its ID list.")

    operations = plan.get("operations")
    unresolved = plan.get("unresolved")
    if not isinstance(operations, list) or not all(isinstance(item, dict) for item in operations):
        raise ValueError("YouTube copy plan operations must be a list of objects.")
    if not isinstance(unresolved, list) or not all(isinstance(item, dict) for item in unresolved):
        raise ValueError("YouTube copy plan unresolved must be a list of objects.")
    expected_counts = {
        "operations_count": len(operations),
        "unresolved_error_videos": len(unresolved),
    }
    for field, expected in expected_counts.items():
        if plan.get(field) != expected:
            raise ValueError(f"YouTube copy plan {field} is {plan.get(field)!r}, expected {expected}.")
    videos_checked = plan.get("videos_checked")
    if videos_checked != len(checked_video_ids):
        raise ValueError(
            f"YouTube copy plan videos_checked is {videos_checked!r}, expected {len(checked_video_ids)}."
        )

    checked_set = set(checked_video_ids)
    all_planned_ids: list[str] = []
    for operation in operations:
        video_id = _required_string(operation.get("video_id"), "operation.video_id")
        channel_id = _required_string(operation.get("channel_id"), f"{video_id}.channel_id")
        before = _required_string(operation.get("before_description"), f"{video_id}.before_description")
        after = _required_string(operation.get("after_description"), f"{video_id}.after_description")
        expected_revision = _required_string(operation.get("expected_revision"), f"{video_id}.expected_revision")
        _ = expected_revision
        if video_id not in checked_set:
            raise ValueError(f"Operation {video_id} is absent from checked_video_ids.")
        if operation.get("operation") != "replace_video_description":
            raise ValueError(f"Unexpected operation type for {video_id}.")
        if operation.get("platform") != "youtube":
            raise ValueError(f"Unexpected platform for {video_id}.")
        if operation.get("ruleset") != ruleset:
            raise ValueError(f"Operation ruleset differs from the plan ruleset for {video_id}.")
        if channel_id != target_channel_id:
            raise ValueError(f"Operation {video_id} targets {channel_id}, not {target_channel_id}.")
        if before == after:
            raise ValueError(f"Operation {video_id} has identical before/after descriptions.")
        if operation.get("before_sha256") != sha256_text(before):
            raise ValueError(f"Operation before_sha256 is invalid for {video_id}.")
        if operation.get("after_sha256") != sha256_text(after):
            raise ValueError(f"Operation after_sha256 is invalid for {video_id}.")
        all_planned_ids.append(video_id)

    for item in unresolved:
        video_id = _required_string(item.get("video_id"), "unresolved.video_id")
        channel_id = _required_string(item.get("channel_id"), f"{video_id}.channel_id")
        if video_id not in checked_set:
            raise ValueError(f"Unresolved video {video_id} is absent from checked_video_ids.")
        if channel_id != target_channel_id:
            raise ValueError(f"Unresolved video {video_id} targets {channel_id}, not {target_channel_id}.")
        errors = item.get("errors")
        if not isinstance(errors, list) or not errors:
            raise ValueError(f"Unresolved video {video_id} must contain error findings.")
        all_planned_ids.append(video_id)

    duplicates = sorted(video_id for video_id, count in Counter(all_planned_ids).items() if count > 1)
    if duplicates:
        raise ValueError(f"YouTube copy plan repeats video IDs across sections: {', '.join(duplicates)}")

    expected_plan_sha256 = calculate_copy_plan_sha256(plan)
    if plan.get("plan_sha256") != expected_plan_sha256:
        raise ValueError("YouTube copy plan plan_sha256 does not match the plan payload.")


__all__ = [
    "COPY_PLAN_SCHEMA_NAME",
    "COPY_PLAN_SCHEMA_VERSION",
    "calculate_copy_plan_sha256",
    "canonical_sha256",
    "finalize_copy_plan",
    "sha256_text",
    "validate_copy_plan",
]
