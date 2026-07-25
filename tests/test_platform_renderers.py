from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

from video_channel_manager.editorial.content import parse_content_record
from video_channel_manager.editorial.preview import preview_records
from video_channel_manager.editorial.rendering import layout_issues
from video_channel_manager.platforms.vk.renderers import VKPostRenderer, VKVideoDescriptionRenderer
from video_channel_manager.platforms.youtube.renderers import YouTubeCommentRenderer, YouTubeDescriptionRenderer


def _record():
    path = Path(__file__).resolve().parents[1] / "content" / "editorial" / "examples" / "tyutchev-night-sea.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return parse_content_record(payload)


def test_same_record_renders_for_youtube_and_vk() -> None:
    record = _record()
    youtube = YouTubeCommentRenderer().render(record)
    vk = VKVideoDescriptionRenderer().render(record)
    assert youtube.is_valid
    assert vk.is_valid
    assert "🌊 *Две редакции одного морского текста*" in youtube.text
    assert "🌊 Две редакции одного морского текста" in vk.text
    assert "*" not in vk.text
    assert "_" not in vk.text
    assert "Сообщество проекта VK: https://vk.com/thelegendarypoet" in vk.text
    assert "VK:\n" not in vk.text


def test_description_and_post_renderers_keep_compact_inline_links() -> None:
    record = _record()
    youtube = YouTubeDescriptionRenderer().render(record)
    vk = VKPostRenderer().render(record)
    assert youtube.is_valid
    assert vk.is_valid
    for rendered in (youtube, vk):
        assert all(not line.strip().endswith("VK:") for line in rendered.text.splitlines())
        assert rendered.link_count == 4


def test_renderers_apply_platform_specific_preferred_link_order() -> None:
    record = replace(
        _record(),
        rendering_metadata=MappingProxyType(
            {
                "preferred_link_order": {
                    "youtube.comment": ["site", "playlist", "vk", "primary_text"],
                    "vk.video_description": ["vk", "site", "primary_text", "playlist"],
                }
            }
        ),
    )
    youtube = YouTubeCommentRenderer().render(record)
    vk = VKVideoDescriptionRenderer().render(record)
    assert youtube.text.index("The Legendary Poet") < youtube.text.index("Фёдор Тютчев — плейлист")
    assert vk.text.index("Сообщество проекта VK") < vk.text.index("The Legendary Poet")


def test_vk_renderer_preserves_plain_text_converter_diagnostics() -> None:
    record = _record()
    unsafe_fact = replace(record.fact, text=f"{record.fact.text} <b>Неподдерживаемая разметка</b>")
    rendered = VKVideoDescriptionRenderer().render(replace(record, fact=unsafe_fact))
    codes = {issue.code for issue in rendered.issues}
    assert "vk_fact_html_tag_not_supported" in codes


def test_layout_detector_finds_orphan_labels_and_long_link_lines() -> None:
    issues = layout_issues(
        "VK:\nОчень длинная подпись, которая не нужна пользователю и только ломает мобильную строку: "
        "https://example.org/very/long/path",
        max_line_length=60,
    )
    codes = {issue.code for issue in issues}
    assert "orphan_link_label" in codes
    assert "long_link_line" in codes


def test_batch_preview_detects_duplicate_rendered_text() -> None:
    record = _record()
    preview = preview_records([record, record], platform="vk", surface="video_description")
    assert "duplicate rendered texts: 1" in preview.errors
