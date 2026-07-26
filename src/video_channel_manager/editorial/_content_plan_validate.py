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
    if payload.get("schema_name") != CONTENT_PLAN_SCHEMA_NAME:
        errors.append(f"schema_name must be {CONTENT_PLAN_SCHEMA_NAME}")
    if payload.get("schema_version") != CONTENT_PLAN_SCHEMA_VERSION:
        errors.append(f"schema_version must be {CONTENT_PLAN_SCHEMA_VERSION}")
    if not str(payload.get("source_snapshot") or "").strip():
        errors.append("source_snapshot cannot be blank")
    if not valid_sha256(payload.get("source_snapshot_sha256")):
        errors.append("source_snapshot_sha256 must be a sha256: digest")
    snapshot_time = parse_aware_datetime(payload.get("source_snapshot_generated_at"))
    if snapshot_time is None:
        errors.append("source_snapshot_generated_at must be a timezone-aware ISO-8601 timestamp")
    created_at = parse_aware_datetime(payload.get("created_at"))
    if created_at is None:
        errors.append("created_at must be a timezone-aware ISO-8601 timestamp")
    elif snapshot_time is not None and created_at < snapshot_time:
        errors.append("created_at cannot be earlier than source_snapshot_generated_at")
    if payload.get("mode") not in ALLOWED_PLAN_MODES:
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

    if payload.get("operation_set_sha256") != object_sha256(sorted(operation_ids)):
        errors.append("operation_set_sha256 mismatch")
    expected_counts = dict(
        sorted(Counter(str(item.get("action")) for item in operations if isinstance(item, dict)).items())
    )
    if payload.get("counts") != expected_counts:
        errors.append("counts mismatch")
    if payload.get("plan_sha256") != object_sha256(without_plan_digest(payload)):
        errors.append("plan_sha256 mismatch")
    return errors


__all__ = ["validate_content_plan"]
