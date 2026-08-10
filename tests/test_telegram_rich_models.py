"""Structural invariants of the provider-neutral rich article domain model."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from video_channel_manager.telegram_rich_models import (
    RICH_ARTICLE_SCHEMA_NAME,
    RICH_ARTICLE_SCHEMA_VERSION,
    RichArticleDocument,
    canonical_json,
    iter_blocks,
)


def valid_document_payload() -> dict[str, Any]:
    return {
        "schema_name": RICH_ARTICLE_SCHEMA_NAME,
        "schema_version": RICH_ARTICLE_SCHEMA_VERSION,
        "document_id": "svodka-demo-0001",
        "project_key": "svodka",
        "metadata": {
            "title": "Венера — день длиннее года",
            "language": "ru",
            "summary": "Краткая сводка о планете Венера.",
            "author": "Редакция Сводки",
            "tags": ["астрономия", "наука"],
            "created_at": "2026-08-10",
            "canonical_url": "https://example.com/venus",
        },
        "media": [
            {"media_id": "venus-photo", "kind": "photo", "uri": "content/media/venus.jpg", "alt_text": "Венера"},
            {"media_id": "venus-video", "kind": "video", "uri": "https://example.com/venus.mp4"},
            {"media_id": "venus-audio", "kind": "audio", "uri": "https://example.com/venus.mp3"},
        ],
        "blocks": [
            {"type": "heading", "block_id": "h-title", "text": "Венера — день длиннее года", "size": 1},
            {
                "type": "paragraph",
                "block_id": "p-intro",
                "text": [
                    "На ",
                    {"type": "bold", "text": "Венере"},
                    " сутки длятся дольше года: ",
                    {"type": "italic", "text": "243 земных дня"},
                    ". Источник: ",
                    {"type": "url", "text": "НАСА", "url": "https://example.com/nasa"},
                    ".",
                ],
            },
            {
                "type": "paragraph",
                "block_id": "p-inline",
                "text": [
                    {"type": "underline", "text": "подчёркнуто"},
                    " ",
                    {"type": "strikethrough", "text": "зачёркнуто"},
                    " ",
                    {"type": "spoiler", "text": "спойлер"},
                    " ",
                    {"type": "marked", "text": "выделено"},
                    " ",
                    {"type": "code", "text": "code"},
                    " ",
                    {"type": "subscript", "text": "sub"},
                    " ",
                    {"type": "superscript", "text": "sup"},
                    " ",
                    {"type": "custom_emoji", "custom_emoji_id": "5368324170671202286", "alternative_text": "👍"},
                    " ",
                    {"type": "mathematical_expression", "expression": "E = mc^2"},
                    " ",
                    {"type": "anchor", "name": "chapter-1"},
                    " ",
                    {"type": "anchor_link", "text": "к разделу", "anchor_name": "chapter-1"},
                    " ",
                    {"type": "reference", "name": "src1", "text": "Источник: НАСА"},
                    " ",
                    {"type": "reference_link", "text": "[1]", "reference_name": "src1"},
                ],
            },
            {"type": "divider", "block_id": "d-1"},
            {"type": "pre", "block_id": "pre-1", "text": "print('hello')", "language": "python"},
            {"type": "mathematical_expression", "block_id": "math-1", "expression": "a^2 + b^2 = c^2"},
            {
                "type": "list",
                "block_id": "list-1",
                "items": [
                    {
                        "blocks": [{"type": "paragraph", "block_id": "list-1-item-1", "text": "первый пункт"}],
                        "has_checkbox": True,
                        "is_checked": True,
                    },
                    {"blocks": [{"type": "paragraph", "block_id": "list-1-item-2", "text": "второй пункт"}]},
                ],
            },
            {
                "type": "list",
                "block_id": "list-2",
                "items": [
                    {
                        "blocks": [{"type": "paragraph", "block_id": "list-2-item-1", "text": "шаг первый"}],
                        "label_type": "i",
                        "value": 3,
                    },
                    {
                        "blocks": [{"type": "paragraph", "block_id": "list-2-item-2", "text": "шаг второй"}],
                        "label_type": "1",
                    },
                ],
            },
            {
                "type": "blockquote",
                "block_id": "quote-1",
                "blocks": [
                    {"type": "paragraph", "block_id": "quote-1-p", "text": "Венера вращается в обратную сторону."}
                ],
                "credit": "НАСА",
            },
            {"type": "pullquote", "block_id": "pull-1", "text": "День длиннее года.", "credit": "Сводка"},
            {
                "type": "table",
                "block_id": "table-1",
                "caption": "Планеты земной группы",
                "cells": [
                    [
                        {"text": "Планета", "is_header": True},
                        {"text": "Длительность суток", "is_header": True},
                    ],
                    [
                        {"text": "Венера"},
                        {"text": "243 дня"},
                    ],
                    [
                        {"text": "Земля"},
                        {"text": "24 часа", "align": "center", "valign": "middle"},
                    ],
                ],
                "is_bordered": True,
                "is_striped": True,
            },
            {
                "type": "details",
                "block_id": "details-1",
                "summary": "Подробнее об осевом вращении",
                "is_open": True,
                "blocks": [{"type": "paragraph", "block_id": "details-1-p", "text": "Ось наклонена на 177 градусов."}],
            },
            {
                "type": "media",
                "block_id": "media-1",
                "media_id": "venus-photo",
                "has_spoiler": True,
                "caption": {"text": "Венера в ультрафиолете", "credit": "НАСА"},
            },
            {
                "type": "collage",
                "block_id": "collage-1",
                "blocks": [
                    {"type": "media", "block_id": "collage-1-media", "media_id": "venus-video"},
                    {"type": "media", "block_id": "collage-1-media-2", "media_id": "venus-audio"},
                ],
                "caption": {"text": "Материалы о Венере"},
            },
            {
                "type": "slideshow",
                "block_id": "slideshow-1",
                "blocks": [
                    {"type": "media", "block_id": "slideshow-1-media", "media_id": "venus-photo"},
                ],
            },
            {
                "type": "footer",
                "block_id": "footer-1",
                "text": ["Источники: ", {"type": "url", "text": "НАСА", "url": "https://example.com/nasa"}],
            },
        ],
    }


def build_document() -> RichArticleDocument:
    return RichArticleDocument.model_validate(valid_document_payload())


def test_complex_document_builds_and_serializes_deterministically() -> None:
    document = build_document()
    assert document.schema_name == RICH_ARTICLE_SCHEMA_NAME
    assert document.schema_version == RICH_ARTICLE_SCHEMA_VERSION
    assert document.digest.startswith("sha256:")

    first = document.canonical_json
    second = document.canonical_json
    assert first == second
    # Canonical JSON round-trips back to an identical document.
    rebuilt = RichArticleDocument.model_validate(json.loads(first))
    assert rebuilt == document
    assert rebuilt.digest == document.digest

    # Block order is preserved in the canonical serialization.
    serialized_ids = [block["block_id"] for block in json.loads(first)["blocks"]]
    assert serialized_ids == [block.block_id for block in document.blocks]


def test_digest_is_stable_for_the_same_document() -> None:
    left = build_document()
    right = build_document()
    assert left == right
    assert left.canonical_json == right.canonical_json
    assert left.digest == right.digest


def test_single_content_change_changes_digest() -> None:
    base = build_document()
    changed_payload = valid_document_payload()
    changed_payload["blocks"][1]["text"][0] = "На Марсе "
    changed = RichArticleDocument.model_validate(changed_payload)
    assert changed != base
    assert changed.digest != base.digest


def test_block_reordering_changes_digest() -> None:
    base = build_document()
    reordered_payload = valid_document_payload()
    blocks = list(reordered_payload["blocks"])
    blocks[0], blocks[1] = blocks[1], blocks[0]
    reordered_payload["blocks"] = blocks
    reordered = RichArticleDocument.model_validate(reordered_payload)
    assert reordered.digest != base.digest


def test_none_optional_fields_do_not_change_serialization() -> None:
    """Absent and explicit-None optional fields serialize identically (stable digests)."""
    with_none = build_document()
    minimal = RichArticleDocument.model_validate(
        {
            "schema_name": RICH_ARTICLE_SCHEMA_NAME,
            "schema_version": RICH_ARTICLE_SCHEMA_VERSION,
            "document_id": "svodka-minimal-0001",
            "project_key": "svodka",
            "metadata": {
                "title": "Минимум",
                "language": "ru",
                "created_at": "2026-08-10",
            },
            "blocks": [{"type": "paragraph", "block_id": "p-1", "text": "Текст"}],
        }
    )
    assert "credit" not in json.loads(minimal.canonical_json)["blocks"][0]
    assert "updated_at" not in json.loads(minimal.canonical_json)["metadata"]
    # Explicit None must serialize the same as omitted.
    explicit_payload = {
        "schema_name": RICH_ARTICLE_SCHEMA_NAME,
        "schema_version": RICH_ARTICLE_SCHEMA_VERSION,
        "document_id": "svodka-minimal-0001",
        "project_key": "svodka",
        "metadata": {
            "title": "Минимум",
            "language": "ru",
            "created_at": "2026-08-10",
            "summary": None,
            "updated_at": None,
        },
        "blocks": [{"type": "paragraph", "block_id": "p-1", "text": "Текст"}],
    }
    explicit = RichArticleDocument.model_validate(explicit_payload)
    assert explicit.canonical_json == minimal.canonical_json
    assert explicit.digest == minimal.digest
    assert with_none.digest != minimal.digest


def test_duplicate_block_id_rejected() -> None:
    payload = valid_document_payload()
    payload["blocks"].append({"type": "paragraph", "block_id": "p-intro", "text": "дубликат"})
    with pytest.raises(ValidationError, match="duplicate block_id"):
        RichArticleDocument.model_validate(payload)


def test_duplicate_media_id_rejected() -> None:
    payload = valid_document_payload()
    payload["media"].append({"media_id": "venus-photo", "kind": "video", "uri": "https://example.com/dup.mp4"})
    with pytest.raises(ValidationError, match="duplicate media_id"):
        RichArticleDocument.model_validate(payload)


def test_dangling_media_reference_rejected() -> None:
    payload = valid_document_payload()
    payload["blocks"][-4]["media_id"] = "missing-media"
    with pytest.raises(ValidationError, match="unknown media_id"):
        RichArticleDocument.model_validate(payload)


def test_unreferenced_media_library_entry_rejected() -> None:
    payload = valid_document_payload()
    payload["media"].append({"media_id": "unused-media", "kind": "photo", "uri": "https://example.com/unused.jpg"})
    with pytest.raises(ValidationError, match="never referenced"):
        RichArticleDocument.model_validate(payload)


def test_empty_text_blocks_rejected() -> None:
    payload = valid_document_payload()
    payload["blocks"][1]["text"] = "   "
    with pytest.raises(ValidationError, match="must contain visible text"):
        RichArticleDocument.model_validate(payload)

    empty_credit = valid_document_payload()
    empty_credit["blocks"][9]["credit"] = "   "
    with pytest.raises(ValidationError, match="credit must contain visible text"):
        RichArticleDocument.model_validate(empty_credit)


def test_empty_structural_blocks_rejected() -> None:
    no_items = valid_document_payload()
    no_items["blocks"].append({"type": "list", "block_id": "list-empty", "items": []})
    with pytest.raises(ValidationError, match="at least 1"):
        RichArticleDocument.model_validate(no_items)

    no_children = valid_document_payload()
    no_children["blocks"].append({"type": "details", "block_id": "details-empty", "summary": "заголовок", "blocks": []})
    with pytest.raises(ValidationError, match="at least 1"):
        RichArticleDocument.model_validate(no_children)

    no_rows = valid_document_payload()
    no_rows["blocks"].append({"type": "table", "block_id": "table-empty", "cells": []})
    with pytest.raises(ValidationError, match="at least 1"):
        RichArticleDocument.model_validate(no_rows)

    invisible_row = valid_document_payload()
    invisible_row["blocks"][10]["cells"].append([{"text": None}])
    with pytest.raises(ValidationError, match="no visible cells"):
        RichArticleDocument.model_validate(invisible_row)


def test_document_requires_at_least_one_block() -> None:
    payload = valid_document_payload()
    payload["blocks"] = []
    with pytest.raises(ValidationError, match="at least 1"):
        RichArticleDocument.model_validate(payload)


def test_list_item_option_constraints() -> None:
    checked_without_checkbox = valid_document_payload()
    checked_without_checkbox["blocks"][6]["items"][0]["is_checked"] = True
    checked_without_checkbox["blocks"][6]["items"][0]["has_checkbox"] = False
    with pytest.raises(ValidationError, match="is_checked requires has_checkbox"):
        RichArticleDocument.model_validate(checked_without_checkbox)

    value_without_type = valid_document_payload()
    value_without_type["blocks"][7]["items"][0]["value"] = 7
    value_without_type["blocks"][7]["items"][0]["label_type"] = None
    with pytest.raises(ValidationError, match="value requires an ordered label_type"):
        RichArticleDocument.model_validate(value_without_type)


def test_inline_formatting_nests_like_official_rich_text() -> None:
    payload = valid_document_payload()
    payload["blocks"].append(
        {
            "type": "paragraph",
            "block_id": "p-deep",
            "text": {
                "type": "bold",
                "text": {
                    "type": "italic",
                    "text": {"type": "url", "text": "ссылка", "url": "https://example.com"},
                },
            },
        }
    )
    document = RichArticleDocument.model_validate(payload)
    all_blocks = list(iter_blocks(document.blocks))
    assert any(block.block_id == "p-deep" for block in all_blocks)


def test_metadata_constraints() -> None:
    bad_tags = valid_document_payload()
    bad_tags["metadata"]["tags"] = ["наука", "наука"]
    with pytest.raises(ValidationError, match="tags must be unique"):
        RichArticleDocument.model_validate(bad_tags)

    bad_dates = valid_document_payload()
    bad_dates["metadata"]["updated_at"] = "2026-08-01"
    bad_dates["metadata"]["created_at"] = "2026-08-10"
    with pytest.raises(ValidationError, match="updated_at cannot precede created_at"):
        RichArticleDocument.model_validate(bad_dates)


def test_unknown_fields_are_rejected() -> None:
    payload = valid_document_payload()
    payload["extra_field"] = "surprise"
    with pytest.raises(ValidationError, match="extra_field"):
        RichArticleDocument.model_validate(payload)


def test_canonical_json_helper_is_deterministic() -> None:
    assert canonical_json({"b": 1, "a": [2, 1]}) == canonical_json({"a": [2, 1], "b": 1})
    assert canonical_json({"x": None}) == canonical_json({})
    assert date(2026, 8, 10).isoformat() == "2026-08-10"
