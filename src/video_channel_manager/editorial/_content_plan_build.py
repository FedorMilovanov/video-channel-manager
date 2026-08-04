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
from video_channel_manager.editorial._content_plan_validate_operation import validate_operation
from video_channel_manager.editorial._project_profiles import PROJECT_KEYS


def without_plan_digest(payload: dict[str, Any]) -> dict[str, Any]:
    copy = deepcopy(payload)
    copy.pop("plan_sha256", None)
    return copy


def _operation_identity(operations: list[object]) -> tuple[list[str], list[str], str]:
    operation_ids: list[str] = []
    actions: list[str] = []
    project_keys: set[str] = set()
    for index, item in enumerate(operations):
        if not isinstance(item, dict):
            raise ValueError(f"Content plan operations[{index}] must be an object.")
        errors, operation_id, _, _, _ = validate_operation(item, index=index)
        if errors:
            detail = "; ".join(errors)
            raise ValueError(f"Cannot seal invalid content plan: {detail}")
        action = item["action"]
        project_key = item["project_key"]
        assert isinstance(action, str)
        assert isinstance(project_key, str)
        operation_ids.append(operation_id)
        actions.append(action)
        project_keys.add(project_key)
    if not operation_ids:
        raise ValueError("Content plan requires at least one operation.")
    if len(project_keys) != 1:
        raise ValueError(f"Content plan operations must belong to one project: {sorted(project_keys)}")
    project_key = next(iter(project_keys))
    if project_key not in PROJECT_KEYS:
        raise ValueError(f"unsupported content plan project_key: {project_key}")
    return operation_ids, actions, project_key


def seal_content_plan(payload: dict[str, Any]) -> dict[str, Any]:
    plan = deepcopy(payload)
    operations = plan.get("operations")
    if not isinstance(operations, list):
        raise ValueError("Content plan operations must be a list.")
    operation_ids, actions, project_key = _operation_identity(operations)
    declared_project = plan.get("project_key")
    if declared_project is not None and declared_project != project_key:
        raise ValueError(
            f"Content plan project_key {declared_project!r} does not match operations project {project_key!r}."
        )
    plan["project_key"] = project_key
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
