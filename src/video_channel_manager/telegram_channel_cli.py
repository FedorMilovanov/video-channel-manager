from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

from video_channel_manager.svodka_queue import SvodkaDraftPost, load_svodka_draft
from video_channel_manager.svodka_release import (
    authorize_svodka_release,
    build_poll_description,
    build_svodka_release_candidate,
)
from video_channel_manager.telegram_channel_discovery import discover_channel_target
from video_channel_manager.telegram_channel_profile import TelegramChannelProfile, load_channel_profile
from video_channel_manager.telegram_multichannel_release import load_release, save_release
from video_channel_manager.telegram_multichannel_transport import (
    GenericTargetProof,
    preflight_channel,
    render_message_payload,
    render_poll_payload,
)
from video_channel_manager.telegram_target_binding import load_target_binding


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Generic multi-channel Telegram preview and preflight tooling")
    sub = root.add_subparsers(dest="command", required=True)

    validate_profile = sub.add_parser("validate-profile")
    validate_profile.add_argument("--profile", type=Path, required=True)

    validate_svodka = sub.add_parser("validate-svodka")
    validate_svodka.add_argument("--profile", type=Path, required=True)
    validate_svodka.add_argument("--queue", type=Path, required=True)

    preview_svodka = sub.add_parser("preview-svodka")
    preview_svodka.add_argument("--profile", type=Path, required=True)
    preview_svodka.add_argument("--queue", type=Path, required=True)
    preview_svodka.add_argument("--sequence", type=int, default=1)

    build_candidate = sub.add_parser("build-svodka-candidate")
    build_candidate.add_argument("--profile", type=Path, required=True)
    build_candidate.add_argument("--queue", type=Path, required=True)
    build_candidate.add_argument("--binding", type=Path)
    build_candidate.add_argument("--release-id", required=True)
    build_candidate.add_argument("--output", type=Path, required=True)

    authorize_release = sub.add_parser("authorize-svodka-release")
    authorize_release.add_argument("--profile", type=Path, required=True)
    authorize_release.add_argument("--candidate", type=Path, required=True)
    authorize_release.add_argument("--reviewed-by", required=True)
    authorize_release.add_argument("--reviewed-at", required=True)
    authorize_release.add_argument("--output", type=Path, required=True)

    discover = sub.add_parser("discover-target")
    discover.add_argument("--profile", type=Path, required=True)
    discover.add_argument("--expected-bot-id", type=int, required=True)
    discover.add_argument("--expected-bot-username", required=True)
    discover.add_argument("--output", type=Path, required=True)

    preflight = sub.add_parser("preflight")
    preflight.add_argument("--profile", type=Path, required=True)
    preflight.add_argument("--expected-chat-id", type=int, required=True)
    preflight.add_argument("--expected-bot-id", type=int, required=True)
    preflight.add_argument("--expected-bot-username", required=True)
    preflight.add_argument("--output", type=Path, required=True)
    return root


def _token(env_name: str) -> str:
    token = os.environ.get(env_name, "").strip()
    if not token:
        raise RuntimeError(f"missing Telegram bot token in {env_name}")
    return token


def _svodka_poll_description(post: SvodkaDraftPost, tagline: str) -> str:
    return build_poll_description(post, tagline)


def _write_proof(path: Path, proof: GenericTargetProof) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(proof.model_dump_json(indent=2) + "\n", encoding="utf-8")


def _proof_summary(proof: GenericTargetProof, *, key: str) -> dict[str, object]:
    return {
        key: True,
        "project_key": proof.project_key,
        "channel_username": proof.channel_username,
        "chat_id": proof.chat_id,
        "chat_username": proof.chat_username,
        "bot_id": proof.bot_id,
        "bot_username": proof.bot_username,
        "can_post_messages": proof.can_post_messages,
        "profile_sha256": proof.profile_sha256,
    }


def _review_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("reviewed-at must include an explicit timezone")
    return parsed


def _release_matches_profile(
    profile_sha256: str,
    project_key: str,
    channel_username: str,
    profile: TelegramChannelProfile,
) -> bool:
    return (
        profile_sha256 == profile.digest
        and project_key == profile.project_key
        and channel_username.casefold() == profile.channel_username.casefold()
    )


