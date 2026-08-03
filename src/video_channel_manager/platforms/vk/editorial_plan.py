from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from video_channel_manager.editorial.content import EditorialContentRecord
from video_channel_manager.platforms.vk.catalog import (
    calculate_vk_catalog_plan_sha256,
    text_sha256,
    validate_vk_catalog_plan,
)
from video_channel_manager.platforms.vk.catalog_upgrade import upgrade_vk_catalog_plan_identity
from video_channel_manager.platforms.vk.renderers import VKVideoDescriptionRenderer
from video_channel_manager.platforms.vk.text_writer import canonical_vk_text

UNIFIED_EDITORIAL_POLICY_VERSION = "unified-editorial-v1"


def _valid_review_timestamp(value: str | None) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def apply_editorial_records_to_vk_catalog_plan(
    plan: dict[str, Any],
    records: list[EditorialContentRecord],
    *,
    require_all_text_operations: bool = False,
) -> dict[str, Any]:
    """Replace VK catalog after-descriptions with approved canonical content.

    The existing VK catalog plan remains the safety envelope: source/target snapshot
    IDs, target inventory digest, exact before-text hashes, operation IDs, and the
    guarded executor are preserved. Legacy plans are first upgraded from their
    verified self-digest to one exact project identity. Only approved, reviewed
    ``after_description`` values and their hashes are then replaced.
    """

    by_video_id: dict[str, EditorialContentRecord] = {}
    for candidate in records:
        if candidate.status != "approved" or not _valid_review_timestamp(candidate.reviewed_at):
            raise ValueError(
                f"VK catalog adaptation requires approved content with a timezone-aware review: {candidate.content_id}"
            )
        if not candidate.video_id:
            continue
        if candidate.video_id in by_video_id:
            raise ValueError(f"Duplicate editorial record for source video: {candidate.video_id}")
        by_video_id[candidate.video_id] = candidate

    adapted = upgrade_vk_catalog_plan_identity(plan)
    validate_vk_catalog_plan(adapted)
    raw_operations = adapted.get("text_operations")
    if not isinstance(raw_operations, list):
        raise ValueError("VK catalog plan text_operations must be a list")
    renderer = VKVideoDescriptionRenderer()
    used_variations: list[str] = []
    used_rendered_hashes: list[str] = []
    missing_source_ids: list[str] = []
    adapted_count = 0
    for raw in raw_operations:
        if not isinstance(raw, dict):
            raise ValueError("VK catalog text operation must be an object")
        source_video_id = str(raw.get("source_video_id") or "").strip()
        record = by_video_id.get(source_video_id)
        if record is None:
            missing_source_ids.append(source_video_id)
            continue
        rendered = renderer.render(record)
        if not rendered.is_valid:
            details = "; ".join(issue.message for issue in rendered.issues if issue.severity == "error")
            raise ValueError(f"Invalid VK rendering for {record.content_id}: {details}")
        after_description = canonical_vk_text(rendered.text)
        raw["after_description"] = after_description
        raw["after_description_sha256"] = text_sha256(after_description)
        raw["publication_policy_version"] = UNIFIED_EDITORIAL_POLICY_VERSION
        raw["editorial_content_id"] = record.content_id
        raw["editorial_variation_key"] = record.variation_key
        raw["editorial_source_ids"] = sorted(record.source_ids)
        raw["editorial_reviewed_at"] = record.reviewed_at
        used_variations.append(record.variation_key)
        used_rendered_hashes.append(raw["after_description_sha256"])
        adapted_count += 1

    if require_all_text_operations and missing_source_ids:
        raise ValueError(
            "No canonical editorial record for source videos: " + ", ".join(sorted(set(missing_source_ids)))
        )
    duplicate_variations = sorted(value for value, count in Counter(used_variations).items() if value and count > 1)
    if duplicate_variations:
        raise ValueError(f"Duplicate variation keys in VK catalog plan: {duplicate_variations}")
    duplicate_renderings = sorted(
        value for value, count in Counter(used_rendered_hashes).items() if value and count > 1
    )
    if duplicate_renderings:
        raise ValueError("Duplicate rendered VK descriptions are not allowed")

    summary = adapted.get("summary")
    if isinstance(summary, dict):
        summary["editorial_texts_adapted"] = adapted_count
        summary["editorial_texts_unmatched"] = len(missing_source_ids)
    adapted["editorial_policy_version"] = UNIFIED_EDITORIAL_POLICY_VERSION
    adapted["plan_sha256"] = calculate_vk_catalog_plan_sha256(adapted)
    validate_vk_catalog_plan(adapted)
    return adapted


__all__ = ["UNIFIED_EDITORIAL_POLICY_VERSION", "apply_editorial_records_to_vk_catalog_plan"]
