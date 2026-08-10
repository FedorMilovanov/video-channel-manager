"""End-to-end integration: Svodka rich-v1 editorial JSON → native rich document.

Every rich-v1 article must load, validate, render into a
``TelegramRichMessageDocument`` the fail-closed transport accepts, and produce
a deterministic legacy HTML fallback — with no media assets (the revision
commits none) and with the manifest mapping intact.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from video_channel_manager.svodka_rich_loader import (
    SVODKA_RICH_ARTICLES_DIR,
    SVODKA_RICH_MANIFEST_PATH,
    iter_svodka_rich_articles,
    load_svodka_rich_manifest,
    svodka_rich_manifest_mappings,
)
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_rich_fallback import render_rich_html_fallback
from video_channel_manager.telegram_rich_models import RichArticleDocument
from video_channel_manager.telegram_rich_provider import (
    TelegramRichMessageDocument,
    TelegramRichTargetBinding,
)
from video_channel_manager.telegram_rich_renderer import render_rich_document
from video_channel_manager.telegram_target_binding import load_target_binding

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "content/telegram/channels/svodka.json"
TARGET_BINDING_PATH = ROOT / "content/telegram/channels/svodka-target-binding.json"


def _rich_target() -> TelegramRichTargetBinding:
    profile = load_channel_profile(PROFILE_PATH)
    source = load_target_binding(TARGET_BINDING_PATH, profile)
    return TelegramRichTargetBinding(
        schema_name="video-channel-manager.telegram-rich-target-binding",
        schema_version=1,
        project_key=profile.project_key,
        channel_username=profile.channel_username,
        profile_sha256=profile.digest,
        target_binding_sha256=source.digest,
        source_binding=source,
        chat_id=source.chat_id,
        chat_username=source.chat_username,
        bot_id=source.bot_id,
        bot_username=source.bot_username,
    )


def test_all_rich_v1_articles_render_into_transport_documents() -> None:
    target = _rich_target()
    articles = list(iter_svodka_rich_articles(ROOT / SVODKA_RICH_ARTICLES_DIR))
    assert len(articles) == 14
    for _path, document in articles:
        assert isinstance(document, RichArticleDocument)
        assert document.media == ()  # this revision commits no media assets
        telegram_document, result = render_rich_document(document, target)
        assert isinstance(telegram_document, TelegramRichMessageDocument)
        assert telegram_document.publication_id == document.document_id
        assert telegram_document.target.chat_id == target.chat_id
        assert telegram_document.target.bot_username == "preaching_mp3_bot"
        # no media -> exact verification is structurally possible
        assert telegram_document.expected_media_sha256 is None
        assert result.media_placeholders == ()
        assert result.article_digest == document.digest
        # the legacy fallback is deterministic and consistent
        fallback = render_rich_html_fallback(document)
        assert fallback.article_digest == document.digest
        assert fallback.publication_id == document.document_id


def test_rich_v1_manifest_mapping_is_consistent() -> None:
    manifest = load_svodka_rich_manifest(ROOT / SVODKA_RICH_MANIFEST_PATH)
    mappings = svodka_rich_manifest_mappings(manifest)
    article_ids = {document.document_id for _, document in iter_svodka_rich_articles(ROOT / SVODKA_RICH_ARTICLES_DIR)}
    assert set(mappings.values()) == article_ids
    assert len(mappings) == 14
    assert all(old.startswith("svodka-") and not old.startswith("svodka-rich-") for old in mappings)
    assert all(new.startswith("svodka-rich-") for new in mappings.values())


def test_render_digests_are_stable_across_runs() -> None:
    target = _rich_target()
    render_digests: dict[str, str] = {}
    for _path, document in iter_svodka_rich_articles(ROOT / SVODKA_RICH_ARTICLES_DIR):
        _, result = render_rich_document(document, target)
        render_digests[document.document_id] = result.render_sha256
    # second pass yields identical digests
    for _path, document in iter_svodka_rich_articles(ROOT / SVODKA_RICH_ARTICLES_DIR):
        _, result = render_rich_document(document, target)
        assert result.render_sha256 == render_digests[document.document_id]


def test_binding_requires_readonly_source_proof() -> None:
    """The rich target binding must come from a verified read-only source binding."""
    from pydantic import ValidationError

    profile = load_channel_profile(PROFILE_PATH)
    source = load_target_binding(TARGET_BINDING_PATH, profile)
    forged = source.model_copy(update={"provider_write_performed": True})
    with pytest.raises(ValidationError, match="digest differs"):
        TelegramRichTargetBinding(
            schema_name="video-channel-manager.telegram-rich-target-binding",
            schema_version=1,
            project_key=profile.project_key,
            channel_username=profile.channel_username,
            profile_sha256=profile.digest,
            target_binding_sha256=source.digest,
            source_binding=forged,
            chat_id=source.chat_id,
            chat_username=source.chat_username,
            bot_id=source.bot_id,
            bot_username=source.bot_username,
        )
