from uuid import UUID

import pytest

from video_channel_manager.application.catalog_identity import (
    build_catalog_identity_evidence,
    validate_catalog_identity_evidence,
)
from video_channel_manager.domain.enums import (
    ChannelKind,
    CollectionKind,
    PlatformName,
)
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


def _video(
    platform: PlatformName,
    channel_id: str,
    remote_id: str,
    title: str,
) -> VideoRecord:
    return VideoRecord(
        ref=_ref(platform, channel_id, remote_id),
        title=title,
        duration_seconds=120,
        privacy_status="public",
        revision=f"sha256:{remote_id}",
    )


def _collection(
    platform: PlatformName,
    channel_id: str,
    remote_id: str,
    title: str,
) -> CollectionRecord:
    kind = (
        CollectionKind.PLAYLIST
        if platform == PlatformName.YOUTUBE
        else CollectionKind.VIDEO_ALBUM
    )
    return CollectionRecord(
        ref=_ref(platform, channel_id, remote_id),
        title=title,
        kind=kind,
        revision=f"sha256:{remote_id}",
    )


def _audit(
    platform: PlatformName,
    channel_id: str,
    *,
    snapshot_id: str,
    videos: list[VideoRecord],
    collections: list[CollectionRecord],
    memberships: list[tuple[str, str, int]],
) -> AuditPackage:
    kind = (
        ChannelKind.VIDEO_CHANNEL
        if platform == PlatformName.YOUTUBE
        else ChannelKind.COMMUNITY
    )
    return AuditPackage(
        snapshot_id=UUID(snapshot_id),
        channel=ChannelRecord(
            ref=_ref(platform, channel_id, channel_id),
            title=channel_id,
            kind=kind,
        ),
        videos=videos,
        collections=collections,
        memberships=[
            CollectionMembership(
                collection_ref=_ref(platform, channel_id, collection_id),
                video_ref=_ref(platform, channel_id, video_id),
                position=position,
            )
            for collection_id, video_id, position in memberships
        ],
    )


def _source(
    *,
    memberships: list[tuple[str, str, int]] | None = None,
) -> AuditPackage:
    return _audit(
        PlatformName.YOUTUBE,
        "UC-source",
        snapshot_id="00000000-0000-0000-0000-000000000001",
        videos=[
            _video(PlatformName.YOUTUBE, "UC-source", "yt-1", "Первое"),
            _video(PlatformName.YOUTUBE, "UC-source", "yt-2", "Второе"),
        ],
        collections=[
            _collection(
                PlatformName.YOUTUBE,
                "UC-source",
                "playlist-1",
                "Сергей Есенин",
            )
        ],
        memberships=(
            memberships
            if memberships is not None
            else [("playlist-1", "yt-1", 0), ("playlist-1", "yt-2", 1)]
        ),
    )


def _target(
    *,
    collections: list[CollectionRecord] | None = None,
    memberships: list[tuple[str, str, int]] | None = None,
) -> AuditPackage:
    return _audit(
        PlatformName.VK,
        "235216998",
        snapshot_id="00000000-0000-0000-0000-000000000002",
        videos=[
            _video(PlatformName.VK, "235216998", "vk-1", "Первое"),
            _video(PlatformName.VK, "235216998", "vk-2", "Второе"),
            _video(PlatformName.VK, "235216998", "vk-extra", "Лишнее"),
        ],
        collections=(
            collections
            if collections is not None
            else [
                _collection(
                    PlatformName.VK,
                    "235216998",
                    "album-1",
                    "Сергей Есенин",
                )
            ]
        ),
        memberships=memberships or [],
    )


def test_reviewed_mapping_uses_exact_id_and_ignores_position_order() -> None:
    source = _source(
        memberships=[
            ("playlist-1", "yt-2", 50),
            ("playlist-1", "yt-1", 5),
        ]
    )
    target = _target(
        memberships=[
            ("album-1", "vk-1", 100),
            ("album-1", "vk-2", 1),
        ]
    )

    evidence = build_catalog_identity_evidence(
        source,
        target,
        project_key="legendary-poet",
        video_mapping={"yt-1": "vk-1", "yt-2": "vk-2"},
        reviewed_collection_mappings={"playlist-1": "album-1"},
    )

    decision = evidence.decisions[0]
    assert decision.decision == "mapped"
    assert decision.missing_target_video_ids == []
    assert decision.extra_target_video_ids == []
    assert decision.actual_target_video_ids == ["vk-1", "vk-2"]
    validate_catalog_identity_evidence(evidence)


def test_reviewed_mapping_records_missing_and_extra_semantic_membership() -> None:
    target = _target(
        memberships=[
            ("album-1", "vk-1", 0),
            ("album-1", "vk-extra", 1),
        ]
    )

    evidence = build_catalog_identity_evidence(
        _source(),
        target,
        project_key="legendary-poet",
        video_mapping={"yt-1": "vk-1", "yt-2": "vk-2"},
        reviewed_collection_mappings={"playlist-1": "album-1"},
    )

    decision = evidence.decisions[0]
    assert decision.missing_target_video_ids == ["vk-2"]
    assert decision.extra_target_video_ids == ["vk-extra"]


