from video_channel_manager.editorial import autofix_youtube_description, validate_youtube_description


def _codes(description: str) -> set[str]:
    return {finding.code for finding in validate_youtube_description(description)}


def test_reference_rendering_style_passes() -> None:
    description = """«На поле Куликовом» показывает историю как продолжающийся путь.

📜 *Первая часть цикла была написана 7 июня 1908 года,* а позднее вошла в раздел *«Родина».*

Обычный абзац без эмодзи сохраняет спокойный ритм текста.

🐎 *«Летит, летит степная кобылица и мнёт ковыль...»* — движение становится главным образом финала.

_Покой нам только снится._

🎧 *The Legendary Poet* — поэзия, история, AI-музыка, голосовые эксперименты и визуальные реконструкции.

*Плейлист «Александр Блок»:* https://www.youtube.com/playlist?list=PL123

*VK:* https://vk.com/thelegendarypoet
*Telegram:* https://t.me/thelegendarypoet
*RUTUBE:* https://rutube.ru/channel/74579453/

#TheLegendaryPoet #АлександрБлок"""

    assert validate_youtube_description(description) == []


def test_punctuation_scope_is_review_only_except_metadata_label() -> None:
    description = """Чистый первый абзац.

Дата указана как *7 июня 1908 года*, а цикл вошёл в раздел *«Родина»*.

*VK*: https://vk.com/thelegendarypoet"""

    findings = validate_youtube_description(description)
    review = [finding for finding in findings if finding.code == "punctuation_scope_review"]
    metadata = [finding for finding in findings if finding.code == "metadata_label_colon"]
    assert len(review) == 2
    assert all(finding.severity == "warning" for finding in review)
    assert len(metadata) == 1
    assert metadata[0].severity == "error"


def test_explanatory_colon_after_emphasis_requires_review_not_error() -> None:
    description = """Чистый первый абзац.

Особенно важен повтор слова *«тленной»*: дальше следует его объяснение."""
    matching = [
        finding
        for finding in validate_youtube_description(description)
        if finding.code == "punctuation_scope_review"
    ]
    assert len(matching) == 1
    assert matching[0].severity == "warning"


def test_extra_period_after_emphasized_question_is_removed_not_moved() -> None:
    description = """Чистый первый абзац.

Так заканчивается стихотворение *«Что это такое?»*."""
    matching = [
        finding
        for finding in validate_youtube_description(description)
        if finding.code == "duplicate_terminal_punctuation"
    ]
    assert len(matching) == 1
    assert matching[0].severity == "error"


def test_external_dash_after_channel_name_is_allowed() -> None:
    description = """Чистый первый абзац.

*The Legendary Poet* — поэзия, история и музыкальные эксперименты."""
    assert "punctuation_scope_review" not in _codes(description)


def test_share_preview_requires_plain_first_paragraph() -> None:
    assert "share_preview_emphasis" not in _codes("⚔️ Первый абзац без разметки.\n\nОбычный текст.")
    assert "share_preview_emphasis" in _codes("⚔️ *Первый абзац с разметкой.*\n\nОбычный текст.")


def test_drkin_first_paragraph_is_fixed_without_touching_later_emphasis() -> None:
    description = """Веня Д’ркин — поэт, чья сила — _беспощадная ясность._ Его песни звучат как свет.

*Anno Domini* по-латыни означает «в лето Господне».

Главный нерв песни — *сопротивление слепоте.*"""
    fixed, fixes = autofix_youtube_description(description)
    assert fixed.startswith("Веня Д’ркин — поэт, чья сила — беспощадная ясность. Его песни звучат как свет.")
    assert "*Anno Domini*" in fixed
    assert "*сопротивление слепоте.*" in fixed
    assert [fix.code for fix in fixes].count("share_preview_emphasis") == 1
    assert "share_preview_emphasis" not in _codes(fixed)


def test_emoji_on_every_body_paragraph_is_only_a_warning() -> None:
    description = """⚔️ Первый крупный абзац без форматирования.

📜 Второй крупный абзац.

🌾 Третий крупный абзац.

🐎 Четвёртый крупный абзац."""
    findings = validate_youtube_description(description)
    matching = [finding for finding in findings if finding.code == "emoji_every_paragraph"]
    assert len(matching) == 1
    assert matching[0].severity == "warning"


