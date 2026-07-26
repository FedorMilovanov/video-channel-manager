from __future__ import annotations

from copy import deepcopy

import pytest

from video_channel_manager.domain.enums import ChannelKind, CollectionKind, PlatformName
from video_channel_manager.domain.models import (
    ChannelRecord,
    CollectionMembership,
    CollectionRecord,
    RemoteRef,
    VideoRecord,
)
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk.editorial_cleanup import clean_vk_title
from video_channel_manager.platforms.vk.editorial_cleanup_plan import (
    build_vk_editorial_cleanup_plan,
    calculate_vk_editorial_plan_sha256,
    membership_state_sha256,
    validate_vk_editorial_cleanup_plan,
)


def _ref(remote_id: str) -> RemoteRef:
    return RemoteRef(
        platform=PlatformName.VK,
        channel_id="235216998",
        remote_id=remote_id,
    )


def _audit() -> AuditPackage:
    video_ref = _ref("-235216998_456239047")
    collection_ref = _ref("3")
    return AuditPackage(
        channel=ChannelRecord(
            ref=_ref("235216998"),
            title="The Legendary Poet",
            kind=ChannelKind.COMMUNITY,
        ),
        videos=[
            VideoRecord(
                ref=video_ref,
                title="Исповедь Самоубийцы - Version 2 - Сергей Есенин @TheLegendaryPoet",
                description=(
                    "*Плейлист «Сергей Есенин»:* "
                    "https://www.youtube.com/playlist?list=playlist-esenin\n\n"
                    "_Важный текст._\n\n"
                    "VK: https://vk.com/thelegendarypoet"
                ),
                duration_seconds=240,
                privacy_status="public",
                revision="sha256:video",
            )
        ],
        collections=[
            CollectionRecord(
                ref=collection_ref,
                title="Сергей Есенин (1895-1925)",
                kind=CollectionKind.VIDEO_ALBUM,
                privacy_status="public",
                revision="sha256:album",
                metadata={"count": 1, "share_url": "https://vkvideo.ru/playlist/-235216998_3?uh=test"},
            )
        ],
        memberships=[
            CollectionMembership(
                collection_ref=collection_ref,
                video_ref=video_ref,
                position=0,
            )
        ],
    )


def _policy() -> dict[str, object]:
    return {
        "policy_version": "test",
        "description_policy": {
            "max_hashtags": 10,
            "max_length": 5000,
            "canonical_footer": (
                "🎧 The Legendary Poet - поэзия, музыка и литературные материалы.\n"
                "🌐 Сайт: https://thelegendarypoet.ru/"
            ),
        },
        "playlist_replacements": {"playlist-esenin": "https://vkvideo.ru/playlist/-235216998_3?uh=test"},
        "youtube_video_replacements": {},
        "title_overrides": {"-235216998_456239047": "Исповедь Самоубийцы ⚡ ВЕРСИЯ 2 ⚡ Сергей Есенин"},
        "album_title_overrides": {"3": "Сергей Есенин"},
    }


def test_title_cleanup_preserves_brand_style_without_pipe() -> None:
    title = clean_vk_title("DJ Маяковский 🎶 𝖭𝖮𝖪TU𝖱𝖭 🎶 А Вы Могли Бы? @TheLegendaryPoet")

    assert title == "DJ Маяковский 🎶 𝖭𝖮𝖪TU𝖱𝖭 🎶 А Вы Могли Бы?"
    assert "|" not in title
    assert "@TheLegendaryPoet" not in title


def test_editorial_plan_is_brand_preserving_and_catalog_safe() -> None:
    audit = _audit()
    membership_digest = membership_state_sha256(audit)

    plan = build_vk_editorial_cleanup_plan(audit, _policy())

    assert plan["operation_scope"] == "editorial_only"
    assert plan["initial_memberships_sha256"] == membership_digest
    assert plan["summary"] == {
        "videos_in_snapshot": 1,
        "video_text_operations": 1,
        "titles_to_update": 1,
        "descriptions_to_update": 1,
        "albums_to_rename": 1,
        "placements_to_add": 0,
        "placements_to_remove": 0,
        "videos_to_delete": 0,
        "review_only": 1,
        "total_operations": 2,
    }

    operation = plan["video_text_operations"][0]
    assert operation["after_title"] == "Исповедь Самоубийцы ⚡ ВЕРСИЯ 2 ⚡ Сергей Есенин"
    assert "|" not in operation["after_title"]
    assert "@TheLegendaryPoet" not in operation["after_title"]
    assert "https://vkvideo.ru/playlist/-235216998_3?uh=test" in operation["after_description"]
    assert "youtube.com/playlist" not in operation["after_description"]
    assert "*" not in operation["after_description"]
    assert "_Важный" not in operation["after_description"]
    assert "https://vk.com/thelegendarypoet" not in operation["after_description"]
    assert plan["album_title_operations"][0]["after_title"] == "Сергей Есенин"
    validate_vk_editorial_cleanup_plan(plan)


def test_editorial_plan_rejects_tampering() -> None:
    plan = build_vk_editorial_cleanup_plan(_audit(), _policy())
    tampered = deepcopy(plan)
    tampered["video_text_operations"][0]["after_title"] += " Подмена"

    with pytest.raises(ValueError, match="self-digest"):
        validate_vk_editorial_cleanup_plan(tampered)

    tampered["plan_sha256"] = calculate_vk_editorial_plan_sha256(tampered)
    with pytest.raises(ValueError, match="Text hash mismatch"):
        validate_vk_editorial_cleanup_plan(tampered)


def test_editorial_plan_rejects_catalog_mutations() -> None:
    plan = build_vk_editorial_cleanup_plan(_audit(), _policy())
    tampered = deepcopy(plan)
    tampered["placement_operations"] = [{"operation_id": "placement:add:forbidden"}]
    tampered["plan_sha256"] = calculate_vk_editorial_plan_sha256(tampered)

    with pytest.raises(ValueError, match="cannot contain placement_operations"):
        validate_vk_editorial_cleanup_plan(tampered)
