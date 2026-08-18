from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_target_binding import load_target_binding

REGISTRY_PATH = Path("content/telegram/lordchrist/rich-v1/media/media-registry.json")
ARTICLE_DIR = Path("content/telegram/lordchrist/rich-v1/articles")
RICH_PROFILE_PATH = Path("content/telegram/channels/lordchrist-rich.json")
RICH_BINDING_PATH = Path("content/telegram/channels/lordchrist-rich-target-binding.json")
LEGACY_BINDING_PATH = Path("content/telegram/channels/lordchrist-target-binding.json")
ARTICLE_IDS = (
    "lordchrist-rich-sermons-survive-century",
    "lordchrist-rich-three-expository-patterns",
)


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_lordchrist_rich_media_registry_is_provider_inert_and_provenance_complete() -> None:
    registry = _read(REGISTRY_PATH)
    assert registry["schema_name"] == "video-channel-manager.lordchrist-rich-v1-media-registry"
    assert registry["schema_version"] == 1
    assert registry["project_key"] == "lord-god-strength"
    assert registry["revision"] == "rich-v1"
    assert registry["provider_writes_authorized"] is False
    assert registry["provider_upload_status"] == "not_uploaded"
    assert registry["slot_bindings"] == 6
    assert registry["unique_remote_files"] == 4

    assets = cast(list[dict[str, Any]], registry["assets"])
    assert len(assets) == 6
    assert len({asset["asset_id"] for asset in assets}) == 6
    assert len({asset["direct_media_url"] for asset in assets}) == 4
    for asset in assets:
        assert asset["article_id"] in ARTICLE_IDS
        assert str(asset["canonical_source_page_url"]).startswith("https://commons.wikimedia.org/wiki/File:")
        assert str(asset["direct_media_url"]).startswith("https://upload.wikimedia.org/")
        assert asset["expected_mime"] == "image/jpeg"
        assert asset["content_checksum"] is None
        assert asset["remote_ready"] is True
        assert asset["acquisition_status"] == "source_and_license_reviewed"
        assert asset["provider_upload_status"] == "not_uploaded"
        assert str(asset["licence"]).strip()
        assert str(asset["caption"]).strip()
        assert str(asset["depicts"]).strip()


def test_every_reviewed_article_media_slot_has_exactly_one_registry_binding() -> None:
    registry = _read(REGISTRY_PATH)
    assets = cast(list[dict[str, Any]], registry["assets"])
    for article_id in ARTICLE_IDS:
        article = _read(ARTICLE_DIR / f"{article_id}.json")
        slots = cast(list[dict[str, Any]], article["media_slots"])
        expected = {str(slot["slot_id"]) for slot in slots}
        actual = {
            str(asset["media_slot_id"])
            for asset in assets
            if asset["article_id"] == article_id
        }
        assert len(expected) == 3
        assert actual == expected
        for slot_id in expected:
            matches = [
                asset
                for asset in assets
                if asset["article_id"] == article_id and asset["media_slot_id"] == slot_id
            ]
            assert len(matches) == 1


def test_reused_historical_portraits_keep_identical_remote_identity() -> None:
    registry = _read(REGISTRY_PATH)
    assets = cast(list[dict[str, Any]], registry["assets"])
    for slot_id in ("media-calvin", "media-spurgeon"):
        matches = [asset for asset in assets if asset["media_slot_id"] == slot_id]
        assert len(matches) == 2
        assert len({asset["canonical_source_page_url"] for asset in matches}) == 1
        assert len({asset["direct_media_url"] for asset in matches}) == 1
        assert len({asset["licence"] for asset in matches}) == 1


def test_first_article_uses_tape_and_second_uses_grace_worship_without_macarthur_portrait() -> None:
    registry = _read(REGISTRY_PATH)
    assets = cast(list[dict[str, Any]], registry["assets"])
    first = [asset for asset in assets if asset["article_id"] == "lordchrist-rich-sermons-survive-century"]
    second = [asset for asset in assets if asset["article_id"] == "lordchrist-rich-three-expository-patterns"]
    assert {asset["media_slot_id"] for asset in first} == {"media-calvin", "media-spurgeon", "media-tape"}
    assert {asset["media_slot_id"] for asset in second} == {"media-calvin", "media-spurgeon", "media-grace"}
    assert any("Reel-to-reel" in asset["canonical_source_page_url"] for asset in first)
    assert any("Grace_Community_Church_Worship" in asset["canonical_source_page_url"] for asset in second)
    assert not any("MacArthur" in asset["canonical_source_page_url"] for asset in assets)


def test_rich_profile_has_its_own_binding_to_the_same_historical_exact_target() -> None:
    profile = load_channel_profile(RICH_PROFILE_PATH)
    binding = load_target_binding(RICH_BINDING_PATH, profile)
    legacy = _read(LEGACY_BINDING_PATH)

    assert profile.provider_writes_authorized is True
    assert binding.profile_sha256 == profile.digest
    assert binding.profile_sha256 == "sha256:a02f33ce5166adb01a7869f6be9becdd46bfb180f80c7143a10c7bbd37a0b173"
    assert binding.project_key == legacy["project_key"]
    assert binding.channel_username == legacy["channel_username"]
    assert binding.chat_id == legacy["chat_id"] == -1001295216957
    assert binding.chat_username == legacy["chat_username"] == "lordchrist"
    assert binding.bot_id == legacy["bot_id"] == 8716602202
    assert binding.bot_username == legacy["bot_username"] == "preaching_mp3_bot"
    assert binding.can_post_messages is True
    assert binding.discovered_at_utc.isoformat() == "2026-08-08T07:13:09.125496+00:00"
    assert binding.provider_write_performed is False
