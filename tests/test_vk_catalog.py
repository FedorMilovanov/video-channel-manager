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
from video_channel_manager.platforms.vk.catalog import (
    build_vk_catalog_plan,
    calculate_vk_catalog_plan_sha256,
    target_video_ids_sha256,
    validate_vk_catalog_plan,
)


def _ref(platform: PlatformName, channel_id: str, remote_id: str) -> RemoteRef:
    return RemoteRef(platform=platform, channel_id=channel_id, remote_id=remote_id)


def _video(
    platform: PlatformName,
    channel_id: str,
    remote_id: str,
    title: str,
    description: str,
    duration: int = 240,
) -> VideoRecord:
    return VideoRecord(
        ref=_ref(platform, channel_id, remote_id),
        title=title,
        description=description,
        duration_seconds=duration,
        privacy_status="public",
        revision=f"sha256:{remote_id}",
    )


def _audit(
    platform: PlatformName,
    channel_id: str,
    videos: list[VideoRecord],
    *,
    collection_id: str | None = None,
    collection_title: str | None = None,
    member_ids: list[str] | None = None,
) -> AuditPackage:
    kind = ChannelKind.VIDEO_CHANNEL if platform == PlatformName.YOUTUBE else ChannelKind.COMMUNITY
    collections: list[CollectionRecord] = []
    memberships: list[CollectionMembership] = []
    if collection_id and collection_title:
        collection_kind = CollectionKind.PLAYLIST if platform == PlatformName.YOUTUBE else CollectionKind.VIDEO_ALBUM
        collection_ref = _ref(platform, channel_id, collection_id)
        collections.append(
            CollectionRecord(
                ref=collection_ref,
                title=collection_title,
                kind=collection_kind,
                revision=f"sha256:{collection_id}",
            )
        )
        for position, video_id in enumerate(member_ids or []):
            memberships.append(
                CollectionMembership(
                    collection_ref=collection_ref,
                    video_ref=_ref(platform, channel_id, video_id),
                    position=position,
                )
            )
    return AuditPackage(
        channel=ChannelRecord(
            ref=_ref(platform, channel_id, channel_id),
            title=channel_id,
            kind=kind,
        ),
        videos=videos,
        collections=collections,
        memberships=memberships,
    )


def test_catalog_plan_builds_album_placement_and_text_update() -> None:
    source = _audit(
        PlatformName.YOUTUBE,
        "youtube-channel",
        [_video(PlatformName.YOUTUBE, "youtube-channel", "yt-1", "Берёза — Сергей Есенин", "О стихотворении.")],
        collection_id="playlist-esenin",
        collection_title="Сергей Есенин",
        member_ids=["yt-1"],
    )
    target = _audit(
        PlatformName.VK,
        "235216998",
        [_video(PlatformName.VK, "235216998", "-235216998_1", "Береза — Сергей Есенин", "Старое описание")],
    )

    plan = build_vk_catalog_plan(source, target)

    assert plan["project_key"] == "legendary-poet"
    assert plan["summary"] == {
        "resolved_video_mappings": 1,
        "albums_to_create": 1,
        "placements_to_add": 1,
        "video_texts_to_update": 1,
        "review_only": 0,
        "total_operations": 3,
    }
    assert plan["album_operations"][0]["title"] == "Сергей Есенин"
    assert plan["placement_operations"][0]["target_video_id"] == "-235216998_1"
    assert plan["text_operations"][0]["project_key"] == "legendary-poet"
    assert plan["text_operations"][0]["after_title"].endswith("⚡")
    assert plan["text_operations"][0]["after_description"].count("https://thelegendarypoet.ru/") == 1
    assert "gospod-bog.ru" not in plan["text_operations"][0]["after_description"]
    assert plan["target_video_ids_sha256"] == target_video_ids_sha256(target)
    validate_vk_catalog_plan(plan)


def test_lord_god_catalog_never_receives_poet_branding() -> None:
    source_channel = "UCeSJsC6go2c9pdJCuUI1BYA"
    source = _audit(
        PlatformName.YOUTUBE,
        source_channel,
        [_video(PlatformName.YOUTUBE, source_channel, "yt-1", "Послание к Римлянам", "Разбор текста.")],
    )
    target = _audit(
        PlatformName.VK,
        "60805374",
        [_video(PlatformName.VK, "60805374", "-60805374_1", "Старый заголовок", "Старое описание")],
    )

    plan = build_vk_catalog_plan(source, target, reviewed_mappings={"yt-1": "-60805374_1"})
    operation = plan["text_operations"][0]

    assert plan["project_key"] == "lord-god-strength"
    assert operation["project_key"] == "lord-god-strength"
    assert operation["after_title"] == "Послание к Римлянам"
    assert "https://gospod-bog.ru/" in operation["after_description"]
    assert "The Legendary Poet" not in operation["after_description"]
    assert "thelegendarypoet.ru" not in operation["after_description"]
    assert not operation["after_title"].endswith("⚡")


