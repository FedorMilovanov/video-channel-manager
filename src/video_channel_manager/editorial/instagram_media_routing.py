from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

from video_channel_manager.domain.enums import PlatformName
from video_channel_manager.exchange.instagram_video import (
    InstagramMediaReview,
    InstagramSourceGeometry,
    InstagramVideoIntakeArtifact,
    InstagramVideoIntakeRecord,
    InstagramVideoRouteArtifact,
    InstagramVideoRouteRecord,
)
from video_channel_manager.local_media import (
    MediaArtifactError,
    MediaArtifactEvidence,
    validate_media_artifact_evidence,
)


class InstagramMediaRoutingError(ValueError):
    pass


def _validate_media_identity(
    *,
    intake: InstagramVideoIntakeArtifact,
    record: InstagramVideoIntakeRecord,
    evidence: MediaArtifactEvidence,
) -> None:
    try:
        validate_media_artifact_evidence(evidence)
    except MediaArtifactError as exc:
        raise InstagramMediaRoutingError(f"invalid media evidence for {record.youtube_video_id}: {exc}") from exc

    source = evidence.source
    expected = (
        intake.project_key,
        PlatformName.YOUTUBE,
        intake.channel_id,
        record.youtube_video_id,
    )
    actual = (
        source.project_key,
        source.platform,
        source.source_channel_id,
        source.source_id,
    )
    if actual != expected:
        raise InstagramMediaRoutingError(
            f"media identity mismatch for {record.youtube_video_id}: expected={expected!r} actual={actual!r}"
        )
    if record.duration_seconds is not None and source.expected_duration_seconds is not None:
        delta = abs(source.expected_duration_seconds - float(record.duration_seconds))
        if delta > evidence.profile.duration_tolerance_seconds:
            raise InstagramMediaRoutingError(
                f"media expected duration differs from intake for {record.youtube_video_id}: "
                f"delta={delta} tolerance={evidence.profile.duration_tolerance_seconds}"
            )


def _validate_review(
    *,
    intake: InstagramVideoIntakeArtifact,
    record: InstagramVideoIntakeRecord,
    evidence: MediaArtifactEvidence,
    review: InstagramMediaReview,
) -> None:
    expected = (
        intake.project_key,
        intake.channel_id,
        record.youtube_video_id,
        evidence.manifest_sha256,
    )
    actual = (
        review.project_key,
        review.youtube_channel_id,
        review.youtube_video_id,
        review.media_manifest_sha256,
    )
    if actual != expected:
        raise InstagramMediaRoutingError(
            f"media review identity mismatch for {record.youtube_video_id}: expected={expected!r} actual={actual!r}"
        )


def _geometry(evidence: MediaArtifactEvidence) -> InstagramSourceGeometry:
    width = evidence.probe.width
    height = evidence.probe.height
    if width is None or height is None:
        return "unknown"
    return "vertical" if height > width else "non_vertical"


def _rebuild_allowed(record: InstagramVideoIntakeRecord, review: InstagramMediaReview) -> bool:
    return review.editorial_rebuild_authorized and record.reviewed_editorial_record is not None


def _base_record_payload(
    *,
    record: InstagramVideoIntakeRecord,
    evidence: MediaArtifactEvidence,
    geometry: InstagramSourceGeometry,
) -> dict[str, Any]:
    return {
        "youtube_video_id": record.youtube_video_id,
        "title": record.title,
        "source_geometry": geometry,
        "media_manifest_sha256": evidence.manifest_sha256,
        "media_sha256": evidence.probe.sha256,
        "width": evidence.probe.width,
        "height": evidence.probe.height,
        "acquisition_method": evidence.acquisition.method,
        "reviewed_editorial_record": record.reviewed_editorial_record,
    }


