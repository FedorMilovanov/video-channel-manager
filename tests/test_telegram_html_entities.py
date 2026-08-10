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
    assert entities[0].model_dump(mode="json") == {
        "type": "bold",
        "offset": 2,
        "length": 6,
        "url": None,
    }


def test_parse_telegram_html_supports_custom_emoji_with_utf16_fallback() -> None:
    plain, entities = parse_telegram_html('📚 <tg-emoji emoji-id="5368324170671202286">1️⃣</tg-emoji> <b>Факт</b>')

    assert plain == "📚 1️⃣ Факт"
    custom = next(entity for entity in entities if entity.type == "custom_emoji")
    assert custom.offset == 3
    assert custom.length == 3
    assert custom.custom_emoji_id == "5368324170671202286"
    assert custom.url is None
    assert custom.model_dump(mode="json") == {
        "type": "custom_emoji",
        "offset": 3,
        "length": 3,
        "url": None,
        "custom_emoji_id": "5368324170671202286",
    }


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


def test_message_entities_match_rejects_custom_emoji_id_drift() -> None:
    _, expected = parse_telegram_html('<tg-emoji emoji-id="5368324170671202286">1️⃣</tg-emoji> факт')
    actual = [
        {
            "type": "custom_emoji",
            "offset": 0,
            "length": 3,
            "custom_emoji_id": "5368324170671202287",
        }
    ]

    assert message_entities_match(expected, actual) is False
