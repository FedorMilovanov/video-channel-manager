#!/usr/bin/env python3
"""Read-only structural check of a new five-block Legendary Poet package v3.1.

Usage: python scripts/validate_legendary_poet_package_v31.py copy.txt

Literary verification, review, and YouTube write permission remain separate.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from video_channel_manager.youtube_package_v31 import validate_five_block_package


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="UTF-8 file containing five unlabeled Markdown code blocks")
    args = parser.parse_args()
    try:
        source = args.file.read_text(encoding="utf-8")
    except OSError as exc:
        parser.error(str(exc))
    issues = validate_five_block_package(source)
    for issue in issues:
        print(f"[{issue.block}] {issue.code}: {issue.message}")
    if issues:
        print(f"REVIEW REQUIRED — {len(issues)} structural issue(s); no provider action.")
        return 1
    print("STRUCTURE ONLY: PASS. Facts, lyrics, media and provider approval NOT verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
