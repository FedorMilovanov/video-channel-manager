"""Official Bot API limit enforcement and plain-text extraction for rich articles."""

from __future__ import annotations

import json
from typing import Any

import pytest

from video_channel_manager.telegram_rich_models import RICH_ARTICLE_SCHEMA_NAME, RichArticleDocument, iter_blocks
from video_channel_manager.telegram_rich_validation import (
    MAX_RICH_BLOCKS,
    MAX_RICH_MEDIA_ATTACHMENTS,
    MAX_RICH_NESTING_DEPTH,
    MAX_RICH_TEXT_UTF8_CHARS,
    MAX_TABLE_COLUMNS,
    RICH_ARTICLE_LIMITS,
    RichArticleValidationError,
    count_blocks,
    document_text_length,
    max_block_nesting_depth,
    max_inline_nesting_depth,
    max_table_columns,
    plain_text,
    plain_text_sha256,
    validate_document,
)
from test_telegram_rich_models import build_document, valid_document_payload


def test_limits_constants_match_official_bot_api_docs() -> None:
    assert RICH_ARTICLE_LIMITS == {
        "max_text_utf8_chars": 32_768,
        "max_blocks": 500,
        "max_nesting_depth": 16,
        "max_media_attachments": 50,
        "max_table_columns": 20,
    }


def test_complex_document_passes_full_validation() -> None:
    document = build_document()
    validate_document(document)
    assert count_blocks(document) == 32
    assert len(list(iter_blocks(document.blocks))) == 25
    assert max_block_nesting_depth(document) == 2
    assert max_inline_nesting_depth(document) == 1
    assert max_table_columns(document) == 2
    assert document_text_length(document) > 0


def test_text_length_limit_boundary() -> None:
    at_limit = RichArticleDocument.model_validate(_paragraph_document("a" * MAX_RICH_TEXT_UTF8_CHARS, "b-1"))
    validate_document(at_limit)
    assert document_text_length(at_limit) == MAX_RICH_TEXT_UTF8_CHARS

    over_limit = RichArticleDocument.model_validate(_paragraph_document("a" * (MAX_RICH_TEXT_UTF8_CHARS + 1), "b-2"))
    with pytest.raises(RichArticleValidationError, match="UTF-8 characters"):
        validate_document(over_limit)


def test_emoji_alt_and_formula_source_count_toward_text_limit() -> None:
    payload = _paragraph_document("a" * (MAX_RICH_TEXT_UTF8_CHARS - 10), "b-1")
    payload["blocks"][0]["text"] = [
        "a" * (MAX_RICH_TEXT_UTF8_CHARS - 10),
        {"type": "custom_emoji", "custom_emoji_id": "5368324170671202286", "alternative_text": "0123456789"},
        {"type": "mathematical_expression", "expression": "E=mc^2"},
    ]
    payload["media"] = []
    over = RichArticleDocument.model_validate(payload)
    assert document_text_length(over) == MAX_RICH_TEXT_UTF8_CHARS + 6
    with pytest.raises(RichArticleValidationError, match="UTF-8 characters"):
        validate_document(over)


def test_block_count_limit_boundary() -> None:
    at_limit = RichArticleDocument.model_validate(_many_paragraph_document(MAX_RICH_BLOCKS))
    validate_document(at_limit)
    assert count_blocks(at_limit) == MAX_RICH_BLOCKS

    over_limit = RichArticleDocument.model_validate(_many_paragraph_document(MAX_RICH_BLOCKS + 1))
    with pytest.raises(RichArticleValidationError, match="block count exceeds"):
        validate_document(over_limit)


def test_block_nesting_depth_limit_boundary() -> None:
    at_limit = RichArticleDocument.model_validate(_details_chain(MAX_RICH_NESTING_DEPTH - 1))
    assert max_block_nesting_depth(at_limit) == MAX_RICH_NESTING_DEPTH
    validate_document(at_limit)

    over_limit = RichArticleDocument.model_validate(_details_chain(MAX_RICH_NESTING_DEPTH))
    assert max_block_nesting_depth(over_limit) == MAX_RICH_NESTING_DEPTH + 1
    with pytest.raises(RichArticleValidationError, match="block nesting depth exceeds"):
        validate_document(over_limit)


