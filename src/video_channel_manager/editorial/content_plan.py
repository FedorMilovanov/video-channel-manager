from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, Literal

from video_channel_manager.editorial.content import EditorialContentRecord
from video_channel_manager.editorial.rendering import RenderedContent

CONTENT_PLAN_SCHEMA_NAME = "video-manager.editorial-content-plan"
CONTENT_PLAN_SCHEMA_VERSION = 1
ContentAction = Literal["create", "update"]
OperationState = Literal["ready", "already_applied", "conflict"]

_ALLOWED_PLATFORM_SURFACES = {
    "youtube": frozenset({"comment", "description"}),
    "vk": frozenset({"video_description", "post", "comment"}),
}
_ALLOWED_PLAN_MODES = frozenset({"dry-run-first"})
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def canonical_text(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in normalized.split("\n")).strip()


def text_sha256(value: str) -> str:
    return f"sha256:{hashlib.sha256(canonical_text(value).encode('utf-8')).hexdigest()}"


def _canonical_json(payload: object) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(payload: object) -> str:
    return f"sha256:{hashlib.sha256(_canonical_json(payload)).hexdigest()}"


def _valid_sha256(value: object) -> bool:
    return _SHA256_RE.fullmatch(str(value or "").strip()) is not None


def _valid_aware_datetime(value: object) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _platform_surface_error(platform: str, surface: str) -> str | None:
    allowed = _ALLOWED_PLATFORM_SURFACES.get(platform)
    if allowed is None:
        return f"unsupported platform: {platform or '<blank>'}"
    if surface not in allowed:
        return f"unsupported {platform} surface: {surface or '<blank>'}"
    return None


def target_state_key(*, platform: str, surface: str, target_id: str) -> str:
    return f"{platform.strip()}:{surface.strip()}:{target_id.strip()}"


def operation_id_for(
    *,
    action: ContentAction,
    platform: str,
    surface: str,
    target_id: str,
    content_id: str,
    variation_key: str,
    rendered_sha256: str,
    expected_before_sha256: str | None,
    expected_revision: str | None,
) -> str:
    digest = _sha256(
        {
            "action": action,
            "platform": platform,
            "surface": surface,
            "target_id": target_id,
            "content_id": content_id,
            "variation_key": variation_key,
            "rendered_sha256": rendered_sha256,
            "expected_before_sha256": expected_before_sha256,
            "expected_revision": expected_revision,
        }
    )
    return digest.removeprefix("sha256:")[:24]


def make_content_operation(
    *,
    record: EditorialContentRecord,
    rendered: RenderedContent,
    target_id: str,
    action: ContentAction,
    expected_before_text: str | None = None,
    expected_revision: str | None = None,
) -> dict[str, Any]:
    if record.status != "approved" or not record.reviewed_at:
        raise ValueError("Content plans can include only approved, reviewed records.")
    normalized_target = target_id.strip()
    if not normalized_target:
        raise ValueError("target_id cannot be blank")
    surface_error = _platform_surface_error(rendered.platform, rendered.surface)
    if surface_error:
        raise ValueError(surface_error)
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
    operation_id = operation_id_for(
        action=action,
        platform=rendered.platform,
        surface=rendered.surface,
        target_id=normalized_target,
        content_id=record.content_id,
        variation_key=record.variation_key,
        rendered_sha256=rendered_sha,
        expected_before_sha256=before_sha,
        expected_revision=normalized_revision,
    )
    return {
        "operation_id": operation_id,
        "action": action,
        "platform": rendered.platform,
        "surface": rendered.surface,
        "target_id": normalized_target,
        "content_id": record.content_id,
        "variation_key": record.variation_key,
        "rendered_text": normalized_text,
        "rendered_sha256": rendered_sha,
        "expected_before_text": before,
        "expected_before_sha256": before_sha,
        "expected_revision": normalized_revision,
        "source_ids": sorted(record.source_ids),
        "review_status": "approved",
        "reviewed_at": record.reviewed_at,
    }


def _without_plan_digest(payload: dict[str, Any]) -> dict[str, Any]:
    copy = deepcopy(payload)
    copy.pop("plan_sha256", None)
    return copy


def seal_content_plan(payload: dict[str, Any]) -> dict[str, Any]:
    plan = deepcopy(payload)
    operations = plan.get("operations")
    if not isinstance(operations, list):
        raise ValueError("Content plan operations must be a list.")
    operation_ids = [str(item.get("operation_id") or "") for item in operations if isinstance(item, dict)]
    plan["operation_set_sha256"] = _sha256(sorted(operation_ids))
    plan["counts"] = dict(
        sorted(Counter(str(item.get("action")) for item in operations if isinstance(item, dict)).items())
    )
    plan["plan_sha256"] = _sha256(_without_plan_digest(plan))
    return plan


def build_content_plan(
    *,
    source_snapshot: str,
    source_snapshot_sha256: str,
    source_snapshot_generated_at: str,
    operations: list[dict[str, Any]],
    mode: str = "dry-run-first",
) -> dict[str, Any]:
    if not source_snapshot.strip():
        raise ValueError("source_snapshot cannot be blank")
    if not _valid_sha256(source_snapshot_sha256):
        raise ValueError("source_snapshot_sha256 must be a sha256: digest")
    if not _valid_aware_datetime(source_snapshot_generated_at):
        raise ValueError("source_snapshot_generated_at must be a timezone-aware ISO-8601 timestamp")
    if mode not in _ALLOWED_PLAN_MODES:
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


