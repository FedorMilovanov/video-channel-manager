"""Regression tests: Lord God YouTube copy cannot lose original provenance."""

from __future__ import annotations

from copy import deepcopy

import pytest

from video_channel_manager.platforms.youtube.copy_plan import (
    finalize_copy_plan,
    sha256_text,
)
from video_channel_manager.platforms.youtube.lord_god_presentation import (
    LORD_GOD_OWNER_CHANNEL,
    require_lord_god_youtube_presentation,
)
from video_channel_manager.platforms.youtube.lord_god_source_preservation import (
    source_preservation_issues,
)

_SOURCE = "https://www.desiringgod.org/messages/when-suffering-is-for-gods-glory"
_PLAYLIST = "PLu2Bhoh2caiUqCagDLyFH4v40eBSKJCdL"
_SHELF = "https://www.youtube.com/channel/UCeSJsC6go2c9pdJCuUI1BYA/playlists?shelf_id=8"
_VALID_TEXT = (
    "Историческая проповедь об избрании и Божьей благодати. "
    "Тема рассматривается через текст Священного Писания.\n\n"
    "*Содержание:* весть Евангелия, Божье провидение и спасение.\n"
    "_Проповедь призывает доверять Христу и Его обетованиям._\n"
    "*Библиотека:* https://gospod-bog.ru/\n"
    "*Telegram:* https://t.me/lordchrist"
)


def _plan(before: str, after: str) -> dict:
    plan = {
        "ruleset": "test-lordgod-source-provenance",
        "source_audit_sha256": "sha256:test",
        "target_channel_id": LORD_GOD_OWNER_CHANNEL,
        "project_key": "lord-god-strength",
        "link_profile": "lord-god-strength",
        "videos_checked": 1,
        "operations_count": 1,
        "unresolved_error_videos": 0,
        "operations": [
            {
                "ruleset": "test-lordgod-source-provenance",
                "operation": "replace_video_description",
                "platform": "youtube",
                "video_id": "abc-123",
                "channel_id": LORD_GOD_OWNER_CHANNEL,
                "title": "Historically sourced sermon",
                "expected_revision": "sha256:old",
                "before_description": before,
                "after_description": after,
                "before_sha256": sha256_text(before),
                "after_sha256": sha256_text(after),
                "fixes": [{"code": "editorial", "count": 1}],
            }
        ],
        "unresolved": [],
    }
    return finalize_copy_plan(plan, checked_video_ids=["abc-123"])


def test_sha_contract_differs_from_archived_raw_hex() -> None:
    import hashlib

    before = "A description"
    assert sha256_text(before) == "sha256:" + hashlib.sha256(before.encode("utf-8")).hexdigest()


def test_only_old_owner_navigation_and_operator_contacts_may_be_dropped() -> None:
    before = (
        "Old intro\n"
        + _SHELF
        + "\nhttps://t.me/fedormilovanov"
        + "\nhttps://facebook.com/fedor.milovanov"
        + "\nhttps://vk.com/curtmf"
        + "\nhttps://new.donatepay.ru/@retired"
    )
    assert source_preservation_issues(before, _VALID_TEXT) == []
    require_lord_god_youtube_presentation(_plan(before, _VALID_TEXT))


def test_original_chapters_must_survive_exactly_including_hour_stamps() -> None:
    before = "00:00 Вступление\n1:04:37 Доверие Богу\n" + _SHELF
    assert "original_chapters_not_preserved" in source_preservation_issues(before, _VALID_TEXT)
    with pytest.raises(ValueError, match="original_chapters_not_preserved"):
        require_lord_god_youtube_presentation(_plan(before, _VALID_TEXT))
    after = _VALID_TEXT + "\n\n00:00 Вступление\n1:04:37 Доверие Богу"
    assert source_preservation_issues(before, after) == []
    require_lord_god_youtube_presentation(_plan(before, after))


def test_existing_translator_and_source_credit_cannot_be_silently_dropped() -> None:
    credit = "Перевод выполнил И. Иванов; источник записи — архив проповеди."
    before = credit + "\n" + _SHELF
    assert "original_translation_or_source_credit_not_preserved" in source_preservation_issues(before, _VALID_TEXT)
    with pytest.raises(ValueError, match="original_translation_or_source_credit_not_preserved"):
        require_lord_god_youtube_presentation(_plan(before, _VALID_TEXT))
    assert source_preservation_issues(before, _VALID_TEXT + "\n" + credit) == []


def test_primary_source_and_related_telegram_post_are_preserved() -> None:
    before = _SOURCE + "\nhttps://t.me/lordchrist/123\n" + _SHELF
    missing = source_preservation_issues(before, _VALID_TEXT)
    assert missing == ["original_source_or_related_link_not_preserved"]
    after = _VALID_TEXT + "\n" + _SOURCE + "\nhttps://t.me/lordchrist/123"
    assert source_preservation_issues(before, after) == []


def test_playlist_identity_survives_canonicalized_url() -> None:
    old = f"http://youtube.com/playlist?feature=share&list={_PLAYLIST}"
    normalized = f"https://www.youtube.com/playlist?list={_PLAYLIST}"
    before = _SHELF + "\n" + old
    assert source_preservation_issues(before, _VALID_TEXT) == ["original_playlist_link_not_preserved"]
    after = _VALID_TEXT + "\n" + normalized
    assert source_preservation_issues(before, after) == []
    require_lord_god_youtube_presentation(_plan(before, after))


def test_non_owner_video_link_is_not_discarded_as_navigation() -> None:
    other = "https://www.youtube.com/watch?v=ABCDEFGHIJK"
    before = _SHELF + "\n" + other
    assert source_preservation_issues(before, _VALID_TEXT) == ["original_source_or_related_link_not_preserved"]


@pytest.mark.parametrize(
    "source_url",
    [
        "https://www.youtube.com/watch?v=ABCDEFGHIJK&shelf_id=8",
        "https://www.youtube.com/channel/UC-other/playlists?shelf_id=8",
        "https://www.youtube.com/channel/UCeSJsC6go2c9pdJCuUI1BYA/videos",
        "https://www.youtube.com/channel/UCeSJsC6go2c9pdJCuUI1BYA/community?shelf_id=8",
        "https://www.youtube.com/channel/UCeSJsC6go2c9pdJCuUI1BYAX/playlists?shelf_id=8",
        "https://www.youtube.com/playlist?list=PLnotlost&shelf_id=8",
    ],
)
def test_only_exact_owner_legacy_shelf_navigation_is_disposable(
    source_url: str,
) -> None:
    assert source_preservation_issues(source_url, _VALID_TEXT) == [
        "original_source_or_related_link_not_preserved"
        if "/playlist?" not in source_url
        else "original_playlist_link_not_preserved"
    ]


def test_old_owner_video_shelf_navigation_is_disposable() -> None:
    source_url = "http://www.youtube.com/channel/UCeSJsC6go2c9pdJCuUI1BYA/videos?sort=p&view=0&shelf_id=10"
    assert source_preservation_issues(source_url, _VALID_TEXT) == []


def test_no_global_effect_on_other_channel_description_plan() -> None:
    plan = _plan("00:00 Источник", _VALID_TEXT)
    foreign = deepcopy(plan)
    foreign["target_channel_id"] = "UC-another"
    # Presentation gate intentionally only applies to exact Lord God owner.
    require_lord_god_youtube_presentation(foreign)
