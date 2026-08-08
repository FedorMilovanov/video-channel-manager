from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_release import save_release
from video_channel_manager.telegram_research import load_research_queue
from video_channel_manager.telegram_research_release import build_research_release_candidate
from video_channel_manager.telegram_target_binding import load_target_binding


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Build an unauthorized generic Telegram release candidate from a validated Lordchrist research queue"
    )
    root.add_argument("--profile", type=Path, required=True)
    root.add_argument("--queue", type=Path, required=True)
    root.add_argument("--release-id", required=True)
    root.add_argument(
        "--start-at",
        required=True,
        help="Timezone-aware ISO-8601 local/offset datetime for editorial T+0, for example 2026-08-09T19:17:00+03:00",
    )
    root.add_argument("--binding", type=Path)
    root.add_argument("--output", type=Path, required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    profile = load_channel_profile(args.profile)
    research = load_research_queue(args.queue)
    start_at = datetime.fromisoformat(args.start_at)
    binding = load_target_binding(args.binding, profile) if args.binding is not None else None

    release = build_research_release_candidate(
        profile,
        research,
        release_id=args.release_id,
        start_at=start_at,
        binding=binding,
    )
    if release.release_authorized:
        raise ValueError("research candidate builder must never authorize a release")
    save_release(args.output, release)
    print(
        json.dumps(
            {
                "candidate_built": True,
                "release_id": release.release_id,
                "count": len(release.items),
                "candidate_sha256": release.candidate_digest(),
                "release_sha256": release.digest,
                "target_bound": release.target_binding_sha256 is not None,
                "release_authorized": release.release_authorized,
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
