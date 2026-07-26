from __future__ import annotations

from typing import Any, cast

from video_channel_manager.editorial._content_plan_common import (
    ContentAction,
    canonical_text,
    normalized_target_id,
    operation_id_for,
    platform_surface_error,
    target_state_key,
    text_sha256,
    valid_aware_datetime,
)


def validate_operation(raw: dict[str, Any], *, index: int) -> tuple[list[str], str, str, str, str]:
    errors: list[str] = []
    prefix = f"operations[{index}]"
    action = str(raw.get("action") or "")
    if action not in {"create", "update"}:
        errors.append(f"{prefix}.action must be create or update")
        return errors, "", "", "", ""
    platform = str(raw.get("platform") or "").strip()
    surface = str(raw.get("surface") or "").strip()
    surface_error = platform_surface_error(platform, surface)
    if surface_error:
        errors.append(f"{prefix}: {surface_error}")
    try:
        target_id = normalized_target_id(str(raw.get("target_id") or ""))
    except ValueError as exc:
        target_id = str(raw.get("target_id") or "").strip()
        errors.append(f"{prefix}: {exc}")
    if "reviewed_target_id" not in raw:
        errors.append(f"{prefix}.reviewed_target_id must be present")
    reviewed_target_raw = raw.get("reviewed_target_id")
    reviewed_target_id: str | None = None
    if reviewed_target_raw is not None:
        try:
            reviewed_target_id = normalized_target_id(str(reviewed_target_raw))
        except ValueError as exc:
            errors.append(f"{prefix}.reviewed_target_id: {exc}")
        if reviewed_target_id is not None and reviewed_target_id != target_id:
            errors.append(f"{prefix}.reviewed_target_id does not match target_id")
    content_id = str(raw.get("content_id") or "").strip()
    variation_key = str(raw.get("variation_key") or "").strip()
    rendered_text = canonical_text(str(raw.get("rendered_text") or ""))
    rendered_sha = text_sha256(rendered_text)
    if raw.get("rendered_sha256") != rendered_sha:
        errors.append(f"{prefix}.rendered_sha256 mismatch")
    before_raw = raw.get("expected_before_text")
    before = canonical_text(str(before_raw)) if before_raw is not None else None
    before_sha = text_sha256(before) if before is not None else None
    if raw.get("expected_before_sha256") != before_sha:
        errors.append(f"{prefix}.expected_before_sha256 mismatch")
    expected_revision = str(raw.get("expected_revision") or "").strip() or None
    if action == "create" and (before is not None or expected_revision is not None):
        errors.append(f"{prefix}: create cannot include exact-before data")
    if action == "update" and (before is None or expected_revision is None):
        errors.append(f"{prefix}: update requires exact before-text and expected_revision")
    if not all((platform, surface, target_id, content_id, variation_key, rendered_text)):
        errors.append(f"{prefix} contains blank identity or rendered-text fields")
    source_ids = raw.get("source_ids")
    if not isinstance(source_ids, list) or not source_ids or not all(str(item).strip() for item in source_ids):
        errors.append(f"{prefix}.source_ids must contain at least one nonblank ID")
    elif len(source_ids) != len({str(item).strip() for item in source_ids}):
        errors.append(f"{prefix}.source_ids cannot contain duplicates")
    if raw.get("review_status") != "approved" or not valid_aware_datetime(raw.get("reviewed_at")):
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
    )
    operation_id = str(raw.get("operation_id") or "")
    if operation_id != expected_id:
        errors.append(f"{prefix}.operation_id mismatch")
    target_key = target_state_key(platform=platform, surface=surface, target_id=target_id)
    return errors, operation_id, target_key, variation_key, rendered_sha


__all__ = ["validate_operation"]
