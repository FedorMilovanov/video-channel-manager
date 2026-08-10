"""Tests for the legacy Telegram HTML fallback renderer."""

from __future__ import annotations


from telegram_rich_fixtures import ALL_RENDER_SCENARIOS, formula_details_article, quote_article
from video_channel_manager.telegram_html_entities import parse_telegram_html
from video_channel_manager.telegram_rich_fallback import (
    MAX_LEGACY_TEXT,
    RichHtmlFallback,
    render_rich_html_fallback,
)
from video_channel_manager.telegram_rich_validation import plain_text


def test_all_scenarios_render_deterministic_fallback() -> None:
    for name, document in ALL_RENDER_SCENARIOS:
        first = render_rich_html_fallback(document)
        second = render_rich_html_fallback(document)
        assert first.model_dump(mode="json") == second.model_dump(mode="json"), name
        assert isinstance(first, RichHtmlFallback)
        assert first.article_digest == document.digest
        assert len(first.expected_plain_text) <= MAX_LEGACY_TEXT
        # visible text equals the canonical projection without media captions
        assert first.expected_plain_text == plain_text(document, include_media_captions=False), name


def test_fallback_html_round_trips_to_entities_and_plain_text() -> None:
    _, document = ALL_RENDER_SCENARIOS[0]  # scientific
    fallback = render_rich_html_fallback(document)
    parsed_plain, parsed_entities = parse_telegram_html(fallback.html_text)
    assert parsed_plain == fallback.expected_plain_text
    assert tuple(parsed_entities) == tuple(fallback.expected_entities)


def test_fallback_uses_only_verified_legacy_tags() -> None:
    _, document = ALL_RENDER_SCENARIOS[0]
    fallback = render_rich_html_fallback(document)
    for tag in ("<tg-emoji", "<blockquote", "<tg-collage", "<tg-slideshow"):
        assert tag not in fallback.html_text
    assert "<b>" in fallback.html_text
    assert "<i>" in fallback.html_text
    assert "<a href=" in fallback.html_text
    assert "def correlate" in fallback.expected_plain_text


def test_fallback_escapes_html_specials() -> None:
    from datetime import date

    from video_channel_manager.telegram_rich_models import (
        RICH_ARTICLE_SCHEMA_NAME,
        RICH_ARTICLE_SCHEMA_VERSION,
        RichArticleDocument,
        RichArticleMetadata,
        RichBlockParagraph,
        RichTextUrl,
    )

    document = RichArticleDocument(
        schema_name=RICH_ARTICLE_SCHEMA_NAME,
        schema_version=RICH_ARTICLE_SCHEMA_VERSION,
        document_id="escape-demo-doc-0001",
        project_key="svodka",
        metadata=RichArticleMetadata(title="A < B & C", language="ru", created_at=date(2026, 8, 10)),
        blocks=(
            RichBlockParagraph(
                block_id="p-1",
                text=(
                    "5 < 6 && 7 > 3",
                    RichTextUrl(text="ссылка", url="https://example.org/x?a=1&b=2"),
                ),
            ),
        ),
    )
    fallback = render_rich_html_fallback(document)
    assert "&lt;" in fallback.html_text
    assert "&gt;" in fallback.html_text
    assert "&amp;" in fallback.html_text
    assert "https://example.org/x?a=1&amp;b=2" in fallback.html_text


def test_fallback_blank_lines_are_normalized() -> None:
    from datetime import date

    from video_channel_manager.telegram_rich_models import (
        RICH_ARTICLE_SCHEMA_NAME,
        RICH_ARTICLE_SCHEMA_VERSION,
        RichArticleDocument,
        RichArticleMetadata,
        RichBlockHeading,
        RichBlockParagraph,
    )

    document = RichArticleDocument(
        schema_name=RICH_ARTICLE_SCHEMA_NAME,
        schema_version=RICH_ARTICLE_SCHEMA_VERSION,
        document_id="spacing-demo-doc-0001",
        project_key="svodka",
        metadata=RichArticleMetadata(title="Заголовок", language="ru", created_at=date(2026, 8, 10)),
        blocks=(
            RichBlockHeading(block_id="h-title", text="Заголовок", size=1),
            RichBlockParagraph(block_id="p-1", text="Абзац первый"),
            RichBlockParagraph(block_id="p-2", text="Абзац второй"),
            RichBlockParagraph(block_id="p-3", text="Абзац третий"),
        ),
    )
    fallback = render_rich_html_fallback(document)
    assert fallback.html_text.count("\n\n") == 3
    assert "\n\n\n" not in fallback.html_text
    assert not fallback.html_text.startswith("\n")
    assert not fallback.html_text.endswith("\n")


def test_fallback_never_emits_premium_emoji_and_downgrades_media() -> None:
    _, document = ALL_RENDER_SCENARIOS[6]  # inline-media
    fallback = render_rich_html_fallback(document)
    assert "tg-emoji" not in fallback.html_text
    assert any(note.startswith("media:") for note in fallback.downgrades)
    assert any(note.startswith("media:") or "media_dropped" in note for note in fallback.downgrades)


def test_fallback_downgrades_unsupported_features_without_losing_text() -> None:
    document = formula_details_article()
    fallback = render_rich_html_fallback(document)
    assert "E = mc^2" in fallback.expected_plain_text
    assert "a^2 + b^2 = c^2" in fallback.expected_plain_text
    assert "Скрытый текст разворачивается." in fallback.expected_plain_text
    assert any(note.startswith("details:") for note in fallback.downgrades)


def test_fallback_quotes_keep_visible_text() -> None:
    document = quote_article()
    fallback = render_rich_html_fallback(document)
    assert "Благодатью вы спасены через веру" in fallback.expected_plain_text
    assert "Еф. 2:8" in fallback.expected_plain_text
    assert "Автор размышления" in fallback.expected_plain_text


def test_fallback_sha256_is_stable() -> None:
    _, document = ALL_RENDER_SCENARIOS[0]
    first = render_rich_html_fallback(document)
    second = render_rich_html_fallback(document)
    assert first.fallback_sha256 == second.fallback_sha256
    assert first.fallback_sha256.startswith("sha256:")
