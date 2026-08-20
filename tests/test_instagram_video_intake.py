from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

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


def _build(audit: AuditPackage, **kwargs: Any) -> dict[str, Any]:
    return build_instagram_video_intake(
        audit,
        project_key=LEGENDARY_POET,
        frozen_youtube_vk_mapping={},
        source_audit_sha256=AUDIT_SHA,
        **kwargs,
    )


def _file_details(
    *,
    width: int,
    height: int,
    duration_ms: int,
    creation_time: str | None = "2026-08-01T00:00:00Z",
) -> dict[str, Any]:
    details: dict[str, Any] = {
        "durationMs": str(duration_ms),
        "videoStreams": [{"widthPixels": width, "heightPixels": height}],
    }
    if creation_time is not None:
        details["creationTime"] = creation_time
    return {"fileDetails": details}


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
        "confirmed_longform": 1,
        "format_unknown": 1,
        "short_candidates": 0,
        "file_details_available": 0,
        "source_geometry_known": 0,
    }
    assert result["reconciliation"]["new_current_ids"] == ["CCCCCCCCCCC"]
    assert result["reconciliation"]["historical_mapped_missing_from_current_snapshot"] == ["BBBBBBBBBBB"]

    first = result["records"][0]
    assert first["exact_vk_video_id"] == "-235216998_1"
    assert first["reviewed_editorial_record"] == "content/youtube-comments/AAAAAAAAAAA.json"
    assert first["youtube_format_status"] == "unknown"
    assert first["provider_writes_authorized"] is False


def test_short_duration_alone_never_promotes_video_to_confirmed_short() -> None:
    audit = _audit(VideoRecord(ref=_ref("AAAAAAAAAAA"), title="55 sec", duration_seconds=55, revision="a"))

    result = _build(audit)

    record = result["records"][0]
    assert record["youtube_format_status"] == "unknown"
    assert record["youtube_short_candidate"] is False
    assert record["youtube_format_reason"] == "insufficient_exact_surface_evidence"
    assert result["counts"]["confirmed_short"] == 0
    assert result["counts"]["format_unknown"] == 1


def test_duration_over_three_minutes_confirms_longform_without_geometry() -> None:
    audit = _audit(VideoRecord(ref=_ref("AAAAAAAAAAA"), title="Long", duration_seconds=181, revision="a"))

    result = _build(audit)

    record = result["records"][0]
    assert record["youtube_format_status"] == "longform"
    assert record["youtube_format_reason"] == "duration_exceeds_current_three_minute_shorts_cap"
    assert result["counts"]["confirmed_longform"] == 1


def test_landscape_owner_file_details_confirm_longform_even_when_short_duration() -> None:
    audit = _audit(
        VideoRecord(
            ref=_ref("AAAAAAAAAAA"),
            title="Landscape",
            duration_seconds=55,
            revision="a",
            metadata=_file_details(width=1920, height=1080, duration_ms=55_400),
        )
    )

    result = _build(audit)

    record = result["records"][0]
    assert record["youtube_format_status"] == "longform"
    assert record["youtube_format_reason"] == "owner_file_details_prove_landscape_source_geometry"
    assert record["youtube_file_details_available"] is True
    assert record["youtube_source_geometry"] == "landscape"
    assert record["youtube_source_width_pixels"] == 1920
    assert record["youtube_source_height_pixels"] == 1080
    assert record["youtube_source_duration_ms"] == 55_400
    assert record["youtube_source_creation_time"] == "2026-08-01T00:00:00Z"


def test_post_universal_cutoff_vertical_under_three_minutes_is_confirmed_short() -> None:
    audit = _audit(
        VideoRecord(
            ref=_ref("AAAAAAAAAAA"),
            title="Confirmed Short",
            duration_seconds=120,
            revision="a",
            metadata=_file_details(width=1080, height=1920, duration_ms=120_250),
        )
    )

    result = _build(audit)

    record = result["records"][0]
    assert record["youtube_format_status"] == "short"
    assert record["youtube_short_candidate"] is False
    assert record["youtube_source_geometry"] == "square_or_vertical"
    assert record["youtube_format_reason"] == (
        "owner_file_creation_time_proves_post_universal_three_minute_shorts_cutoff"
    )
    assert result["counts"]["confirmed_short"] == 1
    assert result["counts"]["format_unknown"] == 0


def test_pre_universal_cutoff_vertical_under_three_minutes_remains_short_candidate() -> None:
    audit = _audit(
        VideoRecord(
            ref=_ref("AAAAAAAAAAA"),
            title="Candidate",
            duration_seconds=120,
            revision="a",
            metadata=_file_details(
                width=1080,
                height=1920,
                duration_ms=120_250,
                creation_time="2025-01-01T00:00:00Z",
            ),
        )
    )

    result = _build(audit)

    record = result["records"][0]
    assert record["youtube_format_status"] == "unknown"
    assert record["youtube_short_candidate"] is True
    assert record["youtube_format_reason"] == (
        "short_geometry_and_duration_proved_but_post_cutoff_upload_not_yet_proved"
    )
    assert result["counts"]["short_candidates"] == 1
    assert result["counts"]["confirmed_short"] == 0


def test_missing_file_creation_time_keeps_vertical_under_three_minutes_as_candidate() -> None:
    audit = _audit(
        VideoRecord(
            ref=_ref("AAAAAAAAAAA"),
            title="Candidate without file creation time",
            duration_seconds=120,
            revision="a",
            metadata=_file_details(width=1080, height=1920, duration_ms=120_250, creation_time=None),
        )
    )

    result = _build(audit)

    record = result["records"][0]
    assert record["youtube_format_status"] == "unknown"
    assert record["youtube_short_candidate"] is True


def test_vertical_owner_duration_over_three_minutes_confirms_longform() -> None:
    audit = _audit(
        VideoRecord(
            ref=_ref("AAAAAAAAAAA"),
            title="Vertical long",
            duration_seconds=181,
            revision="a",
            metadata=_file_details(width=1080, height=1920, duration_ms=181_001),
        )
    )

    result = _build(audit)

    assert result["records"][0]["youtube_format_status"] == "longform"
    assert result["records"][0]["youtube_short_candidate"] is False


def test_conflicting_owner_stream_orientations_stay_unknown() -> None:
    audit = _audit(
        VideoRecord(
            ref=_ref("AAAAAAAAAAA"),
            title="Ambiguous streams",
            duration_seconds=120,
            revision="a",
            metadata={
                "fileDetails": {
                    "durationMs": "120000",
                    "videoStreams": [
                        {"widthPixels": 1080, "heightPixels": 1920},
                        {"widthPixels": 1920, "heightPixels": 1080},
                    ],
                }
            },
        )
    )

    result = _build(audit)

    record = result["records"][0]
    assert record["youtube_source_geometry"] == "unknown"
    assert record["youtube_source_width_pixels"] is None
    assert record["youtube_source_height_pixels"] is None
    assert record["youtube_format_status"] == "unknown"
    assert record["youtube_short_candidate"] is False


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
