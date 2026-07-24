from video_channel_manager.editorial import validate_youtube_description


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


def test_punctuation_outside_emphasis_is_reported() -> None:
    description = """Чистый первый абзац.

Дата указана как *7 июня 1908 года*, а цикл вошёл в раздел *«Родина»*.

*VK*: https://vk.com/thelegendarypoet"""

    findings = validate_youtube_description(description)
    assert sum(finding.code == "punctuation_outside_emphasis" for finding in findings) == 3


def test_external_dash_after_channel_name_is_allowed() -> None:
    description = """Чистый первый абзац.

*The Legendary Poet* — поэзия, история и музыкальные эксперименты."""

    assert "punctuation_outside_emphasis" not in _codes(description)


def test_first_paragraph_emoji_is_allowed_but_formatting_is_not() -> None:
    assert "first_paragraph_formatting" not in _codes("⚔️ Первый абзац без разметки.\n\nОбычный текст.")
    assert "first_paragraph_formatting" in _codes("⚔️ *Первый абзац с разметкой.*\n\nОбычный текст.")


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
