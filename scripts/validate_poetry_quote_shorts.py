#!/usr/bin/env python3
"""Read-only structural preflight for one source-locked poetry Shorts JSON packet.

Usage:
    python scripts/validate_poetry_quote_shorts.py packet.json
    python scripts/validate_poetry_quote_shorts.py packet.json --require-audio-review

Passing this command never verifies source authenticity, audio by listening,
YouTube playlist ownership or grants permission for provider writes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from video_channel_manager.poetry_quote_shorts import validate_poetry_quote_packet


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path, help="UTF-8 JSON packet for ONE edition and ONE Short")
    parser.add_argument("--require-audio-review", action="store_true")
    parser.add_argument("--comment-plan", type=Path, help="Existing single-operation reviewed full-poem comment plan")
    args = parser.parse_args()
    try:
        data = json.loads(args.packet.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    if not isinstance(data, dict):
        parser.error("Expected a JSON object, not a list or scalar.")
    planned_comment = None
    if args.comment_plan is not None:
        try:
            plan = json.loads(args.comment_plan.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        operations = plan.get("operations") if isinstance(plan, dict) else None
        if not isinstance(operations, list) or len(operations) != 1 or not isinstance(operations[0], dict):
            parser.error("Expected one existing reviewed comment operation.")
        operation = operations[0]
        if (
            operation.get("action") not in ("create", "update")
            or operation.get("channel_id") != "UC-78ys2S3cQ3lpqgXfo-SvQ"
            or operation.get("review_status") != "approved"
            or not isinstance(operation.get("comment_text"), str)
            or not operation["comment_text"].strip()
        ):
            parser.error("Expected an approved Legendary Poet top-level comment operation with exact text.")
        planned_comment = operation["comment_text"]
    issues = validate_poetry_quote_packet(
        data, require_audio_review=args.require_audio_review, planned_comment=planned_comment
    )
    for issue in issues:
        print(f"[{issue.code}] {issue.detail}")
    if issues:
        print(f"REVIEW REQUIRED: {len(issues)} structural defect(s). NO PROVIDER ACTION.")
        return 1
    print(
        "STRUCTURE ONLY: PASS. Source witness, spoken audio, links and provider write STILL require independent review."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
