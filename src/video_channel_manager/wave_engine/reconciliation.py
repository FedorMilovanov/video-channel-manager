from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from video_channel_manager.editorial._project_profiles import PROJECT_CHANNEL_IDS
from video_channel_manager.wave_engine.canonical import object_sha256
from video_channel_manager.wave_engine.models import FrozenStrictModel, ProjectBinding

RECONCILIATION_SCHEMA: Literal["video-manager.read-only-reconciliation-evidence"] = (
    "video-manager.read-only-reconciliation-evidence"
)
RECONCILIATION_SCHEMA_VERSION: Literal[1] = 1
RECONCILIATION_RULESET: Literal["wave-9-v1"] = "wave-9-v1"


class ReadOnlyReconciliationError(RuntimeError):
    """Read-only provider and local evidence cannot be reconciled safely."""


class TargetCoverageKind(StrEnum):
    EXACT_RESERVED_IDS = "exact_reserved_ids"
    COMPLETE_OWNER_CATALOG = "complete_owner_catalog"
    COMPLETE_SHORT_SURFACE = "complete_short_surface"
    REVIEWED_BOUNDED_EXPORT = "reviewed_bounded_export"


class LocalMutationStage(StrEnum):
    INVENTORY_ONLY = "inventory_only"
    NEVER_DISPATCHED = "never_dispatched"
    PRE_DISPATCH_FAILED = "pre_dispatch_failed"
    UPLOAD_INTENT_PERSISTED = "upload_intent_persisted"
    ACCEPTED = "accepted"
    PROCESSING = "processing"
    VERIFIED = "verified"
    REJECTED = "rejected"
    UNKNOWN_REQUIRES_RECONCILIATION = "unknown_requires_reconciliation"
    SKIPPED_ALREADY_PRESENT = "skipped_already_present"


class RemoteObservationState(StrEnum):
    VERIFIED = "verified"
    PROCESSING = "processing"
    REJECTED = "rejected"


class RemoteAssociationKind(StrEnum):
    EXACT_SOURCE_ID = "exact_source_id"
    REVIEWED_EXACT_MAPPING = "reviewed_exact_mapping"
    RESERVED_REMOTE_ID = "reserved_remote_id"


class RemoteMediaType(StrEnum):
    VIDEO = "video"
    SHORT_VIDEO = "short_video"
    UNKNOWN = "unknown"


class ReconciliationState(StrEnum):
    PRESENT = "present"
    DUPLICATE = "duplicate"
    MISSING = "missing"
    UNKNOWN = "unknown"
    REQUIRES_ATTENTION = "requires_attention"


class ReconciliationReason(StrEnum):
    EXACT_REMOTE_VERIFIED = "exact_remote_verified"
    MULTIPLE_REMOTE_OBJECTS = "multiple_remote_objects"
    REMOTE_STILL_PROCESSING = "remote_still_processing"
    LOCAL_REMOTE_BINDING_MISMATCH = "local_remote_binding_mismatch"
    LOCAL_PRESENT_CLAIM_NOT_FOUND = "local_present_claim_not_found"
    MUTATION_OUTCOME_UNRESOLVED = "mutation_outcome_unresolved"
    CONFIRMED_ABSENT_NO_MUTATION = "confirmed_absent_no_mutation"
    EXPLICIT_REJECTION_ABSENT = "explicit_rejection_absent"