def test_inline_formatting_depth_limit_boundary() -> None:
    at_limit = RichArticleDocument.model_validate(_paragraph_document(_nested_bold("x", MAX_RICH_NESTING_DEPTH), "b-1"))
    assert max_inline_nesting_depth(at_limit) == MAX_RICH_NESTING_DEPTH
    validate_document(at_limit)

    over_limit = RichArticleDocument.model_validate(
        _paragraph_document(_nested_bold("x", MAX_RICH_NESTING_DEPTH + 1), "b-2")
    )
    with pytest.raises(RichArticleValidationError, match="inline formatting depth exceeds"):
        validate_document(over_limit)


def test_media_attachment_limit_boundary() -> None:
    at_limit = RichArticleDocument.model_validate(_media_document(MAX_RICH_MEDIA_ATTACHMENTS))
    validate_document(at_limit)

    over_limit = RichArticleDocument.model_validate(_media_document(MAX_RICH_MEDIA_ATTACHMENTS + 1))
    with pytest.raises(RichArticleValidationError, match="media attachments exceed"):
        validate_document(over_limit)


def test_table_column_limit_boundary() -> None:
    at_limit = RichArticleDocument.model_validate(_table_document(MAX_TABLE_COLUMNS))
    assert max_table_columns(at_limit) == MAX_TABLE_COLUMNS
    validate_document(at_limit)

    over_limit = RichArticleDocument.model_validate(_table_document(MAX_TABLE_COLUMNS + 1))
    with pytest.raises(RichArticleValidationError, match="table columns exceed"):
        validate_document(over_limit)


def test_media_placement_policy() -> None:
    inside_list = valid_document_payload()
    inside_list["blocks"] = [
        {
            "type": "list",
            "block_id": "list-media",
            "items": [
                {
                    "blocks": [
                        {
                            "type": "media",
                            "block_id": "media-in-list",
                            "media_id": "venus-photo",
                        }
                    ]
                }
            ],
        }
    ]
    inside_list["media"] = [{"media_id": "venus-photo", "kind": "photo", "uri": "content/media/v.jpg"}]
    with pytest.raises(RichArticleValidationError, match="outside top-level/collage/slideshow"):
        validate_document(RichArticleDocument.model_validate(inside_list))

    inside_quote = valid_document_payload()
    inside_quote["blocks"] = [
        {
            "type": "blockquote",
            "block_id": "quote-media",
            "blocks": [
                {"type": "media", "block_id": "media-in-quote", "media_id": "venus-photo"},
            ],
        }
    ]
    inside_quote["media"] = [{"media_id": "venus-photo", "kind": "photo", "uri": "content/media/v.jpg"}]
    with pytest.raises(RichArticleValidationError, match="outside top-level/collage/slideshow"):
        validate_document(RichArticleDocument.model_validate(inside_quote))

    inside_collage = valid_document_payload()
    inside_collage["blocks"] = [
        {
            "type": "collage",
            "block_id": "collage-media",
            "blocks": [
                {"type": "media", "block_id": "media-in-collage", "media_id": "venus-photo"},
            ],
        }
    ]
    inside_collage["media"] = [{"media_id": "venus-photo", "kind": "photo", "uri": "content/media/v.jpg"}]
    validate_document(RichArticleDocument.model_validate(inside_collage))


def test_validate_document_reports_multiple_violations() -> None:
    payload = _paragraph_document("x", "b-1")
    payload["blocks"] = [
        {"type": "paragraph", "block_id": f"b-{i}", "text": "x" * 100} for i in range(MAX_RICH_BLOCKS + 1)
    ]
    document = RichArticleDocument.model_validate(payload)
    with pytest.raises(RichArticleValidationError) as excinfo:
        validate_document(document)
    message = str(excinfo.value)
    assert "UTF-8 characters" in message
    assert "block count exceeds" in message