def test_description_without_emoji_is_valid() -> None:
    description = """Первый абзац без форматирования.

Второй абзац развивает исторический контекст.

Третий абзац объясняет центральный образ.

Четвёртый абзац завершает мысль."""
    assert "emoji_every_paragraph" not in _codes(description)
    assert "emoji_density_high" not in _codes(description)


def test_underscore_inside_url_is_not_treated_as_italic_marker() -> None:
    description = """Первый абзац без форматирования.

Полная версия: https://youtu.be/Ac7Fz_9HS3I"""
    assert "unbalanced_italic" not in _codes(description)


def test_underscore_inside_first_paragraph_url_is_not_formatting() -> None:
    description = "Полная версия: https://youtu.be/ib2ehg2__sg?si=XbQdaxD4bQmkuJ7R"
    assert "share_preview_emphasis" not in _codes(description)
    assert "unbalanced_italic" not in _codes(description)


def test_box_drawing_separator_is_not_an_emoji() -> None:
    description = """Первый абзац без форматирования.

━━━━━━━━━━━━━━━━━━━━

━━━━━━━━━━━━━━━━━━━━

━━━━━━━━━━━━━━━━━━━━

Обычный заключительный абзац."""
    assert "emoji_repeated_mechanically" not in _codes(description)
    assert "emoji_density_high" not in _codes(description)


def test_verse_block_is_not_reported_as_dense_prose() -> None:
    verse = "\n".join(f"Строка стихотворения номер {index}" for index in range(1, 31))
    description = f"Первый абзац без форматирования.\n\n{verse}"
    assert "long_paragraph" not in _codes(description)


def test_literal_triple_star_poem_title_is_not_broken_bold() -> None:
    description = """К *** (Я помню чудное мгновенье…)

Я помню чудное мгновенье:
Передо мной явилась ты."""
    assert "share_preview_emphasis" not in _codes(description)
    assert "unbalanced_bold" not in _codes(description)
    assert "bold_edge_space" not in _codes(description)


def test_autofix_changes_only_unambiguous_punctuation() -> None:
    description = """Чистый первый абзац.

Дата указана как *7 июня 1908 года*, затем раздел *«Родина»*.

Особенно важен повтор *«тленной»*: дальше следует объяснение.

Так заканчивается текст *«Что это такое?»*.

*VK*: https://vk.com/thelegendarypoet"""
    fixed, fixes = autofix_youtube_description(description)
    assert "*7 июня 1908 года*," in fixed
    assert "*«Родина»*." in fixed
    assert "*«тленной»*:" in fixed
    assert "*«Что это такое?»*\n" in fixed
    assert "*VK:* https://" in fixed
    assert {fix.code for fix in fixes} == {
        "duplicate_terminal_punctuation",
        "metadata_label_colon",
    }


def test_autofix_normalizes_blank_lines_and_edge_spaces_without_stealing_period() -> None:
    description = "Первый абзац.\n\n\n\nВторой абзац с * лишним пробелом * и _ лишним курсивом _."
    fixed, fixes = autofix_youtube_description(description)
    assert "\n\n\n" not in fixed
    assert "*лишним пробелом*" in fixed
    assert "_лишним курсивом_." in fixed
    assert {fix.code for fix in fixes} == {
        "multiple_blank_lines",
        "bold_edge_space",
        "italic_edge_space",
    }


def test_regression_sentence_punctuation_remains_outside_titles_dates_and_terms() -> None:
    description = """Чистый первый абзац.

Сборник *«Радуница»*, книга *«Вечер»*, дата *18 сентября 1912 года*, термин *magnitizdat*, имя *Yuri Kasparyan*.

Игра называется _The Witcher 3: Wild Hunt_."""
    fixed, fixes = autofix_youtube_description(description)
    assert fixed == description
    assert fixes == []


def test_autofix_is_idempotent() -> None:
    description = """Первый *абзац*.

Дата — *7 июня 1908 года*, затем обычный текст."""
    fixed_once, first_fixes = autofix_youtube_description(description)
    fixed_twice, second_fixes = autofix_youtube_description(fixed_once)
    assert first_fixes
    assert fixed_twice == fixed_once
    assert second_fixes == []
