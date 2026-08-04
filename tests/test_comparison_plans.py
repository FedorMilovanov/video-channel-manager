from video_channel_manager.application.comparison_plans import (
    build_disabled_collection_plan,
    build_disabled_transfer_plan,
    render_detailed_comparison_markdown,
    summarize_placements,
)
from video_channel_manager.application.cross_platform import compare_audit_packages
from video_channel_manager.domain.enums import ChannelKind, CollectionKind, OperationType, PlatformName
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
    collection_members: dict[str, list[str]],
) -> AuditPackage:
    kind = ChannelKind.VIDEO_CHANNEL if platform == PlatformName.YOUTUBE else ChannelKind.COMMUNITY
    collection_kind = CollectionKind.PLAYLIST if platform == PlatformName.YOUTUBE else CollectionKind.VIDEO_ALBUM
    collections: list[CollectionRecord] = []
    memberships: list[CollectionMembership] = []
    for index, (title, member_ids) in enumerate(collection_members.items(), start=1):
        collection_ref = _ref(platform, channel_id, f"collection-{index}")
        collections.append(
            CollectionRecord(
                ref=collection_ref,
                title=title,
                kind=collection_kind,
                revision=f"sha256:collection-{index}",
            )
        )
        for position, video_id in enumerate(member_ids):
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


def _comparison_fixture() -> tuple[AuditPackage, AuditPackage]:
    source = _audit(
        PlatformName.YOUTUBE,
        "youtube-channel",
        [
            _video(PlatformName.YOUTUBE, "youtube-channel", "yt-a", "Берёза — Сергей Есенин", 242),
            _video(PlatformName.YOUTUBE, "youtube-channel", "yt-b", "Россия — Александр Блок", 315),
            _video(PlatformName.YOUTUBE, "youtube-channel", "yt-c", "На поле Куликовом — Александр Блок", 285),
        ],
        {
            "Сергей Есенин": ["yt-a"],
            "Александр Блок": ["yt-b"],
        },
    )
    target = _audit(
        PlatformName.VK,
        "vk-channel",
        [
            _video(PlatformName.VK, "vk-channel", "vk-a", "Береза — Сергей Есенин", 241),
            _video(PlatformName.VK, "vk-channel", "vk-b", "Россия — Александр Блок", 314),
        ],
        {"Сергей Есенин": []},
    )
    return source, target


def _comparison(source: AuditPackage, target: AuditPackage):
    return compare_audit_packages(
        source,
        target,
        reviewed_collection_mapping={"collection-1": "collection-1"},
        approved_collection_creates={"collection-2"},
    )


def test_placement_summary_separates_existing_and_missing_collections() -> None:
    source, target = _comparison_fixture()
    comparison = _comparison(source, target)

    summary = summarize_placements(comparison)

    assert summary.existing_collection_placements == 1
    assert summary.pending_collection_placements == 1
    assert summary.total_placements == 2
    markdown = render_detailed_comparison_markdown(comparison)
    assert "Недостающих размещений в уже существующих коллекциях: **1**" in markdown
    assert "Размещений, ожидающих создания отсутствующих коллекций: **1**" in markdown
    assert "Всего требуемых размещений: **2**" in markdown


def test_disabled_transfer_plan_contains_only_public_full_length_missing_videos() -> None:
    source, target = _comparison_fixture()
    comparison = _comparison(source, target)

    plan = build_disabled_transfer_plan(source, target, comparison)

    assert len(plan.operations) == 1
    operation = plan.operations[0]
    assert operation.operation == OperationType.TRANSFER_VIDEO
    assert operation.target.remote_id == "yt-c"
    assert operation.payload["destination_channel_id"] == "vk-channel"
    assert operation.enabled is False


def test_disabled_collection_plan_creates_missing_album_and_populates_both() -> None:
    source, target = _comparison_fixture()
    comparison = _comparison(source, target)

    plan = build_disabled_collection_plan(target, comparison)

    create_operations = [item for item in plan.operations if item.operation == OperationType.CREATE_COLLECTION]
    add_operations = [item for item in plan.operations if item.operation == OperationType.ADD_TO_COLLECTION]
    assert len(create_operations) == 1
    assert create_operations[0].payload["title"] == "Александр Блок"
    assert len(add_operations) == 2
    assert {item.target.remote_id for item in add_operations} == {"vk-a", "vk-b"}
    assert any(str(item.payload["collection_id"]).startswith("pending:create:") for item in add_operations)
    assert all(item.enabled is False for item in plan.operations)
