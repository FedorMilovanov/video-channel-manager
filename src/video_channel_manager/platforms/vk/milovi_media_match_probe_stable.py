from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from video_channel_manager.platforms.vk import milovi_media_match_probe as base
from video_channel_manager.platforms.vk import milovi_video_sequence_evidence as sequence
from video_channel_manager.platforms.vk import milovi_video_sequence_evidence_stable as stable_sequence


def build_media_match_probe(
    *,
    final_input: Path,
    gap_input: Path,
    output_dir: Path,
    zip_output: Path,
    browser_executable: Path | None = None,
    headless: bool = False,
    wait_ms: int = 500,
) -> dict[str, Any]:
    """Run the 13x106 probe with the exact, isolated media transport from PR #315."""
    previous_capture = sequence._capture_page_sequence
    previous_identity = sequence._identity_url_matches
    sequence._capture_page_sequence = stable_sequence._isolated_capture_page_sequence
    sequence._identity_url_matches = stable_sequence._stable_identity_url_matches
    try:
        return base.build_media_match_probe(
            final_input=final_input,
            gap_input=gap_input,
            output_dir=output_dir,
            zip_output=zip_output,
            browser_executable=browser_executable,
            headless=headless,
            wait_ms=wait_ms,
        )
    finally:
        sequence._capture_page_sequence = previous_capture
        sequence._identity_url_matches = previous_identity


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description=(
            "Build the read-only Milovi 13 x 106 confectionery reconciliation probe "
            "using exact isolated YouTube/VK player surfaces."
        )
    )
    root.add_argument("--final-input", type=Path, required=True)
    root.add_argument("--gap-input", type=Path, required=True)
    root.add_argument("--output-dir", type=Path, required=True)
    root.add_argument("--zip-output", type=Path, required=True)
    root.add_argument("--browser-executable", type=Path)
    root.add_argument("--headless", action="store_true")
    root.add_argument("--wait-ms", type=int, default=500)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        result = build_media_match_probe(
            final_input=args.final_input,
            gap_input=args.gap_input,
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
                "candidate_count": result["exhaustive_thumbnail_review"]["candidate_count"],
                "pair_space_reviewed": result["exhaustive_thumbnail_review"]["pair_space_reviewed"],
                "sequence_probe_pairs": result["exhaustive_thumbnail_review"]["selected_sequence_probe_pair_count"],
                "youtube_captured": result["browser_probe"]["youtube_capture_count"],
                "vk_captured": result["browser_probe"]["vk_capture_count"],
                "provider_writes": 0,
                "zip_output": str(args.zip_output.resolve()),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
