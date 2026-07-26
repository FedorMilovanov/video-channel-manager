from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from apply_youtube_comment_plan import _preflight, _read_json, _status_groups, _write_json
from video_channel_manager.config import get_settings
from video_channel_manager.platforms.youtube.comment_plan import validate_comment_plan
from video_channel_manager.platforms.youtube.comments import YouTubeCommentWriter
from video_channel_manager.platforms.youtube.models import InstalledClientConfig
from video_channel_manager.platforms.youtube.store import TokenStore

_PREFLIGHT_SCHEMA = "video-manager.youtube-comment-preflight"
_PREFLIGHT_VERSION = 1


def build_preflight_report(plan: dict[str, Any], results: list[dict[str, str]]) -> dict[str, Any]:
    operations = plan.get("operations")
    if not isinstance(operations, list):
        raise ValueError("Plan operations must be a list.")
    ready, already, blockers = _status_groups(results)
    return {
        "schema_name": _PREFLIGHT_SCHEMA,
        "schema_version": _PREFLIGHT_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "channel_id": str(plan["channel_id"]),
        "source_snapshot": str(plan["source_snapshot"]),
        "plan_sha256": str(plan["plan_sha256"]),
        "counts": {
            "planned": len(operations),
            "ready": len(ready),
            "already_applied": len(already),
            "blockers": len(blockers),
        },
        "estimated_write_quota_units": len(ready) * 50,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read live YouTube state and emit a machine-readable preflight report without writes."
    )
    parser.add_argument("plan", type=Path)
    parser.add_argument("--account", default="legendary-poet")
    parser.add_argument("--max-operations", type=int, default=200)
    parser.add_argument("--json-output", type=Path, required=True)
    args = parser.parse_args()

    try:
        plan = _read_json(args.plan)
        validation_errors = validate_comment_plan(plan)
        if validation_errors:
            raise ValueError("; ".join(validation_errors))
        operations_raw = plan.get("operations")
        if not isinstance(operations_raw, list):
            raise ValueError("Plan operations must be a list.")
        operations = [item for item in operations_raw if isinstance(item, dict)]
        if len(operations) != len(operations_raw):
            raise ValueError("Every plan operation must be an object.")
        if len(operations) > args.max_operations:
            raise ValueError(f"Plan has {len(operations)} operations, above --max-operations {args.max_operations}.")

        settings = get_settings()
        config = InstalledClientConfig.from_file(settings.youtube_client_secret_file)
        store = TokenStore(settings.data_dir)
        writer = YouTubeCommentWriter(client_config=config, token_store=store, account_alias=args.account)

        print("Reading live YouTube state before any write…")
        results = _preflight(writer, operations)
        report = build_preflight_report(plan, results)
        _write_json(args.json_output, report)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot build comment preflight: {exc}", file=sys.stderr)
        return 2

    counts = report["counts"]
    assert isinstance(counts, dict)
    print("YouTube comment preflight:")
    print(f"  channel: {report['channel_id']}")
    print(f"  source snapshot: {report['source_snapshot']}")
    print(f"  plan SHA-256: {report['plan_sha256']}")
    print(f"  planned operations: {counts['planned']}")
    print(f"  ready now: {counts['ready']}")
    print(f"  already applied: {counts['already_applied']}")
    print(f"  blockers: {counts['blockers']}")
    print(f"  estimated write quota: {report['estimated_write_quota_units']} units")
    print(f"JSON → {args.json_output}")
    return 0 if int(counts["blockers"]) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
