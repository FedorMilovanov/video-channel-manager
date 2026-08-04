from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any

import pytest
from pydantic import ValidationError

from video_channel_manager.application.catalog_identity import (
    CatalogIdentityEvidence,
    CollectionIdentityDecision,
    calculate_catalog_identity_digest,
)
from video_channel_manager.application.cross_platform.models import (
    CrossPlatformComparison,
    MatchConflict,
    MissingVideo,
    VideoMatch,
)
from video_channel_manager.application.identity import (
    canonicalize_collection_title,
    canonicalize_description,
    canonicalize_identity_title,
)
from video_channel_manager.domain.enums import PlatformName
from video_channel_manager.domain.models import RemoteRef
from video_channel_manager.local_media.artifact import (
    MediaAcquisitionEvidence,
    MediaArtifactEvidence,
    MediaCompatibilityProfile,
    MediaProbeEvidence,
    MediaSourceIdentity,
    calculate_media_manifest_sha256,
)
from video_channel_manager.platforms.vk.thumbnail_lifecycle import (
    ThumbnailOperationRecord,
    ThumbnailStatus,
)
from video_channel_manager.platforms.vk.upload_lifecycle import (
    UploadStage,
    VkUploadReadiness,
    create_upload_record,
)
from video_channel_manager.platforms.vk.upload_media import journal_media_evidence
from video_channel_manager.wave_engine.integration import (
    INTEGRATION_RULESET,
    IntegrationEvidenceError,
    IntegrationOutcome,
    build_operation_integration_evidence,
)
from video_channel_manager.wave_engine.models import (
    EvidenceArtifact,
    MutationClass,
    OperationStatus,
    ProjectBinding,
    WaveOperationResult,
    WaveOperationSpec,
    WavePlan,
    WaveResult,
    WaveSourceEvidence,
    WaveStatus,
)

PROJECT = ProjectBinding(project_key="legendary-poet", community_id=235216998, owner_id=-235216998)
SOURCE_CHANNEL = RemoteRef(
    platform=PlatformName.YOUTUBE,
    channel_id="UC-78ys2S3cQ3lpqgXfo-SvQ",
    remote_id="UC-78ys2S3cQ3lpqgXfo-SvQ",
)
TARGET_CHANNEL = RemoteRef(
    platform=PlatformName.VK,
    channel_id="235216998",
    remote_id="-235216998",
)
SOURCE_SNAPSHOT = "youtube-snapshot-2026-08-04"
TARGET_SNAPSHOT = "vk-snapshot-2026-08-04"


def _catalog(
    *,
    decisions: list[CollectionIdentityDecision] | None = None,
) -> CatalogIdentityEvidence:
    provisional = CatalogIdentityEvidence(
        project_key=PROJECT.project_key,
        source_snapshot_id=SOURCE_SNAPSHOT,
        target_snapshot_id=TARGET_SNAPSHOT,
        source_channel=SOURCE_CHANNEL,
        target_channel=TARGET_CHANNEL,
        decisions=decisions or [],
        digest="pending",
    )
    return provisional.model_copy(update={"digest": calculate_catalog_identity_digest(provisional)})


def _mapped_video(source_id: str, target_id: str) -> VideoMatch:
    title = "Exact title"
    description = "Exact description"
    return VideoMatch(
        source_ref=RemoteRef(platform=PlatformName.YOUTUBE, channel_id=SOURCE_CHANNEL.channel_id, remote_id=source_id),
        target_ref=RemoteRef(platform=PlatformName.VK, channel_id=TARGET_CHANNEL.channel_id, remote_id=target_id),
        source_title=title,
        target_title=title,
        source_title_identity=canonicalize_identity_title(title),
        target_title_identity=canonicalize_identity_title(title),
        source_description_identity=canonicalize_description(description),
        target_description_identity=canonicalize_description(description),
        score=1.0,
        duration_delta_seconds=0,
        exact_normalized_title=True,
        exact_description=True,
        match_method="reviewed_mapping",
    )


def _missing_video(source_id: str) -> MissingVideo:
    title = f"Missing {source_id}"
    return MissingVideo(
        ref=RemoteRef(platform=PlatformName.YOUTUBE, channel_id=SOURCE_CHANNEL.channel_id, remote_id=source_id),
        title=title,
        title_identity=canonicalize_identity_title(title),
        duration_seconds=120,
        privacy_status="public",
    )


