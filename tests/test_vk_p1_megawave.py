from __future__ import annotations

from pathlib import Path

from video_channel_manager.platforms.vk.editorial_megawave import (
    build_evidence_safe_description,
    is_poem_like_block,
)


_WRAPPER = Path("scripts/Invoke-VkP1Megawave.ps1")


def test_evidence_safe_description_preserves_service_blocks_and_poem() -> None:
    poem = """Первая строка
Вторая строка
Третья строка
Четвёртая строка"""
    source = "\n\n".join(
        [
            "Неподтверждённая биографическая и психологическая история.",
            poem,
            "Плейлист: https://example.test/list",
            "#Поэзия #Test",
            "🎧 The Legendary Poet - поэзия, музыка и литературные материалы.\n🌐 Сайт: https://example.test/",
        ]
    )

    rendered, metadata = build_evidence_safe_description(source, "Тестовый ролик")

    assert "Неподтверждённая" not in rendered
    assert poem in rendered
    assert "Плейлист: https://example.test/list" in rendered
    assert "#Поэзия #Test" in rendered
    assert "🎧 The Legendary Poet" in rendered
    assert metadata["urls_unchanged"] is True
    assert metadata["hashtags_unchanged"] is True
    assert metadata["after_length"] <= 5000


def test_evidence_safe_description_strips_prose_around_source_url() -> None:
    source = (
        "Длинное неподтверждённое историческое утверждение, которое нельзя сохранять "
        "только потому, что в конце стоит ссылка. "
        "(Источник: https://example.test/source)"
    )

    rendered, metadata = build_evidence_safe_description(source, "Тестовый ролик")

    assert "Длинное неподтверждённое" not in rendered
    assert "https://example.test/source)" in rendered
    assert "extracted_urls" in metadata["preserved_block_kinds"]
    assert metadata["urls_unchanged"] is True


def test_poem_detection_rejects_prose_list() -> None:
    poem = "Первая строка\nВторая строка\nТретья строка\nЧетвёртая строка"
    prose = "Основные идеи:\n➛ первый тезис\n➛ второй тезис\n➛ третий тезис"

    assert is_poem_like_block(poem) is True
    assert is_poem_like_block(prose) is False


def test_wrapper_is_one_guarded_execute() -> None:
    text = _WRAPPER.read_text(encoding="utf-8")

    assert "$ExpectedCount = 42" in text
    assert "p1-all-remaining-megawave-20260728" in text
    assert "build_vk_p1_megawave_decisions.py" in text
    assert "verify_vk_p1_megawave_plan.py" in text
    assert "verify_vk_p1_megawave_apply_bundle.py" in text
    assert "--max-operations $ExpectedCount" in text
    assert "--execute" in text
    assert "author_batches" not in text
