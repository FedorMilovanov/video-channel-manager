from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_rich_models import (
    RichArticleDocument,
    RichBlockCaption,
    RichBlockMedia,
    RichMediaItem,
)
from video_channel_manager.telegram_rich_provider import (
    TelegramRichMessageDocument,
    TelegramRichTargetBinding,
)
from video_channel_manager.telegram_rich_renderer import RichRenderResult, render_rich_document
from video_channel_manager.telegram_target_binding import load_target_binding

REGISTRY_SCHEMA = "video-channel-manager.lordchrist-rich-v1-media-registry"
PROJECT_KEY = "lord-god-strength"
CHANNEL_USERNAME = "@lordchrist"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON record is not an object: {path}")
    return value


def _load_article(path: Path) -> RichArticleDocument:
    article = RichArticleDocument.model_validate(_read_json(path))
    if article.project_key != PROJECT_KEY or article.document_id not in {
        "lordchrist-rich-sermons-survive-century",
        "lordchrist-rich-three-expository-patterns",
    }:
        raise ValueError("article is outside the reviewed LordChrist rich successor set")
    if article.media:
        raise ValueError("reviewed editorial article must remain provider-neutral before media binding")
    if len(article.media_slots) != 3:
        raise ValueError("reviewed LordChrist rich article must contain exactly three media slots")
    return article


def _registry_assets(path: Path, article: RichArticleDocument) -> dict[str, dict[str, Any]]:
    registry = _read_json(path)
    if (
        registry.get("schema_name") != REGISTRY_SCHEMA
        or registry.get("schema_version") != 1
        or registry.get("project_key") != PROJECT_KEY
        or registry.get("revision") != "rich-v1"
        or registry.get("provider_writes_authorized") is not False
        or registry.get("provider_upload_status") != "not_uploaded"
    ):
        raise ValueError("invalid LordChrist rich media registry header")

    assets_raw = registry.get("assets")
    if not isinstance(assets_raw, list):
        raise ValueError("LordChrist rich media registry has no assets")
    assets = [
        asset
        for asset in assets_raw
        if isinstance(asset, dict) and asset.get("article_id") == article.document_id
    ]
    slots = {slot.slot_id for slot in article.media_slots}
    if len(assets) != len(slots):
        raise ValueError("LordChrist rich article does not have one exact asset per media slot")

    by_slot: dict[str, dict[str, Any]] = {}
    for asset in assets:
        slot_id = str(asset.get("media_slot_id") or "")
        if slot_id not in slots or slot_id in by_slot:
            raise ValueError("LordChrist rich media registry has duplicate or unknown media slot")
        if (
            asset.get("kind") != "photo"
            or asset.get("expected_mime") != "image/jpeg"
            or asset.get("remote_ready") is not True
            or asset.get("acquisition_status") != "source_and_license_reviewed"
            or asset.get("provider_upload_status") != "not_uploaded"
            or asset.get("content_checksum") is not None
        ):
            raise ValueError("LordChrist rich asset is not in the reviewed provider-inert acquisition state")
        direct_url = asset.get("direct_media_url")
        source_url = asset.get("canonical_source_page_url")
        if not isinstance(direct_url, str) or not direct_url.startswith("https://upload.wikimedia.org/"):
            raise ValueError("LordChrist rich media URL is not an exact reviewed Wikimedia HTTPS asset")
        if not isinstance(source_url, str) or not source_url.startswith(
            "https://commons.wikimedia.org/wiki/File:"
        ):
            raise ValueError("LordChrist rich media provenance page is not an exact Wikimedia Commons file page")
        if not str(asset.get("caption") or "").strip() or not str(asset.get("depicts") or "").strip():
            raise ValueError("LordChrist rich media asset lacks caption or alt-text provenance")
        by_slot[slot_id] = cast(dict[str, Any], asset)
    return by_slot


def _section_anchor_index(article: RichArticleDocument, section_key: str) -> int:
    prefix = f"b-{section_key}-"
    indexes = [index for index, block in enumerate(article.blocks) if block.block_id.startswith(prefix)]
    if not indexes:
        raise ValueError(f"LordChrist rich media placement has no section body anchor: {section_key}")
    return indexes[-1]


def bind_reviewed_media(article_path: Path, registry_path: Path) -> RichArticleDocument:
    article = _load_article(article_path)
    assets = _registry_assets(registry_path, article)

    media: list[RichMediaItem] = []
    insertions: dict[int, list[RichBlockMedia]] = {}
    for slot in article.media_slots:
        placement_after = slot.placement.get("after")
        if not placement_after:
            raise ValueError(f"LordChrist rich media slot has no reviewed after-placement: {slot.slot_id}")
        asset = assets[slot.slot_id]
        media.append(
            RichMediaItem(
                media_id=slot.slot_id,
                kind="photo",
                uri=str(asset["direct_media_url"]),
                alt_text=str(asset["depicts"]),
            )
        )
        anchor_index = _section_anchor_index(article, placement_after)
        insertions.setdefault(anchor_index, []).append(
            RichBlockMedia(
                block_id=f"media-{slot.slot_id}",
                media_id=slot.slot_id,
                caption=RichBlockCaption(text=str(asset["caption"])),
            )
        )

    blocks: list[Any] = []
    for index, block in enumerate(article.blocks):
        blocks.append(block)
        blocks.extend(insertions.get(index, ()))
    return article.model_copy(update={"blocks": tuple(blocks), "media": tuple(media)})


def build_provider_free_document(
    article_path: Path,
    registry_path: Path,
    profile_path: Path,
    binding_path: Path,
) -> tuple[TelegramRichMessageDocument, RichRenderResult, RichArticleDocument]:
    article = bind_reviewed_media(article_path, registry_path)
    profile = load_channel_profile(profile_path)
    binding = load_target_binding(binding_path, profile)
    if profile.project_key != PROJECT_KEY or profile.channel_username.casefold() != CHANNEL_USERNAME.casefold():
        raise ValueError("LordChrist rich profile differs from reviewed project/channel")
    if not profile.provider_writes_authorized:
        raise ValueError("LordChrist rich profile provider-write gate is disabled")

    target = TelegramRichTargetBinding(
        schema_name="video-channel-manager.telegram-rich-target-binding",
        schema_version=1,
        project_key=PROJECT_KEY,
        channel_username=CHANNEL_USERNAME,
        profile_sha256=profile.digest,
        target_binding_sha256=binding.digest,
        source_binding=binding,
        chat_id=binding.chat_id,
        chat_username=binding.chat_username,
        bot_id=binding.bot_id,
        bot_username=binding.bot_username,
    )
    document, render = render_rich_document(
        article,
        target,
        publication_id=article.document_id,
        provider_assigned_media_ids=tuple(item.media_id for item in article.media),
        skip_entity_detection=False,
    )
    return document, render, article


__all__ = ["bind_reviewed_media", "build_provider_free_document"]
