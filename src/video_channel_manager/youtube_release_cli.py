from __future__ import annotations

import argparse
import json

from video_channel_manager.youtube_release_execution import execute_next, reconcile
from video_channel_manager.youtube_release_operations import (
    adopt_existing,
    initialize_release,
    prepare_plan,
    record_manual_evidence,
    status,
)
from video_channel_manager.youtube_release_provider import YouTubeReleaseProviderError
from video_channel_manager.youtube_release_state import YouTubeReleaseStateError
from video_channel_manager.youtube_upload_plan import UploadPlanError


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Guarded current-main YouTube release operations.")
    sub = root.add_subparsers(dest="command", required=True)

    adoption = sub.add_parser("adopt-existing")
    adoption.add_argument("--evidence", required=True)
    adoption.add_argument("--data-dir", required=True)
    adoption.add_argument("--output", required=True)
    adoption.set_defaults(func=adopt_existing)

    plan = sub.add_parser("prepare-plan")
    plan.add_argument("--intent", required=True)
    plan.add_argument("--output", required=True)
    plan.add_argument("--thumbnail")
    plan.add_argument("--playlist", action="append", default=[])
    plan.add_argument(
        "--final-privacy",
        choices=("private", "unlisted", "public"),
        default="public",
    )
    plan.add_argument("--comment-file")
    plan.add_argument("--manual-pin", action="store_true")
    plan.set_defaults(func=prepare_plan)

    initialize = sub.add_parser("initialize")
    initialize.add_argument("--plan", required=True)
    initialize.add_argument("--data-dir", required=True)
    initialize.add_argument("--output", required=True)
    initialize.add_argument("--intent")
    initialize.add_argument("--absence-evidence")
    initialize.set_defaults(func=initialize_release)

    execute = sub.add_parser("execute-next")
    execute.add_argument("--plan", required=True)
    execute.add_argument("--approval", required=True)
    execute.add_argument("--data-dir", required=True)
    execute.add_argument("--execute", action="store_true")
    execute.set_defaults(func=execute_next)

    recovery = sub.add_parser("reconcile")
    recovery.add_argument("--plan", required=True)
    recovery.add_argument("--data-dir", required=True)
    recovery.set_defaults(func=reconcile)

    manual = sub.add_parser("record-manual-evidence")
    manual.add_argument("--plan", required=True)
    manual.add_argument("--data-dir", required=True)
    manual.add_argument("--child", required=True)
    manual.add_argument("--evidence", required=True)
    manual.set_defaults(func=record_manual_evidence)

    show = sub.add_parser("status")
    show.add_argument("--plan", required=True)
    show.add_argument("--data-dir", required=True)
    show.set_defaults(func=status)
    return root


def run() -> None:
    args = parser().parse_args()
    try:
        raise SystemExit(args.func(args))
    except (
        OSError,
        ValueError,
        UploadPlanError,
        YouTubeReleaseStateError,
        YouTubeReleaseProviderError,
        json.JSONDecodeError,
    ) as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(2) from exc


if __name__ == "__main__":
    run()
