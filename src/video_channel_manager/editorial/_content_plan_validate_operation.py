from __future__ import annotations

from typing import Any, cast

from video_channel_manager.editorial._content_plan_common import (
    ContentAction,
    canonical_text,
    normalized_target_id,
    object_sha256,
    operation_id_for,
    platform_surface_error,
    target_state_key,
    text_sha256,
    valid_aware_datetime,
    valid_stable_id,
)


def validate_operation(raw: dict[str, Any], *, index: int) -> tuple[list[str], str, str, str, str]:
    errors: list[str] = []
    prefix = f"operations[{index}]"
    action_raw = raw.get("action")
    if not isinstance(action_raw, str):
        errors.append(f"{prefix}.action must be a string")
    action = action_raw.strip() if isinstance(action_raw, str) else ""
    if action not in {"create", "update"}:
        errors.append(f"{prefix}.action must be create or update")
        return errors, "", "", "", ""
    platform_raw = raw.get("platform")
    surface_raw = raw.get("surface")
    if not isinstance(platform_raw, str):
        errors.append(f"{prefix}.platform must be a string")
    if not isinstance(surface_raw, str):
        errors.append(f"{prefix}.surface must be a string")
    platform = platform_raw.strip() if isinstance(platform_raw, str) else ""
    surface = surface_raw.strip() if isinstance(surface_raw, str) else ""
    surface_error = platform_surface_error(platform, surface)
    if surface_error:
        errors.append(f"{prefix}: {surface_error}")
    target_raw = raw.get("target_id")
    if not isinstance(target_raw, str):
        errors.append(f"{prefix}.target_id must be a string")
    try:
        target_id = normalized_target_id(target_raw if isinstance(target_raw, str) else "")
    except ValueError as exc:
        target_id = target_raw.strip() if isinstance(target_raw, str) else ""
        errors.append(f"{prefix}: {exc}")
    if "reviewed_target_id" not in raw:
        errors.append(f"{prefix}.reviewed_target_id must be present")
    reviewed_target_raw = raw.get("reviewed_target_id")
    reviewed_target_id: str | None = None
    if reviewed_target_raw is not None:
        if not isinstance(reviewed_target_raw, str):
            errors.append(f"{prefix}.reviewed_target_id must be a string or null")
        try:
            reviewed_target_value = reviewed_target_raw if isinstance(reviewed_target_raw, str) else ""
            reviewed_target_id = normalized_target_id(reviewed_target_value)
        except ValueError as exc:
            errors.append(f"{prefix}.reviewed_target_id: {exc}")
        if reviewed_target_id is not None and reviewed_target_id != target_id:
            errors.append(f"{prefix}.reviewed_target_id does not match target_id")
    content_raw = raw.get("content_id")
    variation_raw = raw.get("variation_key")
    if not isinstance(content_raw, str):
        errors.append(f"{prefix}.content_id must be a string")
    if not isinstance(variation_raw, str):
        errors.append(f"{prefix}.variation_key must be a string")
    content_id = content_raw.strip() if isinstance(content_raw, str) else ""
    variation_key = variation_raw.strip() if isinstance(variation_raw, str) else ""
    if content_id and not valid_stable_id(content_id):
        errors.append(f"{prefix}.content_id must be a stable identifier")
    if variation_key and not valid_stable_id(variation_key):
        errors.append(f"{prefix}.variation_key must be a stable identifier")
    rendered_raw = raw.get("rendered_text")
    if not isinstance(rendered_raw, str):
        errors.append(f"{prefix}.rendered_text must be a string")
    rendered_text = canonical_text(rendered_raw if isinstance(rendered_raw, str) else "")
    rendered_sha = text_sha256(rendered_text)
    if raw.get("rendered_sha256") != rendered_sha:
        errors.append(f"{prefix}.rendered_sha256 mismatch")
    before_raw = raw.get("expected_before_text")
    if before_raw is not None and not isinstance(before_raw, str):
        errors.append(f"{prefix}.expected_before_text must be a string or null")
    before = canonical_text(before_raw) if isinstance(before_raw, str) else None
    before_sha = text_sha256(before) if before is not None else None
    if raw.get("expected_before_sha256") != before_sha:
        errors.append(f"{prefix}.expected_before_sha256 mismatch")
    expected_revision_raw = raw.get("expected_revision")
    if expected_revision_raw is not None and not isinstance(expected_revision_raw, str):
        errors.append(f"{prefix}.expected_revision must be a string or null")
    expected_revision = expected_revision_raw.strip() if isinstance(expected_revision_raw, str) else None
    expected_revision = expected_revision or None
    if action == "create" and (before is not None or expected_revision is not None):
        errors.append(f"{prefix}: create cannot include exact-before data")
    if action == "update" and (before is None or expected_revision is None):
        errors.append(f"{prefix}: update requires exact before-text and expected_revision")
    if not all((platform, surface, target_id, content_id, variation_key, rendered_text)):
        errors.append(f"{prefix} contains blank identity or rendered-text fields")
    source_ids_raw = raw.get("source_ids")
    source_ids: list[str] = []
    if not isinstance(source_ids_raw, list) or not source_ids_raw:
        errors.append(f"{prefix}.source_ids must contain at least one nonblank ID")
    else:
        if not all(isinstance(item, str) for item in source_ids_raw):
            errors.append(f"{prefix}.source_ids must contain only strings")
        source_ids = [item.strip() for item in source_ids_raw if isinstance(item, str)]
        if any(not item or not valid_stable_id(item) for item in source_ids):
            errors.append(f"{prefix}.source_ids must contain stable nonblank IDs")
        if len(source_ids) != len(set(source_ids)):
            errors.append(f"{prefix}.source_ids cannot contain duplicates")
        if source_ids != sorted(source_ids):
            errors.append(f"{prefix}.source_ids must be sorted")
    source_ids_sha = object_sha256(source_ids)
    if raw.get("source_ids_sha256") != source_ids_sha:
        errors.append(f"{prefix}.source_ids_sha256 mismatch")
    reviewed_at_raw = raw.get("reviewed_at")
    if not isinstance(reviewed_at_raw, str):
        errors.append(f"{prefix}.reviewed_at must be a string")
    reviewed_at = reviewed_at_raw.strip() if isinstance(reviewed_at_raw, str) else None
    reviewed_at = reviewed_at or None
    if raw.get("review_status") != "approved" or not valid_aware_datetime(reviewed_at):
        errors.append(f"{prefix} must be approved with a timezone-aware reviewed_at")
    expected_id = operation_id_for(
        action=cast(ContentAction, action),
        platform=platform,
        surface=surface,
        target_id=target_id,
        content_id=content_id,
        variation_key=variation_key,
        rendered_sha256=rendered_sha,
        expected_before_sha256=before_sha,
        expected_revision=expected_revision,
        reviewed_target_id=reviewed_target_id,
        source_ids_sha256=source_ids_sha,
        reviewed_at=reviewed_at,
    )
    operation_id = str(raw.get("operation_id") or "")
    if operation_id != expected_id:
        errors.append(f"{prefix}.operation_id mismatch")
    target_key = target_state_key(platform=platform, surface=surface, target_id=target_id)
    return errors, operation_id, target_key, variation_key, rendered_sha


__all__ = ["validate_operation"]
