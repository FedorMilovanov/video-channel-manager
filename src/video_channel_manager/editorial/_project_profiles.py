from __future__ import annotations

from types import MappingProxyType
from typing import Any, Mapping

LORD_GOD_STRENGTH = "lord-god-strength"
LEGENDARY_POET = "legendary-poet"

PROJECT_CHANNEL_IDS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        LORD_GOD_STRENGTH: frozenset({"UCeSJsC6go2c9pdJCuUI1BYA"}),
        LEGENDARY_POET: frozenset({"UC-78ys2S3cQ3lpqgXfo-SvQ"}),
    }
)

PROJECT_LINK_PROFILES: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        LORD_GOD_STRENGTH: frozenset(
            {
                "https://gospod-bog.ru/",
                "https://t.me/lordchrist",
                "https://vk.ru/the_lord_god_is_my_strength",
                "https://vk.com/the_lord_god_is_my_strength",
                "https://vkvideo.ru/@the_lord_god_is_my_strength",
                "https://rutube.ru/channel/1876662/",
                "https://ok.ru/christjesus",
                "https://facebook.com/groups/116164165395881",
            }
        ),
        LEGENDARY_POET: frozenset(
            {
                "https://thelegendarypoet.ru/",
                "https://vk.com/thelegendarypoet",
                "https://t.me/thelegendarypoet",
                "https://rutube.ru/channel/74579453/",
                "https://www.youtube.com/@TheLegendaryPoet/playlists",
                "https://www.youtube.com/playlist?list=PLy9lLJfoq3uYdxFo5bxzXEUI8HYIo-sHb",
                "https://www.youtube.com/playlist?list=PLy9lLJfoq3uaxXMvilfZIYVXsf4fY18T8",
                "https://www.youtube.com/playlist?list=PLy9lLJfoq3uaI7EGOexBWQp7WX-KVabKM",
                "https://www.youtube.com/playlist?list=PLy9lLJfoq3uapKkid7HzfXHmSi3FR2y3Q",
                "https://www.youtube.com/playlist?list=PLy9lLJfoq3ubOdGfY8orpQzGNAAvkqul5",
                "https://www.youtube.com/playlist?list=PLy9lLJfoq3ua0FhqDhByHxyaBjVrk0-pE",
                "https://www.youtube.com/playlist?list=PLy9lLJfoq3ua3Q9BQe1Dhuzn7Knbz2djU",
                "https://www.youtube.com/playlist?list=PLKzLtO0ERdzg",
                "https://www.youtube.com/playlist?list=PLy9lLJfoq3uYTrhcN1TDMUeks46Y-TT_M",
                "https://www.youtube.com/playlist?list=PLy9lLJfoq3ua1QeVsZutwScsM0l-asll4",
                "https://www.youtube.com/playlist?list=PLy9lLJfoq3uZcrWY0F3Qux93xos6kIS7-",
            }
        ),
    }
)

CHANNEL_ID_TO_PROJECT_KEY: Mapping[str, str] = MappingProxyType(
    {channel_id: project_key for project_key, channel_ids in PROJECT_CHANNEL_IDS.items() for channel_id in channel_ids}
)

PROJECT_KEYS = frozenset(PROJECT_LINK_PROFILES)


def explicit_project_key(payload: Mapping[str, Any]) -> str | None:
    value = payload.get("project_key")
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def channel_project_key(payload: Mapping[str, Any]) -> str | None:
    value = payload.get("channel_id")
    if not isinstance(value, str):
        return None
    return CHANNEL_ID_TO_PROJECT_KEY.get(value.strip())


def resolve_project_key(
    payload: Mapping[str, Any],
    *,
    legacy_default: bool = False,
) -> str | None:
    explicit = explicit_project_key(payload)
    if explicit in PROJECT_KEYS:
        return explicit
    inferred = channel_project_key(payload)
    if inferred is not None:
        return inferred
    return LEGENDARY_POET if legacy_default else None


__all__ = [
    "CHANNEL_ID_TO_PROJECT_KEY",
    "LEGENDARY_POET",
    "LORD_GOD_STRENGTH",
    "PROJECT_CHANNEL_IDS",
    "PROJECT_KEYS",
    "PROJECT_LINK_PROFILES",
    "channel_project_key",
    "explicit_project_key",
    "resolve_project_key",
]
