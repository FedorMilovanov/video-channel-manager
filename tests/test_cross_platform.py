from video_channel_manager.application.cross_platform import compare_audit_packages, normalize_title
from video_channel_manager.domain.enums import ChannelKind, CollectionKind, PlatformName
from video_channel_manager.domain.models import (
    ChannelRecord,
    CollectionMembership,
    CollectionRecord,
    RemoteRef,
    VideoRecord,
)
from video_channel_manager.exchange.audit_package import AuditPackage


def _ref(platform: PlatformName, channel_id: str, remote_id: str) -> RemoteRef:
    return RemoteRef(platform=platform, channel_id=channel_id, remote_id=remote_id)


def _video(platform: PlatformName, channel_id: str, remote_id: str, title: str, duration: int) -> VideoRecord:
    return VideoRecord(
        ref=_ref(platform, channel_id, remote_id),
        title=title,
        duration_seconds=duration,
        privacy_status="public",
        revision=f"sha256:{remote_id}",
    )


def _audit(
    platform: PlatformName,
    channel_id: str,
    videos: list[VideoRecord],
    *,
    collection_title: str | None = None,
    member_ids: list[str] | None = None,
) -> AuditPackage:
    channel_kind = ChannelKind.VIDEO_CHANNEL if platform == PlatformName.YOUTUBE else ChannelKind.COMMUNITY
    collections: list[CollectionRecord] = []
    memberships: list[CollectionMembership] = []
    if collection_title is not None:
        collection_id = "playlist" if platform == PlatformName.YOUTUBE else "album"
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
            kind=channel_kind,
        ),
        videos=videos,
        collections=collections,
        memberships=memberships,
    )


def test_normalize_title_removes_brand_and_normalizes_version() -> None:
    assert normalize_title("Берёза — Version 2 @TheLegendaryPoet #Shorts") == "береза версия 2"


def test_compare_matches_by_title_and_duration_and_reports_missing() -> None:
    source = _audit(
        PlatformName.YOUTUBE,
        "youtube-channel",
        [
            _video(PlatformName.YOUTUBE, "youtube-channel", "yt-1", "Берёза — Сергей Есенин", 242),
            _video(PlatformName.YOUTUBE, "youtube-channel", "yt-2", "Россия — Александр Блок", 315),
        ],
    )
    target = _audit(
        PlatformName.VK,
        "vk-channel",
        [_video(PlatformName.VK, "vk-channel", "vk-1", "Береза - Сергей Есенин @TheLegendaryPoet", 241)],
    )

    result = compare_audit_packages(source, target)

    assert result.schema_version == "2.0"
    assert len(result.matches) == 1
    assert result.matches[0].source_ref.remote_id == "yt-1"
    assert result.matches[0].target_ref.remote_id == "vk-1"
    assert result.matches[0].match_method == "exact_normalized_title"
    assert result.matches[0].duration_delta_seconds == 1
    assert [item.ref.remote_id for item in result.missing_on_target] == ["yt-2"]
    assert result.extra_on_target == []
    assert result.conflicts == []


def test_compare_reports_missing_collection_placement() -> None:
    source = _audit(
        PlatformName.YOUTUBE,
        "youtube-channel",
        [_video(PlatformName.YOUTUBE, "youtube-channel", "yt-1", "Берёза — Сергей Есенин", 242)],
        collection_title="Сергей Есенин",
        member_ids=["yt-1"],
    )
    target = _audit(
        PlatformName.VK,
        "vk-channel",
        [_video(PlatformName.VK, "vk-channel", "vk-1", "Береза — Сергей Есенин", 241)],
        collection_title="Сергей Есенин",
        member_ids=[],
    )

    result = compare_audit_packages(source, target)

    assert len(result.collection_gaps) == 1
    gap = result.collection_gaps[0]
    assert gap.target_collection_id == "album"
    assert gap.missing_target_video_ids == ["vk-1"]
    assert result.missing_placement_count == 1


def test_duplicate_exact_titles_are_conflict_not_selected_pairs() -> None:
    source = _audit(
        PlatformName.YOUTUBE,
        "youtube-channel",
        [
            _video(PlatformName.YOUTUBE, "youtube-channel", "yt-a", "Сукин сын — Сергей Есенин", 160),
            _video(PlatformName.YOUTUBE, "youtube-channel", "yt-b", "Сукин сын — Сергей Есенин", 160),
        ],
    )
    target = _audit(
        PlatformName.VK,
        "vk-channel",
        [
            _video(PlatformName.VK, "vk-channel", "vk-a", "Сукин сын — Сергей Есенин", 159),
            _video(PlatformName.VK, "vk-channel", "vk-b", "Сукин сын — Сергей Есенин", 159),
        ],
    )

    result = compare_audit_packages(source, target)

    assert result.matches == []
    assert result.conflict_count == 1
    assert result.ambiguous_match_count == 1
    assert result.conflicts[0].reason == "duplicate_exact_title"
    assert [item.remote_id for item in result.conflicts[0].source_refs] == ["yt-a", "yt-b"]
    assert [item.remote_id for item in result.conflicts[0].target_refs] == ["vk-a", "vk-b"]
    assert result.missing_on_target == []
    assert result.extra_on_target == []
