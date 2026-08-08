from __future__ import annotations

import hashlib
import json
from datetime import datetime

from video_channel_manager.svodka_queue import SvodkaDraftPost, SvodkaDraftQueue
from video_channel_manager.telegram_channel_profile import TelegramChannelProfile
from video_channel_manager.telegram_multichannel_release import GenericReleaseItem, GenericReleaseQueue
from video_channel_manager.telegram_multichannel_transport import (
    GenericMessagePayload,
    GenericPollPayload,
    render_message_payload,
    render_poll_payload,
)
from video_channel_manager.telegram_release_review import authorize_release_candidate
from video_channel_manager.telegram_target_binding import TelegramTargetBinding


def source_post_sha256(post: SvodkaDraftPost) -> str:
    canonical = json.dumps(post.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _post_hashtags(post: SvodkaDraftPost) -> str:
    for line in reversed(post.html_text.splitlines()):
        candidate = line.strip()
        if candidate.startswith("#Сводка"):
            return candidate
    return "#Сводка #Тест"


def build_poll_description(post: SvodkaDraftPost, tagline: str) -> str:
    source_lines = [f"📎 {source.label}: {source.url}" for source in post.sources]
    parts = [
        "- Сводка -",
        f"🧠 {post.title}",
        "Ответ и объяснение — после голосования.",
        "\n".join(source_lines),
        tagline,
        _post_hashtags(post),
    ]
    description = "\n\n".join(parts)
    if len(description) > 1024:
        raise ValueError(f"Svodka poll description exceeds Telegram limit: {post.publication_id}")
    return description


def _target_fields(
    profile: TelegramChannelProfile,
    binding: TelegramTargetBinding | None,
) -> dict[str, object | None]:
    if binding is None:
        return {
            "target_binding_sha256": None,
            "chat_id": None,
            "bot_id": None,
            "bot_username": None,
        }
    if (
        binding.project_key != profile.project_key
        or binding.channel_username.casefold() != profile.channel_username.casefold()
        or binding.profile_sha256 != profile.digest
        or binding.chat_username.casefold() != profile.bare_username.casefold()
    ):
        raise ValueError("Svodka target binding differs from selected Telegram channel profile")
    return {
        "target_binding_sha256": binding.digest,
        "chat_id": binding.chat_id,
        "bot_id": binding.bot_id,
        "bot_username": binding.bot_username,
    }


def build_svodka_release_candidate(
    profile: TelegramChannelProfile,
    draft: SvodkaDraftQueue,
    *,
    release_id: str,
    binding: TelegramTargetBinding | None = None,
) -> GenericReleaseQueue:
    if profile.project_key != draft.project_key or profile.channel_username != draft.channel_username:
        raise ValueError("Svodka draft identity differs from selected Telegram channel profile")
    if profile.timezone != draft.timezone or profile.daily_verified_limit != draft.pilot.max_posts_per_day:
        raise ValueError("Svodka draft schedule contract differs from selected Telegram channel profile")
    if draft.provider_writes_authorized:
        raise ValueError("draft queue must remain write-disabled; authorization belongs to a reviewed release")

    items: list[GenericReleaseItem] = []
    for post in draft.posts:
        payload: GenericMessagePayload | GenericPollPayload
        if post.format == "quiz":
            if post.quiz is None:
                raise ValueError(f"quiz metadata missing: {post.publication_id}")
            payload = render_poll_payload(
                profile,
                publication_id=post.publication_id,
                question=post.quiz.question,
                options=post.quiz.options,
                poll_type="quiz",
                correct_option_ids=(post.quiz.correct_option_index,),
                explanation=post.quiz.explanation,
                description=build_poll_description(post, draft.editorial_policy.tagline),
            )
        elif post.format == "poll":
            if post.poll is None:
                raise ValueError(f"poll metadata missing: {post.publication_id}")
            payload = render_poll_payload(
                profile,
                publication_id=post.publication_id,
                question=post.poll.question,
                options=post.poll.options,
                poll_type="regular",
                description=build_poll_description(post, draft.editorial_policy.tagline),
            )
        else:
            payload = render_message_payload(
                profile,
                publication_id=post.publication_id,
                html_text=post.html_text,
            )
        items.append(
            GenericReleaseItem(
                sequence=post.sequence,
                publication_id=post.publication_id,
                scheduled_at=post.scheduled_at,
                source_sha256=source_post_sha256(post),
                payload=payload,
            )
        )

    return GenericReleaseQueue(
        schema_name="video-channel-manager.telegram-release-queue",
        schema_version=1,
        release_id=release_id,
        project_key=profile.project_key,
        channel_username=profile.channel_username,
        profile_sha256=profile.digest,
        timezone=profile.timezone,
        daily_verified_limit=profile.daily_verified_limit,
        **_target_fields(profile, binding),
        release_authorized=False,
        reviewed_candidate_sha256=None,
        reviewed_by=None,
        reviewed_at=None,
        items=tuple(items),
    )


def authorize_svodka_release(
    candidate: GenericReleaseQueue,
    *,
    profile: TelegramChannelProfile,
    binding: TelegramTargetBinding,
    expected_candidate_sha256: str,
    reviewed_by: str,
    reviewed_at: datetime,
) -> GenericReleaseQueue:
    return authorize_release_candidate(
        candidate,
        profile=profile,
        binding=binding,
        expected_candidate_sha256=expected_candidate_sha256,
        reviewed_by=reviewed_by,
        reviewed_at=reviewed_at,
    )
