#!/usr/bin/env python3
"""Validate a self-contained YouTube copy-fix plan v3 without calling Google."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from video_channel_manager.platforms.youtube.copy_plan import validate_copy_plan


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    return parser


def _load(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read YouTube copy plan {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("YouTube copy plan JSON must be an object.")
    return payload


def main() -> int:
    args = _parser().parse_args()
    plan = _load(args.plan)
    validate_copy_plan(plan)
    print("YouTube copy plan is valid.")
    print(f"  schema version: {plan['schema_version']}")
    print(f"  ruleset: {plan['ruleset']}")
    print(f"  target channel: {plan['target_channel_id']}")
    print(f"  videos checked: {plan['videos_checked']}")
    print(f"  operations: {plan['operations_count']}")
    print(f"  unresolved excluded: {plan['unresolved_error_videos']}")
    print(f"  checked video IDs SHA-256: {plan['checked_video_ids_sha256']}")
    print(f"  plan SHA-256: {plan['plan_sha256']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(2) from exc