def test_catalog_plan_rejects_cross_project_provider_targets() -> None:
    source_channel = "UC-78ys2S3cQ3lpqgXfo-SvQ"
    source = _audit(
        PlatformName.YOUTUBE,
        source_channel,
        [_video(PlatformName.YOUTUBE, source_channel, "yt-1", "Поэтический материал", "Описание")],
    )
    target = _audit(
        PlatformName.VK,
        "60805374",
        [_video(PlatformName.VK, "60805374", "-60805374_1", "Старое", "Старое")],
    )

    with pytest.raises(ValueError, match="unknown or conflicting"):
        build_vk_catalog_plan(source, target, reviewed_mappings={"yt-1": "-60805374_1"})


def test_catalog_plan_rejects_unknown_project_identity() -> None:
    source = _audit(
        PlatformName.YOUTUBE,
        "unknown-youtube-channel",
        [_video(PlatformName.YOUTUBE, "unknown-youtube-channel", "yt-1", "Материал", "Описание")],
    )
    target = _audit(
        PlatformName.VK,
        "999999999",
        [_video(PlatformName.VK, "999999999", "-999999999_1", "Старое", "Старое")],
    )

    with pytest.raises(ValueError, match="unknown or conflicting"):
        build_vk_catalog_plan(source, target, reviewed_mappings={"yt-1": "-999999999_1"})


def test_catalog_plan_preserves_existing_album_and_membership() -> None:
    source = _audit(
        PlatformName.YOUTUBE,
        "youtube-channel",
        [_video(PlatformName.YOUTUBE, "youtube-channel", "yt-1", "Берёза — Сергей Есенин", "О стихотворении.")],
        collection_id="playlist-esenin",
        collection_title="Сергей Есенин",
        member_ids=["yt-1"],
    )
    target = _audit(
        PlatformName.VK,
        "235216998",
        [_video(PlatformName.VK, "235216998", "-235216998_1", "Береза — Сергей Есенин", "Старое описание")],
        collection_id="77",
        collection_title="Сергей Есенин",
        member_ids=["-235216998_1"],
    )

    plan = build_vk_catalog_plan(source, target)

    assert plan["album_operations"] == []
    assert plan["placement_operations"] == []
    assert plan["summary"]["video_texts_to_update"] == 1


def test_reviewed_mapping_resolves_ambiguous_matches() -> None:
    source = _audit(
        PlatformName.YOUTUBE,
        "youtube-channel",
        [
            _video(PlatformName.YOUTUBE, "youtube-channel", "yt-a", "Одинаковое название", "Первое"),
            _video(PlatformName.YOUTUBE, "youtube-channel", "yt-b", "Одинаковое название", "Второе"),
        ],
    )
    target = _audit(
        PlatformName.VK,
        "235216998",
        [
            _video(PlatformName.VK, "235216998", "-235216998_1", "Одинаковое название", "Старое 1"),
            _video(PlatformName.VK, "235216998", "-235216998_2", "Одинаковое название", "Старое 2"),
        ],
    )

    plan = build_vk_catalog_plan(
        source,
        target,
        reviewed_mappings={"yt-a": "-235216998_1", "yt-b": "-235216998_2"},
    )

    assert plan["resolved_video_mappings"] == {
        "yt-a": "-235216998_1",
        "yt-b": "-235216998_2",
    }
    assert plan["review_only"] == []


def test_catalog_plan_rejects_tampering() -> None:
    source = _audit(
        PlatformName.YOUTUBE,
        "youtube-channel",
        [_video(PlatformName.YOUTUBE, "youtube-channel", "yt-1", "Берёза — Сергей Есенин", "Описание")],
    )
    target = _audit(
        PlatformName.VK,
        "235216998",
        [_video(PlatformName.VK, "235216998", "-235216998_1", "Береза — Сергей Есенин", "Старое")],
    )
    plan = build_vk_catalog_plan(source, target)
    tampered = deepcopy(plan)
    tampered["text_operations"][0]["after_description"] += " Подмена"

    with pytest.raises(ValueError, match="self-digest"):
        validate_vk_catalog_plan(tampered)

    tampered["plan_sha256"] = calculate_vk_catalog_plan_sha256(tampered)
    with pytest.raises(ValueError, match="Text hash mismatch"):
        validate_vk_catalog_plan(tampered)