def _route_with_evidence(
    *,
    intake: InstagramVideoIntakeArtifact,
    record: InstagramVideoIntakeRecord,
    evidence: MediaArtifactEvidence,
    review: InstagramMediaReview | None,
) -> InstagramVideoRouteRecord:
    _validate_media_identity(intake=intake, record=record, evidence=evidence)
    geometry = _geometry(evidence)
    common = _base_record_payload(record=record, evidence=evidence, geometry=geometry)

    if review is None:
        return InstagramVideoRouteRecord(
            **common,
            route="hold",
            reasons=("media_evidence_present_but_exact_rights_review_missing",),
        )

    _validate_review(intake=intake, record=record, evidence=evidence, review=review)
    reviewed = {
        **common,
        "rights_status": review.rights_status,
        "master_provenance": review.master_provenance,
    }

    if evidence.acquisition.method == "yt_dlp" or review.master_provenance == "social_delivery_copy":
        if _rebuild_allowed(record, review):
            return InstagramVideoRouteRecord(
                **reviewed,
                route="editorial_rebuild",
                reasons=("social_delivery_bytes_rejected_as_source_master", "source_led_rebuild_separately_authorized"),
            )
        return InstagramVideoRouteRecord(
            **reviewed,
            route="hold",
            reasons=("social_delivery_bytes_rejected_as_source_master",),
        )

    if review.rights_status != "cleared":
        if review.rights_status == "unknown" and _rebuild_allowed(record, review):
            return InstagramVideoRouteRecord(
                **reviewed,
                route="editorial_rebuild",
                reasons=("media_reuse_rights_not_cleared", "source_led_rebuild_separately_authorized"),
            )
        return InstagramVideoRouteRecord(
            **reviewed,
            route="hold",
            reasons=(f"media_reuse_rights_{review.rights_status}",),
        )

    if review.master_provenance not in {
        "project_owned_clean_master",
        "derived_from_project_owned_master",
    }:
        if _rebuild_allowed(record, review):
            return InstagramVideoRouteRecord(
                **reviewed,
                route="editorial_rebuild",
                reasons=("clean_master_provenance_not_proved", "source_led_rebuild_separately_authorized"),
            )
        return InstagramVideoRouteRecord(
            **reviewed,
            route="hold",
            reasons=("clean_master_provenance_not_proved",),
        )

    if geometry == "vertical":
        return InstagramVideoRouteRecord(
            **reviewed,
            route="direct_remaster",
            reasons=("rights_cleared", "clean_master_provenance_proved", "vertical_source_geometry"),
        )
    if geometry == "non_vertical":
        return InstagramVideoRouteRecord(
            **reviewed,
            route="editorial_extract",
            reasons=("rights_cleared", "clean_master_provenance_proved", "non_vertical_source_requires_reframing"),
        )
    return InstagramVideoRouteRecord(
        **reviewed,
        route="hold",
        reasons=("source_geometry_unknown",),
    )


def build_instagram_video_routes(
    intake: InstagramVideoIntakeArtifact,
    *,
    source_intake_sha256: str,
    media_by_video_id: Mapping[str, MediaArtifactEvidence],
    reviews_by_video_id: Mapping[str, InstagramMediaReview],
) -> InstagramVideoRouteArtifact:
    """Route every intake video without performing provider or media mutations."""

    intake_ids = {record.youtube_video_id for record in intake.records}
    foreign_media = sorted(set(media_by_video_id) - intake_ids)
    foreign_reviews = sorted(set(reviews_by_video_id) - intake_ids)
    if foreign_media:
        raise InstagramMediaRoutingError(f"media evidence contains IDs outside intake: {foreign_media}")
    if foreign_reviews:
        raise InstagramMediaRoutingError(f"media reviews contain IDs outside intake: {foreign_reviews}")

    orphan_reviews = sorted(set(reviews_by_video_id) - set(media_by_video_id))
    if orphan_reviews:
        raise InstagramMediaRoutingError(f"media reviews have no exact media evidence: {orphan_reviews}")

    routed: list[InstagramVideoRouteRecord] = []
    for record in intake.records:
        evidence = media_by_video_id.get(record.youtube_video_id)
        if evidence is None:
            routed.append(
                InstagramVideoRouteRecord(
                    youtube_video_id=record.youtube_video_id,
                    title=record.title,
                    route="source_binding_required",
                    reasons=("no_exact_media_artifact_evidence",),
                    source_geometry="unknown",
                    reviewed_editorial_record=record.reviewed_editorial_record,
                )
            )
            continue
        routed.append(
            _route_with_evidence(
                intake=intake,
                record=record,
                evidence=evidence,
                review=reviews_by_video_id.get(record.youtube_video_id),
            )
        )

    dispositions = Counter(record.route for record in routed)
    return InstagramVideoRouteArtifact(
        project_key=intake.project_key,
        channel_id=intake.channel_id,
        source_intake_sha256=source_intake_sha256,
        counts={
            "total": len(routed),
            "source_binding_required": dispositions["source_binding_required"],
            "direct_remaster": dispositions["direct_remaster"],
            "editorial_extract": dispositions["editorial_extract"],
            "editorial_rebuild": dispositions["editorial_rebuild"],
            "hold": dispositions["hold"],
        },
        records=tuple(routed),
    )