def test_plain_text_extraction_is_deterministic_and_readable() -> None:
    document = RichArticleDocument.model_validate(
        {
            "schema_name": RICH_ARTICLE_SCHEMA_NAME,
            "schema_version": 1,
            "document_id": "svodka-plain-0001",
            "project_key": "svodka",
            "metadata": {"title": "Сводка", "language": "ru", "created_at": "2026-08-10"},
            "blocks": [
                {"type": "heading", "block_id": "h-1", "text": "Заголовок", "size": 2},
                {"type": "paragraph", "block_id": "p-1", "text": ["Привет, ", {"type": "bold", "text": "мир"}]},
                {"type": "pullquote", "block_id": "pq-1", "text": "Цитата", "credit": "Автор"},
                {
                    "type": "list",
                    "block_id": "l-1",
                    "items": [
                        {"blocks": [{"type": "paragraph", "block_id": "l-1-a", "text": "раз"}]},
                        {"blocks": [{"type": "paragraph", "block_id": "l-1-b", "text": "два"}], "label_type": "1"},
                    ],
                },
                {"type": "divider", "block_id": "d-1"},
                {"type": "mathematical_expression", "block_id": "m-1", "expression": "E=mc^2"},
                {
                    "type": "details",
                    "block_id": "det-1",
                    "summary": "Подробности",
                    "blocks": [{"type": "paragraph", "block_id": "det-1-p", "text": "внутри"}],
                },
            ],
        }
    )
    expected = (
        "Заголовок\n\nПривет, мир\n\n> Цитата\n> — Автор\n\n- раз\n2. два\n\n---\n\n$$E=mc^2$$\n\nПодробности\n  внутри"
    )
    assert plain_text(document) == expected
    assert plain_text(document) == plain_text(document)


def test_plain_text_extraction_media_table_quote() -> None:
    document = RichArticleDocument.model_validate(
        {
            "schema_name": RICH_ARTICLE_SCHEMA_NAME,
            "schema_version": 1,
            "document_id": "svodka-plain-0002",
            "project_key": "svodka",
            "metadata": {"title": "Сводка", "language": "ru", "created_at": "2026-08-10"},
            "media": [
                {"media_id": "img-1", "kind": "photo", "uri": "content/media/img.jpg", "alt_text": "альт"},
            ],
            "blocks": [
                {
                    "type": "table",
                    "block_id": "t-1",
                    "cells": [
                        [{"text": "a", "is_header": True}, {"text": "b", "is_header": True}],
                        [{"text": "1"}, {"text": "2"}],
                    ],
                },
                {
                    "type": "blockquote",
                    "block_id": "q-1",
                    "blocks": [{"type": "paragraph", "block_id": "q-1-p", "text": "строка"}],
                    "credit": "Цитатник",
                },
                {"type": "media", "block_id": "m-1", "media_id": "img-1", "caption": {"text": "Подпись"}},
                {
                    "type": "collage",
                    "block_id": "c-1",
                    "blocks": [{"type": "media", "block_id": "c-1-m", "media_id": "img-1"}],
                    "caption": {"text": "Коллаж"},
                },
            ],
        }
    )
    expected = "| a | b |\n| 1 | 2 |\n\n> строка\n> — Цитатник\n\n[photo] Подпись\n\ncollage: Коллаж\n  [photo] альт"
    assert plain_text(document) == expected


