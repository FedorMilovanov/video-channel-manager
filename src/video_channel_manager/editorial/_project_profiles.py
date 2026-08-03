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

PROJECT_VK_COMMUNITY_IDS: Mapping[str, frozenset[int]] = MappingProxyType(
    {
        LORD_GOD_STRENGTH: frozenset({60805374}),
        LEGENDARY_POET: frozenset({235216998}),
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
                "https://vk.ru/thelegendarypoet",
                "https://vk.com/thelegendarypoet",
                "https://vkvideo.ru/@thelegendarypoet/clips",
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
VK_COMMUNITY_ID_TO_PROJECT_KEY: Mapping[int, str] = MappingProxyType(
    {
        community_id: project_key
        for project_key, community_ids in PROJECT_VK_COMMUNITY_IDS.items()
        for community_id in community_ids
    }
)

PROJECT_KEYS = frozenset(PROJECT_LINK_PROFILES)


def explicit_project_key(payload: Mapping[str, Any]) -> str | None:
    value = payload.get("project_key")
    if value is None or not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def channel_project_key(payload: Mapping[str, Any]) -> str | None:
    value = payload.get("channel_id")
    if not isinstance(value, str):
        return None
    return CHANNEL_ID_TO_PROJECT_KEY.get(value.strip())


def _strict_positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str):
        normalized = value.strip()
        if normalized.isdigit():
            parsed = int(normalized)
            return parsed if parsed > 0 else None
    return None


def vk_community_project_key(payload: Mapping[str, Any]) -> str | None:
    community_id = _strict_positive_int(payload.get("community_id"))
    if community_id is None:
        owner_id = payload.get("owner_id")
        if isinstance(owner_id, bool):
            return None
        if isinstance(owner_id, int) and owner_id < 0:
            community_id = -owner_id
        elif isinstance(owner_id, str):
            normalized = owner_id.strip()
            if normalized.startswith("-") and normalized[1:].isdigit():
                community_id = int(normalized[1:])
    return VK_COMMUNITY_ID_TO_PROJECT_KEY.get(community_id) if community_id is not None else None


def resolve_project_key(
    payload: Mapping[str, Any],
    *,
    legacy_default: bool = False,
) -> str | None:
    """Resolve one registered project from explicit and provider identities.

    ``legacy_default`` is retained only for source compatibility with older
    callers. It no longer supplies an implicit project: reusable parsing must
    never silently assign legacy content to Legendary Poet.
    """

    _ = legacy_default
    explicit = explicit_project_key(payload)
    if explicit is not None and explicit not in PROJECT_KEYS:
        return None

    inferred_values = {
        value
        for value in (
            channel_project_key(payload),
            vk_community_project_key(payload),
        )
        if value is not None
    }
    if len(inferred_values) > 1:
        return None
    inferred = next(iter(inferred_values), None)
    if explicit is not None and inferred is not None and explicit != inferred:
        return None
    if explicit is not None:
        return explicit
    return inferred


__all__ = [
    "CHANNEL_ID_TO_PROJECT_KEY",
    "LEGENDARY_POET",
    "LORD_GOD_STRENGTH",
    "PROJECT_CHANNEL_IDS",
    "PROJECT_KEYS",
    "PROJECT_LINK_PROFILES",
    "PROJECT_VK_COMMUNITY_IDS",
    "VK_COMMUNITY_ID_TO_PROJECT_KEY",
    "channel_project_key",
    "explicit_project_key",
    "resolve_project_key",
    "vk_community_project_key",
]
