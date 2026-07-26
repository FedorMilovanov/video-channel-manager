from __future__ import annotations

from typing import Any, cast

from video_channel_manager.editorial._content_plan_common import target_state_key


def required_string(
    payload: dict[str, Any],
    key: str,
    *,
    context: str,
) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context}.{key} must be a nonblank string")
    return value.strip()


def optional_string(
    payload: dict[str, Any],
    key: str,
    *,
    context: str,
) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{context}.{key} must be a string or null")
    return value


def operation_key(raw: dict[str, Any]) -> str:
    return target_state_key(
        platform=cast(str, raw["platform"]),
        surface=cast(str, raw["surface"]),
        target_id=cast(str, raw["target_id"]),
    )


__all__ = ["operation_key", "optional_string", "required_string"]
