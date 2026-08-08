from __future__ import annotations

import html
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from video_channel_manager.telegram_channel_profile import TelegramChannelProfile
from video_channel_manager.telegram_multichannel_release import GenericReleaseItem, GenericReleaseQueue
from video_channel_manager.telegram_multichannel_transport import render_message_payload
from video_channel_manager.telegram_research import ResearchQueueV2, load_research_queue, validate_public_copy
from video_channel_manager.telegram_target_binding import TelegramTargetBinding


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
        raise ValueError("research target binding differs from selected Telegram channel profile")
    return {
        "target_binding_sha256": binding.digest,
        "chat_id": binding.chat_id,
        "bot_id": binding.bot_id,
        "bot_username": binding.bot_username,
    }


def render_research_html(body: str) -> str:
    """Preserve the canonical reader text while emphasizing only its heading."""

    public_copy = validate_public_copy(body)
    first_line, separator, remainder = public_copy.partition("\n")
    rendered = f"<b>{html.escape(first_line)}</b>"
    if separator:
        rendered += "\n" + html.escape(remainder)
    return rendered


def build_research_release_candidate(
    profile: TelegramChannelProfile,
    research: ResearchQueueV2,
    *,
    release_id: str,
    start_at: datetime,
    binding: TelegramTargetBinding | None = None,
) -> GenericReleaseQueue:
    if research.live_eligible:
        raise ValueError("research evidence queue must remain staged while building a release candidate")
    if (
        profile.project_key != research.project_key
        or profile.channel_username.casefold() != research.channel_username.casefold()
    ):
        raise ValueError("research queue identity differs from selected Telegram channel profile")
    if profile.timezone != research.schedule.timezone:
        raise ValueError("research schedule timezone differs from selected Telegram channel profile")
    if start_at.tzinfo is None:
        raise ValueError("research release start_at must be timezone-aware")

    zone = ZoneInfo(profile.timezone)
    local_start = start_at.astimezone(zone)
    items: list[GenericReleaseItem] = []
    for post in research.posts:
        body = validate_public_copy(Path(post.body_path).read_text(encoding="utf-8"))
        payload = render_message_payload(
            profile,
            publication_id=post.publication_id,
            html_text=render_research_html(body),
        )
        if payload.expected_plain_text != body:
            raise ValueError(f"research provider rendering changed canonical reader text: {post.publication_id}")
        items.append(
            GenericReleaseItem(
                sequence=post.sequence,
                publication_id=post.publication_id,
                scheduled_at=local_start + timedelta(days=post.release_offset_days),
                source_sha256=post.payload_sha256,
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


def build_research_release_candidate_from_file(
    profile: TelegramChannelProfile,
    queue_path: Path,
    *,
    release_id: str,
    start_at: datetime,
    binding: TelegramTargetBinding | None = None,
) -> GenericReleaseQueue:
    return build_research_release_candidate(
        profile,
        load_research_queue(queue_path),
        release_id=release_id,
        start_at=start_at,
        binding=binding,
    )
