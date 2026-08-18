from __future__ import annotations

from pathlib import Path

from video_channel_manager.lordchrist_rich_successor import bind_reviewed_media, build_provider_free_document

REGISTRY = Path("content/telegram/lordchrist/rich-v1/media/media-registry.json")
PROFILE = Path("content/telegram/channels/lordchrist-rich.json")
BINDING = Path("content/telegram/channels/lordchrist-rich-target-binding.json")
ARTICLES = Path("content/telegram/lordchrist/rich-v1/articles")
MODULE = Path("src/video_channel_manager/lordchrist_rich_successor.py")


def _block_ids(article: object) -> list[str]:
    return [block.block_id for block in article.blocks]  # type: ignore[attr-defined]


def test_sermons_article_binds_three_documentary_photos_after_reviewed_sections() -> None:
    article = bind_reviewed_media(ARTICLES / "lordchrist-rich-sermons-survive-century.json", REGISTRY)
    assert [item.media_id for item in article.media] == ["media-calvin", "media-spurgeon", "media-tape"]
    assert all(item.kind == "photo" and item.uri.startswith("https://upload.wikimedia.org/") for item in article.media)

    ids = _block_ids(article)
    assert ids.index("media-media-calvin") == ids.index("b-geneva-2") + 1
    assert ids.index("media-media-spurgeon") == ids.index("b-london-2") + 1
    assert ids.index("media-media-tape") == ids.index("b-california-2") + 1
    assert ids.index("media-media-tape") < ids.index("p-takeaway")


def test_patterns_article_binds_grace_worship_without_macarthur_portrait() -> None:
    article = bind_reviewed_media(ARTICLES / "lordchrist-rich-three-expository-patterns.json", REGISTRY)
    assert [item.media_id for item in article.media] == ["media-calvin", "media-spurgeon", "media-grace"]
    assert "Grace_Community_Church_Worship.jpg" in article.media[-1].uri

    ids = _block_ids(article)
    assert ids.index("media-media-calvin") == ids.index("b-calvin-2") + 1
    assert ids.index("media-media-spurgeon") == ids.index("b-spurgeon-2") + 1
    assert ids.index("media-media-grace") == ids.index("b-macarthur-2") + 1
    assert ids.index("media-media-grace") < ids.index("p-boundary")


def test_provider_free_renderer_builds_exact_target_three_photo_rich_messages() -> None:
    for name in (
        "lordchrist-rich-sermons-survive-century.json",
        "lordchrist-rich-three-expository-patterns.json",
    ):
        document, render, article = build_provider_free_document(ARTICLES / name, REGISTRY, PROFILE, BINDING)
        assert document.publication_id == article.document_id
        assert document.target.channel_username == "@lordchrist"
        assert document.target.chat_id == -1001295216957
        assert document.target.bot_id == 8716602202
        assert document.target.bot_username == "preaching_mp3_bot"
        assert document.legacy_fallback is None
        assert "skip_entity_detection" not in document.input_rich_message
        assert len(document.provider_assigned_media_paths) == 3
        assert len(render.provider_assigned_media) == 3
        assert render.provider_assigned_media == tuple(item.media_id for item in article.media)
        assert sum(block.get("type") == "photo" for block in document.input_rich_message["blocks"]) == 3
        assert sum(block.get("type") == "photo" for block in document.expected_returned_rich_message["blocks"]) == 3


def test_provider_free_module_has_no_mutation_transport_surface() -> None:
    source = MODULE.read_text(encoding="utf-8")
    assert "HttpxTelegramRichMutationProvider" not in source
    assert "publish_rich_once" not in source
    assert "send_rich_message" not in source
    assert "TELEGRAM_BOT_TOKEN" not in source
