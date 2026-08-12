from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from video_channel_manager.platforms.vk import milovi_targeted_youtube_retry as base_retry
from video_channel_manager.platforms.vk import milovi_video_sequence_evidence as sequence
from video_channel_manager.platforms.vk import milovi_video_sequence_evidence_stable as stable_sequence


def build_targeted_retry(
    *,
    input_zip: Path,
    output_dir: Path,
    zip_output: Path,
    browser_executable: Path | None = None,
    headless: bool = True,
    wait_ms: int = 750,
) -> dict[str, Any]:
    previous_identity = sequence._identity_url_matches
    sequence._identity_url_matches = stable_sequence._stable_identity_url_matches
    try:
        return base_retry.build_targeted_retry(
            input_zip=input_zip,
            output_dir=output_dir,
            zip_output=zip_output,
            browser_executable=browser_executable,
            headless=headless,
            wait_ms=wait_ms,
        )
    finally:
        sequence._identity_url_matches = previous_identity


def parser() -> argparse.ArgumentParser:
    return base_retry.parser()


def main() -> int:
    args = parser().parse_args()
    try:
        result = build_targeted_retry(
            input_zip=args.input,
            output_dir=args.output_dir,
            zip_output=args.zip_output,
            browser_executable=args.browser_executable,
            headless=args.headless,
            wait_ms=args.wait_ms,
        )
    except Exception as exc:
        print(
            json.dumps(
                {"status": "failed", "provider_writes": 0, "error": f"{type(exc).__name__}: {exc}"},
                ensure_ascii=False,
            )
        )
        return 2

    print(
        json.dumps(
            {
                "status": result["status"],
                "youtube_captured": result["browser_probe"]["youtube_capture_count"],
                "youtube_expected": result["browser_probe"]["youtube_expected"],
                "pair_count": result["retry_scope"]["pair_count"],
                "provider_writes": 0,
                "zip_output": str(args.zip_output.resolve()),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
