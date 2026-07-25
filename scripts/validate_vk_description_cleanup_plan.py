#!/usr/bin/env python3
"""Validate a VK whole-library description cleanup plan without calling VK."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from video_channel_manager.platforms.vk.live_description_audit import validate_live_description_cleanup_plan


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    return parser


def _load(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read cleanup plan {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Cleanup plan JSON must be an object.")
    return payload


def main() -> int:
    args = _parser().parse_args()
    plan = _load(args.plan)
    validate_live_description_cleanup_plan(plan)
    print("VK description cleanup plan is valid.")
    print(f"  schema version: {plan['schema_version']}")
    print(f"  policy version: {plan['policy_version']}")
    print(f"  community: {plan['community_id']}")
    print(f"  videos checked: {plan['videos_checked']}")
    print(f"  operations: {plan['operations_count']}")
    print(f"  review only: {plan['review_only_count']}")
    print(f"  already safe: {plan['already_safe_count']}")
    print(f"  live snapshot: {plan['live_snapshot_id']}")
    print(f"  plan SHA-256: {plan['plan_sha256']}")
    print(f"  coverage SHA-256: {plan['coverage_remote_ids_sha256']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(2) from exc
