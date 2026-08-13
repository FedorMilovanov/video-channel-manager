from video_channel_manager.editorial import autofix_youtube_description, validate_youtube_description


def _codes(description: str) -> set[str]:
    return {finding.code for finding in validate_youtube_description(description)}


def test_plain_text_reference_description_passes() -> None:
    description = """«На поле Куликовом» показывает историю как продолжающийся путь.

📜 Первая часть цикла была написана 7 июня 1908 года, а позднее вошла в раздел «Родина».

🎧 The Legendary Poet — поэзия, история, AI-музыка, голосовые эксперименты и визуальные реконструкции.

Плейлист «Александр Блок»: https://www.youtube.com/playlist?list=PL123
VK: https://vk.com/thelegendarypoet
Telegram: https://t.me/thelegendarypoet
RUTUBE: https://rutube.ru/channel/74579453/

#TheLegendaryPoet #АлександрБлок"""
    assert validate_youtube_description(description) == []


def test_markdown_style_emphasis_is_blocking_in_video_description() -> None:
    for description in (
        "Лишь в **1833 году** роман появился единым изданием.",
        "🕯 *О РОМАНЕ*\n\nОбычный текст.",
        "Это _курсивная_ попытка оформления.",
        "Это __жирная__ попытка оформления.",
    ):
        findings = validate_youtube_description(description)
        matching = [item for item in findings if item.code == "markdown_emphasis_in_description"]
        assert len(matching) == 1
        assert matching[0].severity == "error"


def test_autofix_removes_description_emphasis_without_changing_words() -> None:
    description = """🕯 *О РОМАНЕ*

Лишь в **1833 году** роман появился единым изданием.

🎼 _Текст:_ Александр Сергеевич Пушкин."""
    fixed, fixes = autofix_youtube_description(description)
    assert (
        fixed
        == """🕯 О РОМАНЕ

Лишь в 1833 году роман появился единым изданием.

🎼 Текст: Александр Сергеевич Пушкин."""
    )
    assert {fix.code for fix in fixes} == {"markdown_emphasis_removed"}
    assert "markdown_emphasis_in_description" not in _codes(fixed)


def test_underscore_inside_url_is_not_treated_as_formatting() -> None:
    description = "Полная версия: https://youtu.be/ib2ehg2__sg?si=XbQdaxD4bQmkuJ7R"
    assert "markdown_emphasis_in_description" not in _codes(description)


def test_literal_triple_star_poem_title_is_not_treated_as_formatting() -> None:
    description = """К *** (Я помню чудное мгновенье…)

Я помню чудное мгновенье:
Передо мной явилась ты."""
    assert "markdown_emphasis_in_description" not in _codes(description)


def test_markdown_link_is_blocking() -> None:
    findings = validate_youtube_description("Сайт: [The Legendary Poet](https://thelegendarypoet.ru/)")
    matching = [item for item in findings if item.code == "hidden_markdown_link"]
    assert len(matching) == 1
    assert matching[0].severity == "error"


def test_unresolved_square_placeholder_is_blocking() -> None:
    findings = validate_youtube_description("Body\n\n[[CHAPTERS_FROM_EXACT_VERIFIED_TIMING]]\n\nFooter")
    matching = [item for item in findings if item.code == "unresolved_template_placeholder"]
    assert len(matching) == 1
    assert matching[0].severity == "error"


def test_autofix_normalizes_multiple_blank_lines() -> None:
    fixed, fixes = autofix_youtube_description("Первый абзац.\n\n\n\nВторой абзац.")
    assert fixed == "Первый абзац.\n\nВторой абзац."
    assert {fix.code for fix in fixes} == {"multiple_blank_lines"}


def test_verse_block_is_not_reported_as_dense_prose() -> None:
    verse = "\n".join(f"Строка стихотворения номер {index}" for index in range(1, 31))
    description = f"Первый абзац.\n\n{verse}"
    assert "long_paragraph" not in _codes(description)


def test_autofix_is_idempotent() -> None:
    description = """Первый абзац.

Дата — **7 июня 1908 года**, затем обычный текст."""
    fixed_once, first_fixes = autofix_youtube_description(description)
    fixed_twice, second_fixes = autofix_youtube_description(fixed_once)
    assert first_fixes
    assert fixed_twice == fixed_once
    assert second_fixes == []
