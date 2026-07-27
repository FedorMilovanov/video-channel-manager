from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk.catalog import canonical_sha256
from video_channel_manager.platforms.vk.editorial_cleanup_plan import (
    build_vk_editorial_cleanup_plan,
    calculate_vk_editorial_plan_sha256,
    validate_vk_editorial_cleanup_plan,
)
from video_channel_manager.platforms.vk.text_writer import canonical_vk_text


_SEMANTIC_LABEL_PATTERNS = {
    "shorts": re.compile(r"\bSHORTS\b", re.IGNORECASE),
    "short": re.compile(r"\bSHORT\b|\bКОРОТК\w*\b", re.IGNORECASE),
    "fragment": re.compile(r"\bФРАГМЕНТ\w*\b", re.IGNORECASE),
    "incomplete": re.compile(r"\bНЕПОЛН\w*\b", re.IGNORECASE),
    "more_full": re.compile(r"\bБОЛЕЕ\s+ПОЛН\w*\b", re.IGNORECASE),
    "full": re.compile(r"\bFULL\b|\bПОЛН\w*\b", re.IGNORECASE),
    "final": re.compile(r"\bФИНАЛЬН\w*\b", re.IGNORECASE),
}
_VERSION_LABEL_RE = re.compile(
    r"\b(?:VERSION|ВЕРСИЯ)\s*([1-9]\d*)\b",
    re.IGNORECASE,
)


def _title_groups(titles: dict[str, str]) -> dict[str, set[str]]:
    groups: dict[str, set[str]] = {}
    for remote_id, title in titles.items():
        groups.setdefault(canonical_vk_text(title).casefold(), set()).add(remote_id)
    return groups


def _semantic_title_labels(value: str) -> set[str]:
    """Extract user-authored semantic labels that automation must preserve.

    Duration, aspect ratio, upload pairing, and other metadata are deliberately
    not consulted. A vertical video may be a SHORTS upload, while a short
    horizontal video may be a fragment or a complete compact performance.
    """

    title = canonical_vk_text(value)
    labels = {
        label
        for label, pattern in _SEMANTIC_LABEL_PATTERNS.items()
        if pattern.search(title)
    }
    labels.update(
        f"version:{match}" for match in _VERSION_LABEL_RE.findall(title)
    )
    return labels