def test_same_title_existing_album_is_conflict_without_reviewed_id() -> None:
    evidence = build_catalog_identity_evidence(
        _source(),
        _target(),
        project_key="legendary-poet",
        video_mapping={"yt-1": "vk-1", "yt-2": "vk-2"},
    )

    decision = evidence.decisions[0]
    assert decision.decision == "conflict"
    assert decision.conflict_reason == "unreviewed_existing_candidate"
    assert [item.remote_id for item in decision.candidate_target_refs] == [
        "album-1"
    ]
    assert decision.missing_target_video_ids == []


def test_duplicate_canonical_album_titles_are_conflict() -> None:
    target = _target(
        collections=[
            _collection(
                PlatformName.VK,
                "235216998",
                "album-1",
                "Сергей Есенин",
            ),
            _collection(
                PlatformName.VK,
                "235216998",
                "album-2",
                "Сергей — Есенин",
            ),
        ]
    )

    evidence = build_catalog_identity_evidence(
        _source(),
        target,
        project_key="legendary-poet",
        video_mapping={"yt-1": "vk-1", "yt-2": "vk-2"},
    )

    decision = evidence.decisions[0]
    assert decision.decision == "conflict"
    assert decision.conflict_reason == "duplicate_canonical_target_title"
    assert [item.remote_id for item in decision.candidate_target_refs] == [
        "album-1",
        "album-2",
    ]


def test_create_requires_explicit_approval_and_no_existing_candidate() -> None:
    empty_target = _target(collections=[])

    blocked = build_catalog_identity_evidence(
        _source(),
        empty_target,
        project_key="legendary-poet",
        video_mapping={"yt-1": "vk-1", "yt-2": "vk-2"},
    )
    allowed = build_catalog_identity_evidence(
        _source(),
        empty_target,
        project_key="legendary-poet",
        video_mapping={"yt-1": "vk-1", "yt-2": "vk-2"},
        approved_collection_creates={"playlist-1"},
    )

    assert blocked.decisions[0].conflict_reason == "creation_not_approved"
    assert allowed.decisions[0].decision == "create"
    assert allowed.decisions[0].missing_target_video_ids == ["vk-1", "vk-2"]


def test_approved_create_is_blocked_by_existing_candidate() -> None:
    evidence = build_catalog_identity_evidence(
        _source(),
        _target(),
        project_key="legendary-poet",
        video_mapping={"yt-1": "vk-1", "yt-2": "vk-2"},
        approved_collection_creates={"playlist-1"},
    )

    assert evidence.decisions[0].decision == "conflict"
    assert (
        evidence.decisions[0].conflict_reason
        == "approved_create_conflicts_with_target"
    )


def test_reviewed_renamed_album_remains_exact_mapping_with_title_drift() -> None:
    target = _target(
        collections=[
            _collection(
                PlatformName.VK,
                "235216998",
                "album-1",
                "Есенин — архив",
            )
        ]
    )

    evidence = build_catalog_identity_evidence(
        _source(),
        target,
        project_key="legendary-poet",
        video_mapping={"yt-1": "vk-1", "yt-2": "vk-2"},
        reviewed_collection_mappings={"playlist-1": "album-1"},
    )

    decision = evidence.decisions[0]
    assert decision.decision == "mapped"
    assert decision.target_ref is not None
    assert decision.target_ref.remote_id == "album-1"
    assert decision.title_drift is True


def test_unknown_and_reused_reviewed_collection_ids_fail_closed() -> None:
    with pytest.raises(ValueError, match="unknown source collection"):
        build_catalog_identity_evidence(
            _source(),
            _target(),
            project_key="legendary-poet",
            video_mapping={},
            reviewed_collection_mappings={"missing": "album-1"},
        )

    source = _audit(
        PlatformName.YOUTUBE,
        "UC-source",
        snapshot_id="00000000-0000-0000-0000-000000000001",
        videos=[],
        collections=[
            _collection(
                PlatformName.YOUTUBE,
                "UC-source",
                "playlist-1",
                "Один",
            ),
            _collection(
                PlatformName.YOUTUBE,
                "UC-source",
                "playlist-2",
                "Два",
            ),
        ],
        memberships=[],
    )
    with pytest.raises(ValueError, match="reuse target collection"):
        build_catalog_identity_evidence(
            source,
            _target(),
            project_key="legendary-poet",
            video_mapping={},
            reviewed_collection_mappings={
                "playlist-1": "album-1",
                "playlist-2": "album-1",
            },
        )


def test_catalog_identity_digest_detects_tampering() -> None:
    evidence = build_catalog_identity_evidence(
        _source(),
        _target(),
        project_key="legendary-poet",
        video_mapping={"yt-1": "vk-1", "yt-2": "vk-2"},
        reviewed_collection_mappings={"playlist-1": "album-1"},
    )

    tampered = evidence.model_copy(update={"digest": "0" * 64})
    with pytest.raises(ValueError, match="digest"):
        validate_catalog_identity_evidence(tampered)
