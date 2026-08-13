from __future__ import annotations

import pytest

from video_channel_manager.platforms.vk.milovi_promotion import (
    MILOVI_ABOUT_URL,
    MILOVI_CERTIFICATES_URL,
    MILOVI_CLIPS_URL,
    MILOVI_GALLERY_URL,
    MILOVI_MARKET_URL,
    MILOVI_MERINGUE_URL,
    MILOVI_SITE_URL,
    assert_internal_promotion_copy,
    public_clip_description,
    public_urls,
    public_wall_message,
)


@pytest.mark.parametrize(
    "title",
    [
        "Меренговый рулет с малиной",
        "Бенто-торт для подруги",
        "Детский торт с персонажем",
        "Свадебный торт",
        "Торт на день рождения",
        "Авторский торт Milovi Cake",
    ],
)
def test_public_copy_is_internal_milovi_promotion(title: str) -> None:
    for text in (public_clip_description(title), public_wall_message(title)):
        assert "youtube" not in text.casefold()
        assert "youtu.be" not in text.casefold()
        urls = public_urls(text)
        for url in (MILOVI_SITE_URL, MILOVI_GALLERY_URL, MILOVI_MARKET_URL, MILOVI_CLIPS_URL):
            assert urls.count(url) == 1
        assert urls.count(MILOVI_ABOUT_URL) == 1
        assert urls.count(MILOVI_CERTIFICATES_URL) == 1
        assert_internal_promotion_copy(text, title=title)


def test_meringue_copy_routes_to_exact_product_page() -> None:
    title = "Меренговый рулет с малиной"
    description = public_clip_description(title)
    assert public_urls(description).count(MILOVI_MERINGUE_URL) == 1
    assert "воздушная меренга" in description.casefold()
    assert "крем-чиз" in description.casefold()
    assert "малина" in description.casefold()


def test_trust_copy_names_viktoria_and_certificates() -> None:
    text = public_wall_message("Авторский торт")
    assert "Виктории Миловановой" in text
    assert "частная кондитерская" in text
    assert "5 лет опыта" in text
    assert "акварельная роспись" in text
    assert "шоколадная флористика" in text
    assert "Сертификаты и обучение" in text


def test_public_copy_guard_rejects_youtube() -> None:
    text = public_clip_description("Авторский торт") + "\nhttps://www.youtube.com/shorts/example"
    with pytest.raises(ValueError, match="YouTube"):
        assert_internal_promotion_copy(text, title="Авторский торт")