def _require_aware_utc(value: datetime, *, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(UTC)


def _normalized_unique(values: tuple[str, ...], *, field: str) -> tuple[str, ...]:
    if any(value != value.strip() or not value for value in values):
        raise ValueError(f"{field} values must be normalized and non-empty")
    if values != tuple(sorted(values)) or len(values) != len(set(values)):
        raise ValueError(f"{field} values must be unique and sorted")
    return values


def _json_value(value: object) -> object:
    if isinstance(value, FrozenStrictModel):
        return value.model_dump(mode="json")
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


class BoundedSourceSnapshot(FrozenStrictModel):
    schema_name: Literal["video-manager.bounded-source-snapshot"] = "video-manager.bounded-source-snapshot"
    schema_version: Literal[1] = 1
    provider_writes: Literal[0] = 0
    project: ProjectBinding
    channel_id: str = Field(min_length=1)
    captured_at: datetime
    coverage_complete: Literal[True] = True
    bounded_source_video_ids: tuple[str, ...] = Field(min_length=1)
    snapshot_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    self_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("channel_id")
    @classmethod
    def validate_channel_id(cls, value: str) -> str:
        if value != value.strip() or not value:
            raise ValueError("channel_id must be normalized and non-empty")
        return value

    @field_validator("captured_at")
    @classmethod
    def validate_captured_at(cls, value: datetime) -> datetime:
        return _require_aware_utc(value, field="captured_at")

    @field_validator("bounded_source_video_ids")
    @classmethod
    def validate_source_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _normalized_unique(value, field="bounded_source_video_ids")

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        registered = PROJECT_CHANNEL_IDS.get(self.project.project_key, frozenset())
        if self.channel_id not in registered:
            raise ValueError("source snapshot channel differs from project binding")
        if self.snapshot_id != self.compute_snapshot_id():
            raise ValueError("source snapshot_id mismatch")
        if self.self_digest != self.compute_digest():
            raise ValueError("source snapshot self_digest mismatch")
        return self

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "project": self.project.model_dump(mode="json"),
            "channel_id": self.channel_id,
            "captured_at": self.captured_at.isoformat(),
            "coverage_complete": self.coverage_complete,
            "bounded_source_video_ids": list(self.bounded_source_video_ids),
            "provider_writes": self.provider_writes,
        }

    def compute_snapshot_id(self) -> str:
        return object_sha256(self.snapshot_payload())

    def compute_digest(self) -> str:
        return object_sha256(self.model_dump(mode="json", exclude={"self_digest"}))

    @classmethod
    def build(
        cls,
        *,
        project: ProjectBinding,
        channel_id: str,
        captured_at: datetime,
        bounded_source_video_ids: tuple[str, ...],
    ) -> Self:
        normalized = _normalized_unique(bounded_source_video_ids, field="bounded_source_video_ids")
        captured = _require_aware_utc(captured_at, field="captured_at")
        snapshot_payload: dict[str, object] = {
            "project": project.model_dump(mode="json"),
            "channel_id": channel_id,
            "captured_at": captured.isoformat(),
            "coverage_complete": True,
            "bounded_source_video_ids": list(normalized),
            "provider_writes": 0,
        }
        snapshot_id = object_sha256(snapshot_payload)
        digest_payload: dict[str, object] = {
            "schema_name": "video-manager.bounded-source-snapshot",
            "schema_version": 1,
            "provider_writes": 0,
            "project": project,
            "channel_id": channel_id,
            "captured_at": captured,
            "coverage_complete": True,
            "bounded_source_video_ids": normalized,
            "snapshot_id": snapshot_id,
        }
        return cls(
            project=project,
            channel_id=channel_id,
            captured_at=captured,
            bounded_source_video_ids=normalized,
            snapshot_id=snapshot_id,
            self_digest=object_sha256(_json_value(digest_payload)),
        )


class RemoteReconciliationObservation(FrozenStrictModel):
    source_video_id: str = Field(min_length=1)
    remote_id: str = Field(min_length=1)
    state: RemoteObservationState
    association_kind: RemoteAssociationKind
    media_type: RemoteMediaType
    duration_seconds: int | None = Field(default=None, ge=0)
    postflight_verified: bool

    @field_validator("source_video_id", "remote_id")
    @classmethod
    def validate_normalized_identity(cls, value: str) -> str:
        if value != value.strip() or not value:
            raise ValueError("remote observation identities must be normalized and non-empty")
        return value

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        if self.state is RemoteObservationState.VERIFIED:
            if not self.postflight_verified:
                raise ValueError("verified remote observation requires postflight evidence")
            if self.media_type is RemoteMediaType.UNKNOWN:
                raise ValueError("verified remote observation requires final media type")
            if self.duration_seconds is None:
                raise ValueError("verified remote observation requires exact duration")
        elif self.state is RemoteObservationState.PROCESSING:
            if self.postflight_verified:
                raise ValueError("processing remote observation cannot be postflight-verified")
        elif self.postflight_verified:
            raise ValueError("rejected remote observation cannot be postflight-verified")
        return self


