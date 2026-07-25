from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from video_channel_manager.platforms.vk.models import VkAccessToken
from video_channel_manager.platforms.vk.store import VkTokenStore
from video_channel_manager.platforms.vk.text import (
    VK_VIDEO_DESCRIPTION_CAPABILITIES,
    render_vk_clip_description,
    render_vk_video_description,
)
from video_channel_manager.platforms.vk.text_writer import VkVideoTextWriter, vk_texts_equivalent
from video_channel_manager.platforms.vk.writer import VkWriteError


def _token() -> VkAccessToken:
    return VkAccessToken(
        access_token="secret",
        scopes=["video", "groups"],
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


def _writer(tmp_path: Path, handler: httpx.MockTransport) -> VkVideoTextWriter:
    store = VkTokenStore(tmp_path)
    store.save_token("legendary-poet", _token())
    return VkVideoTextWriter(
        token_store=store,
        account_alias="legendary-poet",
        http_client=httpx.Client(transport=handler),
        api_base_url="https://api.example/method",
    )


def test_vk_video_capabilities_are_plain_text() -> None:
    assert VK_VIDEO_DESCRIPTION_CAPABILITIES.supports_markdown is False
    assert VK_VIDEO_DESCRIPTION_CAPABILITIES.supports_html is False
    assert VK_VIDEO_DESCRIPTION_CAPABILITIES.supports_inline_bold is False
    assert VK_VIDEO_DESCRIPTION_CAPABILITIES.supports_inline_italic is False
    assert VK_VIDEO_DESCRIPTION_CAPABILITIES.supports_plain_urls is True
    assert VK_VIDEO_DESCRIPTION_CAPABILITIES.supports_hashtags is True


def test_render_vk_description_removes_youtube_emphasis_but_preserves_content() -> None:
    source = """«Шёпот, робкое дыханье…» — ночная версия стихотворения Афанасия Фета.

Стихотворение было написано в *1850 году*, когда *Фет* переживал пик своей любви к *Марии Лазич*.

_Осенью того же года_ Мария погибла страшной смертью.

*Плейлист «Афанасий Фет»:* https://www.youtube.com/playlist?list=PLy9lLJfoq3uYTr
*VK:* https://vk.com/thelegendarypoet

#TheLegendaryPoet #АфанасийФет"""

    rendered = render_vk_video_description(source)

    assert "*1850 году*" not in rendered.text
    assert "1850 году" in rendered.text
    assert "_Осенью того же года_" not in rendered.text
    assert "Осенью того же года" in rendered.text
    assert "Плейлист «Афанасий Фет»: https://" in rendered.text
    assert "VK: https://vk.com/thelegendarypoet" in rendered.text
    assert "#TheLegendaryPoet" in rendered.text
    assert rendered.text.endswith("🌐 https://thelegendarypoet.ru/")
    assert rendered.removed_emphasis_pairs == 6
    assert rendered.footer_added is True
    assert rendered.has_errors is False


def test_render_preserves_underscores_in_urls_ids_and_literal_poem_title() -> None:
    source = """К *** (Я помню чудное мгновенье…)

Полная версия: https://youtu.be/ib2ehg2__sg?si=XbQdaxD4bQmkuJ7R
Технический ID: video_235216998_456239134"""

    rendered = render_vk_video_description(source)

    assert "К *** (Я помню чудное мгновенье…)" in rendered.text
    assert "ib2ehg2__sg" in rendered.text
    assert "video_235216998_456239134" in rendered.text
    assert rendered.removed_emphasis_pairs == 0
    assert not any(issue.code == "literal_asterisk_remaining" for issue in rendered.issues)


def test_render_converts_markdown_links_and_normalizes_invisible_characters() -> None:
    source = "Сайт: [The Legendary Poet](https://thelegendarypoet.ru/)\ufeff\n\n\n\nНовый абзац."

    rendered = render_vk_video_description(source)

    assert "The Legendary Poet: https://thelegendarypoet.ru/" in rendered.text
    assert "\ufeff" not in rendered.text
    assert "\n\n\n" not in rendered.text
    assert rendered.converted_markdown_links == 1
    assert rendered.removed_zero_width_characters == 1
    assert rendered.collapsed_blank_runs == 1
    assert rendered.footer_added is False


def test_render_is_idempotent_and_site_footer_is_not_duplicated() -> None:
    first = render_vk_video_description("Первый *абзац*.")
    second = render_vk_video_description(first.text)

    assert second.text == first.text
    assert second.removed_emphasis_pairs == 0
    assert second.footer_added is False
    assert second.text.count("https://thelegendarypoet.ru/") == 1


def test_clip_renderer_adds_full_video_route_and_reports_policy_limit() -> None:
    rendered = render_vk_clip_description(
        "Короткий *фрагмент*.",
        full_video_url="https://vk.com/video-1_2",
        max_characters=20,
    )

    assert "Короткий фрагмент." in rendered.text
    assert "▶ Полная версия: https://vk.com/video-1_2" in rendered.text
    assert any(issue.code == "clip_description_too_long" and issue.severity == "error" for issue in rendered.issues)


def test_vk_text_equivalence_normalizes_server_whitespace_and_zero_width() -> None:
    assert vk_texts_equivalent("Строка\r\nВторая\ufeff  ", "Строка\nВторая")


def test_guarded_video_edit_uses_desc_and_verifies(tmp_path: Path) -> None:
    state = {
        "owner_id": -235216998,
        "id": 456239134,
        "title": "Шёпот, робкое дыханье… ⚡ Фет",
        "description": "Текст с *видимой разметкой*.",
    }
    calls: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/video.get"):
            return httpx.Response(200, json={"response": {"count": 1, "items": [state]}})
        if request.url.path.endswith("/video.edit"):
            body = request.content.decode("utf-8")
            assert "owner_id=-235216998" in body
            assert "video_id=456239134" in body
            assert "desc=" in body
            state["description"] = "Текст с видимой разметкой."
            return httpx.Response(200, json={"response": 1})
        raise AssertionError(request.url)

    writer = _writer(tmp_path, httpx.MockTransport(respond))
    verified = writer.replace_text_if_current(
        owner_id=-235216998,
        video_id=456239134,
        expected_description="Текст с *видимой разметкой*.",
        new_description="Текст с видимой разметкой.",
    )

    assert verified.description == "Текст с видимой разметкой."
    assert calls == ["/method/video.get", "/method/video.edit", "/method/video.get"]


def test_guarded_video_edit_refuses_unknown_live_description(tmp_path: Path) -> None:
    state = {
        "owner_id": -235216998,
        "id": 456239134,
        "title": "Title",
        "description": "Изменено вручную",
    }
    methods: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        methods.append(request.url.path)
        return httpx.Response(200, json={"response": {"count": 1, "items": [state]}})

    writer = _writer(tmp_path, httpx.MockTransport(respond))
    with pytest.raises(VkWriteError, match="reviewed before-state"):
        writer.replace_text_if_current(
            owner_id=-235216998,
            video_id=456239134,
            expected_description="Старый текст",
            new_description="Новый текст",
        )

    assert methods == ["/method/video.get"]
