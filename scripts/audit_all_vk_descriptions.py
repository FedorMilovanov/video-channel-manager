#!/usr/bin/env python3
"""Audit every live VK video description and build a guarded plain-text cleanup plan."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from video_channel_manager.config import get_settings
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk import VkApiClient, VkTokenStore
from video_channel_manager.platforms.vk.live_description_audit import (
    build_live_description_cleanup_plan,
    render_live_description_report,
    validate_live_description_cleanup_plan,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", default="legendary-poet")
    parser.add_argument("--community", required=True, help="Exact VK community ID or screen name")
    parser.add_argument("--plan-output", type=Path)
    parser.add_argument("--report-output", type=Path)
    return parser


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    args = _parser().parse_args()
    settings = get_settings()
    store = VkTokenStore(settings.data_dir)
    reader = VkApiClient(
        token_store=store,
        account_alias=args.account,
        api_version=settings.vk_api_version,
    )
    community = reader.get_community(args.community)
    community_id = int(community.ref.channel_id)
    if not bool(community.metadata.get("managed_by_token")):
        raise SystemExit("The authorized VK user is not reported as an administrator of this community.")

    print(f"Reading every live VK video for community {community_id} — {community.title}…")
    videos = reader.list_videos(community_id)
    remote_ids = [video.ref.remote_id for video in videos]
    if len(remote_ids) != len(set(remote_ids)):
        raise RuntimeError("VK returned duplicate video IDs; refusing to build a cleanup plan.")
    live = AuditPackage(
        channel=community,
        videos=videos,
        metadata={
            "source": "vk-api-video-only",
            "api_version": settings.vk_api_version,
            "account_alias": args.account,
            "read_only": True,
            "complete_video_pagination": True,
        },
    )
    plan = build_live_description_cleanup_plan(live, community_id=community_id)
    validate_live_description_cleanup_plan(plan)

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    plan_output = args.plan_output or settings.data_dir / "reports" / f"vk-live-description-cleanup-{timestamp}.json"
    report_output = args.report_output or settings.data_dir / "reports" / f"vk-live-description-cleanup-{timestamp}.md"

    _atomic_write_text(plan_output, json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
    _atomic_write_text(report_output, render_live_description_report(plan))

    summary = plan["summary"]
    print(f"Full VK description plan → {plan_output}")
    print(f"Readable diff report → {report_output}")
    print(
        "Checked {checked} | ready {ready} | review only {review} | already safe {safe} | "
        "emphasis pairs {emphasis} | footers {footers}".format(
            checked=plan["videos_checked"],
            ready=plan["operations_count"],
            review=plan["review_only_count"],
            safe=plan["already_safe_count"],
            emphasis=summary.get("removed_emphasis_pairs", 0),
            footers=summary.get("footer_added", 0),
        )
    )
    print(f"Live snapshot confirmation value: {plan['live_snapshot_id']}")
    print(f"Plan SHA-256 confirmation value: {plan['plan_sha256']}")
    print(f"Coverage SHA-256: {plan['coverage_remote_ids_sha256']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(2) from exc
