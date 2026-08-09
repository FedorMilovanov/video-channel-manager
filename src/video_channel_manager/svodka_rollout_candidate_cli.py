from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from video_channel_manager.svodka_queue import load_svodka_draft
from video_channel_manager.svodka_release import build_svodka_release_candidate
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_release import save_release
from video_channel_manager.telegram_target_binding import load_target_binding


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the exact target-bound Svodka rollout candidate with the explicit schedule overlay."
    )
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    profile = load_channel_profile(args.profile)
    queue = load_svodka_draft(args.queue, profile, apply_schedule_overlay=True)
    binding = load_target_binding(args.binding, profile)
    release = build_svodka_release_candidate(
        profile,
        queue,
        release_id=args.release_id,
        binding=binding,
    )
    save_release(args.output, release)
    print(
        json.dumps(
            {
                "built": True,
                "release_id": release.release_id,
                "release_digest": release.digest,
                "profile_sha256": release.profile_sha256,
                "target_binding_sha256": release.target_binding_sha256,
                "chat_id": release.chat_id,
                "bot_id": release.bot_id,
                "bot_username": release.bot_username,
                "count": len(release.items),
                "release_authorized": release.release_authorized,
                "provider_write_performed": False,
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
