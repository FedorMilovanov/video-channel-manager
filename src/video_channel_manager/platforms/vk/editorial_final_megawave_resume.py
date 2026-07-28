from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any

from video_channel_manager.platforms.vk.catalog import canonical_sha256, text_sha256
from video_channel_manager.platforms.vk.editorial_megawave import build_evidence_safe_description

_EXPECTED_RESEARCH_UNITS = 37
_EXPECTED_DUPLICATE_TARGETS = 5


def rebuild_legacy_intermediate_guards(
    plan: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    """Reproduce the exact shared-replacement behavior of the retired megawave.

    The retired implementation created one replacement per research unit and used
    the title of the first target in policy order. Five additional videos shared
    those replacements. Rebuilding an intermediate description per video changes
    the intro title for those five videos and creates false conflicts.
    """

    corrected = deepcopy(plan)
    operations = [item for item in corrected.get("video_text_operations", []) if isinstance(item, dict)]
    operations_by_video = {str(item["target_video_id"]): item for item in operations}
    ordered_video_ids = [
        str(item["video_id"])
        for item in policy.get("targets", [])
        if isinstance(item, dict) and item.get("video_id")
    ]
    if len(ordered_video_ids) != 42 or set(ordered_video_ids) != set(operations_by_video):
        raise ValueError("Resume guard target order does not match the 42 final megawave operations")

    group_sizes = Counter(str(operations_by_video[video_id]["before_description"]) for video_id in ordered_video_ids)
    if len(group_sizes) != _EXPECTED_RESEARCH_UNITS:
        raise ValueError(
            "Resume guard source descriptions do not reproduce the 37 retired research units: "
            f"actual={len(group_sizes)}"
        )
    duplicate_targets = sum(size - 1 for size in group_sizes.values())
    if duplicate_targets != _EXPECTED_DUPLICATE_TARGETS:
        raise ValueError(
            "Resume guard duplicate target count does not reproduce the retired megawave: "
            f"actual={duplicate_targets}"
        )

    legacy_by_source: dict[str, tuple[str, dict[str, Any], str]] = {}
    for video_id in ordered_video_ids:
        operation = operations_by_video[video_id]
        source_description = str(operation["before_description"])
        if source_description in legacy_by_source:
            continue
        legacy_description, legacy_metadata = build_evidence_safe_description(
            source_description,
            str(operation["before_title"]),
        )
        legacy_by_source[source_description] = (legacy_description, legacy_metadata, video_id)

    for operation in operations:
        source_description = str(operation["before_description"])
        legacy_description, legacy_metadata, first_video_id = legacy_by_source[source_description]
        operation["legacy_intermediate_title"] = str(operation["before_title"])
        operation["legacy_intermediate_description"] = legacy_description
        operation["legacy_intermediate_title_sha256"] = text_sha256(str(operation["before_title"]))
        operation["legacy_intermediate_description_sha256"] = text_sha256(legacy_description)
        operation["legacy_intermediate_metadata"] = {
            **legacy_metadata,
            "shared_research_unit_first_video_id": first_video_id,
            "shared_research_unit_target_count": group_sizes[source_description],
            "shared_source_description_sha256": text_sha256(source_description),
        }

    corrected["accepted_intermediate_research_unit_count"] = _EXPECTED_RESEARCH_UNITS
    corrected["accepted_intermediate_duplicate_target_count"] = _EXPECTED_DUPLICATE_TARGETS
    corrected["accepted_intermediate_reconstruction"] = "shared-source-description-first-policy-target-title"
    corrected["plan_sha256"] = canonical_sha256(
        {key: value for key, value in corrected.items() if key != "plan_sha256"}
    )
    return corrected


__all__ = ["rebuild_legacy_intermediate_guards"]
