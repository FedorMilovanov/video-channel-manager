"""Tests for the rich article validation module (limits + plain-text projection)."""

from __future__ import annotations

import pytest

from telegram_rich_fixtures import ALL_RENDER_SCENARIOS, scientific_article
from video_channel_manager.telegram_rich_models import (
    RichArticleDocument,
    RichBlockParagraph,
    RichBlockTable,
    RichTableCell,
)
from video_channel_manager.telegram_rich_validation import (
    MAX_RICH_BLOCKS,
    MAX_RICH_MEDIA_ATTACHMENTS,
    MAX_RICH_NESTING_DEPTH,
    MAX_RICH_TEXT_UTF8_CHARS,
    count_blocks,
    count_media_attachments,
    document_text_length,
    max_block_nesting_depth,
    max_inline_nesting_depth,
    plain_text,
    plain_text_sha256,
    validate_document,
)


def test_all_fixture_documents_pass_validation() -> None:
    for _name, document in ALL_RENDER_SCENARIOS:
        validate_document(document)
        assert document_text_length(document) <= MAX_RICH_TEXT_UTF8_CHARS
        assert count_blocks(document) <= MAX_RICH_BLOCKS
        assert max_block_nesting_depth(document) <= MAX_RICH_NESTING_DEPTH
        assert max_inline_nesting_depth(document) <= MAX_RICH_NESTING_DEPTH
        assert count_media_attachments(document) <= MAX_RICH_MEDIA_ATTACHMENTS


def test_plain_text_projection_is_deterministic_and_stable() -> None:
    for _name, document in ALL_RENDER_SCENARIOS:
        assert plain_text(document) == plain_text(document)
        assert plain_text_sha256(document) == plain_text_sha256(document)
        assert plain_text(document)  # non-empty


def test_plain_text_preserves_every_text_fragment_in_order() -> None:
    from video_channel_manager.telegram_rich_models import iter_blocks, iter_text_fragments

    document = scientific_article()
    text = plain_text(document)
    fragments: list[str] = []
    for block in iter_blocks(document.blocks):
        if block.type in ("paragraph", "heading", "pre", "footer", "pullquote"):
            fragments.append(block.text)
        elif block.type == "mathematical_expression":
            fragments.append(block.expression)
        elif block.type == "blockquote":
            if block.credit is not None:
                fragments.append(block.credit)
            for child in block.blocks:
                if child.type in ("paragraph", "heading", "pre", "footer", "pullquote"):
                    fragments.append(child.text)
        elif block.type == "table":
            if block.caption is not None:
                fragments.append(block.caption)
            for row in block.cells:
                for cell in row:
                    if cell.text is not None:
                        fragments.append(cell.text)
        elif block.type == "details":
            fragments.append(block.summary)
        elif block.type == "list":
            for item in block.items:
                for child in item.blocks:
                    fragments.append(child.text)
    for fragment in fragments:
        for piece in iter_text_fragments(fragment):
            stripped = piece.strip()
            if not stripped:
                continue
            assert stripped in text, f"fragment {stripped!r} missing from projection"


def test_empty_structural_blocks_are_rejected() -> None:
    from pydantic import ValidationError

    from video_channel_manager.telegram_rich_models import RichArticleDocument, RichArticleMetadata

    with pytest.raises(ValidationError, match="must contain visible text"):
        RichArticleDocument(
            schema_name="video-channel-manager.rich-article-document",
            schema_version=1,
            document_id="empty-block-doc-0001",
            project_key="svodka",
            metadata=RichArticleMetadata(
                title="Пусто", language="ru", created_at=__import__("datetime").date(2026, 8, 10)
            ),
            blocks=(RichBlockParagraph(block_id="p-empty", text="   "),),
        )
    with pytest.raises(ValidationError, match="no visible cells"):
        RichArticleDocument(
            schema_name="video-channel-manager.rich-article-document",
            schema_version=1,
            document_id="empty-table-doc-001",
            project_key="svodka",
            metadata=RichArticleMetadata(
                title="Пусто", language="ru", created_at=__import__("datetime").date(2026, 8, 10)
            ),
            blocks=(RichBlockTable(block_id="t-empty", cells=((RichTableCell(text=""),),)),),
        )


def test_dangling_media_refs_are_rejected() -> None:
    from datetime import date

    from pydantic import ValidationError

    from video_channel_manager.telegram_rich_models import (
        RichArticleDocument,
        RichArticleMetadata,
        RichBlockMedia,
    )

    with pytest.raises(ValidationError, match="unknown media_id"):
        RichArticleDocument(
            schema_name="video-channel-manager.rich-article-document",
            schema_version=1,
            document_id="dangling-media-doc-01",
            project_key="svodka",
            metadata=RichArticleMetadata(title="Текст", language="ru", created_at=date(2026, 8, 10)),
            blocks=(
                RichBlockParagraph(block_id="p-1", text="текст"),
                RichBlockMedia(block_id="m-1", media_id="missing-media"),
            ),
            media=(),
        )


def test_unreferenced_media_library_is_rejected() -> None:
    from pydantic import ValidationError

    from video_channel_manager.telegram_rich_models import RichMediaItem

    with pytest.raises(ValidationError, match="never referenced"):
        RichArticleDocument(
            schema_name="video-channel-manager.rich-article-document",
            schema_version=1,
            document_id="unreferenced-media-doc-01",
            project_key="svodka",
            metadata=scientific_article().metadata,
            blocks=(RichBlockParagraph(block_id="p-1", text="текст"),),
            media=(RichMediaItem(media_id="orphan", kind="photo", uri="https://example.org/x.jpg"),),
        )


def test_nesting_depth_limit_is_enforced_by_validation_module() -> None:
    # build an artificial deeply nested details chain and assert the counter works
    from video_channel_manager.telegram_rich_models import RichBlockDetails

    inner: object = RichBlockParagraph(block_id="deep-p", text="дно")
    for index in range(8):
        inner = RichBlockDetails(
            block_id=f"deep-{index}",
            summary=f"Уровень {index}",
            blocks=(inner,),  # type: ignore[arg-type]
        )
    document = scientific_article().model_copy(
        update={
            "blocks": (
                RichBlockParagraph(block_id="p-root", text="корень"),
                inner,  # type: ignore[arg-type]
            )
        }
    )
    assert max_block_nesting_depth(document) == 9
    validate_document(document)
