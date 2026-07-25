from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from difflib import unified_diff
from typing import Any

from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk.text import render_vk_video_description

_SCHEMA_NAME = "video-manager.vk-live-description-cleanup-plan"
_SCHEMA_VERSION = 2
_POLICY_VERSION = "vk-live-description-cleanup-v2"


def _sha256_text(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _plan_payload_for_digest(plan: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in plan.items() if key != "plan_sha256"}


def calculate_cleanup_plan_sha256(plan: dict[str, Any]) -> str:
    return _canonical_sha256(_plan_payload_for_digest(plan))


def _coverage_remote_ids(plan: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for section in ("operations", "review_only", "already_safe"):
        values = plan.get(section)
        if not isinstance(values, list):
            raise ValueError(f"Cleanup plan section {section} must be a list.")
        for item in values:
            if not isinstance(item, dict) or not isinstance(item.get("remote_id"), str):
                raise ValueError(f"Cleanup plan section {section} contains an invalid remote_id.")
            result.append(str(item["remote_id"]))
    return result


def validate_live_description_cleanup_plan(plan: dict[str, Any]) -> None:
    """Validate plan schema, coverage, hashes, and its self-digest."""

    if plan.get("schema_name") != _SCHEMA_NAME:
        raise ValueError(f"Expected schema_name {_SCHEMA_NAME}.")
    if plan.get("schema_version") != _SCHEMA_VERSION:
        raise ValueError(f"Expected schema_version {_SCHEMA_VERSION}.")
    if plan.get("policy_version") != _POLICY_VERSION:
        raise ValueError(f"Expected policy_version {_POLICY_VERSION}.")
    if not isinstance(plan.get("community_id"), int) or int(plan["community_id"]) <= 0:
        raise ValueError("Cleanup plan community_id must be a positive integer.")
    if not isinstance(plan.get("live_snapshot_id"), str) or not str(plan["live_snapshot_id"]).strip():
        raise ValueError("Cleanup plan live_snapshot_id is missing.")

    operations = plan.get("operations")
    review_only = plan.get("review_only")
    already_safe = plan.get("already_safe")
    if not isinstance(operations, list) or not all(isinstance(item, dict) for item in operations):
        raise ValueError("Cleanup plan operations must be a list of objects.")
    if not isinstance(review_only, list) or not all(isinstance(item, dict) for item in review_only):
        raise ValueError("Cleanup plan review_only must be a list of objects.")
    if not isinstance(already_safe, list) or not all(isinstance(item, dict) for item in already_safe):
        raise ValueError("Cleanup plan already_safe must be a list of objects.")

    expected_counts = {
        "operations_count": len(operations),
        "review_only_count": len(review_only),
        "already_safe_count": len(already_safe),
    }
    for field, expected in expected_counts.items():
        if plan.get(field) != expected:
            raise ValueError(f"Cleanup plan {field} is {plan.get(field)!r}, expected {expected}.")

    coverage = _coverage_remote_ids(plan)
    if len(coverage) != len(set(coverage)):
        duplicates = sorted(remote_id for remote_id, count in Counter(coverage).items() if count > 1)
        raise ValueError(f"Cleanup plan contains duplicate VK remote IDs: {', '.join(duplicates)}")
    if plan.get("videos_checked") != len(coverage):
        raise ValueError(
            f"Cleanup plan videos_checked is {plan.get('videos_checked')!r}, expected coverage {len(coverage)}."
        )
    expected_coverage_sha256 = _canonical_sha256(sorted(coverage))
    if plan.get("coverage_remote_ids_sha256") != expected_coverage_sha256:
        raise ValueError("Cleanup plan coverage_remote_ids_sha256 does not match its VK ID set.")

    for operation in operations:
        remote_id = operation.get("remote_id")
        owner_id = operation.get("owner_id")
        video_id = operation.get("video_id")
        before = operation.get("before_description")
        after = operation.get("after_description")
        if not isinstance(remote_id, str) or not isinstance(owner_id, int) or not isinstance(video_id, int):
            raise ValueError("Cleanup operation identity fields are invalid.")
        if remote_id != f"{owner_id}_{video_id}":
            raise ValueError(f"Cleanup operation identity is inconsistent for {remote_id}.")
        if not isinstance(before, str) or not isinstance(after, str):
            raise ValueError(f"Cleanup operation text fields are invalid for {remote_id}.")
        if before == after:
            raise ValueError(f"Cleanup operation for {remote_id} has identical before/after text.")
        if operation.get("before_sha256") != _sha256_text(before):
            raise ValueError(f"Cleanup operation before_sha256 is invalid for {remote_id}.")
        if operation.get("after_sha256") != _sha256_text(after):
            raise ValueError(f"Cleanup operation after_sha256 is invalid for {remote_id}.")

    expected_plan_sha256 = calculate_cleanup_plan_sha256(plan)
    if plan.get("plan_sha256") != expected_plan_sha256:
        raise ValueError("Cleanup plan plan_sha256 does not match the plan payload.")


def _parse_remote_id(remote_id: str) -> tuple[int, int]:
    owner_text, separator, video_text = remote_id.partition("_")
    if not separator:
        raise ValueError(f"Invalid VK video remote ID: {remote_id}")
    try:
        return int(owner_text), int(video_text)
    except ValueError as exc:
        raise ValueError(f"Invalid VK video remote ID: {remote_id}") from exc


def build_live_description_cleanup_plan(
    live: AuditPackage,
    *,
    community_id: int,
) -> dict[str, Any]:
    """Build a conservative cleanup plan from the current VK descriptions themselves.

    This intentionally does not rebuild old VK descriptions from YouTube. It keeps
    manual wording, links, and paragraphs already present in VK and only applies the
    deterministic VK plain-text renderer to that live text.
    """

    if community_id <= 0:
        raise ValueError("community_id must be positive")

    expected_owner_id = -community_id
    operations: list[dict[str, Any]] = []
    review_only: list[dict[str, Any]] = []
    already_safe: list[dict[str, Any]] = []
    counters: Counter[str] = Counter()

    seen_remote_ids: set[str] = set()
    for video in sorted(live.videos, key=lambda item: (item.title.casefold(), item.ref.remote_id)):
        remote_id = video.ref.remote_id
        if remote_id in seen_remote_ids:
            raise ValueError(f"Duplicate VK video remote ID in snapshot: {remote_id}")
        seen_remote_ids.add(remote_id)

        owner_id, video_id = _parse_remote_id(remote_id)
        if owner_id != expected_owner_id:
            review_only.append(
                {
                    "remote_id": remote_id,
                    "title": video.title,
                    "reason": f"video owner {owner_id} differs from community owner {expected_owner_id}",
                }
            )
            counters["foreign_owner"] += 1
            continue

        before = video.description
        rendered = render_vk_video_description(before)
        common = {
            "remote_id": remote_id,
            "owner_id": owner_id,
            "video_id": video_id,
            "title": video.title,
            "duration_seconds": video.duration_seconds,
            "vk_type": video.metadata.get("type") or video.metadata.get("vk_video_type"),
            "before_description": before,
            "after_description": rendered.text,
            "before_sha256": _sha256_text(before),
            "after_sha256": _sha256_text(rendered.text),
            "removed_emphasis_pairs": rendered.removed_emphasis_pairs,
            "converted_markdown_links": rendered.converted_markdown_links,
            "removed_zero_width_characters": rendered.removed_zero_width_characters,
            "collapsed_blank_runs": rendered.collapsed_blank_runs,
            "footer_added": rendered.footer_added,
            "issues": [asdict(issue) for issue in rendered.issues],
        }

        if not rendered.changed:
            already_safe.append(
                {
                    "remote_id": remote_id,
                    "title": video.title,
                    "before_sha256": common["before_sha256"],
                }
            )
            counters["already_safe"] += 1
            continue

        if rendered.issues:
            review_only.append(
                {
                    **common,
                    "reason": "renderer left warning or error findings that require human review",
                }
            )
            counters["review_only"] += 1
            continue

        operations.append(common)
        counters["ready"] += 1
        counters["removed_emphasis_pairs"] += rendered.removed_emphasis_pairs
        counters["converted_markdown_links"] += rendered.converted_markdown_links
        counters["removed_zero_width_characters"] += rendered.removed_zero_width_characters
        counters["collapsed_blank_runs"] += rendered.collapsed_blank_runs
        counters["footer_added"] += int(rendered.footer_added)

    coverage = sorted(seen_remote_ids)
    plan: dict[str, Any] = {
        "schema_name": _SCHEMA_NAME,
        "schema_version": _SCHEMA_VERSION,
        "policy_version": _POLICY_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "live_snapshot_id": str(live.snapshot_id),
        "community_id": community_id,
        "videos_checked": len(live.videos),
        "coverage_remote_ids_sha256": _canonical_sha256(coverage),
        "operations_count": len(operations),
        "review_only_count": len(review_only),
        "already_safe_count": len(already_safe),
        "summary": dict(sorted(counters.items())),
        "operations": operations,
        "review_only": review_only,
        "already_safe": already_safe,
    }
    plan["plan_sha256"] = calculate_cleanup_plan_sha256(plan)
    validate_live_description_cleanup_plan(plan)
    return plan


def render_live_description_report(plan: dict[str, Any]) -> str:
    validate_live_description_cleanup_plan(plan)
    lines = [
        "# Full live VK description audit",
        "",
        f"Live snapshot: `{plan['live_snapshot_id']}`",
        f"Community: `{plan['community_id']}`",
        f"Policy: `{plan['policy_version']}`",
        f"Plan SHA-256: `{plan['plan_sha256']}`",
        f"Coverage SHA-256: `{plan['coverage_remote_ids_sha256']}`",
        "",
        f"- Videos checked: **{plan['videos_checked']}**",
        f"- Safe automatic cleanups: **{plan['operations_count']}**",
        f"- Human review only: **{plan['review_only_count']}**",
        f"- Already safe: **{plan['already_safe_count']}**",
        "",
        "> The proposed text is derived from each current live VK description, not reconstructed from YouTube.",
        "",
    ]

    for operation in plan["operations"]:
        lines.extend(
            [
                f"## {operation['title']}",
                "",
                f"VK: https://vk.com/video{operation['remote_id']}",
                "",
                f"- Removed emphasis pairs: **{operation['removed_emphasis_pairs']}**",
                f"- Converted Markdown links: **{operation['converted_markdown_links']}**",
                f"- Removed zero-width characters: **{operation['removed_zero_width_characters']}**",
                f"- Collapsed blank runs: **{operation['collapsed_blank_runs']}**",
                f"- Footer added: **{operation['footer_added']}**",
                "",
                "```diff",
                "\n".join(
                    unified_diff(
                        str(operation["before_description"]).splitlines(),
                        str(operation["after_description"]).splitlines(),
                        fromfile="live-vk-before",
                        tofile="live-vk-after",
                        lineterm="",
                    )
                ),
                "```",
                "",
            ]
        )

    if plan["review_only"]:
        lines.extend(["# Human review only", ""])
        for item in plan["review_only"]:
            lines.extend(
                [
                    f"## {item['title']}",
                    "",
                    f"VK ID: `{item['remote_id']}`",
                    "",
                    f"Reason: {item['reason']}",
                    "",
                ]
            )
            for issue in item.get("issues", []):
                lines.append(f"- `{issue['severity']}` `{issue['code']}` — {issue['message']}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


__all__ = [
    "build_live_description_cleanup_plan",
    "calculate_cleanup_plan_sha256",
    "render_live_description_report",
    "validate_live_description_cleanup_plan",
]