def test_plain_text_sha256_semantic_verification() -> None:
    formatted = RichArticleDocument.model_validate(
        {
            "schema_name": RICH_ARTICLE_SCHEMA_NAME,
            "schema_version": 1,
            "document_id": "svodka-sem-0001",
            "project_key": "svodka",
            "metadata": {"title": "Сводка", "language": "ru", "created_at": "2026-08-10"},
            "blocks": [{"type": "paragraph", "block_id": "p-1", "text": [{"type": "bold", "text": "Привет мир"}]}],
        }
    )
    plain = RichArticleDocument.model_validate(
        {
            "schema_name": RICH_ARTICLE_SCHEMA_NAME,
            "schema_version": 1,
            "document_id": "svodka-sem-0001",
            "project_key": "svodka",
            "metadata": {"title": "Сводка", "language": "ru", "created_at": "2026-08-10"},
            "blocks": [{"type": "paragraph", "block_id": "p-1", "text": "Привет мир"}],
        }
    )
    # Same visible content, different formatting: same plain text, different digest.
    assert plain_text(formatted) == plain_text(plain) == "Привет мир"
    assert plain_text_sha256(formatted) == plain_text_sha256(plain)
    assert formatted.digest != plain.digest
    assert plain_text_sha256(formatted).startswith("sha256:")


def test_plain_text_is_stable_across_reconstruction() -> None:
    document = build_document()
    rebuilt = RichArticleDocument.model_validate(json.loads(document.canonical_json))
    assert plain_text(document) == plain_text(rebuilt)
    assert plain_text_sha256(document) == plain_text_sha256(rebuilt)


def _paragraph_document(text: object, block_id: str) -> dict[str, Any]:
    return {
        "schema_name": RICH_ARTICLE_SCHEMA_NAME,
        "schema_version": 1,
        "document_id": "svodka-limit-0001",
        "project_key": "svodka",
        "metadata": {"title": "Лимит", "language": "ru", "created_at": "2026-08-10"},
        "blocks": [{"type": "paragraph", "block_id": block_id, "text": text}],
    }


def _many_paragraph_document(count: int) -> dict[str, Any]:
    return {
        "schema_name": RICH_ARTICLE_SCHEMA_NAME,
        "schema_version": 1,
        "document_id": "svodka-blocks-0001",
        "project_key": "svodka",
        "metadata": {"title": "Блоки", "language": "ru", "created_at": "2026-08-10"},
        "blocks": [{"type": "paragraph", "block_id": f"b-{i}", "text": "x"} for i in range(count)],
    }


def _details_chain(details_count: int) -> dict[str, Any]:
    inner: dict[str, Any] = {"type": "paragraph", "block_id": "chain-leaf", "text": "лист"}
    for index in range(details_count):
        inner = {
            "type": "details",
            "block_id": f"chain-{index}",
            "summary": "раздел",
            "blocks": [inner],
        }
    return {
        "schema_name": RICH_ARTICLE_SCHEMA_NAME,
        "schema_version": 1,
        "document_id": "svodka-depth-0001",
        "project_key": "svodka",
        "metadata": {"title": "Глубина", "language": "ru", "created_at": "2026-08-10"},
        "blocks": [inner],
    }


def _nested_bold(text: str, depth: int) -> dict[str, Any]:
    node: object = text
    for _ in range(depth):
        node = {"type": "bold", "text": node}
    return node  # type: ignore[return-value]


def _media_document(count: int) -> dict[str, Any]:
    return {
        "schema_name": RICH_ARTICLE_SCHEMA_NAME,
        "schema_version": 1,
        "document_id": "svodka-media-0001",
        "project_key": "svodka",
        "metadata": {"title": "Медиа", "language": "ru", "created_at": "2026-08-10"},
        "media": [
            {"media_id": f"media-{index}", "kind": "photo", "uri": f"content/media/{index}.jpg"}
            for index in range(count)
        ],
        "blocks": [
            {"type": "media", "block_id": f"media-block-{index}", "media_id": f"media-{index}"}
            for index in range(count)
        ],
    }


def _table_document(columns: int) -> dict[str, Any]:
    row = [{"text": f"c{index}"} for index in range(columns)]
    return {
        "schema_name": RICH_ARTICLE_SCHEMA_NAME,
        "schema_version": 1,
        "document_id": "svodka-table-0001",
        "project_key": "svodka",
        "metadata": {"title": "Таблица", "language": "ru", "created_at": "2026-08-10"},
        "blocks": [{"type": "table", "block_id": "table-1", "cells": [row]}],
    }
