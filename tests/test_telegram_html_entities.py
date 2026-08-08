from __future__ import annotations

from video_channel_manager.telegram_html_entities import message_entities_match, parse_telegram_html


def test_parse_telegram_html_uses_utf16_offsets_and_preserves_text_links() -> None:
    plain, entities = parse_telegram_html(
        '⚡ <b>Жирный</b> и <i>курсив</i> — <a href="https://example.test/source">источник</a>'
    )

    assert plain == "⚡ Жирный и курсив — источник"
    assert [(entity.type, entity.offset, entity.length, entity.url) for entity in entities] == [
        ("bold", 2, 6, None),
        ("italic", 11, 6, None),
        ("text_link", 20, 8, "https://example.test/source"),
    ]


def test_message_entities_match_ignores_unrelated_telegram_entities() -> None:
    _, expected = parse_telegram_html('<b>Факт</b> #Сводка <a href="https://example.test">источник</a>')
    actual = [
        {"type": "bold", "offset": 0, "length": 4},
        {"type": "hashtag", "offset": 5, "length": 7},
        {"type": "text_link", "offset": 13, "length": 8, "url": "https://example.test"},
    ]

    assert message_entities_match(expected, actual) is True


def test_message_entities_match_rejects_link_or_formatting_drift() -> None:
    _, expected = parse_telegram_html('<b>Факт</b> <a href="https://example.test/a">источник</a>')

    assert (
        message_entities_match(
            expected,
            [
                {"type": "italic", "offset": 0, "length": 4},
                {"type": "text_link", "offset": 5, "length": 8, "url": "https://example.test/a"},
            ],
        )
        is False
    )
    assert (
        message_entities_match(
            expected,
            [
                {"type": "bold", "offset": 0, "length": 4},
                {"type": "text_link", "offset": 5, "length": 8, "url": "https://example.test/b"},
            ],
        )
        is False
    )
