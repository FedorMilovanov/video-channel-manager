from __future__ import annotations

from scripts import build_youtube_comment_plan


def test_legacy_vk_label_renders_with_natural_preposition(monkeypatch) -> None:
    monkeypatch.setattr(
        build_youtube_comment_plan,
        "render_comment_content",
        lambda _record: "*Сообщество проекта VK:* https://vk.com/thelegendarypoet",
    )

    rendered = build_youtube_comment_plan._render_for_youtube({})

    assert rendered == "*Сообщество проекта в VK:* https://vk.com/thelegendarypoet"
    assert "*Сообщество проекта VK:*" not in rendered