def validate_content_plan(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_name") != CONTENT_PLAN_SCHEMA_NAME:
        errors.append(f"schema_name must be {CONTENT_PLAN_SCHEMA_NAME}")
    if payload.get("schema_version") != CONTENT_PLAN_SCHEMA_VERSION:
        errors.append(f"schema_version must be {CONTENT_PLAN_SCHEMA_VERSION}")
    if not str(payload.get("source_snapshot") or "").strip():
        errors.append("source_snapshot cannot be blank")
    if not _valid_sha256(payload.get("source_snapshot_sha256")):
        errors.append("source_snapshot_sha256 must be a sha256: digest")
    if not _valid_aware_datetime(payload.get("source_snapshot_generated_at")):
        errors.append("source_snapshot_generated_at must be a timezone-aware ISO-8601 timestamp")
    if not _valid_aware_datetime(payload.get("created_at")):
        errors.append("created_at must be a timezone-aware ISO-8601 timestamp")
    if payload.get("mode") not in _ALLOWED_PLAN_MODES:
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
        prefix = f"operations[{index}]"
        if not isinstance(raw, dict):
            errors.append(f"{prefix} must be an object")
            continue
        action = str(raw.get("action") or "")
        if action not in {"create", "update"}:
            errors.append(f"{prefix}.action must be create or update")
            continue
        platform = str(raw.get("platform") or "").strip()
        surface = str(raw.get("surface") or "").strip()
        surface_error = _platform_surface_error(platform, surface)
        if surface_error:
            errors.append(f"{prefix}: {surface_error}")
        target_id = str(raw.get("target_id") or "").strip()
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
        if raw.get("review_status") != "approved" or not _valid_aware_datetime(raw.get("reviewed_at")):
            errors.append(f"{prefix} must be approved with a timezone-aware reviewed_at")
        expected_id = operation_id_for(
            action=action,  # type: ignore[arg-type]
            platform=platform,
            surface=surface,
            target_id=target_id,
            content_id=content_id,
            variation_key=variation_key,
            rendered_sha256=rendered_sha,
            expected_before_sha256=before_sha,
            expected_revision=expected_revision,
        )
        operation_id = str(raw.get("operation_id") or "")
        if operation_id != expected_id:
            errors.append(f"{prefix}.operation_id mismatch")
        operation_ids.append(operation_id)
        target_keys.append(target_state_key(platform=platform, surface=surface, target_id=target_id))
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

    if payload.get("operation_set_sha256") != _sha256(sorted(operation_ids)):
        errors.append("operation_set_sha256 mismatch")
    expected_counts = dict(
        sorted(Counter(str(item.get("action")) for item in operations if isinstance(item, dict)).items())
    )
    if payload.get("counts") != expected_counts:
        errors.append("counts mismatch")
    if payload.get("plan_sha256") != _sha256(_without_plan_digest(payload)):
        errors.append("plan_sha256 mismatch")
    return errors


def validate_preflight_state(
    payload: dict[str, Any],
    *,
    expected_source_snapshot: str,
    expected_source_snapshot_sha256: str,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    actual_snapshot = str(payload.get("source_snapshot") or "").strip()
    if actual_snapshot != expected_source_snapshot.strip():
        errors.append("state source_snapshot does not match the signed plan")
    actual_snapshot_sha256 = str(payload.get("source_snapshot_sha256") or "").strip()
    if actual_snapshot_sha256 != expected_source_snapshot_sha256.strip():
        errors.append("state source_snapshot_sha256 does not match the signed plan")
    if not _valid_sha256(actual_snapshot_sha256):
        errors.append("state source_snapshot_sha256 must be a sha256: digest")
    if not _valid_aware_datetime(payload.get("source_snapshot_generated_at")):
        errors.append("state source_snapshot_generated_at must be a timezone-aware ISO-8601 timestamp")
    raw_targets = payload.get("targets")
    if not isinstance(raw_targets, list):
        return {}, errors + ["state targets must be a list"]

    state_by_key: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(raw_targets):
        prefix = f"targets[{index}]"
        if not isinstance(raw, dict):
            errors.append(f"{prefix} must be an object")
            continue
        platform = str(raw.get("platform") or "").strip()
        surface = str(raw.get("surface") or "").strip()
        target_id = str(raw.get("target_id") or "").strip()
        surface_error = _platform_surface_error(platform, surface)
        if surface_error:
            errors.append(f"{prefix}: {surface_error}")
        if not target_id:
            errors.append(f"{prefix}.target_id cannot be blank")
        exists = raw.get("exists")
        if not isinstance(exists, bool):
            errors.append(f"{prefix}.exists must be true or false")
        current_text = raw.get("current_text")
        current_revision = str(raw.get("current_revision") or "").strip() or None
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


def operation_state(
    operation: dict[str, Any],
    *,
    target_exists: bool | None,
    current_text: str | None,
    current_revision: str | None,
) -> OperationState:
    desired = canonical_text(str(operation.get("rendered_text") or ""))
    current = canonical_text(current_text) if current_text is not None else None
    if target_exists is True and current is not None and text_sha256(current) == text_sha256(desired):
        return "already_applied"
    action = str(operation.get("action") or "")
    if action == "create":
        return "ready" if target_exists is False else "conflict"
    if action != "update" or target_exists is not True:
        return "conflict"
    expected_before = operation.get("expected_before_text")
    expected_revision = str(operation.get("expected_revision") or "").strip() or None
    if expected_before is None or expected_revision is None:
        return "conflict"
    before = canonical_text(str(expected_before))
    if current == before and current_revision == expected_revision:
        return "ready"
    return "conflict"


__all__ = [
    "CONTENT_PLAN_SCHEMA_NAME",
    "CONTENT_PLAN_SCHEMA_VERSION",
    "ContentAction",
    "OperationState",
    "build_content_plan",
    "canonical_text",
    "make_content_operation",
    "operation_id_for",
    "operation_state",
    "seal_content_plan",
    "target_state_key",
    "text_sha256",
    "validate_content_plan",
    "validate_preflight_state",
]
