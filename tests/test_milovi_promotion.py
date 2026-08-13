from __future__ import annotations

from pathlib import Path

import pytest

from video_channel_manager.platforms.vk.milovi_issue323_finalize import ANOMALY_POST_ID, _validate_anomaly_post
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
from video_channel_manager.platforms.vk.milovi_rollout_sources import SourceAsset


def _legacy_anomaly_asset() -> SourceAsset:
    source_id = "o1WXIMupuws"
    title = "Меренговый рулет с малиной"
    source_url = f"https://www.youtube.com/shorts/{source_id}"
    return SourceAsset(
        source_id=source_id,
        source_url=source_url,
        title=title,
        duration_seconds=27,
        media_path=str(Path("clip.mp4")),
        media_sha256="a" * 64,
        width=1080,
        height=1920,
        description=f"{title}\n\nИсточник YouTube Shorts: {source_url}",
        wall_message=f"{title}\n\nИсточник: {source_url}",
    )


def _exact_anomaly_post() -> dict[str, object]:
    asset = _legacy_anomaly_asset()
    return {
        "owner_id": -68859909,
        "id": ANOMALY_POST_ID,
        "text": "",
        "attachments": [
            {
                "type": "video",
                "video": {
                    "owner_id": -68859909,
                    "id": 456239232,
                    "type": "short_video",
                    "description": asset.description,
                },
            }
        ],
    }


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


def test_issue323_anomaly_guard_accepts_only_exact_wall_shape() -> None:
    _validate_anomaly_post(_exact_anomaly_post(), _legacy_anomaly_asset())


@pytest.mark.parametrize(
    ("field", "value"),
    (("owner_id", -1), ("id", 999), ("text", "unexpected text")),
)
def test_issue323_anomaly_guard_rejects_identity_or_text_drift(field: str, value: object) -> None:
    post = _exact_anomaly_post()
    post[field] = value
    with pytest.raises(Exception):
        _validate_anomaly_post(post, _legacy_anomaly_asset())


def test_issue323_anomaly_guard_rejects_another_clip() -> None:
    post = _exact_anomaly_post()
    attachments = post["attachments"]
    assert isinstance(attachments, list)
    video = attachments[0]["video"]
    assert isinstance(video, dict)
    video["id"] = 456239999
    with pytest.raises(Exception):
        _validate_anomaly_post(post, _legacy_anomaly_asset())
