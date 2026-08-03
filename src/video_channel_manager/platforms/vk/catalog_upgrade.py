from __future__ import annotations

from copy import deepcopy
from typing import Any

from video_channel_manager.editorial._project_profiles import resolve_project_key
from video_channel_manager.platforms.vk.catalog import (
    VK_CATALOG_PLAN_SCHEMA,
    VK_CATALOG_PLAN_VERSION,
    VK_CATALOG_POLICY_VERSION,
    calculate_vk_catalog_plan_sha256,
)


def upgrade_vk_catalog_plan_identity(plan: dict[str, Any]) -> dict[str, Any]:
    """Upgrade a signed legacy catalog plan to the project-bound schema.

    The old plan digest is verified before any field is changed. Project identity
    may be inferred only from registered exact source-channel and target-community
    IDs; an explicit project key must agree with those provider identities.
    Full operation validation remains the caller's responsibility because some
    adapters intentionally remove or replace operations before validating.
    """

    if plan.get("schema_name") != VK_CATALOG_PLAN_SCHEMA:
        raise ValueError("Unexpected VK catalog plan schema")
    original_digest = plan.get("plan_sha256")
    if not isinstance(original_digest, str) or not original_digest.startswith("sha256:"):
        raise ValueError("VK catalog plan has no valid self-digest")
    if original_digest != calculate_vk_catalog_plan_sha256(plan):
        raise ValueError("VK catalog plan self-digest does not match its contents")

    project_key = resolve_project_key(
        {
            "project_key": plan.get("project_key"),
            "channel_id": plan.get("source_channel_id"),
            "community_id": plan.get("target_community_id"),
        }
    )
    if project_key is None:
        raise ValueError(
            "VK catalog project identity is unknown or conflicting; "
            "legacy plan cannot be upgraded safely"
        )

    upgraded = deepcopy(plan)
    upgraded["schema_version"] = VK_CATALOG_PLAN_VERSION
    upgraded["policy_version"] = VK_CATALOG_POLICY_VERSION
    upgraded["project_key"] = project_key
    operations = upgraded.get("text_operations")
    if not isinstance(operations, list):
        raise ValueError("VK catalog plan text_operations must be a list")
    for operation in operations:
        if not isinstance(operation, dict):
            raise ValueError("VK catalog text operation must be an object")
        existing_project = operation.get("project_key")
        if existing_project not in (None, "", project_key):
            raise ValueError(
                f"VK catalog text operation project conflicts with provider identity: "
                f"{operation.get('operation_id')}"
            )
        operation["project_key"] = project_key

    upgraded["plan_sha256"] = calculate_vk_catalog_plan_sha256(upgraded)
    return upgraded


__all__ = ["upgrade_vk_catalog_plan_identity"]
