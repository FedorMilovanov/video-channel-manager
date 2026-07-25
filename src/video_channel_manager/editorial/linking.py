from __future__ import annotations

from collections.abc import Mapping, Sequence

from video_channel_manager.editorial.content import EditorialContentRecord, LinkBlock


def _string_order(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    result: list[str] = []
    for item in value:
        normalized = str(item).strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


def preferred_link_order(
    record: EditorialContentRecord,
    *,
    platform: str,
    surface: str,
) -> tuple[str, ...]:
    raw = record.rendering_metadata.get("preferred_link_order")
    if isinstance(raw, Mapping):
        for key in (f"{platform}.{surface}", platform, "default"):
            order = _string_order(raw.get(key))
            if order:
                return order
        return ()
    return _string_order(raw)


def ordered_links(
    record: EditorialContentRecord,
    *,
    platform: str,
    surface: str,
) -> tuple[LinkBlock, ...]:
    links = list(record.links_for(platform, surface))
    order = preferred_link_order(record, platform=platform, surface=surface)
    if not order:
        return tuple(links)
    rank = {kind: index for index, kind in enumerate(order)}
    indexed = list(enumerate(links))
    indexed.sort(key=lambda pair: (rank.get(pair[1].kind, len(rank)), pair[0]))
    return tuple(link for _, link in indexed)


__all__ = ["ordered_links", "preferred_link_order"]
