from __future__ import annotations

from collections import Counter
from typing import Any

from video_channel_manager.editorial._content_plan_build import without_plan_digest
from video_channel_manager.editorial._content_plan_common import (
    ALLOWED_PLAN_MODES,
    CONTENT_PLAN_SCHEMA_NAME,
    CONTENT_PLAN_SCHEMA_VERSION,
    object_sha256,
    parse_aware_datetime,
    valid_sha256,
)
from video_channel_manager.editorial._content_plan_validate_operation import validate_operation


def validate_content_plan(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    schema_name = payload.get("schema_name")
    if not isinstance(schema_name, str) or schema_name != CONTENT_PLAN_SCHEMA_NAME:
        errors.append(f"schema_name must be {CONTENT_PLAN_SCHEMA_NAME}")
    schema_version = payload.get("schema_version")
    if type(schema_version) is not int or schema_version != CONTENT_PLAN_SCHEMA_VERSION:
        errors.append(f"schema_version must be {CONTENT_PLAN_SCHEMA_VERSION}")
    source_snapshot = payload.get("source_snapshot")
    if not isinstance(source_snapshot, str) or not source_snapshot.strip():
        errors.append("source_snapshot must be a nonblank string")
    source_snapshot_sha256 = payload.get("source_snapshot_sha256")
    if not isinstance(source_snapshot_sha256, str) or not valid_sha256(source_snapshot_sha256):
        errors.append("source_snapshot_sha256 must be a sha256: digest")
    snapshot_time_raw = payload.get("source_snapshot_generated_at")
    if not isinstance(snapshot_time_raw, str):
        errors.append("source_snapshot_generated_at must be a string")
    snapshot_time = parse_aware_datetime(snapshot_time_raw) if isinstance(snapshot_time_raw, str) else None
    if snapshot_time is None:
        errors.append("source_snapshot_generated_at must be a timezone-aware ISO-8601 timestamp")
    created_at_raw = payload.get("created_at")
    if not isinstance(created_at_raw, str):
        errors.append("created_at must be a string")
    created_at = parse_aware_datetime(created_at_raw) if isinstance(created_at_raw, str) else None
    if created_at is None:
        errors.append("created_at must be a timezone-aware ISO-8601 timestamp")
    elif snapshot_time is not None and created_at < snapshot_time:
        errors.append("created_at cannot be earlier than source_snapshot_generated_at")
    mode = payload.get("mode")
    if not isinstance(mode, str):
        errors.append("mode must be a string")
    if mode not in ALLOWED_PLAN_MODES:
        errors.append("mode must be dry-run-first")
    operations = payload.get("operations")
    if not isinstance(operations, list):
        return errors + ["operations must be a list"]
    if len(operations) > 500:
        errors.append("operations exceed the hard safety cap of 500")

    operation_ids: list[str] = []
    target_keys: list[str] = []
    variation_keys: list[str] = []
    rendered_hashes: list[str] = []
    for index, raw in enumerate(operations):
        if not isinstance(raw, dict):
            errors.append(f"operations[{index}] must be an object")
            continue
        operation_errors, operation_id, target_key, variation_key, rendered_sha = validate_operation(
            raw,
            index=index,
        )
        errors.extend(operation_errors)
        operation_ids.append(operation_id)
        target_keys.append(target_key)
        variation_keys.append(variation_key)
        rendered_hashes.append(rendered_sha)

    for label, values in (
        ("operation IDs", operation_ids),
        ("targets", target_keys),
        ("variation keys", variation_keys),
        ("rendered texts", rendered_hashes),
    ):
        duplicates = sorted(value for value, count in Counter(values).items() if value and count > 1)
        if duplicates:
            errors.append(f"duplicate {label}: {', '.join(duplicates)}")

    operation_set_sha = payload.get("operation_set_sha256")
    if not isinstance(operation_set_sha, str):
        errors.append("operation_set_sha256 must be a string")
    elif not valid_sha256(operation_set_sha):
        errors.append("operation_set_sha256 must be a sha256: digest")
    if operation_set_sha != object_sha256(sorted(operation_ids)):
        errors.append("operation_set_sha256 mismatch")
    countable_actions = [
        action
        for item in operations
        if isinstance(item, dict)
        for action in [item.get("action")]
        if isinstance(action, str)
    ]
    expected_counts = dict(sorted(Counter(countable_actions).items()))
    counts = payload.get("counts")
    if not isinstance(counts, dict):
        errors.append("counts must be an object")
    elif any(key not in {"create", "update"} or type(value) is not int or value < 0 for key, value in counts.items()):
        errors.append("counts must map create/update to nonnegative integers")
    if counts != expected_counts:
        errors.append("counts mismatch")
    plan_sha = payload.get("plan_sha256")
    if not isinstance(plan_sha, str):
        errors.append("plan_sha256 must be a string")
    elif not valid_sha256(plan_sha):
        errors.append("plan_sha256 must be a sha256: digest")
    if plan_sha != object_sha256(without_plan_digest(payload)):
        errors.append("plan_sha256 mismatch")
    return errors


__all__ = ["validate_content_plan"]
