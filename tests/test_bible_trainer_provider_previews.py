from __future__ import annotations

from copy import deepcopy

from video_channel_manager.editorial.content import LORD_GOD_STRENGTH, validate_content_record
from video_channel_manager.editorial.preview import preview_payload


def _base_payload() -> dict[str, object]:
    return {
        "schema_name": "video-manager.editorial-content",
        "schema_version": 1,
        "project_key": LORD_GOD_STRENGTH,
        "content_id": "lord-god-bible-trainer-preview",
        "status": "approved",
        "profile": "historical",
        "variation_key": "lord-god-bible-trainer-preview-v1",
        "channel_id": "UCeSJsC6go2c9pdJCuUI1BYA",
        "video_id": "preview-only",
        "video_title": "Provider-inert Bible trainer preview fixture",
        "reviewed_at": "2026-08-17T17:30:00+00:00",
        "source_ids": ["bible-app-site"],
        "fact": {
            "heading": "📖 *Проверка после чтения*",
            "fact_type": "documented_context",
            "source_ids": ["bible-app-site"],
            "text": (
                "После чтения материала можно открыть Библейский тренажёр "
                "и проверить знание соответствующей главы 1 Петра."
            ),
        },
        "question": {
            "lead": "_Что стоит повторить перед следующим материалом:_",
            "text": "основные аргументы и связи текста?",
        },
        "links": [
            {
                "kind": "site",
                "label": "📌 *Господь Бог — Сила Моя:*",
                "url": "https://gospod-bog.ru/",
            },
            {
                "kind": "vk",
                "label": "*Сообщество проекта в VK:*",
                "url": "https://vk.ru/the_lord_god_is_my_strength",
            },
        ],
        "sources": [
            {
                "source_id": "bible-app-site",
                "title": "Библейский тренажёр — Господь Бог, Сила Моя",
                "url": "https://gospod-bog.ru/app/",
            }
        ],
        "platform_suitability": {
            "youtube": ["description"],
            "vk": ["video_description", "post"],
        },
        "rendering_metadata": {
            "editorial_angle": "contextual-study-tool",
            "preferred_link_order": {
                "youtube.description": ["site", "bible_trainer", "vk"],
                "vk.video_description": ["site", "bible_trainer", "vk"],
                "vk.post": ["site", "bible_trainer", "vk"],
            },
        },
        "platform_targets": {
            "youtube.description": "preview-only",
            "vk.video_description": "preview-only",
            "vk.post": "preview-only",
        },
    }


def _with_trainer(
    *,
    url: str,
    platform: str,
    surfaces: list[str],
) -> dict[str, object]:
    payload = deepcopy(_base_payload())
    links = payload["links"]
    assert isinstance(links, list)
    links.append(
        {
            "kind": "bible_trainer",
            "label": "📖 *Проверить знания:*",
            "url": url,
            "platforms": [platform],
            "surfaces": surfaces,
        }
    )
    return payload


def test_youtube_profile_preview_renders_exact_home_launch_without_vk_attribution() -> None:
    url = "https://t.me/milovanovaibot?startapp=v1_yt_profile__home"
    payload = _with_trainer(url=url, platform="youtube", surfaces=["description"])

    assert validate_content_record(payload) == []
    preview = preview_payload(payload, platform="youtube", surface="description")

    assert preview.rendered.is_valid
    assert url in preview.rendered.text
    assert "v1_vk_pin__home" not in preview.rendered.text
    assert "📖 *Проверить знания:*" in preview.rendered.text
    assert preview.rendered.link_count == 3


def test_vk_pin_preview_renders_exact_home_launch_without_youtube_attribution() -> None:
    url = "https://t.me/milovanovaibot?startapp=v1_vk_pin__home"
    payload = _with_trainer(
        url=url,
        platform="vk",
        surfaces=["video_description", "post"],
    )

    assert validate_content_record(payload) == []
    video_preview = preview_payload(payload, platform="vk", surface="video_description")
    post_preview = preview_payload(payload, platform="vk", surface="post")

    for preview in (video_preview, post_preview):
        assert preview.rendered.is_valid
        assert url in preview.rendered.text
        assert "v1_yt_profile__home" not in preview.rendered.text
        assert "Проверить знания" in preview.rendered.text
        assert preview.rendered.link_count == 3


def test_provider_preview_is_cta_free_until_bible_trainer_is_explicitly_added() -> None:
    payload = _base_payload()

    assert validate_content_record(payload) == []
    youtube = preview_payload(payload, platform="youtube", surface="description")
    vk = preview_payload(payload, platform="vk", surface="video_description")

    assert youtube.rendered.is_valid
    assert vk.rendered.is_valid
    assert "milovanovaibot" not in youtube.rendered.text
    assert "milovanovaibot" not in vk.rendered.text
    assert youtube.rendered.link_count == 2
    assert vk.rendered.link_count == 2


def test_chapter_specific_previews_keep_source_and_destination_coupled() -> None:
    youtube_url = "https://t.me/milovanovaibot?startapp=v1_yt_ch3__chapter3"
    vk_url = "https://t.me/milovanovaibot?startapp=v1_vk_ch4__chapter4"

    youtube = preview_payload(
        _with_trainer(url=youtube_url, platform="youtube", surfaces=["description"]),
        platform="youtube",
        surface="description",
    )
    vk = preview_payload(
        _with_trainer(url=vk_url, platform="vk", surfaces=["video_description"]),
        platform="vk",
        surface="video_description",
    )

    assert youtube.rendered.is_valid
    assert vk.rendered.is_valid
    assert youtube_url in youtube.rendered.text
    assert vk_url in vk.rendered.text
    assert "v1_yt_ch3__chapter4" not in youtube.rendered.text
    assert "v1_vk_ch4__chapter3" not in vk.rendered.text
