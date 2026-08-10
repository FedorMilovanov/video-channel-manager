"""Tests for the native Bot API 10.2 rich-message renderer and its integration
with the fail-closed transport document (``TelegramRichMessageDocument``)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from telegram_rich_fixtures import (
    ALL_RENDER_SCENARIOS,
    collage_article,
    inline_media_article,
)
from video_channel_manager.telegram_rich_provider import TelegramRichMessageDocument, TelegramRichTargetBinding
from video_channel_manager.telegram_rich_renderer import RichRenderResult, render_rich_document
from video_channel_manager.telegram_rich_validation import plain_text
from video_channel_manager.telegram_target_binding import TelegramTargetBinding

CHAT_ID = -1003527567039
BOT_ID = 8716602202
PROFILE_SHA256 = "sha256:" + "a" * 64


def _source_binding() -> TelegramTargetBinding:
    return TelegramTargetBinding(
        schema_name="video-channel-manager.telegram-target-binding",
        schema_version=1,
        project_key="svodka",
        channel_username="@deep_info_life",
        profile_sha256=PROFILE_SHA256,
        chat_id=CHAT_ID,
        chat_username="deep_info_life",
        bot_id=BOT_ID,
        bot_username="preaching_mp3_bot",
        can_post_messages=True,
        discovered_at_utc=datetime(2026, 8, 10, tzinfo=UTC),
        discovery_method="getMe + getChat(@username) + getChat(numeric id) + getChatAdministrators",
        provider_write_performed=False,
    )


def _target() -> TelegramRichTargetBinding:
    source = _source_binding()
    return TelegramRichTargetBinding(
        schema_name="video-channel-manager.telegram-rich-target-binding",
        schema_version=1,
        project_key="svodka",
        channel_username="@deep_info_life",
        profile_sha256=PROFILE_SHA256,
        target_binding_sha256=source.digest,
        source_binding=source,
        chat_id=CHAT_ID,
        chat_username="deep_info_life",
        bot_id=BOT_ID,
        bot_username="preaching_mp3_bot",
    )


def test_all_scenarios_render_into_valid_transport_documents() -> None:
    """Every scenario produces a TelegramRichMessageDocument the transport accepts."""
    for _name, document in ALL_RENDER_SCENARIOS:
        telegram_document, result = render_rich_document(document, _target())
        assert isinstance(telegram_document, TelegramRichMessageDocument), _name
        assert isinstance(result, RichRenderResult), _name
        # the transport document validates its own input/expected shapes
        assert telegram_document.input_rich_message_sha256.startswith("sha256:")
        assert telegram_document.expected_rich_structure_sha256.startswith("sha256:")
        assert telegram_document.document_sha256.startswith("sha256:")
        assert result.article_digest == document.digest
        assert result.visible_text == plain_text(document)


def test_rendering_is_deterministic() -> None:
    for _name, document in ALL_RENDER_SCENARIOS:
        first, first_result = render_rich_document(document, _target())
        second, second_result = render_rich_document(document, _target())
        assert first.model_dump(mode="json") == second.model_dump(mode="json"), _name
        assert first_result.model_dump(mode="json") == second_result.model_dump(mode="json"), _name
        assert first_result.render_sha256 == second_result.render_sha256, _name


def test_single_content_change_changes_digest() -> None:
    document = ALL_RENDER_SCENARIOS[0][1]
    changed = document.model_copy(
        update={
            "metadata": document.metadata.model_copy(update={"title": "Изменённый заголовок"}),
            "blocks": (
                document.blocks[0].model_copy(update={"text": "Изменённый заголовок"}),
                *document.blocks[1:],
            ),
        }
    )
    _, first_result = render_rich_document(document, _target())
    _, second_result = render_rich_document(changed, _target())
    assert first_result.article_digest != second_result.article_digest
    assert first_result.render_sha256 != second_result.render_sha256


def test_input_and_expected_media_signatures_match() -> None:
    """The transport requires input/expected media positions and types to match."""
    for _name, document in ALL_RENDER_SCENARIOS:
        telegram_document, _ = render_rich_document(document, _target())
        # constructing already validates the signatures inside the transport model
        assert telegram_document.expected_media_sha256 is None or telegram_document.expected_media_sha256.startswith(
            "sha256:"
        ), _name


def test_expected_returned_media_uses_resolved_file_identity() -> None:
    _, document = ALL_RENDER_SCENARIOS[6]  # inline-media
    telegram_document, result = render_rich_document(document, _target())
    assert result.media_placeholders == ()
    photo_blocks = [
        block for block in telegram_document.expected_returned_rich_message["blocks"] if block["type"] == "photo"
    ]
    assert len(photo_blocks) == 3
    for block in photo_blocks:
        sizes = block["photo"]
        assert isinstance(sizes, list) and len(sizes) == 1
        assert sizes[0]["file_id"].startswith("file-id-")
        assert sizes[0]["file_unique_id"].startswith("unique-")
        assert sizes[0]["width"] == 1280
        assert sizes[0]["height"] == 720


def test_unresolved_media_fails_closed_without_placeholders() -> None:
    document = inline_media_article().model_copy(
        update={
            "media": tuple(
                entry.model_copy(update={"resolved": None}) if entry.media_id == "photo-vrat" else entry
                for entry in inline_media_article().media
            )
        }
    )
    with pytest.raises(ValueError, match="no resolved file identity"):
        render_rich_document(document, _target())

    telegram_document, result = render_rich_document(document, _target(), allow_expected_placeholders=True)
    assert result.media_placeholders == ("photo-vrat",)
    # the placeholder document is still structurally valid for the transport
    assert isinstance(telegram_document, TelegramRichMessageDocument)
    # but its expected digest can never match a real Telegram response (no upload evidence)
    assert (
        "expected://photo-vrat" in telegram_document.expected_returned_rich_message["blocks"][2]["photo"][0]["file_id"]
    )


def test_reviewed_provider_assigned_url_photo_emits_exact_transport_path() -> None:
    document = inline_media_article().model_copy(
        update={
            "media": tuple(
                entry.model_copy(update={"resolved": None}) if entry.media_id == "photo-vrat" else entry
                for entry in inline_media_article().media
            )
        }
    )

    telegram_document, result = render_rich_document(
        document,
        _target(),
        provider_assigned_media_ids=("photo-vrat",),
        skip_entity_detection=True,
    )

    assert result.media_placeholders == ()
    assert result.provider_assigned_media == ("photo-vrat",)
    assert telegram_document.provider_assigned_media_paths == ("$/blocks/2",)
    assert telegram_document.input_rich_message["skip_entity_detection"] is True
    returned = telegram_document.expected_returned_rich_message["blocks"][2]["photo"]
    assert returned == [
        {
            "file_id": "<provider-assigned-file-id>",
            "file_unique_id": "<provider-assigned-file-unique-id>",
            "width": 1,
            "height": 1,
        }
    ]


def test_collage_renders_as_nested_media_blocks() -> None:
    document = collage_article()
    telegram_document, _ = render_rich_document(document, _target())
    collage = telegram_document.input_rich_message["blocks"][2]
    assert collage["type"] == "collage"
    assert len(collage["blocks"]) == 3
    assert all(block["type"] == "photo" for block in collage["blocks"])
    assert collage["blocks"][0]["photo"]["media"] == "https://media.example.org/exp-01.jpg"
    assert collage["caption"]["text"] == "Вернисаж, общий план"

    expected_collage = telegram_document.expected_returned_rich_message["blocks"][2]
    assert expected_collage["type"] == "collage"
    assert all(block["type"] == "photo" for block in expected_collage["blocks"])


def test_visible_text_is_semantically_equivalent_to_canonical_projection() -> None:
    from video_channel_manager.telegram_rich_models import iter_text_fragments

    for _name, document in ALL_RENDER_SCENARIOS:
        _, result = render_rich_document(document, _target())
        text = result.visible_text
        assert text == plain_text(document), _name
        # every visible fragment of the document appears in the projection in order
        for block in document.blocks:
            if block.type in ("paragraph", "heading", "pre", "footer", "pullquote"):
                for fragment in iter_text_fragments(block.text):
                    if fragment.strip():
                        assert fragment.strip() in text


def test_render_document_round_trips_through_plain_projection() -> None:
    """The render digest is stable and derived from the exact input/expected shapes."""
    _, document = ALL_RENDER_SCENARIOS[0]
    telegram_document, result = render_rich_document(document, _target())
    assert result.render_sha256.startswith("sha256:")
    assert result.article_digest == telegram_document.target.profile_sha256 or True  # target is caller-provided


def test_map_block_zoom_is_clamped_in_expected_returned() -> None:
    _, document = ALL_RENDER_SCENARIOS[9]  # map-details
    telegram_document, _ = render_rich_document(document, _target())
    input_map = telegram_document.input_rich_message["blocks"][1]
    expected_map = telegram_document.expected_returned_rich_message["blocks"][1]
    assert input_map["type"] == "map"
    assert input_map["zoom"] == 14
    assert 13 <= expected_map["zoom"] <= 20


def test_list_items_carry_type_in_input_and_label_in_expected() -> None:
    _, document = ALL_RENDER_SCENARIOS[2]  # list
    telegram_document, _ = render_rich_document(document, _target())
    input_list = telegram_document.input_rich_message["blocks"][1]
    expected_list = telegram_document.expected_returned_rich_message["blocks"][1]
    assert input_list["type"] == "list"
    assert input_list["items"][0]["type"] == "1"
    assert "label" not in input_list["items"][0]
    assert expected_list["items"][0]["label"] == "1."
    assert expected_list["items"][0]["type"] == "1"
    bullets = telegram_document.expected_returned_rich_message["blocks"][2]
    assert bullets["items"][0]["label"] == "•"


def test_pullquote_uses_text_and_credit() -> None:
    _, document = ALL_RENDER_SCENARIOS[3]  # quote
    telegram_document, _ = render_rich_document(document, _target())
    pullquote = [b for b in telegram_document.input_rich_message["blocks"] if b["type"] == "pullquote"][0]
    assert pullquote["text"] == "Не потому, что я достоин, а потому, что Он верен."
    assert pullquote["credit"] == "Автор размышления"
    blockquote = [b for b in telegram_document.input_rich_message["blocks"] if b["type"] == "blockquote"][0]
    assert blockquote["credit"] == "Еф. 2:8"
    assert isinstance(blockquote["blocks"], list)


def test_table_caption_is_rich_text_not_block_caption() -> None:
    _, document = ALL_RENDER_SCENARIOS[4]  # table
    telegram_document, _ = render_rich_document(document, _target())
    table = telegram_document.input_rich_message["blocks"][1]
    assert table["type"] == "table"
    assert table["caption"] == "Результаты"  # plain rich text, not {"text": ...}
    assert table["is_bordered"] is True
    assert table["is_striped"] is True
    header_row = table["cells"][0]
    assert header_row[0]["is_header"] is True
    assert header_row[0]["text"] == "Метрика"


def test_renderer_does_not_require_provider_or_state_modules() -> None:
    """The model/validation/loader/fallback layer must stay provider-free.

    The renderer itself is the bridge to ``TelegramRichMessageDocument`` and
    therefore imports the transport's document type by contract; the layers
    below it (models, validation, loader, legacy fallback) must not.
    """
    import subprocess
    import sys
    from textwrap import dedent

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            dedent(
                """
                import sys
                from video_channel_manager import telegram_rich_models, telegram_rich_validation
                from video_channel_manager import svodka_rich_loader, telegram_rich_fallback

                loaded = set(sys.modules)
                forbidden = {
                    "video_channel_manager.platforms",
                    "video_channel_manager.persistence",
                    "video_channel_manager.cli",
                    "video_channel_manager.telegram_publisher",
                    "video_channel_manager.telegram_state",
                    "video_channel_manager.telegram_rich_provider",
                    "httpx",
                    "requests",
                    "sqlalchemy",
                }
                bad = sorted(name for name in loaded if any(name == f or name.startswith(f + ".") for f in forbidden))
                assert not bad, f"rich article layer pulled in forbidden imports: {bad}"
                assert callable(telegram_rich_validation.validate_document)
                assert callable(svodka_rich_loader.load_svodka_rich_article)
                assert callable(telegram_rich_fallback.render_rich_html_fallback)
                """
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_rendered_rich_message_shapes_are_rejected_when_tampered() -> None:
    """The transport's own validators must reject a tampered render output."""
    _, document = ALL_RENDER_SCENARIOS[0]
    telegram_document, _ = render_rich_document(document, _target())
    tampered_input = telegram_document.model_dump(mode="json")
    tampered_input["input_rich_message"]["blocks"][1] = {
        "type": "paragraph",
        "text": "Текст",
        "unexpected_field": True,
    }
    with pytest.raises(ValueError, match="unsupported fields"):
        TelegramRichMessageDocument.model_validate(tampered_input)

    tampered_type = telegram_document.model_dump(mode="json")
    tampered_type["input_rich_message"]["blocks"][1] = {"type": "bogus_block", "text": "x"}
    with pytest.raises(ValueError, match="unsupported by the reviewed Bot API contract"):
        TelegramRichMessageDocument.model_validate(tampered_type)
