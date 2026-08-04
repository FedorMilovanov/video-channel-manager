from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import Field, field_validator, model_validator

from video_channel_manager.application.catalog_identity import validate_catalog_identity_evidence
from video_channel_manager.application.cross_platform.models import CrossPlatformComparison
from video_channel_manager.domain.enums import PlatformName
from video_channel_manager.editorial._project_profiles import PROJECT_CHANNEL_IDS
from video_channel_manager.local_media.artifact import (
    MediaArtifactEvidence,
    validate_media_artifact_evidence,
)
from video_channel_manager.platforms.vk.thumbnail_lifecycle import (
    ThumbnailOperationRecord,
    ThumbnailStatus,
)
from video_channel_manager.platforms.vk.upload_lifecycle import UploadStage
from video_channel_manager.wave_engine.canonical import object_sha256
from video_channel_manager.wave_engine.models import (
    FrozenStrictModel,
    OperationStatus,
    ProjectBinding,
    WaveOperation,
    WaveOperationResult,
    WavePlan,
    WaveResult,
)

INTEGRATION_SCHEMA = "video-manager.operation-integration-evidence"
INTEGRATION_SCHEMA_VERSION = 1
INTEGRATION_RULESET = "wave-8f-v1"


class IntegrationEvidenceError(RuntimeError):
    """Cross-wave evidence is incomplete, inconsistent, or unsafe."""


class IntegrationStageKind(StrEnum):
    UPLOAD = "upload"
    METADATA = "metadata"
    CATALOG_CREATE = "catalog_create"
    CATALOG_PLACEMENT = "catalog_placement"
    THUMBNAIL = "thumbnail"


class IntegrationOutcome(StrEnum):
    VERIFIED = "verified"
    DUPLICATE = "duplicate"
    FAILED = "failed"
    REQUIRES_ATTENTION = "requires_attention"


class IntegrationExpectedDelta(FrozenStrictModel):
    uploads: int = Field(ge=0)
    metadata_updates: int = Field(ge=0)
    catalog_creates: int = Field(ge=0)
    catalog_placements: int = Field(ge=0)
    thumbnail_updates: int = Field(ge=0)
    wall_posts: Literal[0] = 0


class IntegrationTotals(FrozenStrictModel):
    planned: int = Field(ge=0)
    uploaded: int = Field(ge=0)
    verified: int = Field(ge=0)
    duplicate: int = Field(ge=0)
    failed: int = Field(ge=0)
    requires_attention: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_partition(self) -> Self:
        terminal = self.verified + self.duplicate + self.failed + self.requires_attention
        if terminal != self.planned:
            raise ValueError("integration totals must partition every planned source item")
        if self.uploaded > self.planned:
            raise ValueError("uploaded count cannot exceed planned count")
        return self


class IntegrationOperationBinding(FrozenStrictModel):
    operation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    sequence: int = Field(ge=0)
    stage_kind: IntegrationStageKind
    result_status: OperationStatus
    attempt_count: int = Field(ge=0, le=1)
    unknown_requires_reconciliation: bool