def main() -> int:
    args = parser().parse_args()
    profile = load_channel_profile(args.profile)

    if args.command == "validate-profile":
        print(
            json.dumps(
                {
                    "valid": True,
                    "project_key": profile.project_key,
                    "channel_username": profile.channel_username,
                    "profile_sha256": profile.digest,
                    "provider_writes_authorized": profile.provider_writes_authorized,
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "validate-svodka":
        queue = load_svodka_draft(args.queue, profile)
        counts: dict[str, int] = {}
        for post in queue.posts:
            counts[post.format] = counts.get(post.format, 0) + 1
        print(
            json.dumps(
                {
                    "valid": True,
                    "count": len(queue.posts),
                    "format_counts": counts,
                    "queue_sha256": queue.digest,
                    "review_state": queue.review_state,
                    "provider_writes_authorized": queue.provider_writes_authorized,
                    "first_publication_id": queue.posts[0].publication_id,
                    "last_publication_id": queue.posts[-1].publication_id,
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "preview-svodka":
        queue = load_svodka_draft(args.queue, profile)
        post = next((candidate for candidate in queue.posts if candidate.sequence == args.sequence), None)
        if post is None:
            raise ValueError(f"unknown Svodka sequence: {args.sequence}")

        common = {
            "sequence": post.sequence,
            "publication_id": post.publication_id,
            "format": post.format,
            "scheduled_at": post.scheduled_at.isoformat(),
            "queue_sha256": queue.digest,
            "profile_sha256": profile.digest,
            "source_urls": [str(source.url) for source in post.sources],
        }
        if post.format == "quiz":
            if post.quiz is None:
                raise ValueError(f"quiz metadata missing: {post.publication_id}")
            rendered_poll = render_poll_payload(
                profile,
                publication_id=post.publication_id,
                question=post.quiz.question,
                options=post.quiz.options,
                poll_type="quiz",
                correct_option_ids=(post.quiz.correct_option_index,),
                explanation=post.quiz.explanation,
                description=_svodka_poll_description(post, queue.editorial_policy.tagline),
            )
            output = {
                **common,
                "provider_method": "sendPoll",
                "provider_payload_sha256": rendered_poll.provider_payload_sha256,
                "question": rendered_poll.question,
                "options": list(rendered_poll.options),
                "correct_option_ids": list(rendered_poll.correct_option_ids or ()),
                "explanation": rendered_poll.explanation,
                "description": rendered_poll.description,
            }
        elif post.format == "poll":
            if post.poll is None:
                raise ValueError(f"poll metadata missing: {post.publication_id}")
            rendered_poll = render_poll_payload(
                profile,
                publication_id=post.publication_id,
                question=post.poll.question,
                options=post.poll.options,
                poll_type="regular",
                description=_svodka_poll_description(post, queue.editorial_policy.tagline),
            )
            output = {
                **common,
                "provider_method": "sendPoll",
                "provider_payload_sha256": rendered_poll.provider_payload_sha256,
                "question": rendered_poll.question,
                "options": list(rendered_poll.options),
                "description": rendered_poll.description,
            }
        else:
            rendered_message = render_message_payload(
                profile,
                publication_id=post.publication_id,
                html_text=post.html_text,
            )
            output = {
                **common,
                "provider_method": "sendMessage",
                "provider_payload_sha256": rendered_message.provider_payload_sha256,
                "expected_plain_text": rendered_message.expected_plain_text,
                "html_text": rendered_message.html_text,
            }

        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0

    if args.command == "build-svodka-candidate":
        queue = load_svodka_draft(args.queue, profile)
        binding = load_target_binding(args.binding, profile) if args.binding is not None else None
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
                    "output": str(args.output),
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "authorize-svodka-release":
        candidate = load_release(args.candidate)
        if not _release_matches_profile(
            candidate.profile_sha256,
            candidate.project_key,
            candidate.channel_username,
            profile,
        ):
            raise ValueError("Svodka release candidate differs from selected channel profile")
        release = authorize_svodka_release(
            candidate,
            reviewed_by=args.reviewed_by,
            reviewed_at=_review_timestamp(args.reviewed_at),
        )
        save_release(args.output, release)
        print(
            json.dumps(
                {
                    "authorized": True,
                    "release_id": release.release_id,
                    "release_digest": release.digest,
                    "target_binding_sha256": release.target_binding_sha256,
                    "chat_id": release.chat_id,
                    "bot_id": release.bot_id,
                    "bot_username": release.bot_username,
                    "count": len(release.items),
                    "reviewed_by": release.reviewed_by,
                    "reviewed_at": release.reviewed_at.isoformat() if release.reviewed_at else None,
                    "output": str(args.output),
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "discover-target":
        proof = discover_channel_target(
            profile,
            token=_token(profile.bot_token_env),
            expected_bot_id=args.expected_bot_id,
            expected_bot_username=args.expected_bot_username,
        )
        _write_proof(args.output, proof)
        print(json.dumps(_proof_summary(proof, key="discovered"), ensure_ascii=False))
        return 0

    if args.command == "preflight":
        proof = preflight_channel(
            profile,
            token=_token(profile.bot_token_env),
            expected_chat_id=args.expected_chat_id,
            expected_bot_id=args.expected_bot_id,
            expected_bot_username=args.expected_bot_username,
        )
        _write_proof(args.output, proof)
        print(json.dumps(_proof_summary(proof, key="preflight"), ensure_ascii=False))
        return 0

    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
