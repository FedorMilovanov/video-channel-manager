"""Signed editorial content plans with fail-closed operation and preflight guards."""

from video_channel_manager.editorial._content_plan_build import build_content_plan, seal_content_plan
from video_channel_manager.editorial._content_plan_common import (
    CONTENT_PLAN_SCHEMA_NAME,
    CONTENT_PLAN_SCHEMA_VERSION,
    ContentAction,
    OperationState,
    canonical_text,
    operation_id_for,
    target_state_key,
    text_sha256,
)
from video_channel_manager.editorial._content_plan_operations import make_content_operation, operation_state
from video_channel_manager.editorial._content_plan_preflight import validate_preflight_state
from video_channel_manager.editorial._content_plan_validate import validate_content_plan

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
