"""Golden/snapshot and invariant tests for the legacy Telegram HTML fallback renderer."""

from __future__ import annotations

import json
import os
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from telegram_rich_fixtures import FALLBACK_MIXED
from video_channel_manager.telegram_rich_fallback import (
    MAX_FALLBACK_MESSAGE_TEXT,
    TelegramHtmlFallback,
    compute_html_fallback_sha256,
    render_html_fallback,
)
from video_channel_manager.telegram_rich_models import (
    RICH_ARTICLE_SCHEMA_NAME,
    RICH_ARTICLE_SCHEMA_VERSION,
    RichArticleDocument,
    RichArticleMetadata,
    RichBlockParagraph,
    RichTextBold,
    RichTextUrl,
)
from video_channel_manager.telegram_rich_renderer import canonical_article_text, utf16_length

GOLDEN_DIR = Path(__file__).resolve().parent / "golden" / "telegram_rich"


class _TextExtractor(HTMLParser):
    """Extracts the visible text of a generated Telegram HTML message."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _extract_html_text(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value)
    parser.close()
    return "".join(parser.parts)


def _golden_path(name: str) -> Path:
    return GOLDEN_DIR / f"{name}.json"


def _load_golden(name: str) -> dict[str, Any]:
    return json.loads(_golden_path(name).read_text(encoding="utf-8"))


def _write_golden(name: str, value: dict[str, Any]) -> None:
    path = _golden_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _check_golden(name: str, fallback: TelegramHtmlFallback) -> None:
    dump = fallback.model_dump(mode="json")
    if os.environ.get("UPDATE_GOLDEN") == "1":
        _write_golden(name, dump)
    assert dump == _load_golden(name), f"golden snapshot mismatch: {name}"


def test_fallback_golden_snapshot_is_exact() -> None:
    _check_golden("fallback-rendering", render_html_fallback(FALLBACK_MIXED))


def test_fallback_is_deterministic_and_matches_canonical_article_text() -> None:
    first = render_html_fallback(FALLBACK_MIXED)
    second = render_html_fallback(FALLBACK_MIXED)
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.visible_text == canonical_article_text(FALLBACK_MIXED, include_media_captions=False)
    joined = "\n\n".join(message.visible_text for message in first.messages if message.visible_text)
    assert joined == first.visible_text
    assert first.payload_sha256 == compute_html_fallback_sha256(first)
    assert first.parse_mode == "HTML"
    assert first.article_sha256 == FALLBACK_MIXED.digest
    assert first.media_bundle_sha256 is not None
    assert first.media_bundle_sha256.startswith("sha256:")


def test_fallback_html_round_trips_to_visible_text() -> None:
    fallback = render_html_fallback(FALLBACK_MIXED)
    for message in fallback.messages:
        assert _extract_html_text(message.html_text) == message.visible_text
        assert utf16_length(message.visible_text) <= MAX_FALLBACK_MESSAGE_TEXT


def test_fallback_never_emits_premium_emoji_tags() -> None:
    fallback = render_html_fallback(FALLBACK_MIXED)
    for message in fallback.messages:
        assert "<tg-emoji" not in message.html_text
        assert "tg-emoji" not in message.html_text
    # the premium span appears as its Unicode alternative text instead
    assert "👍" in fallback.visible_text


def test_fallback_records_deterministic_downgrades() -> None:
    fallback = render_html_fallback(FALLBACK_MIXED)
    expected = {
        "custom_emoji:5368324170671202286:unicode_fallback",
        "details:det-1:expanded",
        "footnote:plain_text",
        "formula:plain_text",
        "marked:plain_text",
        "media:m-fallback:dropped_text_only_fallback",
        "subscript:plain_text",
        "superscript:plain_text",
        "table:t-1:plain_text",
    }
    assert set(fallback.downgrades) == expected
    # media captions are media metadata, so the canonical text stays media-free
    assert "Кадр для downgrade" not in fallback.visible_text


def test_fallback_escapes_html_specials_in_text_and_links() -> None:
    document = RichArticleDocument(
        schema_name=RICH_ARTICLE_SCHEMA_NAME,
        schema_version=RICH_ARTICLE_SCHEMA_VERSION,
        document_id="escape-demo-doc-01",
        project_key="svodka",
        metadata=RichArticleMetadata(
            title="A < B & C > D",
            language="ru",
            created_at=date(2026, 8, 10),
        ),
        blocks=(
            RichBlockParagraph(
                block_id="p-escape",
                text=(
                    "5 < 6 && 7 > 3",
                    RichTextBold(text=' и «цитата» "кавычки"'),
                    RichTextUrl(text=" ссылка", url="https://example.org/x?a=1&b=2"),
                ),
            ),
        ),
    )
    fallback = render_html_fallback(document)
    html_text = fallback.messages[0].html_text
    assert "&lt;" in html_text
    assert "&gt;" in html_text
    assert "&amp;" in html_text
    assert "https://example.org/x?a=1&amp;b=2" in html_text
    assert _extract_html_text(html_text) == fallback.visible_text


def test_fallback_blank_lines_are_normalized() -> None:
    document = RichArticleDocument(
        schema_name=RICH_ARTICLE_SCHEMA_NAME,
        schema_version=RICH_ARTICLE_SCHEMA_VERSION,
        document_id="spacing-demo-doc-01",
        project_key="svodka",
        metadata=RichArticleMetadata(
            title="Заголовок",
            language="ru",
            created_at=date(2026, 8, 10),
        ),
        blocks=(
            RichBlockParagraph(block_id="p-1", text="Абзац первый"),
            RichBlockParagraph(block_id="p-2", text="Абзац второй"),
            RichBlockParagraph(block_id="p-3", text="Абзац третий"),
        ),
    )
    fallback = render_html_fallback(document)
    html_text = fallback.messages[0].html_text
    assert html_text.count("\n\n") == 3
    assert "\n\n\n" not in html_text
    assert not html_text.startswith("\n")
    assert not html_text.endswith("\n")
    assert fallback.visible_text == "Заголовок\n\nАбзац первый\n\nАбзац второй\n\nАбзац третий"


def test_fallback_supports_all_verified_html_tags() -> None:
    fallback = render_html_fallback(FALLBACK_MIXED)
    html_text = "\n\n".join(message.html_text for message in fallback.messages)
    assert "<b>" in html_text
    assert "<i>" in html_text
    assert "<u>" in html_text
    assert "<s>" in html_text
    assert "<tg-spoiler>" in html_text
    assert "<code>" in html_text
    assert '<pre><code class="language-bash">' in html_text
    assert "<blockquote>" in html_text
    assert '<a href="https://example.org/source">' in html_text


def test_fallback_splits_long_articles_at_block_boundaries() -> None:
    document = RichArticleDocument(
        schema_name=RICH_ARTICLE_SCHEMA_NAME,
        schema_version=RICH_ARTICLE_SCHEMA_VERSION,
        document_id="long-demo-doc-0001",
        project_key="svodka",
        metadata=RichArticleMetadata(
            title="Длинная статья",
            language="ru",
            created_at=date(2026, 8, 10),
        ),
        blocks=tuple(
            RichBlockParagraph(block_id=f"long-p-{index}", text=f"Абзац номер {index} " + "слово " * 120)
            for index in range(1, 12)
        ),
    )
    fallback = render_html_fallback(document)
    assert len(fallback.messages) > 1
    for message in fallback.messages:
        assert len(message.visible_text) <= MAX_FALLBACK_MESSAGE_TEXT
    # splitting never loses or reorders content
    assert fallback.visible_text == canonical_article_text(document, include_media_captions=False)
    assert fallback.visible_text == "\n\n".join(m.visible_text for m in fallback.messages)
