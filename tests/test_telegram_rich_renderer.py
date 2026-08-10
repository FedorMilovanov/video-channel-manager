"""Golden/snapshot and invariant tests for the deterministic Telegram rich renderer."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest

from telegram_rich_fixtures import (
    ALL_RICH_SCENARIOS,
    top10_list_article,
)
from video_channel_manager.telegram_models import canonical_json
from video_channel_manager.telegram_rich_models import (
    RICH_ARTICLE_SCHEMA_NAME,
    RICH_ARTICLE_SCHEMA_VERSION,
    RichArticleDocument,
    RichArticleMetadata,
    RichBlockCaption,
    RichBlockCollage,
    RichBlockMath,
    RichBlockMedia,
    RichBlockParagraph,
    RichBlockTable,
    RichMediaRef,
    RichTableCell,
    RichTextBold,
    RichTextCustomEmoji,
    RichTextItalic,
    iter_text_fragments,
)
from video_channel_manager.telegram_rich_renderer import (
    MAX_CAPTION_TEXT,
    MAX_MEDIA_GROUP_ITEMS,
    MAX_MESSAGE_TEXT,
    TelegramRichEntity,
    TelegramRichPlan,
    canonical_article_text,
    compute_rich_payload_sha256,
    extract_visible_text,
    render_rich_article,
    utf16_length,
    validate_message_text,
)
from video_channel_manager.telegram_rich_validation import validate_document

GOLDEN_DIR = Path(__file__).resolve().parent / "golden" / "telegram_rich"


def _golden_path(name: str) -> Path:
    return GOLDEN_DIR / f"{name}.json"


def _load_golden(name: str) -> dict[str, Any]:
    return json.loads(_golden_path(name).read_text(encoding="utf-8"))


def _write_golden(name: str, value: dict[str, Any]) -> None:
    path = _golden_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _check_golden(name: str, plan: TelegramRichPlan) -> None:
    dump = plan.model_dump(mode="json")
    if os.environ.get("UPDATE_GOLDEN") == "1":
        _write_golden(name, dump)
    assert dump == _load_golden(name), f"golden snapshot mismatch: {name}"


def _scenario(name: str) -> tuple[str, RichArticleDocument]:
    for candidate in ALL_RICH_SCENARIOS:
        if candidate[0] == name:
            return candidate
    raise AssertionError(f"unknown scenario: {name}")


def _utf16_slice(text: str, offset: int, length: int) -> str:
    """Slice ``text`` by UTF-16 code unit offsets (Telegram entity semantics)."""
    positions: dict[int, int] = {}
    python_index = 0
    utf16_position = 0
    for char in text:
        positions[utf16_position] = python_index
        python_index += 1
        utf16_position += utf16_length(char)
    positions[utf16_position] = python_index
    return text[positions[offset] : positions[offset + length]]


def test_scenario_golden_snapshots_are_exact() -> None:
    """Every documented scenario renders byte-for-byte like its golden snapshot."""
    for name, document in ALL_RICH_SCENARIOS:
        _check_golden(name, render_rich_article(document))


def test_rendering_is_deterministic_and_visible_text_is_canonical() -> None:
    for name, document in ALL_RICH_SCENARIOS:
        plan = render_rich_article(document)
        again = render_rich_article(document)
        assert plan.model_dump(mode="json") == again.model_dump(mode="json")
        assert canonical_json(plan.model_dump(mode="json")) == canonical_json(again.model_dump(mode="json"))
        assert plan.visible_text == canonical_article_text(document)
        assert extract_visible_text(plan) == plan.visible_text
        assert plan.rich_payload_sha256 == compute_rich_payload_sha256(plan)
        assert plan.article_sha256 == document.digest
        if document.media:
            assert plan.media_bundle_sha256 is not None
            assert plan.media_bundle_sha256.startswith("sha256:")
        else:
            assert plan.media_bundle_sha256 is None
        sequences = [request.sequence for request in plan.requests]
        assert sequences == list(range(1, len(sequences) + 1)), name


def _collect_fragments(blocks: tuple[Any, ...], *, parent: str | None) -> list[str]:
    """Collect every visible text fragment of the document in document order.

    Media captions inside collage blocks are excluded because a classic media
    group renders only the first caption (matching the renderer's deterministic
    downgrade of the remaining captions).
    """
    out: list[str] = []
    for block in blocks:
        block_type = block.type
        if block_type in ("paragraph", "heading", "pre", "footer"):
            out.extend(iter_text_fragments(block.text))
        elif block_type == "pullquote":
            out.extend(iter_text_fragments(block.text))
            if block.credit is not None:
                out.extend(iter_text_fragments(block.credit))
        elif block_type == "media":
            if parent != "collage" and block.caption is not None:
                out.extend(iter_text_fragments(block.caption.text))
                if block.caption.credit is not None:
                    out.extend(iter_text_fragments(block.caption.credit))
        elif block_type == "blockquote":
            out.extend(_collect_fragments(block.blocks, parent="blockquote"))
            if block.credit is not None:
                out.extend(iter_text_fragments(block.credit))
        elif block_type in ("collage", "slideshow"):
            if block.caption is not None:
                out.extend(iter_text_fragments(block.caption.text))
                if block.caption.credit is not None:
                    out.extend(iter_text_fragments(block.caption.credit))
            out.extend(_collect_fragments(block.blocks, parent=block_type))
        elif block_type == "list":
            for item in block.items:
                out.extend(_collect_fragments(item.blocks, parent="list"))
        elif block_type == "table":
            if block.caption is not None:
                out.extend(iter_text_fragments(block.caption))
            for row in block.cells:
                for cell in row:
                    if cell.text is not None:
                        out.extend(iter_text_fragments(cell.text))
        elif block_type == "details":
            out.extend(iter_text_fragments(block.summary))
            out.extend(_collect_fragments(block.blocks, parent="details"))
    return out


def test_visible_text_preserves_every_document_text_fragment_in_order() -> None:
    """Semantic equivalence: every text fragment of the domain document appears
    in the rendered visible text, in document order."""
    for name, document in ALL_RICH_SCENARIOS:
        plan = render_rich_article(document)
        text = plan.visible_text
        fragments = [document.metadata.title, *_collect_fragments(document.blocks, parent=None)]
        cursor = 0
        for fragment in fragments:
            stripped = fragment.strip()
            if not stripped:
                continue
            found = text.find(stripped, cursor)
            assert found != -1, f"{name}: fragment {stripped!r} missing from visible text"
            cursor = found + len(stripped)


def test_every_request_obeys_official_bot_api_limits() -> None:
    for name, document in ALL_RICH_SCENARIOS:
        plan = render_rich_article(document)
        for request in plan.requests:
            if request.method == "sendMessage":
                text = str(request.payload["text"])
                assert len(text) <= MAX_MESSAGE_TEXT, name
                entities = tuple(
                    TelegramRichEntity.model_validate(entity) for entity in request.payload.get("entities", [])
                )
                validate_message_text(text, entities)
            elif request.method in ("sendPhoto", "sendVideo", "sendAnimation", "sendAudio", "sendVoice"):
                caption = request.payload.get("caption")
                if caption is not None:
                    assert len(caption) <= MAX_CAPTION_TEXT, name
                    validate_message_text(str(caption), ())
            elif request.method == "sendMediaGroup":
                media_list = request.payload["media"]
                assert 2 <= len(media_list) <= MAX_MEDIA_GROUP_ITEMS, name
                for index, entry in enumerate(media_list):
                    assert entry["type"] in {"photo", "video", "animation", "audio"}, name
                    if index > 0:
                        assert "caption" not in entry, name


def test_plan_round_trips_through_canonical_json() -> None:
    for name, document in ALL_RICH_SCENARIOS:
        plan = render_rich_article(document)
        restored = TelegramRichPlan.model_validate_json(canonical_json(plan.model_dump(mode="json")))
        assert restored == plan, name


def _utf16_demo_document() -> RichArticleDocument:
    return RichArticleDocument(
        schema_name=RICH_ARTICLE_SCHEMA_NAME,
        schema_version=RICH_ARTICLE_SCHEMA_VERSION,
        document_id="utf16-demo-doc",
        project_key="svodka",
        metadata=RichArticleMetadata(
            title="Эмодзи 🔬 и форматирование",
            language="ru",
            created_at=date(2026, 8, 10),
        ),
        blocks=(
            RichBlockParagraph(
                block_id="p-demo",
                text=(
                    "🔬 Начало с эмодзи, ",
                    RichTextBold(text="потом жирное"),
                    ", затем 🏞️ и ",
                    RichTextItalic(text="курсив"),
                    ".",
                ),
            ),
        ),
    )


def test_utf16_entity_offsets_are_exact_around_emoji() -> None:
    document = _utf16_demo_document()
    plan = render_rich_article(document)
    request = plan.requests[0]
    text = str(request.payload["text"])
    entities = [TelegramRichEntity.model_validate(entity) for entity in request.payload["entities"]]

    title_prefix = "Эмодзи 🔬 и форматирование" + "\n\n"
    bold_prefix = "🔬 Начало с эмодзи, "
    bold = next(entity for entity in entities if _utf16_slice(text, entity.offset, entity.length) == "потом жирное")
    assert bold.offset == utf16_length(title_prefix) + utf16_length(bold_prefix)
    assert bold.length == utf16_length("потом жирное")

    italic_prefix = bold_prefix + "потом жирное, затем 🏞️ и "
    italic = next(entity for entity in entities if _utf16_slice(text, entity.offset, entity.length) == "курсив")
    assert italic.offset == utf16_length(title_prefix) + utf16_length(italic_prefix)
    assert italic.length == utf16_length("курсив")

    boundaries = {0}
    position = 0
    for char in text:
        position += utf16_length(char)
        boundaries.add(position)
    for entity in entities:
        assert entity.offset in boundaries
        assert entity.offset + entity.length in boundaries


def test_utf16_offsets_in_list_items_include_markers() -> None:
    plan = render_rich_article(top10_list_article())
    request = plan.requests[0]
    text = str(request.payload["text"])
    entities = [TelegramRichEntity.model_validate(entity) for entity in request.payload["entities"]]
    lines = text.split("\n")
    assert any(line.startswith("1. ") for line in lines)

    bold_entity = next(
        entity for entity in entities if _utf16_slice(text, entity.offset, entity.length) == "Дело Христа"
    )
    item_index = next(index for index, line in enumerate(lines) if line.startswith("5. Ли Строубел"))
    prefix = "5. Ли Строубел — «"
    expected_offset = utf16_length("\n".join(lines[:item_index])) + 1 + utf16_length(prefix)
    assert bold_entity.offset == expected_offset
    assert bold_entity.length == utf16_length("Дело Христа")
    assert _utf16_slice(text, bold_entity.offset, bold_entity.length) == "Дело Христа"


def test_standalone_media_blocks_produce_interleaved_media_messages() -> None:
    _, document = _scenario("inline-images")
    plan = render_rich_article(document)
    methods = [request.method for request in plan.requests]
    assert methods == [
        "sendMessage",
        "sendPhoto",
        "sendMessage",
        "sendPhoto",
        "sendMessage",
        "sendPhoto",
        "sendMessage",
    ]
    photos = [request for request in plan.requests if request.method == "sendPhoto"]
    media_by_id = {entry.media_id: entry for entry in document.media}
    block_order = ["photo-vrat", "photo-khram", "photo-skit"]
    assert [photo.payload["photo"] for photo in photos] == [media_by_id[logical_id].uri for logical_id in block_order]
    assert photos[0].payload["caption"] == "Врата обители, 6:40 утра"
    assert photos[1].payload["caption"] == "Иконостас главного храма"
    assert "caption" not in photos[2].payload


def test_collage_produces_a_single_media_group_with_first_caption() -> None:
    _, document = _scenario("collage")
    plan = render_rich_article(document)
    groups = [request for request in plan.requests if request.method == "sendMediaGroup"]
    assert len(groups) == 1
    group = groups[0]
    media_by_id = {entry.media_id: entry for entry in document.media}
    assert len(group.payload["media"]) == len(document.media)
    assert group.payload["media"][0]["caption"] == "Вернисаж, общий план"
    assert all("caption" not in entry for entry in group.payload["media"][1:])
    assert [entry["media"] for entry in group.payload["media"]] == [
        media_by_id[logical_id].uri for logical_id in ("exp-01", "exp-02", "exp-03", "exp-04")
    ]


def test_slideshow_produces_one_media_message_per_item() -> None:
    _, document = _scenario("slideshow")
    plan = render_rich_article(document)
    photos = [request for request in plan.requests if request.method == "sendPhoto"]
    assert len(photos) == len(document.media)
    expected_captions = [
        "Ладожские шхеры на рассвете",
        "Водопад Кивач",
        "Озеро с каменным островом",
        "Закат над лесом",
    ]
    assert [photo.payload["caption"] for photo in photos] == expected_captions


def _small_document(
    blocks: tuple[object, ...],
    media: tuple[RichMediaRef, ...] = (),
    title: str = "Документ",
) -> RichArticleDocument:
    return RichArticleDocument(
        schema_name=RICH_ARTICLE_SCHEMA_NAME,
        schema_version=RICH_ARTICLE_SCHEMA_VERSION,
        document_id="small-test-doc-01",
        project_key="svodka",
        metadata=RichArticleMetadata(title=title, language="ru", created_at=date(2026, 8, 10)),
        blocks=tuple(block for block in blocks if block is not None),
        media=media,
    )


def test_single_item_collage_downgrades_to_a_media_message() -> None:
    document = _small_document(
        blocks=(
            RichBlockParagraph(block_id="p-1", text="Один кадр."),
            RichBlockCollage(
                block_id="c-1",
                blocks=(RichBlockMedia(block_id="c-1-m", media_id="only-photo"),),
                caption=RichBlockCaption(text="Один кадр"),
            ),
        ),
        media=(RichMediaRef(media_id="only-photo", kind="photo", uri="https://media.example.org/only.jpg"),),
    )
    plan = render_rich_article(document)
    assert [request.method for request in plan.requests] == ["sendMessage", "sendPhoto"]
    assert plan.downgrades == ("collage:c-1-m:single_item:sendPhoto",)
    assert plan.visible_text == canonical_article_text(document)


def test_collage_exceeding_classic_ten_items_fails_closed() -> None:
    media = tuple(
        RichMediaRef(media_id=f"img-{index}", kind="photo", uri=f"https://media.example.org/{index}.jpg")
        for index in range(1, 12)
    )
    document = _small_document(
        blocks=(
            RichBlockCollage(
                block_id="c-big",
                blocks=tuple(
                    RichBlockMedia(block_id=f"c-m-{index}", media_id=f"img-{index}") for index in range(1, 12)
                ),
            ),
        ),
        media=media,
    )
    with pytest.raises(ValueError, match="limit of 10 items"):
        render_rich_article(document)


def test_voice_note_in_collage_fails_closed() -> None:
    document = _small_document(
        blocks=(
            RichBlockCollage(
                block_id="c-voice",
                blocks=(
                    RichBlockMedia(block_id="c-v-1", media_id="img-1"),
                    RichBlockMedia(block_id="c-v-2", media_id="voice-1"),
                ),
            ),
        ),
        media=(
            RichMediaRef(media_id="img-1", kind="photo", uri="https://media.example.org/1.jpg"),
            RichMediaRef(media_id="voice-1", kind="voice_note", uri="https://media.example.org/voice.ogg"),
        ),
    )
    with pytest.raises(ValueError, match="voice notes cannot be sent in a classic sendMediaGroup collage"):
        render_rich_article(document)


def test_unsupported_features_downgrade_without_losing_text() -> None:
    document = _small_document(
        blocks=(
            RichBlockParagraph(
                block_id="p-1",
                text=(
                    "Формула ",
                    RichTextCustomEmoji(custom_emoji_id="5368324170671202286", alternative_text="👍"),
                    " и ",
                    {"type": "mathematical_expression", "expression": "E = mc^2"},
                    ".",
                ),
            ),
            RichBlockMath(block_id="m-1", expression="a^2 + b^2 = c^2"),
            RichBlockTable(
                block_id="t-1",
                caption="Данные",
                cells=(
                    (RichTableCell(text="A"), RichTableCell(text="B")),
                    (RichTableCell(text="1"), RichTableCell(text=(RichTextBold(text="2"),))),
                ),
            ),
        ),
    )
    plan = render_rich_article(document)
    assert plan.downgrades == (
        "custom_emoji:5368324170671202286:unicode_fallback",
        "formula:plain_text",
        "table:t-1:plain_text",
    )
    assert plan.visible_text == canonical_article_text(document)
    assert "👍" in plan.visible_text
    assert "E = mc^2" in plan.visible_text
    assert "$$a^2 + b^2 = c^2$$" in plan.visible_text
    assert "| A | B |" in plan.visible_text
    for request in plan.requests:
        for entity in request.payload.get("entities", []):
            assert entity["type"] != "custom_emoji"


def test_media_uri_is_used_verbatim_and_media_bundle_digest_is_stable() -> None:
    _, document = _scenario("inline-images")
    plan = render_rich_article(document)
    assert plan.media_bundle_sha256 is not None
    again = render_rich_article(document)
    assert plan.media_bundle_sha256 == again.media_bundle_sha256
    photos = [request for request in plan.requests if request.method == "sendPhoto"]
    assert photos[0].payload["photo"] == "https://media.example.org/photo-vrat.jpg"


def test_renderer_modules_are_http_free() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            dedent("""
            import sys
            from video_channel_manager.telegram_rich_models import RichArticleDocument
            from video_channel_manager.telegram_rich_renderer import render_rich_article
            from video_channel_manager.telegram_rich_fallback import render_html_fallback
            from video_channel_manager.telegram_rich_validation import validate_document

            assert "httpx" not in sys.modules
            assert "requests" not in sys.modules
            assert callable(render_rich_article)
            assert callable(render_html_fallback)
            assert callable(validate_document)
            assert RichArticleDocument.__name__ == "RichArticleDocument"
        """),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    source_root = Path(__file__).resolve().parents[1] / "src" / "video_channel_manager"
    for filename in (
        "telegram_rich_models.py",
        "telegram_rich_renderer.py",
        "telegram_rich_fallback.py",
        "telegram_rich_validation.py",
    ):
        source = (source_root / filename).read_text(encoding="utf-8")
        assert "import httpx" not in source, filename
        assert "import requests" not in source, filename
        assert "import aiohttp" not in source, filename


def test_document_passes_official_limits_before_rendering() -> None:
    for _name, document in ALL_RICH_SCENARIOS:
        validate_document(document)  # must not raise
        assert document.canonical_json  # deterministic serialization is available
