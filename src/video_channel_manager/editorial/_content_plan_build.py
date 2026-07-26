from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from video_channel_manager.editorial._content_plan_common import (
    ALLOWED_PLAN_MODES,
    CONTENT_PLAN_SCHEMA_NAME,
    CONTENT_PLAN_SCHEMA_VERSION,
    object_sha256,
    valid_aware_datetime,
    valid_sha256,
)


def without_plan_digest(payload: dict[str, Any]) -> dict[str, Any]:
    copy = deepcopy(payload)
    copy.pop("plan_sha256", None)
    return copy


def _operation_identity(operations: list[object]) -> tuple[list[str], list[str]]:
    operation_ids: list[str] = []
    actions: list[str] = []
    for index, item in enumerate(operations):
        if not isinstance(item, dict):
            raise ValueError(f"Content plan operations[{index}] must be an object.")
        operation_id = item.get("operation_id")
        if not isinstance(operation_id, str) or not operation_id.strip():
            raise ValueError(f"Content plan operations[{index}].operation_id must be a nonblank string.")
        action = item.get("action")
        if not isinstance(action, str) or action not in {"create", "update"}:
            raise ValueError(f"Content plan operations[{index}].action must be create or update.")
        operation_ids.append(operation_id)
        actions.append(action)
    return operation_ids, actions


def seal_content_plan(payload: dict[str, Any]) -> dict[str, Any]:
    plan = deepcopy(payload)
    operations = plan.get("operations")
    if not isinstance(operations, list):
        raise ValueError("Content plan operations must be a list.")
    operation_ids, actions = _operation_identity(operations)
    plan["operation_set_sha256"] = object_sha256(sorted(operation_ids))
    plan["counts"] = dict(sorted(Counter(actions).items()))
    plan["plan_sha256"] = object_sha256(without_plan_digest(plan))
    return plan


def build_content_plan(
    *,
    source_snapshot: str,
    source_snapshot_sha256: str,
    source_snapshot_generated_at: str,
    operations: list[dict[str, Any]],
    mode: str = "dry-run-first",
) -> dict[str, Any]:
    if not isinstance(source_snapshot, str) or not source_snapshot.strip():
        raise ValueError("source_snapshot must be a nonblank string")
    if not isinstance(source_snapshot_sha256, str) or not valid_sha256(source_snapshot_sha256):
        raise ValueError("source_snapshot_sha256 must be a sha256: digest")
    if not isinstance(source_snapshot_generated_at, str) or not valid_aware_datetime(source_snapshot_generated_at):
        raise ValueError("source_snapshot_generated_at must be a timezone-aware ISO-8601 timestamp")
    if not isinstance(mode, str) or mode not in ALLOWED_PLAN_MODES:
        raise ValueError(f"unsupported content plan mode: {mode}")
    payload: dict[str, Any] = {
        "schema_name": CONTENT_PLAN_SCHEMA_NAME,
        "schema_version": CONTENT_PLAN_SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "source_snapshot": source_snapshot,
        "source_snapshot_sha256": source_snapshot_sha256,
        "source_snapshot_generated_at": source_snapshot_generated_at,
        "mode": mode,
        "operations": operations,
    }
    return seal_content_plan(payload)


__all__ = ["build_content_plan", "seal_content_plan", "without_plan_digest"]