def _comparison(
    *,
    matches: list[VideoMatch] | None = None,
    missing: list[MissingVideo] | None = None,
    conflicts: list[MatchConflict] | None = None,
    catalog: CatalogIdentityEvidence | None = None,
) -> CrossPlatformComparison:
    return CrossPlatformComparison(
        source_snapshot_id=SOURCE_SNAPSHOT,
        target_snapshot_id=TARGET_SNAPSHOT,
        source_channel=SOURCE_CHANNEL,
        target_channel=TARGET_CHANNEL,
        matches=matches or [],
        missing_on_target=missing or [],
        conflicts=conflicts or [],
        catalog_identity=catalog or _catalog(),
    )


def _wave_plan(specs: tuple[WaveOperationSpec, ...]) -> WavePlan:
    source = WaveSourceEvidence.build(
        project=PROJECT,
        policy_version="wave-8f-test-v1",
        artifacts=(EvidenceArtifact(path="fixtures/source.json", sha256="a" * 64),),
    )
    return WavePlan.build(source=source, specs=specs)


def _spec(source_id: str, stage: str, order: int) -> WaveOperationSpec:
    return WaveOperationSpec(
        order_key=f"{order:02d}-{source_id}-{stage}",
        operation_kind=f"wave8f_{stage}",
        mutation_class=MutationClass.AMBIGUOUS_MUTATION,
        payload={"source_video_id": source_id, "integration_stage": stage},
    )


def _result(
    plan: WavePlan,
    statuses: tuple[OperationStatus, ...],
) -> WaveResult:
    operation_results: list[WaveOperationResult] = []
    for operation, status in zip(plan.operations, statuses, strict=True):
        if status is OperationStatus.SUCCEEDED:
            operation_results.append(
                WaveOperationResult(
                    operation_id=operation.operation_id,
                    status=status,
                    attempt_count=1,
                    retry_safe=False,
                    unknown_requires_reconciliation=False,
                    evidence={"proof": "mocked-self-test"},
                )
            )
        elif status is OperationStatus.UNKNOWN_REQUIRES_RECONCILIATION:
            operation_results.append(
                WaveOperationResult(
                    operation_id=operation.operation_id,
                    status=status,
                    attempt_count=1,
                    retry_safe=False,
                    unknown_requires_reconciliation=True,
                    evidence={"proof": "mocked-unknown"},
                    error_kind="ambiguous_provider_outcome",
                    error_message="mocked unknown outcome",
                )
            )
        elif status is OperationStatus.FAILED:
            operation_results.append(
                WaveOperationResult(
                    operation_id=operation.operation_id,
                    status=status,
                    attempt_count=1,
                    retry_safe=True,
                    unknown_requires_reconciliation=False,
                    evidence={"proof": "rejected-before-dispatch"},
                    error_kind="rejected_before_dispatch",
                    error_message="mocked later-stage rejection",
                )
            )
        elif status is OperationStatus.NOT_ATTEMPTED:
            operation_results.append(
                WaveOperationResult(
                    operation_id=operation.operation_id,
                    status=status,
                    attempt_count=0,
                    retry_safe=False,
                    unknown_requires_reconciliation=False,
                    evidence={"proof": "terminal-stage-not-attempted"},
                )
            )
        else:
            raise AssertionError(status)
    if OperationStatus.UNKNOWN_REQUIRES_RECONCILIATION in statuses:
        wave_status = WaveStatus.UNKNOWN_REQUIRES_RECONCILIATION
    elif OperationStatus.FAILED in statuses:
        wave_status = WaveStatus.FAILED
    else:
        wave_status = WaveStatus.SUCCEEDED
    return WaveResult.build(plan=plan, status=wave_status, operations=tuple(operation_results))


