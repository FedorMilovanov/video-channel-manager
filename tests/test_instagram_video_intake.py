from __future__ import annotations

from datetime import UTC, datetime

import pytest

from video_channel_manager.domain.enums import ChannelKind, PlatformName
from video_channel_manager.domain.models import ChannelRecord, RemoteRef, VideoRecord
from video_channel_manager.editorial._project_profiles import LEGENDARY_POET
from video_channel_manager.editorial.instagram_video_intake import (
    InstagramVideoIntakeError,
    build_instagram_video_intake,
)
from video_channel_manager.exchange.audit_package import AuditPackage


CHANNEL_ID = "UC-78ys2S3cQ3lpqgXfo-SvQ"
AUDIT_SHA = "sha256:" + "a" * 64
MAPPING_SHA = "sha256:" + "b" * 64
REVIEWED_SHA = "sha256:" + "c" * 64


def _ref(remote_id: str, *, channel_id: str = CHANNEL_ID) -> RemoteRef:
    return RemoteRef(platform=PlatformName.YOUTUBE, channel_id=channel_id, remote_id=remote_id)


def _audit(*videos: VideoRecord, channel_id: str = CHANNEL_ID) -> AuditPackage:
    return AuditPackage(
        generated_at=datetime(2026, 8, 20, tzinfo=UTC),
        channel=ChannelRecord(
            ref=_ref(channel_id, channel_id=channel_id),
            title="The Legendary Poet",
            kind=ChannelKind.VIDEO_CHANNEL,
        ),
        videos=list(videos),
    )


def _build(audit: AuditPackage, **kwargs: object) -> dict[str, object]:
    return build_instagram_video_intake(
        audit,
        project_key=LEGENDARY_POET,
        frozen_youtube_vk_mapping={},
        source_audit_sha256=AUDIT_SHA,
        **kwargs,
    )


def test_build_intake_reconciles_current_new_and_historical_ids() -> None:
    audit = _audit(
        VideoRecord(
            ref=_ref("AAAAAAAAAAA"),
            title="Mapped reviewed video",
            duration_seconds=55,
            published_at=datetime(2026, 7, 1, tzinfo=UTC),
            privacy_status="public",
            tags=["poetry"],
            revision="sha256:a",
        ),
        VideoRecord(
            ref=_ref("CCCCCCCCCCC"),
            title="New current video",
            duration_seconds=600,
            revision="sha256:c",
        ),
    )

    result = build_instagram_video_intake(
        audit,
        project_key=LEGENDARY_POET,
        frozen_youtube_vk_mapping={
            "AAAAAAAAAAA": "-235216998_1",
            "BBBBBBBBBBB": "-235216998_2",
        },
        reviewed_video_ids={"AAAAAAAAAAA"},
        source_audit_sha256=AUDIT_SHA,
        frozen_mapping_sha256=MAPPING_SHA,
        reviewed_corpus_sha256=REVIEWED_SHA,
    )

    assert result["status"] == "provider-inert"
    assert result["provider_effect"] == "impossible"
    assert result["provider_writes_authorized"] is False
    assert result["project_key"] == LEGENDARY_POET
    assert result["source_evidence"] == {
        "audit_package_sha256": AUDIT_SHA,
        "frozen_mapping_sha256": MAPPING_SHA,
        "reviewed_corpus_sha256": REVIEWED_SHA,
    }
    assert result["counts"] == {
        "current_videos": 2,
        "frozen_mapping_ids": 2,
        "reviewed_editorial_ids": 1,
        "current_also_in_frozen_mapping": 1,
        "new_current_vs_frozen_mapping": 1,
        "historical_mapped_missing_from_current_snapshot": 1,
        "confirmed_short": 0,
        "confirmed_longform": 0,
        "format_unknown": 2,
    }
    assert result["reconciliation"]["new_current_ids"] == ["CCCCCCCCCCC"]
    assert result["reconciliation"]["historical_mapped_missing_from_current_snapshot"] == ["BBBBBBBBBBB"]

    first = result["records"][0]
    assert first["exact_vk_video_id"] == "-235216998_1"
    assert first["reviewed_editorial_record"] == "content/youtube-comments/AAAAAAAAAAA.json"
    assert first["youtube_format_status"] == "unknown"
    assert first["provider_writes_authorized"] is False


def test_duration_never_promotes_video_to_confirmed_short_or_longform() -> None:
    audit = _audit(
        VideoRecord(ref=_ref("AAAAAAAAAAA"), title="55 sec", duration_seconds=55, revision="a"),
        VideoRecord(ref=_ref("BBBBBBBBBBB"), title="10 min", duration_seconds=600, revision="b"),
    )

    result = _build(audit)

    assert {record["youtube_format_status"] for record in result["records"]} == {"unknown"}
    assert result["counts"]["confirmed_short"] == 0
    assert result["counts"]["confirmed_longform"] == 0
    assert result["counts"]["format_unknown"] == 2


def test_project_channel_guard_is_fail_closed() -> None:
    audit = _audit(channel_id="UC_OTHER")

    with pytest.raises(InstagramVideoIntakeError, match="unexpected YouTube channel"):
        _build(audit)


def test_unknown_project_is_rejected() -> None:
    with pytest.raises(InstagramVideoIntakeError, match="unknown project_key"):
        build_instagram_video_intake(
            _audit(),
            project_key="unknown-project",
            frozen_youtube_vk_mapping={},
            source_audit_sha256=AUDIT_SHA,
        )


def test_evidence_digest_must_be_exact_sha256() -> None:
    with pytest.raises(InstagramVideoIntakeError, match="source_audit_sha256"):
        build_instagram_video_intake(
            _audit(),
            project_key=LEGENDARY_POET,
            frozen_youtube_vk_mapping={},
            source_audit_sha256="sha256:not-a-digest",
        )
