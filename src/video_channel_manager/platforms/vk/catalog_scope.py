from __future__ import annotations

from copy import deepcopy
from typing import Any

from video_channel_manager.platforms.vk.catalog import (
    calculate_vk_catalog_plan_sha256,
    validate_vk_catalog_plan,
)

VK_CATALOG_OPERATION_SCOPE_CATALOG_ONLY = "catalog_only"
_DESCRIPTION_REVIEW_KINDS = frozenset({"description_requires_editorial_review"})


def restrict_vk_catalog_plan_to_catalog_only(plan: dict[str, Any]) -> dict[str, Any]:
    """Return a self-validating copy that can only mutate albums and placements."""

    scoped = deepcopy(plan)
    scoped["operation_scope"] = VK_CATALOG_OPERATION_SCOPE_CATALOG_ONLY
    scoped["text_operations"] = []
    scoped["review_only"] = [
        item
        for item in scoped.get("review_only", [])
        if not isinstance(item, dict) or item.get("kind") not in _DESCRIPTION_REVIEW_KINDS
    ]

    summary = scoped["summary"]
    summary["video_texts_to_update"] = 0
    summary["review_only"] = len(scoped["review_only"])
    summary["total_operations"] = len(scoped["album_operations"]) + len(scoped["placement_operations"])

    scoped["plan_sha256"] = calculate_vk_catalog_plan_sha256(scoped)
    validate_vk_catalog_plan(scoped)

    if scoped["text_operations"] or scoped["summary"]["video_texts_to_update"] != 0:
        raise ValueError("Catalog-only VK plan must contain zero text operations")
    return scoped


__all__ = [
    "VK_CATALOG_OPERATION_SCOPE_CATALOG_ONLY",
    "restrict_vk_catalog_plan_to_catalog_only",
]
