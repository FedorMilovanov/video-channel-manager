from __future__ import annotations

from copy import deepcopy

import pytest

from video_channel_manager.domain.enums import ChannelKind, PlatformName
from video_channel_manager.domain.models import ChannelRecord, RemoteRef, VideoRecord
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk.editorial_title_wave import (
    build_vk_editorial_title_wave,
)


def _ref(remote_id: str) -> RemoteRef:
    return RemoteRef(
        platform=PlatformName.VK,
        channel_id="235216998",
        remote_id=remote_id,
    )


def _video(remote_id: str, title: str, duration: int = 180) -> VideoRecord:
    return VideoRecord(
        ref=_ref(remote_id),
        title=title,
        description="Техническое описание без ссылок.",
        duration_seconds=duration,
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
                "-235216998_456239047",
                "Исповедь Самоубийцы - Version 2 - Сергей Есенин @TheLegendaryPoet",
                240,
            ),
            _video(
                "-235216998_456239040",
                "Сукин Сын - Сергей Есенин @TheLegendaryPoet",
                159,
            ),
            _video(
                "-235216998_456239041",
                "Сукин Сын - Сергей Есенин @TheLegendaryPoet",
                159,
            ),
        ],
        collections=[],
        memberships=[],
    )


def _policy() -> dict[str, object]:
    return {
        "policy_version": "test",
        "description_policy": {
            "max_hashtags": 10,
            "max_length": 5000,
            "canonical_footer": "",
        },
        "playlist_replacements": {},
        "youtube_video_replacements": {},
        "title_overrides": {
            "-235216998_456239047": ("Исповедь Самоубийцы ⚡ ВЕРСИЯ 2 ⚡ Сергей Есенин"),
            "-235216998_456239040": "Сукин Сын ⚡ Сергей Есенин",
            "-235216998_456239041": "Сукин Сын ⚡ Сергей Есенин",
        },
        "album_title_overrides": {},
        "title_review_only_ids": [
            "-235216998_456239040",
            "-235216998_456239041",
        ],
        "title_semantic_label_reviewed_ids": [],
        "title_review_only_reason": "Manual distinction required.",
    }


def test_title_wave_changes_titles_only_and_excludes_ambiguous_pairs() -> None:
    plan = build_vk_editorial_title_wave(_audit(), _policy())

    assert plan["operation_scope"] == "editorial_only"
    assert plan["component_scope"] == "titles_only"
    assert plan["summary"] == {
        "videos_in_snapshot": 3,
        "video_text_operations": 1,
        "titles_to_update": 1,
        "descriptions_to_update": 0,
        "albums_to_rename": 0,
        "placements_to_add": 0,
        "placements_to_remove": 0,
        "videos_to_delete": 0,
        "review_only": 3,
        "total_operations": 1,
    }
    operation = plan["video_text_operations"][0]
    assert operation["target_video_id"] == "-235216998_456239047"
    assert operation["after_title"] == "Исповедь Самоубийцы ⚡ ВЕРСИЯ 2 ⚡ Сергей Есенин"
    assert operation["after_description"] == operation["before_description"]
    assert operation["description_changed"] is False
    assert operation["semantic_title_labels_before"] == ["version:2"]
    assert operation["semantic_title_labels_after"] == ["version:2"]
    assert operation["semantic_title_labels_preserved"] is True
    excluded = {
        finding["target_video_id"]
        for finding in plan["review_only"]
        if finding["kind"] == "title_manual_review_excluded"
    }
    assert excluded == {
        "-235216998_456239040",
        "-235216998_456239041",
    }


def test_title_wave_rejects_a_new_duplicate_title() -> None:
    audit = AuditPackage(
        channel=ChannelRecord(
            ref=_ref("235216998"),
            title="The Legendary Poet",
            kind=ChannelKind.COMMUNITY,
        ),
        videos=[
            _video("-235216998_456239090", "Первое Название"),
            _video("-235216998_456239095", "Второе Название"),
        ],
        collections=[],
        memberships=[],
    )
    policy = deepcopy(_policy())
    policy["title_review_only_ids"] = []
    policy["title_overrides"] = {
        "-235216998_456239090": "Одинаковое Название",
        "-235216998_456239095": "Одинаковое Название",
    }

    with pytest.raises(ValueError, match="introduces duplicate titles"):
        build_vk_editorial_title_wave(audit, policy)


def test_title_wave_rejects_unknown_review_exclusion() -> None:
    policy = deepcopy(_policy())
    policy["title_review_only_ids"] = ["-235216998_999999999"]

    with pytest.raises(ValueError, match="Unknown title_review_only_ids"):
        build_vk_editorial_title_wave(_audit(), policy)


def test_title_wave_rejects_inferred_short_or_full_labels() -> None:
    policy = deepcopy(_policy())
    policy["title_overrides"] = {"-235216998_456239047": ("Исповедь Самоубийцы ⚡ КОРОТКАЯ ВЕРСИЯ 2 ⚡ Сергей Есенин")}

    with pytest.raises(ValueError, match="changes semantic labels"):
        build_vk_editorial_title_wave(_audit(), policy)


def test_title_wave_allows_exact_reviewed_semantic_label_change() -> None:
    policy = deepcopy(_policy())
    policy["title_overrides"] = {"-235216998_456239047": ("Исповедь Самоубийцы ⚡ КОРОТКАЯ ВЕРСИЯ 2 ⚡ Сергей Есенин")}
    policy["title_semantic_label_reviewed_ids"] = ["-235216998_456239047"]

    plan = build_vk_editorial_title_wave(_audit(), policy)

    operation = plan["video_text_operations"][0]
    assert operation["semantic_title_labels_before"] == ["version:2"]
    assert operation["semantic_title_labels_after"] == ["short", "version:2"]
    assert operation["semantic_title_labels_preserved"] is False
