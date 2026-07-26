from __future__ import annotations

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
from video_channel_manager.platforms.vk.catalog_policy import (
    apply_vk_catalog_policy,
    parse_vk_catalog_policy,
)


def _ref(platform: PlatformName, channel_id: str, remote_id: str) -> RemoteRef:
    return RemoteRef(platform=platform, channel_id=channel_id, remote_id=remote_id)


def _video(platform: PlatformName, channel_id: str, remote_id: str, title: str) -> VideoRecord:
    return VideoRecord(
        ref=_ref(platform, channel_id, remote_id),
        title=title,
        description="Описание",
        duration_seconds=240,
        privacy_status="public",
        revision=f"sha256:{remote_id}",
    )


def _source() -> AuditPackage:
    channel_id = "youtube-channel"
    mapped = _video(PlatformName.YOUTUBE, channel_id, "yt-mapped", "Берёза — Сергей Есенин")
    unmapped = _video(PlatformName.YOUTUBE, channel_id, "yt-unmapped", "Несопоставленный ролик")
    singing_ref = _ref(PlatformName.YOUTUBE, channel_id, "playlist-singing")
    empty_ref = _ref(PlatformName.YOUTUBE, channel_id, "playlist-empty")
    return AuditPackage(
        channel=ChannelRecord(
            ref=_ref(PlatformName.YOUTUBE, channel_id, channel_id),
            title="YouTube",
            kind=ChannelKind.VIDEO_CHANNEL,
        ),
        videos=[mapped, unmapped],
        collections=[
            CollectionRecord(
                ref=singing_ref,
                title="Поющие Поэты",
                kind=CollectionKind.PLAYLIST,
                revision="sha256:singing",
            ),
            CollectionRecord(
                ref=empty_ref,
                title="Пустой плейлист",
                kind=CollectionKind.PLAYLIST,
                revision="sha256:empty",
            ),
        ],
        memberships=[
            CollectionMembership(
                collection_ref=singing_ref,
                video_ref=mapped.ref,
                position=0,
            ),
            CollectionMembership(
                collection_ref=empty_ref,
                video_ref=unmapped.ref,
                position=0,
            ),
        ],
    )


def _target() -> AuditPackage:
    channel_id = "235216998"
    return AuditPackage(
        channel=ChannelRecord(
            ref=_ref(PlatformName.VK, channel_id, channel_id),
            title="VK",
            kind=ChannelKind.COMMUNITY,
        ),
        videos=[
            _video(
                PlatformName.VK,
                channel_id,
                "-235216998_1",
                "Берёза — Сергей Есенин",
            )
        ],
    )


def test_policy_skips_collections_without_mapped_videos_and_applies_override() -> None:
    policy = parse_vk_catalog_policy(
        {
            "schema_name": "video-manager.vk-catalog-policy",
            "schema_version": 1,
            "title_overrides": {"Поющие Поэты": "Поющие поэты"},
            "excluded_titles": [],
            "skip_collections_without_mapped_videos": True,
        }
    )

    curated, events = apply_vk_catalog_policy(
        _source(),
        _target(),
        reviewed_mappings={"yt-mapped": "-235216998_1"},
        policy=policy,
    )

    assert [item.title for item in curated.collections] == ["Поющие поэты"]
    assert [item.collection_ref.remote_id for item in curated.memberships] == ["playlist-singing"]
    assert {item["kind"] for item in events} == {
        "collection_title_overridden",
        "collection_skipped_without_mapped_videos",
    }
    assert policy.sha256.startswith("sha256:")


def test_default_policy_also_skips_empty_collections() -> None:
    curated, events = apply_vk_catalog_policy(
        _source(),
        _target(),
        reviewed_mappings={"yt-mapped": "-235216998_1"},
        policy=parse_vk_catalog_policy(None),
    )

    assert [item.title for item in curated.collections] == ["Поющие Поэты"]
    assert any(item["kind"] == "collection_skipped_without_mapped_videos" for item in events)


def test_policy_can_exclude_a_mapped_collection() -> None:
    policy = parse_vk_catalog_policy(
        {
            "schema_name": "video-manager.vk-catalog-policy",
            "schema_version": 1,
            "title_overrides": {},
            "excluded_titles": ["Поющие Поэты"],
            "skip_collections_without_mapped_videos": True,
        }
    )

    curated, events = apply_vk_catalog_policy(
        _source(),
        _target(),
        reviewed_mappings={"yt-mapped": "-235216998_1"},
        policy=policy,
    )

    assert curated.collections == []
    assert curated.memberships == []
    assert any(item["kind"] == "collection_excluded_by_policy" for item in events)


def test_policy_rejects_duplicate_normalized_override_targets() -> None:
    with pytest.raises(ValueError, match="same VK album title"):
        parse_vk_catalog_policy(
            {
                "schema_name": "video-manager.vk-catalog-policy",
                "schema_version": 1,
                "title_overrides": {
                    "Первый": "Один альбом",
                    "Второй": "  один   альбом  ",
                },
                "excluded_titles": [],
                "skip_collections_without_mapped_videos": True,
            }
        )


def test_policy_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError, match="Unknown VK catalog policy fields"):
        parse_vk_catalog_policy(
            {
                "schema_name": "video-manager.vk-catalog-policy",
                "schema_version": 1,
                "title_overrides": {},
                "excluded_titles": [],
                "skip_collections_without_mapped_videos": True,
                "unexpected": True,
            }
        )
