from __future__ import annotations

from typing import Any

from video_channel_manager.editorial._content_plan_common import (
    normalized_target_id,
    platform_surface_error,
    same_aware_datetime,
    target_state_key,
    valid_aware_datetime,
    valid_sha256,
)


def validate_preflight_state(
    payload: dict[str, Any],
    *,
    expected_source_snapshot: str,
    expected_source_snapshot_sha256: str,
    expected_source_snapshot_generated_at: str | None = None,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    actual_snapshot = str(payload.get("source_snapshot") or "").strip()
    if actual_snapshot != expected_source_snapshot.strip():
        errors.append("state source_snapshot does not match the signed plan")
    actual_snapshot_sha256 = str(payload.get("source_snapshot_sha256") or "").strip()
    if actual_snapshot_sha256 != expected_source_snapshot_sha256.strip():
        errors.append("state source_snapshot_sha256 does not match the signed plan")
    if not valid_sha256(actual_snapshot_sha256):
        errors.append("state source_snapshot_sha256 must be a sha256: digest")
    actual_generated_at = payload.get("source_snapshot_generated_at")
    if not valid_aware_datetime(actual_generated_at):
        errors.append("state source_snapshot_generated_at must be a timezone-aware ISO-8601 timestamp")
    elif expected_source_snapshot_generated_at is not None and not same_aware_datetime(
        actual_generated_at,
        expected_source_snapshot_generated_at,
    ):
        errors.append("state source_snapshot_generated_at does not match the signed plan")
    raw_targets = payload.get("targets")
    if not isinstance(raw_targets, list):
        return {}, errors + ["state targets must be a list"]

    state_by_key: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(raw_targets):
        prefix = f"targets[{index}]"
        if not isinstance(raw, dict):
            errors.append(f"{prefix} must be an object")
            continue
        platform_raw = raw.get("platform")
        surface_raw = raw.get("surface")
        target_raw = raw.get("target_id")
        if not isinstance(platform_raw, str):
            errors.append(f"{prefix}.platform must be a string")
        if not isinstance(surface_raw, str):
            errors.append(f"{prefix}.surface must be a string")
        if not isinstance(target_raw, str):
            errors.append(f"{prefix}.target_id must be a string")
        platform = platform_raw.strip() if isinstance(platform_raw, str) else ""
        surface = surface_raw.strip() if isinstance(surface_raw, str) else ""
        surface_error = platform_surface_error(platform, surface)
        if surface_error:
            errors.append(f"{prefix}: {surface_error}")
        try:
            target_id = normalized_target_id(target_raw if isinstance(target_raw, str) else "")
        except ValueError as exc:
            target_id = target_raw.strip() if isinstance(target_raw, str) else ""
            errors.append(f"{prefix}: {exc}")
        exists = raw.get("exists")
        if not isinstance(exists, bool):
            errors.append(f"{prefix}.exists must be true or false")
        current_text = raw.get("current_text")
        revision_raw = raw.get("current_revision")
        if current_text is not None and not isinstance(current_text, str):
            errors.append(f"{prefix}.current_text must be a string or null")
        if revision_raw is not None and not isinstance(revision_raw, str):
            errors.append(f"{prefix}.current_revision must be a string or null")
        current_revision = revision_raw.strip() if isinstance(revision_raw, str) else None
        current_revision = current_revision or None
        if exists is True:
            if current_text is None:
                errors.append(f"{prefix}.current_text is required when exists is true")
            if current_revision is None:
                errors.append(f"{prefix}.current_revision is required when exists is true")
        elif exists is False:
            if current_text is not None:
                errors.append(f"{prefix}.current_text must be null when exists is false")
            if current_revision is not None:
                errors.append(f"{prefix}.current_revision must be null when exists is false")
        key = target_state_key(platform=platform, surface=surface, target_id=target_id)
        if key in state_by_key:
            errors.append(f"duplicate state target: {key}")
        else:
            state_by_key[key] = raw
    return state_by_key, errors


__all__ = ["validate_preflight_state"]
