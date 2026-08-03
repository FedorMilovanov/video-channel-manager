from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Literal

CONTENT_PLAN_SCHEMA_NAME = "video-manager.editorial-content-plan"
CONTENT_PLAN_SCHEMA_VERSION = 2
ContentAction = Literal["create", "update"]
OperationState = Literal["ready", "already_applied", "conflict"]

ALLOWED_PLATFORM_SURFACES = {
    "youtube": frozenset({"comment", "description"}),
    "vk": frozenset({"video_description", "post", "comment"}),
}
ALLOWED_PLAN_MODES = frozenset({"dry-run-first"})
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_STABLE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,159}$")


def canonical_text(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in normalized.split("\n")).strip()


def text_sha256(value: str) -> str:
    return f"sha256:{hashlib.sha256(canonical_text(value).encode('utf-8')).hexdigest()}"


def canonical_json(payload: object) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def object_sha256(payload: object) -> str:
    return f"sha256:{hashlib.sha256(canonical_json(payload)).hexdigest()}"


def valid_sha256(value: object) -> bool:
    return isinstance(value, str) and _SHA256_RE.fullmatch(value.strip()) is not None


def valid_stable_id(value: object) -> bool:
    return isinstance(value, str) and _STABLE_ID_RE.fullmatch(value.strip()) is not None


def parse_aware_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def valid_aware_datetime(value: object) -> bool:
    return parse_aware_datetime(value) is not None


def same_aware_datetime(left: object, right: object) -> bool:
    left_value = parse_aware_datetime(left)
    right_value = parse_aware_datetime(right)
    return left_value is not None and right_value is not None and left_value.timestamp() == right_value.timestamp()


def platform_surface_error(platform: str, surface: str) -> str | None:
    allowed = ALLOWED_PLATFORM_SURFACES.get(platform)
    if allowed is None:
        return f"unsupported platform: {platform or '<blank>'}"
    if surface not in allowed:
        return f"unsupported {platform} surface: {surface or '<blank>'}"
    return None


def normalized_target_id(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("target_id cannot be blank")
    if any(character.isspace() for character in normalized):
        raise ValueError("target_id cannot contain whitespace")
    return normalized


def target_state_key(*, platform: str, surface: str, target_id: str) -> str:
    return f"{platform.strip()}:{surface.strip()}:{target_id.strip()}"


def operation_id_for(
    *,
    project_key: str,
    action: ContentAction,
    platform: str,
    surface: str,
    target_id: str,
    content_id: str,
    variation_key: str,
    rendered_sha256: str,
    expected_before_sha256: str | None,
    expected_revision: str | None,
    reviewed_target_id: str | None = None,
    source_ids_sha256: str | None = None,
    reviewed_at: str | None = None,
) -> str:
    digest = object_sha256(
        {
            "project_key": project_key,
            "action": action,
            "platform": platform,
            "surface": surface,
            "target_id": target_id,
            "content_id": content_id,
            "variation_key": variation_key,
            "rendered_sha256": rendered_sha256,
            "expected_before_sha256": expected_before_sha256,
            "expected_revision": expected_revision,
            "reviewed_target_id": reviewed_target_id,
            "source_ids_sha256": source_ids_sha256,
            "reviewed_at": reviewed_at,
        }
    )
    return digest.removeprefix("sha256:")[:24]


__all__ = [
    "ALLOWED_PLAN_MODES",
    "ALLOWED_PLATFORM_SURFACES",
    "CONTENT_PLAN_SCHEMA_NAME",
    "CONTENT_PLAN_SCHEMA_VERSION",
    "ContentAction",
    "OperationState",
    "canonical_text",
    "normalized_target_id",
    "object_sha256",
    "operation_id_for",
    "parse_aware_datetime",
    "platform_surface_error",
    "same_aware_datetime",
    "target_state_key",
    "text_sha256",
    "valid_aware_datetime",
    "valid_sha256",
    "valid_stable_id",
]
