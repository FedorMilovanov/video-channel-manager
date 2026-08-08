from __future__ import annotations

import argparse
import json
from pathlib import Path

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_transport import GenericTargetProof
from video_channel_manager.telegram_target_binding import target_binding_from_proof


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Convert a verified read-only Telegram target proof into an immutable binding"
    )
    root.add_argument("--profile", type=Path, required=True)
    root.add_argument("--proof", type=Path, required=True)
    root.add_argument("--output", type=Path, required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    profile = load_channel_profile(args.profile)
    proof = GenericTargetProof.model_validate_json(args.proof.read_text(encoding="utf-8"))
    binding = target_binding_from_proof(profile, proof)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(binding.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "bound": True,
                "project_key": binding.project_key,
                "channel_username": binding.channel_username,
                "chat_id": binding.chat_id,
                "chat_username": binding.chat_username,
                "bot_id": binding.bot_id,
                "bot_username": binding.bot_username,
                "profile_sha256": binding.profile_sha256,
                "binding_sha256": binding.digest,
                "provider_write_performed": binding.provider_write_performed,
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
