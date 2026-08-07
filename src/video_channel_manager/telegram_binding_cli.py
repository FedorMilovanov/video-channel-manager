from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_transport import preflight_channel
from video_channel_manager.telegram_target_binding import load_target_binding


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Pinned multi-channel Telegram target binding tooling")
    sub = root.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate")
    validate.add_argument("--profile", type=Path, required=True)
    validate.add_argument("--binding", type=Path, required=True)

    preflight = sub.add_parser("preflight")
    preflight.add_argument("--profile", type=Path, required=True)
    preflight.add_argument("--binding", type=Path, required=True)
    preflight.add_argument("--output", type=Path, required=True)
    return root


def _token(env_name: str) -> str:
    token = os.environ.get(env_name, "").strip()
    if not token:
        raise RuntimeError(f"missing Telegram bot token in {env_name}")
    return token


def main() -> int:
    args = parser().parse_args()
    profile = load_channel_profile(args.profile)
    binding = load_target_binding(args.binding, profile)

    if args.command == "validate":
        print(
            json.dumps(
                {
                    "valid": True,
                    "project_key": binding.project_key,
                    "channel_username": binding.channel_username,
                    "chat_id": binding.chat_id,
                    "bot_id": binding.bot_id,
                    "bot_username": binding.bot_username,
                    "profile_sha256": binding.profile_sha256,
                    "binding_sha256": binding.digest,
                    "provider_write_performed": binding.provider_write_performed,
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "preflight":
        proof = preflight_channel(
            profile,
            token=_token(profile.bot_token_env),
            expected_chat_id=binding.chat_id,
            expected_bot_id=binding.bot_id,
            expected_bot_username=binding.bot_username,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(proof.model_dump_json(indent=2) + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    "preflight": True,
                    "project_key": proof.project_key,
                    "channel_username": proof.channel_username,
                    "chat_id": proof.chat_id,
                    "bot_id": proof.bot_id,
                    "bot_username": proof.bot_username,
                    "profile_sha256": proof.profile_sha256,
                    "binding_sha256": binding.digest,
                    "can_post_messages": proof.can_post_messages,
                },
                ensure_ascii=False,
            )
        )
        return 0

    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
