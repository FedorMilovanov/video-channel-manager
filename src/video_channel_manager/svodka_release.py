from __future__ import annotations

import hashlib
import json

from video_channel_manager.svodka_queue import SvodkaDraftPost, SvodkaDraftQueue
from video_channel_manager.telegram_channel_profile import TelegramChannelProfile
from video_channel_manager.telegram_multichannel_release import GenericReleaseItem, GenericReleaseQueue
from video_channel_manager.telegram_multichannel_transport import (
    GenericMessagePayload,
    GenericPollPayload,
    render_message_payload,
    render_poll_payload,
)


def source_post_sha256(post: SvodkaDraftPost) -> str:
    canonical = json.dumps(post.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_poll_description(post: SvodkaDraftPost, tagline: str) -> str:
    source_lines = [f"📎 {source.label}: {source.url}" for source in post.sources]
    description = "- Сводка -\n\n" + "\n".join(source_lines) + f"\n\n{tagline}\n\n#Сводка #Тест"
    if len(description) > 1024:
        raise ValueError(f"Svodka poll description exceeds Telegram limit: {post.publication_id}")
    return description


def build_svodka_release_candidate(
    profile: TelegramChannelProfile,
    draft: SvodkaDraftQueue,
    *,
    release_id: str,
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
        release_authorized=False,
        reviewed_by=None,
        reviewed_at=None,
        items=tuple(items),
    )
