from __future__ import annotations

from copy import deepcopy

import pytest

from video_channel_manager.domain.enums import ChannelKind, PlatformName
from video_channel_manager.domain.models import ChannelRecord, RemoteRef, VideoRecord
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk.editorial_cleanup import description_semantic_body
from video_channel_manager.platforms.vk.editorial_description_wave import (
    build_vk_editorial_description_wave,
)


def _ref(remote_id: str) -> RemoteRef:
    return RemoteRef(
        platform=PlatformName.VK,
        channel_id="235216998",
        remote_id=remote_id,
    )


def _video(remote_id: str, title: str, description: str) -> VideoRecord:
    return VideoRecord(
        ref=_ref(remote_id),
        title=title,
        description=description,
        duration_seconds=180,
        privacy_status="public",
        revision=f"sha256:{remote_id}",
    )


def _audit() -> AuditPackage:
    return AuditPackage(
        channel=ChannelRecord(
            ref=_ref("235216998"),
            title="The Legendary Poet",
            kind=ChannelKind.COMMUNITY,
        ),
        videos=[
            _video(
                "-235216998_456239017",
                "Парус 🎶 DJ ВЕРСИЯ 🎶 Михаил Лермонтов",
                "Сохраняем *каждое* содержательное слово.\n\n"
                "Плейлист: https://www.youtube.com/playlist?list=PLAYLIST_ONE\n"
                "#Один #Два #Три\n"
                "VK: https://vk.com/thelegendarypoet",
            ),
            _video(
                "-235216998_456239019",
                "Чёрный Человек ⚡ ВЕРСИЯ 4 ⚡ Сергей Есенин",
                "Тема смерти требует отдельной фактологической проверки.\n"
                "https://youtu.be/VIDEO_ONE",
            ),
        ],
        collections=[],
        memberships=[],
    )


def _policy() -> dict[str, object]:
    return {
        "policy_version": "test",
        "description_policy": {
            "max_hashtags": 2,
            "max_length": 5000,
            "canonical_footer": (
                "🎧 The Legendary Poet - поэзия, музыка и литературные материалы.\n"
                "🌐 Сайт: https://thelegendarypoet.ru/"
            ),
        },
        "playlist_replacements": {
            "PLAYLIST_ONE": "https://vkvideo.ru/playlist/-235216998_3?uh=test",
        },
        "youtube_video_replacements": {
            "VIDEO_ONE": "https://vkvideo.ru/video-235216998_456239019",
        },
        "title_overrides": {},
        "album_title_overrides": {},
        "description_review_only_ids": [],
    }


def test_description_wave_changes_descriptions_only_and_preserves_body() -> None:
    policy = _policy()
    plan = build_vk_editorial_description_wave(_audit(), policy)

    assert plan["operation_scope"] == "editorial_only"
    assert plan["component_scope"] == "descriptions_only"
    assert plan["summary"]["titles_to_update"] == 0
    assert plan["summary"]["descriptions_to_update"] == 2
    assert plan["summary"]["albums_to_rename"] == 0
    assert plan["summary"]["total_operations"] == 2
    assert plan["summary"]["deferred_editorial_review"] >= 1

    for operation in plan["video_text_operations"]:
        assert operation["after_title"] == operation["before_title"]
        assert operation["title_changed"] is False
        assert operation["description_changed"] is True
        assert operation["semantic_body_preserved"] is True
        assert description_semantic_body(
            operation["before_description"], policy
        ) == description_semantic_body(operation["after_description"], policy)
        assert operation["change_reasons"]

    first = plan["video_text_operations"][0]
    assert "replace_youtube_playlist" in first["change_reasons"]
    assert "remove_markdown_markers" in first["change_reasons"]
    assert "replace_legacy_footer" in first["change_reasons"]
    assert "cap_hashtags" in first["change_reasons"]


def test_description_semantic_body_detects_content_rewrite() -> None:
    policy = _policy()
    before = "Сохраняем каждое содержательное слово. https://example.com/a"
    after = "Удаляем одно содержательное слово. https://example.com/b"

    assert description_semantic_body(before, policy) != description_semantic_body(
        after, policy
    )


def test_description_wave_excludes_explicit_manual_review_ids() -> None:
    policy = deepcopy(_policy())
    policy["description_review_only_ids"] = ["-235216998_456239017"]
    plan = build_vk_editorial_description_wave(_audit(), policy)

    operation_ids = {
        operation["target_video_id"] for operation in plan["video_text_operations"]
    }
    assert "-235216998_456239017" not in operation_ids
    assert any(
        finding.get("target_video_id") == "-235216998_456239017"
        and finding["kind"] == "description_manual_review_excluded"
        for finding in plan["review_only"]
    )


def test_description_wave_rejects_unknown_review_exclusion() -> None:
    policy = deepcopy(_policy())
    policy["description_review_only_ids"] = ["-235216998_999999999"]

    with pytest.raises(ValueError, match="Unknown description_review_only_ids"):
        build_vk_editorial_description_wave(_audit(), policy)
