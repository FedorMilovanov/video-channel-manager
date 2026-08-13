from __future__ import annotations

MILOVI_SITE_URL = "https://milovicake.ru/"
MILOVI_GALLERY_URL = "https://milovicake.ru/gallery/"
MILOVI_MARKET_URL = "https://vk.ru/market-68859909?screen=group"
MILOVI_CLIPS_URL = "https://vk.ru/clips/milovi_cake"

PUBLIC_PROMOTION_URLS = (
    MILOVI_SITE_URL,
    MILOVI_GALLERY_URL,
    MILOVI_MARKET_URL,
    MILOVI_CLIPS_URL,
)


def promotion_block() -> str:
    return "\n".join(
        (
            "🎂 Milovi Cake — торты и десерты на заказ",
            "",
            f"🌐 Сайт: {MILOVI_SITE_URL}",
            f"📸 Галерея работ: {MILOVI_GALLERY_URL}",
            f"🛍 Товары — выбрать и заказать: {MILOVI_MARKET_URL}",
            f"🎬 Все клипы: {MILOVI_CLIPS_URL}",
        )
    )


def public_clip_description(title: str) -> str:
    normalized = title.strip() or "Milovi Cake"
    return f"{normalized}\n\n{promotion_block()}"


def public_wall_message(title: str) -> str:
    normalized = title.strip() or "Milovi Cake"
    return f"{normalized}\n\n{promotion_block()}"


def assert_internal_promotion_copy(value: str) -> None:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Milovi public copy cannot be blank")
    lowered = normalized.casefold()
    if "youtube.com" in lowered or "youtu.be" in lowered:
        raise ValueError("YouTube links are provenance-only and forbidden in Milovi public copy")
    for url in PUBLIC_PROMOTION_URLS:
        if normalized.count(url) != 1:
            raise ValueError(f"Milovi public copy must contain canonical URL exactly once: {url}")


__all__ = [
    "MILOVI_CLIPS_URL",
    "MILOVI_GALLERY_URL",
    "MILOVI_MARKET_URL",
    "MILOVI_SITE_URL",
    "PUBLIC_PROMOTION_URLS",
    "assert_internal_promotion_copy",
    "promotion_block",
    "public_clip_description",
    "public_wall_message",
]
