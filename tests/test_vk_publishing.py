from __future__ import annotations

import pytest

from video_channel_manager.platforms.vk.publishing import (
    VK_PUBLICATION_POLICY_VERSION,
    render_vk_publication,
    render_vk_publication_description,
    render_vk_publication_title,
)


def test_poet_publication_title_adds_one_lightning_marker() -> None:
    assert (
        render_vk_publication_title("  Скифы   — Александр Блок ", project_key="legendary-poet")
        == "Скифы — Александр Блок ⚡"
    )
    assert render_vk_publication_title("Скифы 🔥", project_key="legendary-poet") == "Скифы ⚡"
    assert render_vk_publication_title("Скифы ⚡", project_key="legendary-poet") == "Скифы ⚡"


def test_poet_publication_description_is_plain_text_and_branded_once() -> None:
    publication = render_vk_publication(
        "Стихотворение",
        "*Фет* написал _стихотворение_.\n\nVK: https://vk.com/the_legendary_poet",
        project_key="legendary-poet",
    )

    assert publication.project_key == "legendary-poet"
    assert publication.title == "Стихотворение ⚡"
    assert publication.description.startswith("Фет написал стихотворение.")
    assert "https://vk.com/the_legendary_poet" in publication.description
    assert publication.description.count("https://thelegendarypoet.ru/") == 1
    assert "gospod-bog.ru" not in publication.description
    assert publication.policy_version == VK_PUBLICATION_POLICY_VERSION
    assert publication.description_sha256.startswith("sha256:")


def test_lord_god_publication_uses_only_its_profile() -> None:
    publication = render_vk_publication(
        "Послание к Римлянам",
        "*Разбор* седьмой главы.",
        project_key="lord-god-strength",
    )

    assert publication.project_key == "lord-god-strength"
    assert publication.title == "Послание к Римлянам"
    assert "https://gospod-bog.ru/" in publication.description
    assert "The Legendary Poet" not in publication.description
    assert "thelegendarypoet.ru" not in publication.description


def test_publication_rendering_fails_closed_without_project_identity() -> None:
    with pytest.raises(ValueError, match="explicit registered project_key"):
        render_vk_publication("Заголовок", "Описание")
    with pytest.raises(ValueError, match="explicit registered project_key"):
        render_vk_publication_description("Описание")
    with pytest.raises(ValueError, match="explicit registered project_key"):
        render_vk_publication_title("Заголовок")


def test_publication_description_blocks_unresolved_html() -> None:
    with pytest.raises(ValueError, match="requires editorial review"):
        render_vk_publication_description("<b>Текст</b>", project_key="legendary-poet")


def test_publication_title_rejects_blank_value() -> None:
    with pytest.raises(ValueError, match="cannot be blank"):
        render_vk_publication_title("   ", project_key="legendary-poet")
