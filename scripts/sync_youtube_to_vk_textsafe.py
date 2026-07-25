#!/usr/bin/env python3
"""Run the existing YouTube→VK sync with the VK plain-text description renderer enabled."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import sync_youtube_to_vk as sync  # noqa: E402
from video_channel_manager.platforms.vk.text import render_vk_video_description  # noqa: E402


def _vk_description(source_description: str) -> str:
    rendered = render_vk_video_description(source_description)
    if rendered.has_errors:
        codes = ", ".join(issue.code for issue in rendered.issues if issue.severity == "error")
        raise ValueError(f"VK description renderer blocked publication: {codes}")
    return rendered.text


def main() -> int:
    sync._vk_description = _vk_description
    print(
        "VK plain-text renderer enabled: YouTube *...*, _..._, Markdown links, zero-width characters, "
        "and excessive blank lines will be normalized before upload."
    )
    return sync.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError, sync.VkWriteError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
