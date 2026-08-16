from __future__ import annotations

import argparse
import json
from pathlib import Path

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_release import load_release, save_release
from video_channel_manager.telegram_release_binding import bind_release_candidate
from video_channel_manager.telegram_target_binding import load_target_binding


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Bind an unauthorized Telegram release to an exact reviewed target")
    root.add_argument("--profile", type=Path, required=True)
    root.add_argument("--binding", type=Path, required=True)
    root.add_argument("--candidate", type=Path, required=True)
    root.add_argument("--expected-unbound-candidate-sha256", required=True)
    root.add_argument("--output", type=Path, required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    profile = load_channel_profile(args.profile)
    binding = load_target_binding(args.binding, profile)
    candidate = load_release(args.candidate)
    unbound_candidate_sha256 = candidate.candidate_digest()
    bound = bind_release_candidate(
        candidate,
        profile=profile,
        binding=binding,
        expected_unbound_candidate_sha256=args.expected_unbound_candidate_sha256,
    )
    save_release(args.output, bound)
    print(
        json.dumps(
            {
                "bound": True,
                "authorized": False,
                "provider_write_performed": False,
                "project_key": bound.project_key,
                "channel_username": bound.channel_username,
                "profile_sha256": profile.digest,
                "target_binding_sha256": binding.digest,
                "unbound_candidate_sha256": unbound_candidate_sha256,
                "bound_candidate_sha256": bound.candidate_digest(),
                "bound_release_sha256": bound.digest,
                "chat_id": bound.chat_id,
                "bot_id": bound.bot_id,
                "bot_username": bound.bot_username,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
