from __future__ import annotations

from datetime import UTC, datetime

import pytest

from video_channel_manager.domain.enums import PlatformName
from video_channel_manager.editorial.instagram_media_routing import (
    InstagramMediaRoutingError,
    build_instagram_video_routes,
)
from video_channel_manager.exchange.instagram_video import (
    InstagramMediaReview,
    InstagramVideoIntakeArtifact,
)
from video_channel_manager.local_media import (
    MediaAcquisitionEvidence,
    MediaArtifactEvidence,
    MediaCompatibilityProfile,
    MediaProbeEvidence,
    MediaSourceIdentity,
    calculate_media_manifest_sha256,
)


CHANNEL_ID = "UC-78ys2S3cQ3lpqgXfo-SvQ"
VIDEO_ID = "AAAAAAAAAAA"
INTAKE_SHA = "sha256:" + "1" * 64
MEDIA_SHA = "sha256:" + "2" * 64
STRUCTURED_SHA = "sha256:" + "3" * 64


def _intake(*, reviewed: bool = True) -> InstagramVideoIntakeArtifact:
    reviewed_record = f"content/youtube-comments/{VIDEO_ID}.json" if reviewed else None
    return InstagramVideoIntakeArtifact.model_validate(
        {
            "project_key": "legendary-poet",
            "channel_id": CHANNEL_ID,
            "source_snapshot_id": "00000000-0000-0000-0000-000000000001",
            "source_generated_at": "2026-08-20T00:00:00+00:00",
            "source_evidence": {"audit_package_sha256": "sha256:" + "a" * 64},
            "counts": {
                "current_videos": 1,
                "frozen_mapping_ids": 1,
                "reviewed_editorial_ids": 1 if reviewed else 0,
                "current_also_in_frozen_mapping": 1,
                "new_current_vs_frozen_mapping": 0,
                "historical_mapped_missing_from_current_snapshot": 0,
                "confirmed_short": 0,
                "confirmed_longform": 0,
                "format_unknown": 1,
            },
            "reconciliation": {
                "new_current_ids": [],
                "historical_mapped_missing_from_current_snapshot": [],
                "reviewed_missing_from_current_snapshot": [],
            },
            "classification_policy": {
                "shorts": "fail closed",
                "longform": "fail closed",
                "unknown_is_not_excluded": True,
                "social_delivery_encoding_is_not_source_master": True,
            },
            "records": [
                {
                    "youtube_video_id": VIDEO_ID,
                    "title": "Video",
                    "duration_seconds": 60,
                    "published_at": "2026-08-01T00:00:00+00:00",
                    "privacy_status": "public",
                    "tags": [],
                    "thumbnail_url": None,
                    "revision": "sha256:video-revision",
                    "present_in_frozen_mapping": True,
                    "exact_vk_video_id": "-235216998_1",
                    "reviewed_editorial_record": reviewed_record,
                    "youtube_format_status": "unknown",
                    "source_aspect_ratio": None,
                    "clean_master_status": "unbound",
                    "instagram_route": "source_binding_required",
                    "provider_writes_authorized": False,
                }
            ],
        }
    )


def _media(*, width: int, height: int, method: str = "controlled_master") -> MediaArtifactEvidence:
    path = "/tmp/legendary-poet-master.mp4"
    source = MediaSourceIdentity(
        project_key="legendary-poet",
        platform=PlatformName.YOUTUBE,
        source_channel_id=CHANNEL_ID,
        source_id=VIDEO_ID,
        source_url=f"https://www.youtube.com/watch?v={VIDEO_ID}" if method == "yt_dlp" else None,
        expected_duration_seconds=60.0,
    )
    if method == "yt_dlp":
        acquisition = MediaAcquisitionEvidence(
            method="yt_dlp",
            path_authority="structured_result",
            requested_output_path=path,
            authoritative_final_path=path,
            tool_name="yt-dlp",
            structured_result_sha256=STRUCTURED_SHA,
            result_path_field="requested_downloads[0].filepath",
        )
    else:
        acquisition = MediaAcquisitionEvidence(
            method="controlled_master",
            path_authority="controlled_master",
            requested_output_path=path,
            authoritative_final_path=path,
            tool_name="controlled-master",
        )
    probe = MediaProbeEvidence(
        path=path,
        size_bytes=1_000_000,
        sha256=MEDIA_SHA,
        duration_seconds=60.0,
        format_names=("mp4",),
        video_stream_count=1,
        audio_stream_count=1,
        video_codec="h264",
        audio_codec="aac",
        width=width,
        height=height,
        sample_rate_hz=48_000,
        audio_channels=2,
    )
    provisional = MediaArtifactEvidence(
        source=source,
        acquisition=acquisition,
        profile=MediaCompatibilityProfile(),
        probe=probe,
        manifest_sha256="sha256:" + "0" * 64,
    )
    return provisional.model_copy(update={"manifest_sha256": calculate_media_manifest_sha256(provisional)})


