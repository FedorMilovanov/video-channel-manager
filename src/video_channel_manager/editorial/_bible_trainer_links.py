from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from video_channel_manager.application.identity import canonicalize_public_url

BIBLE_TRAINER_BOT_USERNAME = "milovanovaibot"


def _launch_url(source: str, destination: str) -> str:
    raw = f"https://t.me/{BIBLE_TRAINER_BOT_USERNAME}?startapp=v1_{source}__{destination}"
    return canonicalize_public_url(raw).canonical


# This is intentionally an exact allow-list rather than a bot/profile wildcard.
# Store the same canonical URL identity that validate_links() compares against.
# Chapter 1 is deliberately absent: the Mini App exposes several distinct
# chapter-1 course keys, so a generic ``chapter1`` destination would be fake.
BIBLE_TRAINER_LINKS_BY_PLATFORM: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "youtube": frozenset(
            {
                _launch_url("yt_profile", "home"),
                _launch_url("yt_ch2", "chapter2"),
                _launch_url("yt_ch3", "chapter3"),
                _launch_url("yt_ch4", "chapter4"),
                _launch_url("yt_ch5", "chapter5"),
            }
        ),
        "vk": frozenset(
            {
                _launch_url("vk_pin", "home"),
                _launch_url("vk_ch2", "chapter2"),
                _launch_url("vk_ch3", "chapter3"),
                _launch_url("vk_ch4", "chapter4"),
                _launch_url("vk_ch5", "chapter5"),
            }
        ),
    }
)

BIBLE_TRAINER_URL_TO_PLATFORM: Mapping[str, str] = MappingProxyType(
    {
        url: platform
        for platform, urls in BIBLE_TRAINER_LINKS_BY_PLATFORM.items()
        for url in urls
    }
)
BIBLE_TRAINER_LINKS = frozenset(BIBLE_TRAINER_URL_TO_PLATFORM)


def approved_bible_trainer_platform(canonical_url: str) -> str | None:
    return BIBLE_TRAINER_URL_TO_PLATFORM.get(canonical_url)


__all__ = [
    "BIBLE_TRAINER_BOT_USERNAME",
    "BIBLE_TRAINER_LINKS",
    "BIBLE_TRAINER_LINKS_BY_PLATFORM",
    "approved_bible_trainer_platform",
]