class BoundedTargetSnapshot(FrozenStrictModel):
    schema_name: Literal["video-manager.bounded-target-snapshot"] = "video-manager.bounded-target-snapshot"
    schema_version: Literal[1] = 1
    provider_writes: Literal[0] = 0
    project: ProjectBinding
    captured_at: datetime
    coverage_kind: TargetCoverageKind
    coverage_complete: Literal[True] = True
    bounded_source_video_ids: tuple[str, ...] = Field(min_length=1)
    observations: tuple[RemoteReconciliationObservation, ...] = ()
    snapshot_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    self_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("captured_at")
    @classmethod
    def validate_captured_at(cls, value: datetime) -> datetime:
        return _require_aware_utc(value, field="captured_at")

    @field_validator("bounded_source_video_ids")
    @classmethod
    def validate_source_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _normalized_unique(value, field="bounded_source_video_ids")

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        keys = [(item.source_video_id, item.remote_id) for item in self.observations]
        if keys != sorted(keys) or len(keys) != len(set(keys)):
            raise ValueError("target observations must be unique and sorted by source_video_id and remote_id")
        bounded = set(self.bounded_source_video_ids)
        outside = sorted({item.source_video_id for item in self.observations} - bounded)
        if outside:
            raise ValueError(f"target observations exist outside bounded source set: {outside}")
        remote_ids = [item.remote_id for item in self.observations]
        if len(remote_ids) != len(set(remote_ids)):
            raise ValueError("one remote_id cannot be associated with multiple source items")
        owner_prefix = f"{self.project.owner_id}_"
        if any(not item.remote_id.startswith(owner_prefix) for item in self.observations):
            raise ValueError("target observation remote_id differs from project owner")
        if self.coverage_kind is TargetCoverageKind.EXACT_RESERVED_IDS and any(
            item.association_kind is not RemoteAssociationKind.RESERVED_REMOTE_ID for item in self.observations
        ):
            raise ValueError("exact reserved-ID coverage requires reserved_remote_id observations")
        if self.snapshot_id != self.compute_snapshot_id():
            raise ValueError("target snapshot_id mismatch")
        if self.self_digest != self.compute_digest():
            raise ValueError("target snapshot self_digest mismatch")
        return self

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "project": self.project.model_dump(mode="json"),
            "captured_at": self.captured_at.isoformat(),
            "coverage_kind": self.coverage_kind.value,
            "coverage_complete": self.coverage_complete,
            "bounded_source_video_ids": list(self.bounded_source_video_ids),
            "observations": [item.model_dump(mode="json") for item in self.observations],
            "provider_writes": self.provider_writes,
        }

    def compute_snapshot_id(self) -> str:
        return object_sha256(self.snapshot_payload())

    def compute_digest(self) -> str:
        return object_sha256(self.model_dump(mode="json", exclude={"self_digest"}))

    @classmethod
    def build(
        cls,
        *,
        project: ProjectBinding,
        captured_at: datetime,
        coverage_kind: TargetCoverageKind,
        bounded_source_video_ids: tuple[str, ...],
        observations: tuple[RemoteReconciliationObservation, ...],
    ) -> Self:
        normalized = _normalized_unique(bounded_source_video_ids, field="bounded_source_video_ids")
        ordered = tuple(sorted(observations, key=lambda item: (item.source_video_id, item.remote_id)))
        captured = _require_aware_utc(captured_at, field="captured_at")
        snapshot_payload: dict[str, object] = {
            "project": project.model_dump(mode="json"),
            "captured_at": captured.isoformat(),
            "coverage_kind": coverage_kind.value,
            "coverage_complete": True,
            "bounded_source_video_ids": list(normalized),
            "observations": [item.model_dump(mode="json") for item in ordered],
            "provider_writes": 0,
        }
        snapshot_id = object_sha256(snapshot_payload)
        digest_payload: dict[str, object] = {
            "schema_name": "video-manager.bounded-target-snapshot",
            "schema_version": 1,
            "provider_writes": 0,
            "project": project,
            "captured_at": captured,
            "coverage_kind": coverage_kind,
            "coverage_complete": True,
            "bounded_source_video_ids": normalized,
            "observations": ordered,
            "snapshot_id": snapshot_id,
        }
        return cls(
            project=project,
            captured_at=captured,
            coverage_kind=coverage_kind,
            bounded_source_video_ids=normalized,
            observations=ordered,
            snapshot_id=snapshot_id,
            self_digest=object_sha256(_json_value(digest_payload)),
        )