def build_vk_editorial_title_wave(
    target: AuditPackage,
    policy: dict[str, Any],
) -> dict[str, Any]:
    """Build a signed title-only wave, excluding explicitly ambiguous videos.

    Description text and album titles are retained byte-for-byte after VK text
    canonicalization. Existing duplicate titles may remain for manual review,
    but this wave is forbidden from introducing any new title collision.

    User-authored semantic labels such as SHORTS, short, fragment, incomplete,
    full, more-full, final, and numbered versions are frozen. They may change
    only for an exact video ID listed in ``title_semantic_label_reviewed_ids``.
    """

    base_plan = build_vk_editorial_cleanup_plan(target, policy)
    excluded_ids = {
        str(remote_id).strip()
        for remote_id in list(policy.get("title_review_only_ids") or [])
        if str(remote_id).strip()
    }
    semantic_reviewed_ids = {
        str(remote_id).strip()
        for remote_id in list(
            policy.get("title_semantic_label_reviewed_ids") or []
        )
        if str(remote_id).strip()
    }
    target_ids = {video.ref.remote_id for video in target.videos}
    unknown_exclusions = sorted(excluded_ids - target_ids)
    if unknown_exclusions:
        raise ValueError(f"Unknown title_review_only_ids: {unknown_exclusions}")
    unknown_semantic_reviews = sorted(semantic_reviewed_ids - target_ids)
    if unknown_semantic_reviews:
        raise ValueError(
            "Unknown title_semantic_label_reviewed_ids: "
            f"{unknown_semantic_reviews}"
        )

    operations: list[dict[str, Any]] = []
    proposed_by_id = {
        video.ref.remote_id: canonical_vk_text(video.title)
        for video in target.videos
    }
    base_operations = {
        operation["target_video_id"]: operation
        for operation in base_plan["video_text_operations"]
    }

    for remote_id, operation in base_operations.items():
        if not bool(operation["title_changed"]):
            continue
        proposed_by_id[remote_id] = str(operation["after_title"])
        if remote_id in excluded_ids:
            continue

        before_labels = _semantic_title_labels(str(operation["before_title"]))
        after_labels = _semantic_title_labels(str(operation["after_title"]))
        if before_labels != after_labels and remote_id not in semantic_reviewed_ids:
            raise ValueError(
                "Title automation changes semantic labels for "
                f"{remote_id}: {sorted(before_labels)} -> {sorted(after_labels)}. "
                "Do not infer SHORTS/short/full status from duration, aspect "
                "ratio, or paired uploads; require an exact reviewed video ID."
            )

        title_operation = deepcopy(operation)
        title_operation["after_description"] = title_operation[
            "before_description"
        ]
        title_operation["after_description_sha256"] = title_operation[
            "before_description_sha256"
        ]
        title_operation["description_changed"] = False
        title_operation["semantic_title_labels_before"] = sorted(before_labels)
        title_operation["semantic_title_labels_after"] = sorted(after_labels)
        title_operation["semantic_title_labels_preserved"] = (
            before_labels == after_labels
        )
        operations.append(title_operation)

    before_titles = {
        video.ref.remote_id: canonical_vk_text(video.title)
        for video in target.videos
    }
    final_titles = dict(before_titles)
    for operation in operations:
        final_titles[operation["target_video_id"]] = str(
            operation["after_title"]
        )

    before_groups = _title_groups(before_titles)
    final_groups = _title_groups(final_titles)
    introduced_collisions: list[dict[str, Any]] = []
    for key, remote_ids in final_groups.items():
        if len(remote_ids) <= 1:
            continue
        if remote_ids != before_groups.get(key, set()):
            introduced_collisions.append(
                {
                    "title": final_titles[sorted(remote_ids)[0]],
                    "target_video_ids": sorted(remote_ids),
                }
            )
    if introduced_collisions:
        raise ValueError(
            f"Title-only wave introduces duplicate titles: {introduced_collisions}"
        )

    review_only = [
        deepcopy(finding)
        for finding in base_plan["review_only"]
        if finding.get("kind") == "mention_rendering_ui_test_required"
    ]
    reason = str(
        policy.get("title_review_only_reason")
        or "Ambiguous title requires manual audio/visual review."
    )
    for remote_id in sorted(excluded_ids):
        before_title = before_titles[remote_id]
        proposed_title = proposed_by_id.get(remote_id, before_title)
        review_only.append(
            {
                "kind": "title_manual_review_excluded",
                "target_video_id": remote_id,
                "before_title": before_title,
                "proposed_title": proposed_title,
                "message": reason,
            }
        )

    operations.sort(key=lambda item: item["operation_id"])
    review_only.sort(key=lambda item: canonical_sha256(item))

    plan: dict[str, Any] = {
        "schema_name": base_plan["schema_name"],
        "schema_version": base_plan["schema_version"],
        "operation_scope": "editorial_only",
        "component_scope": "titles_only",
        "generated_at": base_plan["generated_at"],
        "target_snapshot_id": base_plan["target_snapshot_id"],
        "target_community_id": base_plan["target_community_id"],
        "target_video_ids_sha256": base_plan["target_video_ids_sha256"],
        "initial_memberships_sha256": base_plan[
            "initial_memberships_sha256"
        ],
        "policy": policy,
        "policy_sha256": canonical_sha256(policy),
        "source_full_plan_sha256": base_plan["plan_sha256"],
        "video_text_operations": operations,
        "album_title_operations": [],
        "review_only": review_only,
    }
    plan["summary"] = {
        "videos_in_snapshot": len(target.videos),
        "video_text_operations": len(operations),
        "titles_to_update": len(operations),
        "descriptions_to_update": 0,
        "albums_to_rename": 0,
        "placements_to_add": 0,
        "placements_to_remove": 0,
        "videos_to_delete": 0,
        "review_only": len(review_only),
        "total_operations": len(operations),
    }
    plan["plan_sha256"] = calculate_vk_editorial_plan_sha256(plan)
    validate_vk_editorial_cleanup_plan(plan)
    return plan


__all__ = ["build_vk_editorial_title_wave"]