def _media(source_id: str) -> MediaArtifactEvidence:
    path = f"/tmp/{source_id}.mp4"
    source = MediaSourceIdentity(
        project_key=PROJECT.project_key,
        platform=PlatformName.YOUTUBE,
        source_channel_id=SOURCE_CHANNEL.channel_id,
        source_id=source_id,
        source_url=f"https://www.youtube.com/watch?v={source_id}",
        expected_duration_seconds=120.0,
    )
    acquisition = MediaAcquisitionEvidence(
        method="controlled_master",
        path_authority="controlled_master",
        requested_output_path=path,
        authoritative_final_path=path,
        tool_name="wave-8f-fixture",
    )
    profile = MediaCompatibilityProfile()
    probe = MediaProbeEvidence(
        path=path,
        size_bytes=1024,
        sha256="sha256:" + "b" * 64,
        duration_seconds=120.0,
        format_names=("mp4",),
        video_stream_count=1,
        audio_stream_count=1,
        video_codec="h264",
        audio_codec="aac",
        width=1920,
        height=1080,
        sample_rate_hz=48000,
        audio_channels=2,
    )
    provisional = MediaArtifactEvidence(
        source=source,
        acquisition=acquisition,
        profile=profile,
        probe=probe,
        manifest_sha256="sha256:" + "0" * 64,
    )
    return provisional.model_copy(update={"manifest_sha256": calculate_media_manifest_sha256(provisional)})


def _upload_record(
    source_id: str,
    media: MediaArtifactEvidence,
    *,
    stage: UploadStage = UploadStage.VERIFIED,
) -> dict[str, Any]:
    record = create_upload_record(
        source_snapshot_id=SOURCE_SNAPSHOT,
        community_id=PROJECT.community_id,
        source_video_id=source_id,
        source_title=f"Source {source_id}",
        source_duration_seconds=120,
        published_title=f"Published {source_id}",
        published_description="Description",
        readiness=VkUploadReadiness(expected_title=f"Published {source_id}", minimum_duration_seconds=115),
    )
    record["media"] = journal_media_evidence(media)
    record["stage"] = stage.value
    record["reservation"] = {
        "owner_id": PROJECT.owner_id,
        "video_id": 456239999,
        "remote_id": f"{PROJECT.owner_id}_456239999",
        "upload_url": "journal-reconciliation-only",
        "reservation_response": None,
    }
    return record