class LocalReconciliationRecord(FrozenStrictModel):
    source_video_id: str = Field(min_length=1)
    stage: LocalMutationStage
    remote_ids: tuple[str, ...] = ()
    evidence_digests: tuple[str, ...] = ()

    @field_validator("source_video_id")
    @classmethod
    def validate_source_id(cls, value: str) -> str:
        if value != value.strip() or not value:
            raise ValueError("source_video_id must be normalized and non-empty")
        return value

    @field_validator("remote_ids")
    @classmethod
    def validate_remote_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _normalized_unique(value, field="remote_ids") if value else value

    @field_validator("evidence_digests")
    @classmethod
    def validate_evidence_digests(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value:
            _normalized_unique(value, field="evidence_digests")
        if any(len(item) != 64 or any(character not in "0123456789abcdef" for character in item) for item in value):
            raise ValueError("evidence_digests must contain lowercase SHA-256 values")
        return value

    @model_validator(mode="after")
    def validate_stage_binding(self) -> Self:
        no_remote_id = {
            LocalMutationStage.INVENTORY_ONLY,
            LocalMutationStage.NEVER_DISPATCHED,
            LocalMutationStage.PRE_DISPATCH_FAILED,
            LocalMutationStage.REJECTED,
        }
        requires_remote_id = {
            LocalMutationStage.ACCEPTED,
            LocalMutationStage.PROCESSING,
            LocalMutationStage.VERIFIED,
            LocalMutationStage.SKIPPED_ALREADY_PRESENT,
        }
        if self.stage in no_remote_id and self.remote_ids:
            raise ValueError(f"{self.stage.value} cannot carry remote IDs")
        if self.stage in requires_remote_id and not self.remote_ids:
            raise ValueError(f"{self.stage.value} requires at least one exact remote ID")
        return self

    @property
    def mutation_may_have_reached_provider(self) -> bool:
        return self.stage in {
            LocalMutationStage.UPLOAD_INTENT_PERSISTED,
            LocalMutationStage.ACCEPTED,
            LocalMutationStage.PROCESSING,
            LocalMutationStage.VERIFIED,
            LocalMutationStage.UNKNOWN_REQUIRES_RECONCILIATION,
        }


class ReconciliationItemEvidence(FrozenStrictModel):
    source_video_id: str = Field(min_length=1)
    local_stage: LocalMutationStage
    local_remote_ids: tuple[str, ...] = ()
    verified_remote_ids: tuple[str, ...] = ()
    processing_remote_ids: tuple[str, ...] = ()
    rejected_remote_ids: tuple[str, ...] = ()
    mutation_may_have_reached_provider: bool
    state: ReconciliationState
    reason: ReconciliationReason
    replay_prohibited: bool
    future_write_authorized: Literal[False] = False

    @field_validator("source_video_id")
    @classmethod
    def validate_source_id(cls, value: str) -> str:
        if value != value.strip() or not value:
            raise ValueError("source_video_id must be normalized and non-empty")
        return value

    @field_validator(
        "local_remote_ids",
        "verified_remote_ids",
        "processing_remote_ids",
        "rejected_remote_ids",
    )
    @classmethod
    def validate_remote_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _normalized_unique(value, field="remote_ids") if value else value

    @model_validator(mode="after")
    def validate_classification(self) -> Self:
        live_ids = self.verified_remote_ids + self.processing_remote_ids
        if len(live_ids) != len(set(live_ids)):
            raise ValueError("one remote ID cannot appear in multiple live states")
        if self.state is ReconciliationState.PRESENT:
            if len(self.verified_remote_ids) != 1 or self.processing_remote_ids:
                raise ValueError("present classification requires one verified remote object")
        elif self.state is ReconciliationState.DUPLICATE:
            if len(live_ids) < 2:
                raise ValueError("duplicate classification requires multiple live remote objects")
        elif self.state is ReconciliationState.MISSING:
            if live_ids or self.mutation_may_have_reached_provider:
                raise ValueError("missing classification requires proven absence and no unresolved mutation")
        elif self.state is ReconciliationState.UNKNOWN:
            if live_ids or not self.mutation_may_have_reached_provider or not self.replay_prohibited:
                raise ValueError("unknown classification requires unresolved mutation and no live object")
        elif not self.replay_prohibited:
            raise ValueError("requires_attention classification must prohibit replay")
        return self


class ReconciliationTotals(FrozenStrictModel):
    total: int = Field(ge=0)
    present: int = Field(ge=0)
    duplicate: int = Field(ge=0)
    missing: int = Field(ge=0)
    unknown: int = Field(ge=0)
    requires_attention: int = Field(ge=0)
    mutation_may_have_reached_provider: int = Field(ge=0)
    replay_prohibited: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_partition(self) -> Self:
        terminal = self.present + self.duplicate + self.missing + self.unknown + self.requires_attention
        if terminal != self.total:
            raise ValueError("reconciliation totals must partition the bounded source set")
        if self.mutation_may_have_reached_provider > self.total or self.replay_prohibited > self.total:
            raise ValueError("reconciliation safety totals cannot exceed the bounded source count")
        return self


class ReadOnlyReconciliationEvidence(FrozenStrictModel):
    schema_name: Literal["video-manager.read-only-reconciliation-evidence"] = RECONCILIATION_SCHEMA
    schema_version: Literal[1] = RECONCILIATION_SCHEMA_VERSION
    ruleset: Literal["wave-9-v1"] = RECONCILIATION_RULESET
    evidence_level: Literal["read_only_reconciliation"] = "read_only_reconciliation"
    provider_writes: Literal[0] = 0
    write_plan_created: Literal[False] = False
    project: ProjectBinding
    evaluated_at: datetime
    maximum_snapshot_age_seconds: int = Field(gt=0)
    source_snapshot_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    target_snapshot_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    target_snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    bounded_source_video_ids: tuple[str, ...] = Field(min_length=1)
    items: tuple[ReconciliationItemEvidence, ...] = Field(min_length=1)
    totals: ReconciliationTotals
    self_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("evaluated_at")
    @classmethod
    def validate_evaluated_at(cls, value: datetime) -> datetime:
        return _require_aware_utc(value, field="evaluated_at")

    @field_validator("bounded_source_video_ids")
    @classmethod
    def validate_source_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _normalized_unique(value, field="bounded_source_video_ids")

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        item_ids = tuple(item.source_video_id for item in self.items)
        if item_ids != self.bounded_source_video_ids:
            raise ValueError("reconciliation items must exactly cover the bounded source set")
        if self.totals != calculate_reconciliation_totals(self.items):
            raise ValueError("reconciliation totals do not match item evidence")
        if self.self_digest != self.compute_digest():
            raise ValueError("reconciliation evidence self_digest mismatch")
        return self

    def compute_digest(self) -> str:
        return object_sha256(self.model_dump(mode="json", exclude={"self_digest"}))


def _snapshot_age_seconds(*, captured_at: datetime, evaluated_at: datetime) -> float:
    age = (evaluated_at - captured_at).total_seconds()
    if age < 0:
        raise ReadOnlyReconciliationError("snapshot capture time cannot be after reconciliation evaluation")
    return age


def _classify_item(
    *,
    local: LocalReconciliationRecord,
    observations: tuple[RemoteReconciliationObservation, ...],
) -> ReconciliationItemEvidence:
    verified = tuple(sorted(item.remote_id for item in observations if item.state is RemoteObservationState.VERIFIED))
    processing = tuple(
        sorted(item.remote_id for item in observations if item.state is RemoteObservationState.PROCESSING)
    )
    rejected = tuple(sorted(item.remote_id for item in observations if item.state is RemoteObservationState.REJECTED))
    live_ids = verified + processing
    local_set = set(local.remote_ids)
    live_set = set(live_ids)
    binding_mismatch = bool(local_set and live_set and local_set != live_set)

    if len(live_ids) > 1:
        state = ReconciliationState.DUPLICATE
        reason = ReconciliationReason.MULTIPLE_REMOTE_OBJECTS
        replay_prohibited = True
    elif binding_mismatch:
        state = ReconciliationState.REQUIRES_ATTENTION
        reason = ReconciliationReason.LOCAL_REMOTE_BINDING_MISMATCH
        replay_prohibited = True
    elif len(verified) == 1:
        state = ReconciliationState.PRESENT
        reason = ReconciliationReason.EXACT_REMOTE_VERIFIED
        replay_prohibited = local.mutation_may_have_reached_provider
    elif len(processing) == 1:
        state = ReconciliationState.REQUIRES_ATTENTION
        reason = ReconciliationReason.REMOTE_STILL_PROCESSING
        replay_prohibited = True
    elif local.stage in {LocalMutationStage.VERIFIED, LocalMutationStage.SKIPPED_ALREADY_PRESENT}:
        state = ReconciliationState.REQUIRES_ATTENTION
        reason = ReconciliationReason.LOCAL_PRESENT_CLAIM_NOT_FOUND
        replay_prohibited = True
    elif local.mutation_may_have_reached_provider:
        state = ReconciliationState.UNKNOWN
        reason = ReconciliationReason.MUTATION_OUTCOME_UNRESOLVED
        replay_prohibited = True
    else:
        state = ReconciliationState.MISSING
        if local.stage in {LocalMutationStage.PRE_DISPATCH_FAILED, LocalMutationStage.REJECTED} or rejected:
            reason = ReconciliationReason.EXPLICIT_REJECTION_ABSENT
        else:
            reason = ReconciliationReason.CONFIRMED_ABSENT_NO_MUTATION
        replay_prohibited = False

    return ReconciliationItemEvidence(
        source_video_id=local.source_video_id,
        local_stage=local.stage,
        local_remote_ids=local.remote_ids,
        verified_remote_ids=verified,
        processing_remote_ids=processing,
        rejected_remote_ids=rejected,
        mutation_may_have_reached_provider=local.mutation_may_have_reached_provider,
        state=state,
        reason=reason,
        replay_prohibited=replay_prohibited,
    )


def calculate_reconciliation_totals(
    items: tuple[ReconciliationItemEvidence, ...],
) -> ReconciliationTotals:
    return ReconciliationTotals(
        total=len(items),
        present=sum(item.state is ReconciliationState.PRESENT for item in items),
        duplicate=sum(item.state is ReconciliationState.DUPLICATE for item in items),
        missing=sum(item.state is ReconciliationState.MISSING for item in items),
        unknown=sum(item.state is ReconciliationState.UNKNOWN for item in items),
        requires_attention=sum(item.state is ReconciliationState.REQUIRES_ATTENTION for item in items),
        mutation_may_have_reached_provider=sum(item.mutation_may_have_reached_provider for item in items),
        replay_prohibited=sum(item.replay_prohibited for item in items),
    )


def build_read_only_reconciliation_evidence(
    *,
    project: ProjectBinding,
    source_snapshot: BoundedSourceSnapshot,
    target_snapshot: BoundedTargetSnapshot,
    local_records: tuple[LocalReconciliationRecord, ...],
    evaluated_at: datetime,
    maximum_snapshot_age_seconds: int = 3600,
) -> ReadOnlyReconciliationEvidence:
    """Reconcile bounded local and provider readback evidence without creating write work."""

    if source_snapshot.project != project or target_snapshot.project != project:
        raise ReadOnlyReconciliationError("snapshot project differs from reconciliation project")
    if source_snapshot.bounded_source_video_ids != target_snapshot.bounded_source_video_ids:
        raise ReadOnlyReconciliationError("source and target snapshots cover different bounded source sets")
    if maximum_snapshot_age_seconds <= 0:
        raise ReadOnlyReconciliationError("maximum_snapshot_age_seconds must be positive")
    evaluated = _require_aware_utc(evaluated_at, field="evaluated_at")
    for label, captured_at in (
        ("source", source_snapshot.captured_at),
        ("target", target_snapshot.captured_at),
    ):
        if _snapshot_age_seconds(captured_at=captured_at, evaluated_at=evaluated) > maximum_snapshot_age_seconds:
            raise ReadOnlyReconciliationError(f"{label} snapshot is stale for this reconciliation")

    ordered_records = tuple(sorted(local_records, key=lambda item: item.source_video_id))
    record_ids = tuple(item.source_video_id for item in ordered_records)
    bounded_ids = source_snapshot.bounded_source_video_ids
    if record_ids != bounded_ids or len(record_ids) != len(set(record_ids)):
        raise ReadOnlyReconciliationError("local records must uniquely and exactly cover the bounded source set")
    if target_snapshot.coverage_kind is TargetCoverageKind.EXACT_RESERVED_IDS:
        uncovered = [item.source_video_id for item in ordered_records if not item.remote_ids]
        if uncovered:
            raise ReadOnlyReconciliationError(
                f"reserved-ID coverage cannot prove absence for sources without exact remote IDs: {uncovered}"
            )

    observations_by_source: dict[str, list[RemoteReconciliationObservation]] = defaultdict(list)
    for observation in target_snapshot.observations:
        observations_by_source[observation.source_video_id].append(observation)

    items = tuple(
        _classify_item(
            local=record,
            observations=tuple(observations_by_source.get(record.source_video_id, [])),
        )
        for record in ordered_records
    )
    totals = calculate_reconciliation_totals(items)
    digest_payload: dict[str, object] = {
        "schema_name": RECONCILIATION_SCHEMA,
        "schema_version": RECONCILIATION_SCHEMA_VERSION,
        "ruleset": RECONCILIATION_RULESET,
        "evidence_level": "read_only_reconciliation",
        "provider_writes": 0,
        "write_plan_created": False,
        "project": project,
        "evaluated_at": evaluated,
        "maximum_snapshot_age_seconds": maximum_snapshot_age_seconds,
        "source_snapshot_id": source_snapshot.snapshot_id,
        "source_snapshot_digest": source_snapshot.self_digest,
        "target_snapshot_id": target_snapshot.snapshot_id,
        "target_snapshot_digest": target_snapshot.self_digest,
        "bounded_source_video_ids": bounded_ids,
        "items": items,
        "totals": totals,
    }
    return ReadOnlyReconciliationEvidence(
        project=project,
        evaluated_at=evaluated,
        maximum_snapshot_age_seconds=maximum_snapshot_age_seconds,
        source_snapshot_id=source_snapshot.snapshot_id,
        source_snapshot_digest=source_snapshot.self_digest,
        target_snapshot_id=target_snapshot.snapshot_id,
        target_snapshot_digest=target_snapshot.self_digest,
        bounded_source_video_ids=bounded_ids,
        items=items,
        totals=totals,
        self_digest=object_sha256(_json_value(digest_payload)),
    )
