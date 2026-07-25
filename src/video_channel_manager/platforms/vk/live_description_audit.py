from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from difflib import unified_diff
from typing import Any

from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk.text import render_vk_video_description

_SCHEMA_NAME = "video-manager.vk-live-description-cleanup-plan"
_SCHEMA_VERSION = 1


def _sha256_text(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


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
            "vk_type": video.metadata.get("type"),
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

    return {
        "schema_name": _SCHEMA_NAME,
        "schema_version": _SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "live_snapshot_id": str(live.snapshot_id),
        "community_id": community_id,
        "videos_checked": len(live.videos),
        "operations_count": len(operations),
        "review_only_count": len(review_only),
        "already_safe_count": len(already_safe),
        "summary": dict(sorted(counters.items())),
        "operations": operations,
        "review_only": review_only,
        "already_safe": already_safe,
    }


def render_live_description_report(plan: dict[str, Any]) -> str:
    lines = [
        "# Full live VK description audit",
        "",
        f"Live snapshot: `{plan['live_snapshot_id']}`",
        f"Community: `{plan['community_id']}`",
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
    "render_live_description_report",
]
