from __future__ import annotations

import pytest

from video_channel_manager.platforms.vk.publishing import (
    VK_PUBLICATION_POLICY_VERSION,
    render_vk_publication,
    render_vk_publication_description,
    render_vk_publication_title,
)


def test_publication_title_adds_one_lightning_marker() -> None:
    assert render_vk_publication_title("  Скифы   — Александр Блок ") == "Скифы — Александр Блок ⚡"
    assert render_vk_publication_title("Скифы 🔥") == "Скифы ⚡"
    assert render_vk_publication_title("Скифы ⚡") == "Скифы ⚡"


def test_publication_description_is_plain_text_and_branded_once() -> None:
    publication = render_vk_publication(
        "Стихотворение",
        "*Фет* написал _стихотворение_.\n\nVK: https://vk.com/the_legendary_poet",
    )

    assert publication.title == "Стихотворение ⚡"
    assert publication.description.startswith("Фет написал стихотворение.")
    assert "https://vk.com/the_legendary_poet" in publication.description
    assert publication.description.count("https://thelegendarypoet.ru/") == 1
    assert publication.policy_version == VK_PUBLICATION_POLICY_VERSION
    assert publication.description_sha256.startswith("sha256:")


def test_publication_description_blocks_unresolved_html() -> None:
    with pytest.raises(ValueError, match="requires editorial review"):
        render_vk_publication_description("<b>Текст</b>")


def test_publication_title_rejects_blank_value() -> None:
    with pytest.raises(ValueError, match="cannot be blank"):
        render_vk_publication_title("   ")
