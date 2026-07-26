from uuid import uuid4

import pytest
from pydantic import ValidationError

from video_channel_manager.domain.enums import ChannelKind, CollectionKind, PlatformName
from video_channel_manager.domain.models import (
    ChannelRecord,
    CollectionMembership,
    CollectionRecord,
    RemoteRef,
    VideoRecord,
)
from video_channel_manager.exchange.audit_package import AuditPackage


def ref(remote_id: str) -> RemoteRef:
    return RemoteRef(platform=PlatformName.YOUTUBE, channel_id="UC1", remote_id=remote_id)


def test_audit_package_accepts_linked_membership() -> None:
    package = AuditPackage(
        channel=ChannelRecord(ref=ref("UC1"), title="Channel", kind=ChannelKind.VIDEO_CHANNEL),
        videos=[VideoRecord(ref=ref("v1"), title="Video", revision="rev-v1")],
        collections=[
            CollectionRecord(ref=ref("p1"), title="Playlist", kind=CollectionKind.PLAYLIST, revision="rev-p1")
        ],
        memberships=[CollectionMembership(collection_ref=ref("p1"), video_ref=ref("v1"))],
    )
    assert package.snapshot_id != uuid4()


def test_audit_package_rejects_unknown_membership_video() -> None:
    with pytest.raises(ValidationError, match="unknown video"):
        AuditPackage(
            channel=ChannelRecord(ref=ref("UC1"), title="Channel", kind=ChannelKind.VIDEO_CHANNEL),
            collections=[
                CollectionRecord(ref=ref("p1"), title="Playlist", kind=CollectionKind.PLAYLIST, revision="rev")
            ],
            memberships=[CollectionMembership(collection_ref=ref("p1"), video_ref=ref("missing"))],
        )
