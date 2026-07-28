#!/usr/bin/env python3
"""Diagnose VK token, video permission, and community video access without writes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk import VkApiClient, VkApiError, VkTokenStore


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", default="legendary-poet")
    parser.add_argument("--community", type=int, required=True)
    parser.add_argument("--json-output", type=Path)
    return parser


def _error_payload(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, VkApiError):
        return {
            "ok": False,
            "method": exc.method,
            "code": exc.code,
            "retryable": exc.retryable,
            "message": str(exc),
        }
    return {"ok": False, "message": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    args = _parser().parse_args()
    settings = get_settings()
    client = VkApiClient(
        token_store=VkTokenStore(settings.data_dir),
        account_alias=args.account,
        api_version=settings.vk_api_version,
        max_attempts=1,
    )
    report: dict[str, Any] = {
        "schema_name": "video-manager.vk-video-access-diagnostic",
        "schema_version": 1,
        "account": args.account,
        "community_id": args.community,
        "checks": {},
        "recommendation": None,
    }

    try:
        user = client.get_current_user()
        report["checks"]["token_identity"] = {
            "ok": True,
            "user_id": user.user_id,
            "display_name": user.display_name,
        }
    except Exception as exc:  # noqa: BLE001 - diagnostic must serialize provider failures
        report["checks"]["token_identity"] = _error_payload(exc)
        report["recommendation"] = f"Refresh the VK user token: video-manager vk login --account {args.account}"
        exit_code = 2
    else:
        exit_code = 0
        try:
            client.validate_video_access(user.user_id)
            report["checks"]["user_video_permission"] = {"ok": True}
        except Exception as exc:  # noqa: BLE001
            report["checks"]["user_video_permission"] = _error_payload(exc)
            report["recommendation"] = (
                "The token cannot read video.get for its own user. Refresh it with video and groups permissions: "
                f"video-manager vk login --account {args.account}"
            )
            exit_code = 2

        if exit_code == 0:
            try:
                communities = client.list_managed_communities()
                managed_ids = {item.community_id for item in communities}
                is_managed = args.community in managed_ids
                report["checks"]["managed_community"] = {
                    "ok": is_managed,
                    "managed_community_ids": sorted(managed_ids),
                }
                if not is_managed:
                    report["recommendation"] = (
                        "The token does not report the target community as managed. "
                        "Confirm administrator access or refresh the token."
                    )
                    exit_code = 3
            except Exception as exc:  # noqa: BLE001
                report["checks"]["managed_community"] = _error_payload(exc)
                report["recommendation"] = (
                    f"Refresh the VK token with groups permission: video-manager vk login --account {args.account}"
                )
                exit_code = 3

        if exit_code == 0:
            try:
                videos = client.list_videos(args.community)
                report["checks"]["community_video_access"] = {
                    "ok": True,
                    "visible_video_count": len(videos),
                }
            except Exception as exc:  # noqa: BLE001
                report["checks"]["community_video_access"] = _error_payload(exc)
                report["recommendation"] = (
                    "Token identity, video permission, and community administration are valid, but VK denied "
                    "community video.get. Treat this as a provider-side or community-specific read denial; "
                    "retry the read-only preflight. If it persists, refresh the VK token."
                )
                exit_code = 4

    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(rendered, end="")
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(rendered, encoding="utf-8")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
