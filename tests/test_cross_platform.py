from video_channel_manager.application.cross_platform import compare_audit_packages, normalize_title
from video_channel_manager.application.identity import TextPurpose
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

    assert result.schema_version == "3.0"
    assert len(result.matches) == 1
    match = result.matches[0]
    assert match.source_ref.remote_id == "yt-1"
    assert match.target_ref.remote_id == "vk-1"
    assert match.match_method == "exact_normalized_title"
    assert match.duration_delta_seconds == 1
    assert match.source_title_identity.purpose == TextPurpose.IDENTITY_TITLE
    assert match.source_title_identity.original == "Берёза — Сергей Есенин"
    assert match.source_title_identity.canonical == match.target_title_identity.canonical
    assert match.source_description_identity.purpose == TextPurpose.DESCRIPTION
    assert [item.ref.remote_id for item in result.missing_on_target] == ["yt-2"]
    assert result.missing_on_target[0].title_identity.purpose == TextPurpose.IDENTITY_TITLE
    assert result.extra_on_target == []
    assert result.conflicts == []
    assert result.catalog_identity is not None
    assert result.catalog_identity.decisions == []


def test_compare_reports_missing_collection_placement_from_reviewed_ids() -> None:
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

    result = compare_audit_packages(
        source,
        target,
        reviewed_collection_mapping={"playlist": "album"},
    )

    assert len(result.collection_gaps) == 1
    gap = result.collection_gaps[0]
    assert gap.decision == "mapped"
    assert gap.target_collection_id == "album"
    assert gap.source_title_identity.purpose == TextPurpose.COLLECTION_TITLE
    assert gap.target_title_identity is not None
    assert gap.target_title_identity.purpose == TextPurpose.COLLECTION_TITLE
    assert gap.missing_target_video_ids == ["vk-1"]
    assert result.collection_conflict_count == 0
    assert result.missing_placement_count == 1


def test_same_title_collection_without_review_is_conflict() -> None:
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

    gap = result.collection_gaps[0]
    assert gap.decision == "conflict"
    assert gap.conflict_reason == "unreviewed_existing_candidate"
    assert gap.target_collection_id is None
    assert gap.missing_target_video_ids == []
    assert result.collection_conflict_count == 1
    assert result.missing_placement_count == 0


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
    conflict = result.conflicts[0]
    assert conflict.reason == "duplicate_exact_title"
    assert [item.remote_id for item in conflict.source_refs] == ["yt-a", "yt-b"]
    assert [item.remote_id for item in conflict.target_refs] == ["vk-a", "vk-b"]
    assert [item.original for item in conflict.source_title_identities] == [
        "Сукин сын — Сергей Есенин",
        "Сукин сын — Сергей Есенин",
    ]
    assert len(conflict.target_title_identities) == 2
    assert result.missing_on_target == []
    assert result.extra_on_target == []
