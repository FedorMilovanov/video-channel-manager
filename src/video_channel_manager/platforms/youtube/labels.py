from __future__ import annotations

CANONICAL_VK_COMMUNITY_LABEL = "*Сообщество проекта в VK:*"
LEGACY_VK_COMMUNITY_LABEL = "*Сообщество проекта VK:*"
ACCEPTED_VK_COMMUNITY_LABELS = frozenset(
    {
        CANONICAL_VK_COMMUNITY_LABEL,
        LEGACY_VK_COMMUNITY_LABEL,
    }
)


def canonicalize_youtube_link_label(kind: str, label: str) -> str:
    """Return the viewer-facing canonical label for a YouTube link.

    The old VK label remains accepted as input so already reviewed schema-v2
    records do not need a risky mass rewrite. Every newly rendered comment or
    description uses the natural-language canonical wording.
    """

    normalized = label.strip()
    if kind.strip() == "vk" and normalized in ACCEPTED_VK_COMMUNITY_LABELS:
        return CANONICAL_VK_COMMUNITY_LABEL
    return normalized


__all__ = [
    "ACCEPTED_VK_COMMUNITY_LABELS",
    "CANONICAL_VK_COMMUNITY_LABEL",
    "LEGACY_VK_COMMUNITY_LABEL",
    "canonicalize_youtube_link_label",
]
