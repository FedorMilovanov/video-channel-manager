from __future__ import annotations

from typing import Any

from video_channel_manager.editorial._content_plan_common import (
    ContentAction,
    OperationState,
    canonical_text,
    normalized_target_id,
    object_sha256,
    operation_id_for,
    platform_surface_error,
    text_sha256,
    valid_aware_datetime,
)
from video_channel_manager.editorial._content_plan_validate_operation import validate_operation
from video_channel_manager.editorial._project_profiles import PROJECT_KEYS
from video_channel_manager.editorial.content import EditorialContentRecord
from video_channel_manager.editorial.rendering import RenderedContent


def make_content_operation(
    *,
    record: EditorialContentRecord,
    rendered: RenderedContent,
    target_id: str,
    action: ContentAction,
    expected_before_text: str | None = None,
    expected_revision: str | None = None,
) -> dict[str, Any]:
    if record.status != "approved" or not valid_aware_datetime(record.reviewed_at):
        raise ValueError("Content plans can include only approved records with a timezone-aware reviewed_at.")
    if record.project_key not in PROJECT_KEYS:
        raise ValueError("Content plans require one registered project_key.")
    if action not in {"create", "update"}:
        raise ValueError(f"unsupported content action: {action}")
    normalized_target = normalized_target_id(target_id)
    surface_error = platform_surface_error(rendered.platform, rendered.surface)
    if surface_error:
        raise ValueError(surface_error)
    if not record.supports(rendered.platform, rendered.surface):
        raise ValueError(f"Content record does not allow {rendered.platform}.{rendered.surface} planning.")
    reviewed_target = record.target_for(rendered.platform, rendered.surface)
    if reviewed_target is not None:
        reviewed_target = normalized_target_id(reviewed_target)
        if normalized_target != reviewed_target:
            raise ValueError(
                f"target_id does not match reviewed platform target for {rendered.platform}.{rendered.surface}"
            )
    if not rendered.is_valid:
        raise ValueError("Cannot plan invalid rendered content.")

    normalized_text = canonical_text(rendered.text)
    before = canonical_text(expected_before_text) if expected_before_text is not None else None
    normalized_revision = expected_revision.strip() if expected_revision else None
    if action == "create" and (before is not None or normalized_revision is not None):
        raise ValueError("Create operations require an absent target and cannot declare exact-before data.")
    if action == "update" and (before is None or not normalized_revision):
        raise ValueError("Update operations require exact before-text and expected_revision guards.")

    rendered_sha = text_sha256(normalized_text)
    before_sha = text_sha256(before) if before is not None else None
    source_ids = sorted(record.source_ids)
    source_ids_sha = object_sha256(source_ids)
    operation_id = operation_id_for(
        project_key=record.project_key,
        action=action,
        platform=rendered.platform,
        surface=rendered.surface,
        target_id=normalized_target,
        content_id=record.content_id,
        variation_key=record.variation_key,
        rendered_sha256=rendered_sha,
        expected_before_sha256=before_sha,
        expected_revision=normalized_revision,
        reviewed_target_id=reviewed_target,
        source_ids_sha256=source_ids_sha,
        reviewed_at=record.reviewed_at,
    )
    return {
        "operation_id": operation_id,
        "project_key": record.project_key,
        "action": action,
        "platform": rendered.platform,
        "surface": rendered.surface,
        "target_id": normalized_target,
        "reviewed_target_id": reviewed_target,
        "content_id": record.content_id,
        "variation_key": record.variation_key,
        "rendered_text": normalized_text,
        "rendered_sha256": rendered_sha,
        "expected_before_text": before,
        "expected_before_sha256": before_sha,
        "expected_revision": normalized_revision,
        "source_ids": source_ids,
        "source_ids_sha256": source_ids_sha,
        "review_status": "approved",
        "reviewed_at": record.reviewed_at,
    }


def operation_state(
    operation: dict[str, Any],
    *,
    target_exists: bool | None,
    current_text: str | None,
    current_revision: str | None,
) -> OperationState:
    operation_errors, _, _, _, _ = validate_operation(operation, index=0)
    if operation_errors:
        return "conflict"
    if target_exists is not None and type(target_exists) is not bool:
        return "conflict"
    if current_text is not None and not isinstance(current_text, str):
        return "conflict"
    if current_revision is not None and not isinstance(current_revision, str):
        return "conflict"

    rendered_text = operation["rendered_text"]
    action = operation["action"]
    assert isinstance(rendered_text, str)
    assert isinstance(action, str)
    desired = canonical_text(rendered_text)
    current = canonical_text(current_text) if current_text is not None else None
    if target_exists is True and current is not None and text_sha256(current) == text_sha256(desired):
        return "already_applied"
    if action == "create":
        return "ready" if target_exists is False else "conflict"
    if target_exists is not True:
        return "conflict"

    expected_before = operation["expected_before_text"]
    expected_revision = operation["expected_revision"]
    assert isinstance(expected_before, str)
    assert isinstance(expected_revision, str)
    before = canonical_text(expected_before)
    if current == before and current_revision == expected_revision:
        return "ready"
    return "conflict"


__all__ = ["make_content_operation", "operation_state"]