def _review(
    evidence: MediaArtifactEvidence,
    *,
    rights_status: str = "cleared",
    provenance: str = "project_owned_clean_master",
    rebuild: bool = False,
) -> InstagramMediaReview:
    return InstagramMediaReview.model_validate(
        {
            "project_key": "legendary-poet",
            "youtube_channel_id": CHANNEL_ID,
            "youtube_video_id": VIDEO_ID,
            "media_manifest_sha256": evidence.manifest_sha256,
            "rights_status": rights_status,
            "master_provenance": provenance,
            "reviewed_at": datetime(2026, 8, 20, tzinfo=UTC),
            "reviewed_by": "test-reviewer",
            "editorial_rebuild_authorized": rebuild,
        }
    )


def _route(
    intake: InstagramVideoIntakeArtifact,
    *,
    evidence: MediaArtifactEvidence | None = None,
    review: InstagramMediaReview | None = None,
):
    media = {VIDEO_ID: evidence} if evidence is not None else {}
    reviews = {VIDEO_ID: review} if review is not None else {}
    return build_instagram_video_routes(
        intake,
        source_intake_sha256=INTAKE_SHA,
        media_by_video_id=media,
        reviews_by_video_id=reviews,
    )


def test_missing_media_stays_source_binding_required() -> None:
    result = _route(_intake())

    assert result.counts.source_binding_required == 1
    assert result.records[0].route == "source_binding_required"
    assert result.provider_writes_authorized is False


def test_vertical_clean_master_with_cleared_rights_routes_direct_remaster() -> None:
    evidence = _media(width=1080, height=1920)
    result = _route(_intake(), evidence=evidence, review=_review(evidence))

    assert result.records[0].route == "direct_remaster"
    assert result.records[0].source_geometry == "vertical"
    assert result.records[0].media_manifest_sha256 == evidence.manifest_sha256


def test_non_vertical_clean_master_with_cleared_rights_routes_editorial_extract() -> None:
    evidence = _media(width=1920, height=1080)
    result = _route(_intake(), evidence=evidence, review=_review(evidence))

    assert result.records[0].route == "editorial_extract"
    assert result.records[0].source_geometry == "non_vertical"


def test_media_without_exact_rights_review_is_held() -> None:
    evidence = _media(width=1080, height=1920)
    result = _route(_intake(), evidence=evidence)

    assert result.records[0].route == "hold"
    assert result.records[0].reasons == ("media_evidence_present_but_exact_rights_review_missing",)


def test_social_delivery_copy_is_never_promoted_to_clean_master() -> None:
    evidence = _media(width=1080, height=1920, method="yt_dlp")
    review = _review(evidence, provenance="project_owned_clean_master")
    result = _route(_intake(), evidence=evidence, review=review)

    assert result.records[0].route == "hold"
    assert result.records[0].reasons == ("social_delivery_bytes_rejected_as_source_master",)


def test_unknown_media_rights_can_only_fall_back_to_separately_authorized_rebuild() -> None:
    evidence = _media(width=1920, height=1080)
    review = _review(evidence, rights_status="unknown", rebuild=True)
    result = _route(_intake(reviewed=True), evidence=evidence, review=review)

    assert result.records[0].route == "editorial_rebuild"
    assert result.records[0].reviewed_editorial_record is not None


def test_rebuild_requires_reviewed_editorial_authority() -> None:
    evidence = _media(width=1920, height=1080)
    review = _review(evidence, rights_status="unknown", rebuild=True)
    result = _route(_intake(reviewed=False), evidence=evidence, review=review)

    assert result.records[0].route == "hold"


def test_media_source_identity_mismatch_fails_closed() -> None:
    evidence = _media(width=1080, height=1920)
    foreign_source = evidence.source.model_copy(update={"source_id": "BBBBBBBBBBB"})
    provisional = evidence.model_copy(
        update={
            "source": foreign_source,
            "manifest_sha256": "sha256:" + "0" * 64,
        }
    )
    foreign = provisional.model_copy(update={"manifest_sha256": calculate_media_manifest_sha256(provisional)})

    with pytest.raises(InstagramMediaRoutingError, match="media identity mismatch"):
        _route(_intake(), evidence=foreign, review=_review(foreign))
