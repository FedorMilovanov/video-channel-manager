from __future__ import annotations

from video_channel_manager.platforms.youtube.labels import (
    CANONICAL_VK_COMMUNITY_LABEL,
    LEGACY_VK_COMMUNITY_LABEL,
    canonicalize_youtube_link_label,
)


def test_legacy_vk_label_renders_with_natural_preposition() -> None:
    rendered = canonicalize_youtube_link_label("vk", LEGACY_VK_COMMUNITY_LABEL)

    assert rendered == CANONICAL_VK_COMMUNITY_LABEL
    assert rendered != LEGACY_VK_COMMUNITY_LABEL


def test_non_vk_labels_are_not_rewritten() -> None:
    label = "🎧 *Сергей Есенин — плейлист:*"
    assert canonicalize_youtube_link_label("playlist", label) == label