class IntegrationItemEvidence(FrozenStrictModel):
    source_video_id: str = Field(min_length=1)
    comparison_state: Literal["matched", "missing", "conflict"]
    target_video_id: str | None = None
    operations: tuple[IntegrationOperationBinding, ...] = ()
    media_manifest_sha256: str | None = None
    upload_operation_id: str | None = None
    upload_stage: UploadStage | None = None
    upload_remote_id: str | None = None
    thumbnail_operation_id: str | None = None
    thumbnail_status: ThumbnailStatus | None = None
    uploaded: bool
    outcome: IntegrationOutcome

    @field_validator("source_video_id")
    @classmethod
    def normalize_source_id(cls, value: str) -> str:
        normalized = value.strip()
        if normalized != value or not normalized:
            raise ValueError("source_video_id must be normalized and non-empty")
        return value

    @model_validator(mode="after")
    def validate_item_contract(self) -> Self:
        if self.comparison_state == "conflict":
            if self.operations or any(
                value is not None
                for value in (
                    self.target_video_id,
                    self.media_manifest_sha256,
                    self.upload_operation_id,
                    self.upload_stage,
                    self.upload_remote_id,
                    self.thumbnail_operation_id,
                    self.thumbnail_status,
                )
            ):
                raise ValueError("conflicted source item cannot carry later operation evidence")
            if self.uploaded or self.outcome is not IntegrationOutcome.REQUIRES_ATTENTION:
                raise ValueError("conflicted source item must require attention and cannot be uploaded")
        if self.comparison_state == "matched":
            if self.target_video_id is None:
                raise ValueError("matched source item requires target_video_id")
            if any(
                value is not None
                for value in (
                    self.media_manifest_sha256,
                    self.upload_operation_id,
                    self.upload_stage,
                    self.upload_remote_id,
                    self.thumbnail_operation_id,
                    self.thumbnail_status,
                )
            ):
                raise ValueError("matched source item cannot carry upload or thumbnail evidence")
            if self.uploaded or self.outcome is not IntegrationOutcome.DUPLICATE:
                raise ValueError("matched source item must be classified as duplicate")
        if self.comparison_state == "missing":
            if not self.operations:
                raise ValueError("missing source item requires at least one exact plan operation")
            upload_bindings = [item for item in self.operations if item.stage_kind is IntegrationStageKind.UPLOAD]
            if len(upload_bindings) != 1:
                raise ValueError("missing source item requires exactly one upload operation")
            if self.media_manifest_sha256 is None:
                raise ValueError("missing source item requires media manifest evidence")
            if self.thumbnail_operation_id is not None and self.upload_stage is not UploadStage.VERIFIED:
                raise ValueError("thumbnail evidence requires a verified upload target")
            if self.thumbnail_status is ThumbnailStatus.VERIFIED and self.thumbnail_operation_id is None:
                raise ValueError("verified thumbnail status requires thumbnail operation identity")
            if self.outcome is IntegrationOutcome.VERIFIED:
                if self.upload_stage is not UploadStage.VERIFIED or not self.uploaded or self.target_video_id is None:
                    raise ValueError("verified source item requires verified uploaded target evidence")
                thumbnail_expected = any(
                    item.stage_kind is IntegrationStageKind.THUMBNAIL for item in self.operations
                )
                if thumbnail_expected and self.thumbnail_status is not ThumbnailStatus.VERIFIED:
                    raise ValueError("verified source item requires verified thumbnail evidence")
            if self.outcome is IntegrationOutcome.FAILED and self.uploaded:
                raise ValueError("failure after an accepted upload must be requires_attention, not failed")
        return self


class OperationIntegrationEvidence(FrozenStrictModel):
    schema_name: Literal["video-manager.operation-integration-evidence"] = INTEGRATION_SCHEMA
    schema_version: Literal[1] = INTEGRATION_SCHEMA_VERSION
    ruleset: Literal["wave-8f-v1"] = INTEGRATION_RULESET
    evidence_level: Literal["self_tested"] = "self_tested"
    provider_writes: Literal[0] = 0
    project: ProjectBinding
    comparison_source_snapshot_id: str = Field(min_length=1)
    comparison_target_snapshot_id: str = Field(min_length=1)
    comparison_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    catalog_identity_digest: str = Field(min_length=1)
    wave_source_snapshot_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    plan_self_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    operation_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_self_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    bounded_source_video_ids: tuple[str, ...]
    expected_delta: IntegrationExpectedDelta
    items: tuple[IntegrationItemEvidence, ...]
    totals: IntegrationTotals
    self_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        source_ids = [item.source_video_id for item in self.items]
        if source_ids != sorted(source_ids) or len(source_ids) != len(set(source_ids)):
            raise ValueError("integration items must be unique and sorted by source_video_id")
        if self.bounded_source_video_ids != tuple(source_ids):
            raise ValueError("bounded source set must equal exact integration item coverage")
        if self.totals != calculate_integration_totals(self.items):
            raise ValueError("integration totals do not match item evidence")
        if self.self_digest != self.compute_digest():
            raise ValueError("integration evidence self_digest mismatch")
        return self

    def compute_digest(self) -> str:
        return object_sha256(self.model_dump(mode="json", exclude={"self_digest"}))


