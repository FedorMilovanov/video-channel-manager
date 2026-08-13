from __future__ import annotations

from dataclasses import dataclass

MILOVI_SITE_URL = "https://milovicake.ru/"
MILOVI_GALLERY_URL = "https://milovicake.ru/gallery/"
MILOVI_MARKET_URL = "https://vk.ru/market-68859909?screen=group"
MILOVI_CLIPS_URL = "https://vk.ru/clips/milovi_cake"
MILOVI_ORDER_URL = "https://milovicake.ru/zakazat-tort-spb/"
MILOVI_ABOUT_URL = "https://milovicake.ru/o-konditere/"
MILOVI_CERTIFICATES_URL = "https://milovicake.ru/certificates/"
MILOVI_REVIEWS_URL = "https://milovicake.ru/otzyvy/"
MILOVI_DELIVERY_URL = "https://milovicake.ru/dostavka-i-oplata/"
MILOVI_MERINGUE_URL = "https://milovicake.ru/meringue-roll/"
MILOVI_BENTO_URL = "https://milovicake.ru/bento-torty/"
MILOVI_CHILDREN_URL = "https://milovicake.ru/detskie-torty/"
MILOVI_WEDDING_URL = "https://milovicake.ru/svadebnye-torty/"
MILOVI_BIRTHDAY_URL = "https://milovicake.ru/tort-na-den-rozhdeniya/"

PUBLIC_PROMOTION_URLS = (
    MILOVI_SITE_URL,
    MILOVI_GALLERY_URL,
    MILOVI_MARKET_URL,
    MILOVI_CLIPS_URL,
)


@dataclass(frozen=True, slots=True)
class PromotionRoute:
    label: str
    url: str
    lead: str


def _route_for_title(title: str) -> PromotionRoute:
    lowered = title.casefold()
    if "меренг" in lowered or "рулет" in lowered:
        return PromotionRoute(
            label="Меренговый рулет",
            url=MILOVI_MERINGUE_URL,
            lead=(
                "Воздушная меренга, нежный крем-чиз и свежая малина — тот самый десерт, "
                "для которого у Milovi Cake есть отдельная страница с подробностями заказа."
            ),
        )
    if "бенто" in lowered or "мини-торт" in lowered or "мини торт" in lowered:
        return PromotionRoute(
            label="Бенто-торты",
            url=MILOVI_BENTO_URL,
            lead=(
                "Небольшой торт может быть очень личным: надпись, цвет, настроение и детали "
                "подбираются под конкретного человека и повод."
            ),
        )
    if "свад" in lowered or "невест" in lowered or "жених" in lowered:
        return PromotionRoute(
            label="Свадебные торты",
            url=MILOVI_WEDDING_URL,
            lead=(
                "Свадебный торт в Milovi Cake собирается вокруг самого события: формат, вкус, "
                "декор и подача обсуждаются как часть общей стилистики праздника."
            ),
        )
    if "дет" in lowered or "реб" in lowered or "малыш" in lowered or "персонаж" in lowered:
        return PromotionRoute(
            label="Детские торты",
            url=MILOVI_CHILDREN_URL,
            lead=(
                "Детский торт — это маленькая история про любимые цвета, персонажей и момент, "
                "который ребёнок узнаёт с первого взгляда."
            ),
        )
    if "день рождения" in lowered or "дню рождения" in lowered or "юбиле" in lowered:
        return PromotionRoute(
            label="Торты на день рождения",
            url=MILOVI_BIRTHDAY_URL,
            lead=(
                "Для дня рождения важен не просто красивый декор: Milovi Cake подбирает вкус, "
                "размер и оформление под человека, гостей и атмосферу праздника."
            ),
        )
    return PromotionRoute(
        label="Заказать торт в Санкт-Петербурге",
        url=MILOVI_ORDER_URL,
        lead=(
            "В Milovi Cake каждый заказ обсуждается индивидуально: повод, дата, количество гостей, "
            "вкус, оформление, референсы и доставка."
        ),
    )


def promotion_block(title: str) -> str:
    route = _route_for_title(title)
    return "\n".join(
        (
            f"🍰 {route.label}: {route.url}",
            f"🌐 Главный сайт: {MILOVI_SITE_URL}",
            f"📸 Галерея работ: {MILOVI_GALLERY_URL}",
            f"🛍 Товары — выбрать и заказать: {MILOVI_MARKET_URL}",
            f"🎬 Все клипы Milovi Cake: {MILOVI_CLIPS_URL}",
        )
    )


def trust_block() -> str:
    return "\n".join(
        (
            "Milovi Cake — частная кондитерская Виктории Миловановой в Санкт-Петербурге. "
            "Авторские торты и десерты создаются вручную и под конкретный заказ.",
            f"👩‍🍳 О Виктории и её подходе: {MILOVI_ABOUT_URL}",
            f"🎓 Сертификаты и обучение: {MILOVI_CERTIFICATES_URL}",
            f"💬 Отзывы клиентов: {MILOVI_REVIEWS_URL}",
            f"🚚 Доставка и оплата: {MILOVI_DELIVERY_URL}",
        )
    )


def public_clip_description(title: str) -> str:
    normalized = title.strip() or "Milovi Cake"
    route = _route_for_title(normalized)
    return f"{normalized}\n\n{route.lead}\n\n{trust_block()}\n\n{promotion_block(normalized)}"


def public_wall_message(title: str) -> str:
    normalized = title.strip() or "Milovi Cake"
    route = _route_for_title(normalized)
    return (
        f"{normalized}\n\n{route.lead}\n\n"
        "За красивой работой здесь стоит не потоковое производство, а частный кондитер и "
        "индивидуальная работа с каждым заказом.\n\n"
        f"{trust_block()}\n\n{promotion_block(normalized)}"
    )


def assert_internal_promotion_copy(value: str, *, title: str) -> None:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Milovi public copy cannot be blank")
    lowered = normalized.casefold()
    if "youtube.com" in lowered or "youtu.be" in lowered or "youtube" in lowered:
        raise ValueError("YouTube is provenance-only and forbidden in Milovi public copy")
    for url in PUBLIC_PROMOTION_URLS:
        if normalized.count(url) != 1:
            raise ValueError(f"Milovi public copy must contain canonical URL exactly once: {url}")
    route = _route_for_title(title)
    for url in (route.url, MILOVI_ABOUT_URL, MILOVI_CERTIFICATES_URL):
        if normalized.count(url) != 1:
            raise ValueError(f"Milovi public copy must contain required deep link exactly once: {url}")


__all__ = [
    "MILOVI_ABOUT_URL",
    "MILOVI_BENTO_URL",
    "MILOVI_BIRTHDAY_URL",
    "MILOVI_CERTIFICATES_URL",
    "MILOVI_CHILDREN_URL",
    "MILOVI_CLIPS_URL",
    "MILOVI_DELIVERY_URL",
    "MILOVI_GALLERY_URL",
    "MILOVI_MARKET_URL",
    "MILOVI_MERINGUE_URL",
    "MILOVI_ORDER_URL",
    "MILOVI_REVIEWS_URL",
    "MILOVI_SITE_URL",
    "MILOVI_WEDDING_URL",
    "PUBLIC_PROMOTION_URLS",
    "PromotionRoute",
    "assert_internal_promotion_copy",
    "promotion_block",
    "public_clip_description",
    "public_wall_message",
    "trust_block",
]
