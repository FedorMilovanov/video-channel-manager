from __future__ import annotations

import argparse
import json
from pathlib import Path

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_models import DispatchEnvelope
from video_channel_manager.telegram_multichannel_transport import GenericTargetProof
from video_channel_manager.telegram_target_binding import (
    target_binding_from_legacy_dispatch,
    target_binding_from_proof,
)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Convert verified Telegram target evidence into an immutable binding")
    root.add_argument("--profile", type=Path, required=True)
    evidence = root.add_mutually_exclusive_group(required=True)
    evidence.add_argument("--proof", type=Path)
    evidence.add_argument("--legacy-dispatch", type=Path)
    root.add_argument("--output", type=Path, required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    profile = load_channel_profile(args.profile)
    if args.proof is not None:
        proof = GenericTargetProof.model_validate_json(args.proof.read_text(encoding="utf-8"))
        binding = target_binding_from_proof(profile, proof)
        evidence_source = "generic_target_proof"
    else:
        dispatch = DispatchEnvelope.model_validate_json(args.legacy_dispatch.read_text(encoding="utf-8"))
        binding = target_binding_from_legacy_dispatch(profile, dispatch)
        evidence_source = "legacy_verified_dispatch"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(binding.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "bound": True,
                "evidence_source": evidence_source,
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