def _canonical_prefixed_sha256(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _thumbnail_record_digest(record: ThumbnailOperationRecord) -> str:
    payload = record.to_dict()
    payload.pop("evidence_digest", None)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_thumbnail_record(record: ThumbnailOperationRecord) -> None:
    if record.schema_name != "video-manager.vk-thumbnail-evidence":
        raise IntegrationEvidenceError("thumbnail record has an unexpected schema")
    if record.schema_version != "1.0" or record.ruleset != "wave-8e-v1":
        raise IntegrationEvidenceError("thumbnail record has an unsupported version or ruleset")
    if record.evidence_digest != _thumbnail_record_digest(record):
        raise IntegrationEvidenceError("thumbnail record digest does not match its contents")
    try:
        ThumbnailStatus(record.status)
    except ValueError as exc:
        raise IntegrationEvidenceError("thumbnail record has an unknown status") from exc


def _upload_operation_payload(record: Mapping[str, Any]) -> dict[str, object]:
    return {
        "source_snapshot_id": record.get("source_snapshot_id"),
        "community_id": record.get("community_id"),
        "source_video_id": record.get("source_video_id"),
        "source_title": record.get("source_title"),
        "source_duration_seconds": record.get("source_duration_seconds"),
        "published_title": record.get("published_title"),
        "published_description_sha256": record.get("published_description_sha256"),
        "readiness": record.get("readiness"),
        "wall_policy": record.get("wall_policy"),
    }


def _validate_upload_record(
    record: Mapping[str, Any],
    *,
    project: ProjectBinding,
    source_snapshot_id: str,
    source_video_id: str,
    media_manifest_sha256: str,
) -> tuple[UploadStage, str | None, str]:
    if record.get("schema_name") != "video-manager.vk-upload-operation" or record.get("schema_version") != 1:
        raise IntegrationEvidenceError("upload journal has an unexpected schema")
    if record.get("source_snapshot_id") != source_snapshot_id:
        raise IntegrationEvidenceError("upload journal source snapshot differs from comparison")
    if record.get("community_id") != project.community_id:
        raise IntegrationEvidenceError("upload journal community differs from project binding")
    if record.get("source_video_id") != source_video_id:
        raise IntegrationEvidenceError("upload journal source video differs from integration item")
    operation_id = record.get("operation_id")
    if not isinstance(operation_id, str) or operation_id != _canonical_prefixed_sha256(
        _upload_operation_payload(record)
    ):
        raise IntegrationEvidenceError("upload journal operation_id does not match its exact binding")
    try:
        stage = UploadStage(str(record.get("stage")))
    except ValueError as exc:
        raise IntegrationEvidenceError("upload journal has an unknown stage") from exc
    media = record.get("media")
    if not isinstance(media, Mapping) or media.get("manifest_sha256") != media_manifest_sha256:
        raise IntegrationEvidenceError("upload journal media manifest differs from authoritative media evidence")
    nested = media.get("artifact")
    if not isinstance(nested, Mapping) or nested.get("manifest_sha256") != media_manifest_sha256:
        raise IntegrationEvidenceError("upload journal nested media artifact differs from manifest binding")
    reservation = record.get("reservation")
    remote_id: str | None = None
    if isinstance(reservation, Mapping):
        raw_remote_id = reservation.get("remote_id")
        if isinstance(raw_remote_id, str) and raw_remote_id.strip():
            remote_id = raw_remote_id.strip()
            expected_prefix = f"{project.owner_id}_"
            if not remote_id.startswith(expected_prefix):
                raise IntegrationEvidenceError("upload reservation remote ID differs from project owner")
    return stage, remote_id, operation_id


def _operation_stage(operation: WaveOperation) -> IntegrationStageKind:
    raw = operation.payload.get("integration_stage")
    try:
        return IntegrationStageKind(str(raw))
    except ValueError as exc:
        raise IntegrationEvidenceError(
            f"operation {operation.operation_id} has no supported integration_stage"
        ) from exc


def _operation_source_id(operation: WaveOperation) -> str:
    raw = operation.payload.get("source_video_id")
    if not isinstance(raw, str) or not raw.strip() or raw.strip() != raw:
        raise IntegrationEvidenceError(
            f"operation {operation.operation_id} has no exact normalized source_video_id"
        )
    return raw


def _result_bindings(
    *,
    plan: WavePlan,
    result: WaveResult,
) -> dict[str, list[tuple[WaveOperation, WaveOperationResult, IntegrationStageKind]]]:
    result.assert_matches(plan)
    grouped: dict[str, list[tuple[WaveOperation, WaveOperationResult, IntegrationStageKind]]] = defaultdict(list)
    for operation, operation_result in zip(plan.operations, result.operations, strict=True):
        source_id = _operation_source_id(operation)
        grouped[source_id].append((operation, operation_result, _operation_stage(operation)))
    return grouped


def _comparison_partition(
    comparison: CrossPlatformComparison,
) -> tuple[dict[str, str], set[str], set[str]]:
    matched: dict[str, str] = {}
    for item in comparison.matches:
        source_id = item.source_ref.remote_id
        if source_id in matched:
            raise IntegrationEvidenceError("comparison contains duplicate matched source IDs")
        matched[source_id] = item.target_ref.remote_id
    missing = {item.ref.remote_id for item in comparison.missing_on_target}
    conflicts = {ref.remote_id for conflict in comparison.conflicts for ref in conflict.source_refs}
    overlap = (set(matched) & missing) | (set(matched) & conflicts) | (missing & conflicts)
    if overlap:
        raise IntegrationEvidenceError(f"comparison source partition overlaps: {sorted(overlap)}")
    return matched, missing, conflicts


def _validate_comparison_project(
    comparison: CrossPlatformComparison,
    project: ProjectBinding,
) -> None:
    registered_channels = PROJECT_CHANNEL_IDS.get(project.project_key, frozenset())
    if comparison.source_channel.platform is not PlatformName.YOUTUBE:
        raise IntegrationEvidenceError("comparison source channel must be YouTube")
    if comparison.source_channel.channel_id not in registered_channels:
        raise IntegrationEvidenceError("comparison source channel differs from project binding")
    if comparison.target_channel.platform is not PlatformName.VK:
        raise IntegrationEvidenceError("comparison target channel must be VK")
    if comparison.target_channel.channel_id != str(project.community_id):
        raise IntegrationEvidenceError("comparison target channel differs from project community")


def _validate_catalog(comparison: CrossPlatformComparison, project: ProjectBinding) -> str:
    catalog = comparison.catalog_identity
    if catalog is None:
        raise IntegrationEvidenceError("Wave 8F requires catalog identity evidence")
    try:
        validate_catalog_identity_evidence(catalog)
    except ValueError as exc:
        raise IntegrationEvidenceError(str(exc)) from exc
    if catalog.project_key != project.project_key:
        raise IntegrationEvidenceError("catalog evidence project differs from integration project")
    if catalog.source_snapshot_id != comparison.source_snapshot_id:
        raise IntegrationEvidenceError("catalog source snapshot differs from comparison")
    if catalog.target_snapshot_id != comparison.target_snapshot_id:
        raise IntegrationEvidenceError("catalog target snapshot differs from comparison")
    if catalog.source_channel != comparison.source_channel or catalog.target_channel != comparison.target_channel:
        raise IntegrationEvidenceError("catalog channel binding differs from comparison")
    return catalog.digest


def _validate_plan_project(plan: WavePlan, result: WaveResult, project: ProjectBinding) -> None:
    if plan.project != project or result.project != project:
        raise IntegrationEvidenceError("Wave plan/result project differs from integration project")
    result.assert_matches(plan)


def _expected_delta(
    *,
    plan: WavePlan,
    comparison: CrossPlatformComparison,
) -> IntegrationExpectedDelta:
    counts = {stage: 0 for stage in IntegrationStageKind}
    for operation in plan.operations:
        counts[_operation_stage(operation)] += 1
    catalog = comparison.catalog_identity
    if catalog is None:
        raise IntegrationEvidenceError("catalog identity evidence is required")
    expected_catalog_creates = catalog.create_count
    expected_catalog_placements = sum(
        len(item.missing_target_video_ids)
        for item in catalog.decisions
        if item.decision != "conflict"
    )
    if counts[IntegrationStageKind.CATALOG_CREATE] != expected_catalog_creates:
        raise IntegrationEvidenceError("plan catalog-create count differs from reviewed catalog evidence")
    if counts[IntegrationStageKind.CATALOG_PLACEMENT] != expected_catalog_placements:
        raise IntegrationEvidenceError("plan catalog-placement count differs from reviewed catalog evidence")
    return IntegrationExpectedDelta(
        uploads=counts[IntegrationStageKind.UPLOAD],
        metadata_updates=counts[IntegrationStageKind.METADATA],
        catalog_creates=counts[IntegrationStageKind.CATALOG_CREATE],
        catalog_placements=counts[IntegrationStageKind.CATALOG_PLACEMENT],
        thumbnail_updates=counts[IntegrationStageKind.THUMBNAIL],
        wall_posts=0,
    )


def _operation_bindings(
    values: list[tuple[WaveOperation, WaveOperationResult, IntegrationStageKind]],
) -> tuple[IntegrationOperationBinding, ...]:
    return tuple(
        IntegrationOperationBinding(
            operation_id=operation.operation_id,
            sequence=operation.sequence,
            stage_kind=stage,
            result_status=result.status,
            attempt_count=result.attempt_count,
            unknown_requires_reconciliation=result.unknown_requires_reconciliation,
        )
        for operation, result, stage in values
    )


def _has_status(
    values: list[tuple[WaveOperation, WaveOperationResult, IntegrationStageKind]],
    status: OperationStatus,
) -> bool:
    return any(result.status is status for _, result, _ in values)


def _upload_binding(
    values: list[tuple[WaveOperation, WaveOperationResult, IntegrationStageKind]],
) -> tuple[WaveOperation, WaveOperationResult] | None:
    found = [(operation, result) for operation, result, stage in values if stage is IntegrationStageKind.UPLOAD]
    if not found:
        return None
    if len(found) != 1:
        raise IntegrationEvidenceError("source item has more than one upload operation")
    return found[0]


def _thumbnail_binding(
    values: list[tuple[WaveOperation, WaveOperationResult, IntegrationStageKind]],
) -> tuple[WaveOperation, WaveOperationResult] | None:
    found = [(operation, result) for operation, result, stage in values if stage is IntegrationStageKind.THUMBNAIL]
    if not found:
        return None
    if len(found) != 1:
        raise IntegrationEvidenceError("source item has more than one thumbnail operation")
    return found[0]


def _remote_video_id(remote_id: str | None) -> str | None:
    if remote_id is None:
        return None
    _, separator, video_id = remote_id.partition("_")
    if separator != "_" or not video_id.isdigit():
        raise IntegrationEvidenceError("upload reservation remote ID is malformed")
    return video_id


def _build_missing_item(
    *,
    source_id: str,
    values: list[tuple[WaveOperation, WaveOperationResult, IntegrationStageKind]],
    media: MediaArtifactEvidence | None,
    upload_record: Mapping[str, Any] | None,
    thumbnail_record: ThumbnailOperationRecord | None,
    project: ProjectBinding,
    comparison_source_snapshot_id: str,
) -> IntegrationItemEvidence:
    upload = _upload_binding(values)
    if upload is None:
        raise IntegrationEvidenceError(f"missing source {source_id} has no upload operation")
    if media is None:
        raise IntegrationEvidenceError(f"missing source {source_id} has no media artifact evidence")
    try:
        validate_media_artifact_evidence(media)
    except Exception as exc:
        raise IntegrationEvidenceError(f"media artifact for {source_id} is invalid: {exc}") from exc
    if media.source.project_key != project.project_key or media.source.source_id != source_id:
        raise IntegrationEvidenceError("media source identity differs from integration item")
    registered_channels = PROJECT_CHANNEL_IDS.get(project.project_key, frozenset())
    if media.source.source_channel_id not in registered_channels:
        raise IntegrationEvidenceError("media source channel differs from project binding")

    upload_stage: UploadStage | None = None
    upload_remote_id: str | None = None
    upload_operation_id: str | None = None
    if upload_record is not None:
        upload_stage, upload_remote_id, upload_operation_id = _validate_upload_record(
            upload_record,
            project=project,
            source_snapshot_id=comparison_source_snapshot_id,
            source_video_id=source_id,
            media_manifest_sha256=media.manifest_sha256,
        )

    upload_operation, upload_result = upload
    if upload_result.status is OperationStatus.SUCCEEDED:
        if upload_stage is not UploadStage.VERIFIED or upload_remote_id is None:
            raise IntegrationEvidenceError("succeeded upload result lacks verified upload journal evidence")
    if upload_result.status is OperationStatus.UNKNOWN_REQUIRES_RECONCILIATION:
        if upload_stage is not UploadStage.UNKNOWN_REQUIRES_RECONCILIATION:
            raise IntegrationEvidenceError("unknown upload result lacks unknown upload journal evidence")
    if upload_result.status is OperationStatus.NOT_ATTEMPTED and upload_record is not None:
        raise IntegrationEvidenceError("not-attempted upload cannot have a dispatched upload journal")

    thumbnail_operation_id: str | None = None
    thumbnail_status: ThumbnailStatus | None = None
    thumbnail = _thumbnail_binding(values)
    if thumbnail_record is not None:
        _validate_thumbnail_record(thumbnail_record)
        if thumbnail is None:
            raise IntegrationEvidenceError("thumbnail journal exists without a thumbnail plan operation")
        target_video_id = _remote_video_id(upload_remote_id)
        if target_video_id is None:
            raise IntegrationEvidenceError("thumbnail journal exists without an exact upload target")
        if (
            thumbnail_record.project_key != project.project_key
            or thumbnail_record.owner_id != project.owner_id
            or str(thumbnail_record.video_id) != target_video_id
        ):
            raise IntegrationEvidenceError("thumbnail journal identity differs from uploaded target")
        thumbnail_operation_id = thumbnail_record.operation_id
        thumbnail_status = ThumbnailStatus(thumbnail_record.status)

    if thumbnail is not None:
        _, thumbnail_result = thumbnail
        if thumbnail_result.status is OperationStatus.SUCCEEDED:
            if thumbnail_status is not ThumbnailStatus.VERIFIED:
                raise IntegrationEvidenceError("succeeded thumbnail result lacks verified thumbnail evidence")
        if thumbnail_result.status is OperationStatus.UNKNOWN_REQUIRES_RECONCILIATION:
            if thumbnail_status is not ThumbnailStatus.UNKNOWN_REQUIRES_RECONCILIATION:
                raise IntegrationEvidenceError("unknown thumbnail result lacks unknown thumbnail evidence")
        if thumbnail_result.status is OperationStatus.NOT_ATTEMPTED and thumbnail_record is not None:
            raise IntegrationEvidenceError("not-attempted thumbnail cannot have a thumbnail journal")

    uploaded = upload_stage is UploadStage.VERIFIED
    target_video_id = _remote_video_id(upload_remote_id)
    failed = _has_status(values, OperationStatus.FAILED)
    unknown = _has_status(values, OperationStatus.UNKNOWN_REQUIRES_RECONCILIATION)
    not_attempted = _has_status(values, OperationStatus.NOT_ATTEMPTED)
    if unknown or not_attempted or (failed and uploaded):
        outcome = IntegrationOutcome.REQUIRES_ATTENTION
    elif failed:
        outcome = IntegrationOutcome.FAILED
    else:
        if upload_result.status is not OperationStatus.SUCCEEDED:
            raise IntegrationEvidenceError("non-terminal missing item lacks a succeeded upload result")
        if thumbnail is not None and thumbnail[1].status is not OperationStatus.SUCCEEDED:
            raise IntegrationEvidenceError("non-terminal missing item lacks a succeeded thumbnail result")
        outcome = IntegrationOutcome.VERIFIED

    return IntegrationItemEvidence(
        source_video_id=source_id,
        comparison_state="missing",
        target_video_id=target_video_id,
        operations=_operation_bindings(values),
        media_manifest_sha256=media.manifest_sha256,
        upload_operation_id=upload_operation_id,
        upload_stage=upload_stage,
        upload_remote_id=upload_remote_id,
        thumbnail_operation_id=thumbnail_operation_id,
        thumbnail_status=thumbnail_status,
        uploaded=uploaded,
        outcome=outcome,
    )


def _build_matched_item(
    *,
    source_id: str,
    target_id: str,
    values: list[tuple[WaveOperation, WaveOperationResult, IntegrationStageKind]],
) -> IntegrationItemEvidence:
    if any(stage in {IntegrationStageKind.UPLOAD, IntegrationStageKind.THUMBNAIL} for _, _, stage in values):
        raise IntegrationEvidenceError("matched source item cannot schedule upload or thumbnail operations")
    if _has_status(values, OperationStatus.UNKNOWN_REQUIRES_RECONCILIATION) or _has_status(
        values, OperationStatus.NOT_ATTEMPTED
    ):
        raise IntegrationEvidenceError("matched item later operation is unresolved")
    if _has_status(values, OperationStatus.FAILED):
        raise IntegrationEvidenceError("matched item later operation failed; evidence cannot classify it as duplicate")
    return IntegrationItemEvidence(
        source_video_id=source_id,
        comparison_state="matched",
        target_video_id=target_id,
        operations=_operation_bindings(values),
        uploaded=False,
        outcome=IntegrationOutcome.DUPLICATE,
    )


def calculate_integration_totals(
    items: tuple[IntegrationItemEvidence, ...],
) -> IntegrationTotals:
    return IntegrationTotals(
        planned=len(items),
        uploaded=sum(item.uploaded for item in items),
        verified=sum(item.outcome is IntegrationOutcome.VERIFIED for item in items),
        duplicate=sum(item.outcome is IntegrationOutcome.DUPLICATE for item in items),
        failed=sum(item.outcome is IntegrationOutcome.FAILED for item in items),
        requires_attention=sum(item.outcome is IntegrationOutcome.REQUIRES_ATTENTION for item in items),
    )


def build_operation_integration_evidence(
    *,
    project: ProjectBinding,
    comparison: CrossPlatformComparison,
    bounded_source_video_ids: tuple[str, ...],
    plan: WavePlan,
    result: WaveResult,
    media_artifacts: Mapping[str, MediaArtifactEvidence] | None = None,
    upload_records: Mapping[str, Mapping[str, Any]] | None = None,
    thumbnail_records: Mapping[str, ThumbnailOperationRecord] | None = None,
) -> OperationIntegrationEvidence:
    """Bind Waves 8A–8E and Wave 6 plan/result evidence without provider access."""

    normalized = tuple(sorted({value.strip() for value in bounded_source_video_ids if value.strip()}))
    if normalized != bounded_source_video_ids:
        raise IntegrationEvidenceError("bounded source IDs must be normalized, unique, and sorted")
    _validate_comparison_project(comparison, project)
    catalog_digest = _validate_catalog(comparison, project)
    _validate_plan_project(plan, result, project)
    grouped = _result_bindings(plan=plan, result=result)
    unknown_operation_sources = sorted(set(grouped) - set(normalized))
    if unknown_operation_sources:
        raise IntegrationEvidenceError(
            f"plan contains operations outside bounded source set: {unknown_operation_sources}"
        )

    matched, missing, conflicts = _comparison_partition(comparison)
    known = set(matched) | missing | conflicts
    absent = sorted(set(normalized) - known)
    if absent:
        raise IntegrationEvidenceError(f"bounded source IDs are absent from comparison: {absent}")

    media_map = dict(media_artifacts or {})
    upload_map = dict(upload_records or {})
    thumbnail_map = dict(thumbnail_records or {})
    unexpected_evidence = sorted((set(media_map) | set(upload_map) | set(thumbnail_map)) - set(normalized))
    if unexpected_evidence:
        raise IntegrationEvidenceError(f"stage evidence exists outside bounded source set: {unexpected_evidence}")

    items: list[IntegrationItemEvidence] = []
    for source_id in normalized:
        values = grouped.get(source_id, [])
        if source_id in conflicts:
            if values or source_id in media_map or source_id in upload_map or source_id in thumbnail_map:
                raise IntegrationEvidenceError("conflicted source item created unauthorized later evidence")
            items.append(
                IntegrationItemEvidence(
                    source_video_id=source_id,
                    comparison_state="conflict",
                    uploaded=False,
                    outcome=IntegrationOutcome.REQUIRES_ATTENTION,
                )
            )
        elif source_id in matched:
            if source_id in media_map or source_id in upload_map or source_id in thumbnail_map:
                raise IntegrationEvidenceError("matched source item created unauthorized upload evidence")
            items.append(_build_matched_item(source_id=source_id, target_id=matched[source_id], values=values))
        elif source_id in missing:
            items.append(
                _build_missing_item(
                    source_id=source_id,
                    values=values,
                    media=media_map.get(source_id),
                    upload_record=upload_map.get(source_id),
                    thumbnail_record=thumbnail_map.get(source_id),
                    project=project,
                    comparison_source_snapshot_id=comparison.source_snapshot_id,
                )
            )

    ordered = tuple(sorted(items, key=lambda item: item.source_video_id))
    expected_delta = _expected_delta(plan=plan, comparison=comparison)
    comparison_digest = object_sha256(comparison.model_dump(mode="json"))
    payload = {
        "schema_name": INTEGRATION_SCHEMA,
        "schema_version": INTEGRATION_SCHEMA_VERSION,
        "ruleset": INTEGRATION_RULESET,
        "evidence_level": "self_tested",
        "provider_writes": 0,
        "project": project.model_dump(mode="json"),
        "comparison_source_snapshot_id": comparison.source_snapshot_id,
        "comparison_target_snapshot_id": comparison.target_snapshot_id,
        "comparison_digest": comparison_digest,
        "catalog_identity_digest": catalog_digest,
        "wave_source_snapshot_id": plan.source_snapshot_id,
        "plan_self_digest": plan.self_digest,
        "operation_set_digest": plan.operation_set_digest,
        "result_self_digest": result.self_digest,
        "bounded_source_video_ids": list(normalized),
        "expected_delta": expected_delta.model_dump(mode="json"),
        "items": [item.model_dump(mode="json") for item in ordered],
        "totals": calculate_integration_totals(ordered).model_dump(mode="json"),
    }
    return OperationIntegrationEvidence(
        project=project,
        comparison_source_snapshot_id=comparison.source_snapshot_id,
        comparison_target_snapshot_id=comparison.target_snapshot_id,
        comparison_digest=comparison_digest,
        catalog_identity_digest=catalog_digest,
        wave_source_snapshot_id=plan.source_snapshot_id,
        plan_self_digest=plan.self_digest,
        operation_set_digest=plan.operation_set_digest,
        result_self_digest=result.self_digest,
        bounded_source_video_ids=normalized,
        expected_delta=expected_delta,
        items=ordered,
        totals=calculate_integration_totals(ordered),
        self_digest=object_sha256(payload),
    )


__all__ = [
    "INTEGRATION_RULESET",
    "INTEGRATION_SCHEMA",
    "INTEGRATION_SCHEMA_VERSION",
    "IntegrationEvidenceError",
    "IntegrationExpectedDelta",
    "IntegrationItemEvidence",
    "IntegrationOperationBinding",
    "IntegrationOutcome",
    "IntegrationStageKind",
    "IntegrationTotals",
    "OperationIntegrationEvidence",
    "build_operation_integration_evidence",
    "calculate_integration_totals",
]