def _thumbnail_record(*, status: ThumbnailStatus) -> ThumbnailOperationRecord:
    local_thumbnail: dict[str, object] = {
        "path": "/tmp/thumb.png",
        "size_bytes": 512,
        "sha256": "c" * 64,
        "format": "png",
        "width": 1280,
        "height": 720,
    }
    operation_payload = {
        "local_sha256": local_thumbnail["sha256"],
        "owner_id": PROJECT.owner_id,
        "project_key": PROJECT.project_key,
        "video_id": 456239999,
    }
    operation_id = hashlib.sha256(
        json.dumps(operation_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    saved_receipt = {
        "owner_id": PROJECT.owner_id,
        "video_id": 456239999,
        "photo_owner_id": PROJECT.owner_id,
        "photo_id": 77,
        "photo_hash": "hash",
        "image_descriptors": [],
        "response_digest": "d" * 64,
    }
    readback = {
        "owner_id": PROJECT.owner_id,
        "video_id": 456239999,
        "image_descriptors": [],
        "response_digest": "e" * 64,
        "observed_at": "2026-08-04T20:00:00+00:00",
    }
    provisional = ThumbnailOperationRecord(
        schema_name="video-manager.vk-thumbnail-evidence",
        schema_version="1.0",
        ruleset="wave-8e-v1",
        operation_id=operation_id,
        project_key=PROJECT.project_key,
        owner_id=PROJECT.owner_id,
        video_id=456239999,
        local_thumbnail=local_thumbnail,
        status=status.value,
        saved_receipt=saved_receipt,
        readback=readback if status is ThumbnailStatus.VERIFIED else None,
        failure=(
            None
            if status is ThumbnailStatus.VERIFIED
            else "mocked delayed readback did not prove the selected thumbnail"
        ),
        created_at="2026-08-04T20:00:00+00:00",
        updated_at="2026-08-04T20:00:01+00:00",
        evidence_digest="",
    )
    payload = asdict(provisional)
    payload.pop("evidence_digest")
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return ThumbnailOperationRecord(**{**asdict(provisional), "evidence_digest": digest})


def test_wave8_happy_path_binds_real_contracts_and_totals() -> None:
    existing_source = "src-existing"
    missing_source = "src-missing"
    existing_target = "456239111"
    source_collection = RemoteRef(
        platform=PlatformName.YOUTUBE,
        channel_id=SOURCE_CHANNEL.channel_id,
        remote_id="playlist-1",
    )
    target_collection = RemoteRef(
        platform=PlatformName.VK,
        channel_id=TARGET_CHANNEL.channel_id,
        remote_id="album-1",
    )
    catalog_decision = CollectionIdentityDecision(
        source_ref=source_collection,
        source_title_identity=canonicalize_collection_title("Collection"),
        decision="mapped",
        target_ref=target_collection,
        target_title_identity=canonicalize_collection_title("Collection"),
        source_member_video_ids=[existing_source],
        mapped_target_video_ids=[existing_target],
        actual_target_video_ids=[],
        missing_target_video_ids=[existing_target],
    )
    comparison = _comparison(
        matches=[_mapped_video(existing_source, existing_target)],
        missing=[_missing_video(missing_source)],
        catalog=_catalog(decisions=[catalog_decision]),
    )
    plan = _wave_plan(
        (
            _spec(missing_source, "upload", 10),
            _spec(missing_source, "metadata", 20),
            _spec(missing_source, "thumbnail", 30),
            _spec(existing_source, "catalog_placement", 40),
        )
    )
    result = _result(plan, (OperationStatus.SUCCEEDED,) * 4)
    media = _media(missing_source)

    evidence = build_operation_integration_evidence(
        project=PROJECT,
        comparison=comparison,
        bounded_source_video_ids=(existing_source, missing_source),
        plan=plan,
        result=result,
        media_artifacts={missing_source: media},
        upload_records={missing_source: _upload_record(missing_source, media)},
        thumbnail_records={missing_source: _thumbnail_record(status=ThumbnailStatus.VERIFIED)},
    )

    assert evidence.ruleset == INTEGRATION_RULESET
    assert evidence.evidence_level == "self_tested"
    assert evidence.provider_writes == 0
    assert evidence.expected_delta.model_dump() == {
        "uploads": 1,
        "metadata_updates": 1,
        "catalog_creates": 0,
        "catalog_placements": 1,
        "thumbnail_updates": 1,
        "wall_posts": 0,
    }
    assert evidence.totals.model_dump() == {
        "planned": 2,
        "uploaded": 1,
        "verified": 1,
        "duplicate": 1,
        "failed": 0,
        "requires_attention": 0,
    }
    outcomes = {item.source_video_id: item.outcome for item in evidence.items}
    assert outcomes == {
        existing_source: IntegrationOutcome.DUPLICATE,
        missing_source: IntegrationOutcome.VERIFIED,
    }
    assert evidence.self_digest == evidence.compute_digest()


def test_conflict_creates_no_later_operation_or_stage_evidence() -> None:
    source_id = "src-conflict"
    conflict = MatchConflict(
        reason="duplicate_exact_title",
        normalized_title="same title",
        source_refs=[
            RemoteRef(platform=PlatformName.YOUTUBE, channel_id=SOURCE_CHANNEL.channel_id, remote_id=source_id)
        ],
        target_refs=[
            RemoteRef(platform=PlatformName.VK, channel_id=TARGET_CHANNEL.channel_id, remote_id="456239101"),
            RemoteRef(platform=PlatformName.VK, channel_id=TARGET_CHANNEL.channel_id, remote_id="456239102"),
        ],
    )
    comparison = _comparison(conflicts=[conflict])
    plan = _wave_plan(())
    result = _result(plan, ())

    evidence = build_operation_integration_evidence(
        project=PROJECT,
        comparison=comparison,
        bounded_source_video_ids=(source_id,),
        plan=plan,
        result=result,
    )

    assert evidence.items[0].outcome is IntegrationOutcome.REQUIRES_ATTENTION
    assert evidence.items[0].operations == ()
    assert evidence.totals.requires_attention == 1
    assert evidence.expected_delta.uploads == 0

    unauthorized_plan = _wave_plan((_spec(source_id, "metadata", 10),))
    unauthorized_result = _result(unauthorized_plan, (OperationStatus.SUCCEEDED,))
    with pytest.raises(IntegrationEvidenceError, match="unauthorized later evidence"):
        build_operation_integration_evidence(
            project=PROJECT,
            comparison=comparison,
            bounded_source_video_ids=(source_id,),
            plan=unauthorized_plan,
            result=unauthorized_result,
        )


def test_unknown_thumbnail_preserves_verified_upload_without_replay_classification() -> None:
    source_id = "src-unknown-thumb"
    comparison = _comparison(missing=[_missing_video(source_id)])
    plan = _wave_plan((_spec(source_id, "upload", 10), _spec(source_id, "thumbnail", 20)))
    result = _result(
        plan,
        (OperationStatus.SUCCEEDED, OperationStatus.UNKNOWN_REQUIRES_RECONCILIATION),
    )
    media = _media(source_id)

    evidence = build_operation_integration_evidence(
        project=PROJECT,
        comparison=comparison,
        bounded_source_video_ids=(source_id,),
        plan=plan,
        result=result,
        media_artifacts={source_id: media},
        upload_records={source_id: _upload_record(source_id, media)},
        thumbnail_records={source_id: _thumbnail_record(status=ThumbnailStatus.UNKNOWN_REQUIRES_RECONCILIATION)},
    )

    item = evidence.items[0]
    assert item.uploaded is True
    assert item.upload_stage is UploadStage.VERIFIED
    assert item.thumbnail_status is ThumbnailStatus.UNKNOWN_REQUIRES_RECONCILIATION
    assert item.outcome is IntegrationOutcome.REQUIRES_ATTENTION
    assert evidence.totals.uploaded == 1
    assert evidence.totals.failed == 0
    assert evidence.totals.requires_attention == 1


def test_later_rejection_after_verified_upload_is_attention_not_failed() -> None:
    source_id = "src-later-failure"
    comparison = _comparison(missing=[_missing_video(source_id)])
    plan = _wave_plan((_spec(source_id, "upload", 10), _spec(source_id, "metadata", 20)))
    result = _result(plan, (OperationStatus.SUCCEEDED, OperationStatus.FAILED))
    media = _media(source_id)

    evidence = build_operation_integration_evidence(
        project=PROJECT,
        comparison=comparison,
        bounded_source_video_ids=(source_id,),
        plan=plan,
        result=result,
        media_artifacts={source_id: media},
        upload_records={source_id: _upload_record(source_id, media)},
    )

    item = evidence.items[0]
    assert item.uploaded is True
    assert item.outcome is IntegrationOutcome.REQUIRES_ATTENTION
    assert evidence.totals.uploaded == 1
    assert evidence.totals.failed == 0
    assert evidence.totals.requires_attention == 1


def test_scope_digest_and_project_tampering_fail_closed() -> None:
    source_id = "src-tamper"
    comparison = _comparison(missing=[_missing_video(source_id)])
    plan = _wave_plan((_spec(source_id, "upload", 10),))
    result = _result(plan, (OperationStatus.SUCCEEDED,))
    media = _media(source_id)
    upload = _upload_record(source_id, media)

    with pytest.raises(IntegrationEvidenceError, match="normalized, unique, and sorted"):
        build_operation_integration_evidence(
            project=PROJECT,
            comparison=comparison,
            bounded_source_video_ids=(source_id, source_id),
            plan=plan,
            result=result,
            media_artifacts={source_id: media},
            upload_records={source_id: upload},
        )

    upload["community_id"] = 60805374
    with pytest.raises(IntegrationEvidenceError, match="community differs"):
        build_operation_integration_evidence(
            project=PROJECT,
            comparison=comparison,
            bounded_source_video_ids=(source_id,),
            plan=plan,
            result=result,
            media_artifacts={source_id: media},
            upload_records={source_id: upload},
        )

    valid_upload = _upload_record(source_id, media)
    evidence = build_operation_integration_evidence(
        project=PROJECT,
        comparison=comparison,
        bounded_source_video_ids=(source_id,),
        plan=plan,
        result=result,
        media_artifacts={source_id: media},
        upload_records={source_id: valid_upload},
    )
    payload = evidence.model_dump(mode="json")
    payload["totals"]["verified"] = 0
    with pytest.raises(ValidationError, match="totals|self_digest"):
        type(evidence).model_validate(payload)
