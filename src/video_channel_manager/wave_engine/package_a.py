from __future__ import annotations

import html
import os
import sqlite3
import tempfile
from contextlib import closing
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, TypeAdapter, ValidationInfo, field_validator, model_validator

from video_channel_manager.wave_engine.canonical import (
    file_sha256,
    object_sha256,
    resolve_repository_relative_path,
    write_json_atomic,
)
from video_channel_manager.wave_engine.models import EvidenceArtifact, FrozenStrictModel, ProjectBinding
from video_channel_manager.wave_engine.reconciliation import (
    BoundedSourceSnapshot,
    BoundedTargetSnapshot,
    LocalMutationStage,
    LocalReconciliationRecord,
    ReadOnlyReconciliationEvidence,
    ReconciliationReason,
    ReconciliationState,
    ReconciliationTotals,
    build_read_only_reconciliation_evidence,
)

PACKAGE_A_REQUEST_SCHEMA: Literal["video-manager.package-a-run-request"] = "video-manager.package-a-run-request"
PACKAGE_A_REQUEST_VERSION: Literal[1] = 1
PACKAGE_A_RECOVERY_SCHEMA: Literal["video-manager.recovery-decision-ledger"] = "video-manager.recovery-decision-ledger"
PACKAGE_A_RECOVERY_RULESET: Literal["wave-9b-v1"] = "wave-9b-v1"
PACKAGE_A_BOARD_SCHEMA: Literal["video-manager.operator-board"] = "video-manager.operator-board"
PACKAGE_A_BOARD_RULESET: Literal["wave-10-v1"] = "wave-10-v1"
PACKAGE_A_SUMMARY_SCHEMA: Literal["video-manager.package-a-run-summary"] = "video-manager.package-a-run-summary"

_IDENTIFIER_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")


class PackageAError(RuntimeError):
    """Package A input, evidence, or governance could not be verified safely."""


class PackageAInputMode(StrEnum):
    CANONICAL_JSON = "canonical_json"
    SQLITE_LEDGER = "sqlite_ledger"


class RecoveryDecisionKind(StrEnum):
    NO_ACTION = "no_action"
    RECONCILE_ONLY = "reconcile_only"
    BLOCKED = "blocked"
    ELIGIBLE_AFTER_SEPARATE_REVIEW = "eligible_after_separate_review"


class OperatorBoardState(StrEnum):
    COMPLETE = "complete"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    SEPARATE_REVIEW_REQUIRED = "separate_review_required"
    BLOCKED = "blocked"


def _normalized_identifier(value: str, *, field: str) -> str:
    if value != value.strip() or not value:
        raise ValueError(f"{field} must be normalized and non-empty")
    if value[0].isdigit() or any(character not in _IDENTIFIER_CHARS for character in value):
        raise ValueError(f"{field} must be a simple SQLite identifier")
    return value


def _normalized_nonempty(value: str, *, field: str) -> str:
    if value != value.strip() or not value:
        raise ValueError(f"{field} must be normalized and non-empty")
    return value


def _write_text_atomic(path: Path, content: str) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            if not content.endswith("\n"):
                stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class SqliteStageMapEntry(FrozenStrictModel):
    raw_stage: str = Field(min_length=1)
    stage: LocalMutationStage

    @field_validator("raw_stage")
    @classmethod
    def validate_raw_stage(cls, value: str) -> str:
        return _normalized_nonempty(value, field="raw_stage")


class SqliteLedgerContract(FrozenStrictModel):
    table_name: str = Field(min_length=1)
    source_video_id_column: str = Field(min_length=1)
    stage_column: str = Field(min_length=1)
    remote_id_column: str | None = None
    remote_owner_id_column: str | None = None
    remote_object_id_column: str | None = None
    evidence_digest_column: str | None = None
    stage_map: tuple[SqliteStageMapEntry, ...] = Field(min_length=1)

    @field_validator(
        "table_name",
        "source_video_id_column",
        "stage_column",
        "remote_id_column",
        "remote_owner_id_column",
        "remote_object_id_column",
        "evidence_digest_column",
    )
    @classmethod
    def validate_identifier(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is None:
            return None
        return _normalized_identifier(value, field=info.field_name or "identifier")

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        raw_stages = tuple(item.raw_stage for item in self.stage_map)
        if raw_stages != tuple(sorted(raw_stages)) or len(raw_stages) != len(set(raw_stages)):
            raise ValueError("stage_map must be unique and sorted by raw_stage")
        direct = self.remote_id_column is not None
        pair = self.remote_owner_id_column is not None or self.remote_object_id_column is not None
        if pair and (self.remote_owner_id_column is None or self.remote_object_id_column is None):
            raise ValueError("remote owner/object columns must be supplied together")
        if direct and pair:
            raise ValueError("remote identity must use either one exact ID column or owner/object columns")
        return self

    @property
    def stage_lookup(self) -> dict[str, LocalMutationStage]:
        return {item.raw_stage: item.stage for item in self.stage_map}


class PackageARunRequest(FrozenStrictModel):
    schema_name: Literal["video-manager.package-a-run-request"] = PACKAGE_A_REQUEST_SCHEMA
    schema_version: Literal[1] = PACKAGE_A_REQUEST_VERSION
    provider_queries: Literal[0] = 0
    provider_writes: Literal[0] = 0
    write_plan_created: Literal[False] = False
    project: ProjectBinding
    source_snapshot: EvidenceArtifact
    target_snapshot: EvidenceArtifact
    input_mode: PackageAInputMode
    local_records_json: EvidenceArtifact | None = None
    sqlite_ledger: EvidenceArtifact | None = None
    sqlite_contract: SqliteLedgerContract | None = None
    maximum_snapshot_age_seconds: int = Field(gt=0)
    self_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        if self.input_mode is PackageAInputMode.CANONICAL_JSON:
            if self.local_records_json is None or self.sqlite_ledger is not None or self.sqlite_contract is not None:
                raise ValueError("canonical_json mode requires only local_records_json")
        else:
            if self.sqlite_ledger is None or self.sqlite_contract is None or self.local_records_json is not None:
                raise ValueError("sqlite_ledger mode requires only sqlite_ledger and sqlite_contract")
        if self.self_digest != self.compute_digest():
            raise ValueError("Package A request self_digest mismatch")
        return self

    def compute_digest(self) -> str:
        return object_sha256(self.model_dump(mode="json", exclude={"self_digest"}))

    @classmethod
    def build(
        cls,
        *,
        project: ProjectBinding,
        source_snapshot: EvidenceArtifact,
        target_snapshot: EvidenceArtifact,
        input_mode: PackageAInputMode,
        maximum_snapshot_age_seconds: int,
        local_records_json: EvidenceArtifact | None = None,
        sqlite_ledger: EvidenceArtifact | None = None,
        sqlite_contract: SqliteLedgerContract | None = None,
    ) -> Self:
        payload = {
            "schema_name": PACKAGE_A_REQUEST_SCHEMA,
            "schema_version": PACKAGE_A_REQUEST_VERSION,
            "provider_queries": 0,
            "provider_writes": 0,
            "write_plan_created": False,
            "project": project.model_dump(mode="json"),
            "source_snapshot": source_snapshot.model_dump(mode="json"),
            "target_snapshot": target_snapshot.model_dump(mode="json"),
            "input_mode": input_mode.value,
            "local_records_json": (
                local_records_json.model_dump(mode="json") if local_records_json is not None else None
            ),
            "sqlite_ledger": sqlite_ledger.model_dump(mode="json") if sqlite_ledger is not None else None,
            "sqlite_contract": sqlite_contract.model_dump(mode="json") if sqlite_contract is not None else None,
            "maximum_snapshot_age_seconds": maximum_snapshot_age_seconds,
        }
        return cls(
            project=project,
            source_snapshot=source_snapshot,
            target_snapshot=target_snapshot,
            input_mode=input_mode,
            local_records_json=local_records_json,
            sqlite_ledger=sqlite_ledger,
            sqlite_contract=sqlite_contract,
            maximum_snapshot_age_seconds=maximum_snapshot_age_seconds,
            self_digest=object_sha256(payload),
        )


class RecoveryDecisionItem(FrozenStrictModel):
    source_video_id: str = Field(min_length=1)
    reconciliation_state: ReconciliationState
    reconciliation_reason: ReconciliationReason
    local_stage: LocalMutationStage
    remote_ids: tuple[str, ...] = ()
    decision: RecoveryDecisionKind
    replay_prohibited: bool
    separate_review_required: bool
    provider_write_authorized: Literal[False] = False
    automatic_execution: Literal[False] = False

    @field_validator("source_video_id")
    @classmethod
    def validate_source_id(cls, value: str) -> str:
        return _normalized_nonempty(value, field="source_video_id")

    @field_validator("remote_ids")
    @classmethod
    def validate_remote_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(value)) or len(value) != len(set(value)):
            raise ValueError("recovery remote_ids must be unique and sorted")
        return value

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        if self.decision is RecoveryDecisionKind.NO_ACTION:
            if self.reconciliation_state is not ReconciliationState.PRESENT or self.separate_review_required:
                raise ValueError("no_action requires a present item and no review request")
        elif self.decision is RecoveryDecisionKind.RECONCILE_ONLY:
            if self.reconciliation_state not in {
                ReconciliationState.UNKNOWN,
                ReconciliationState.REQUIRES_ATTENTION,
            }:
                raise ValueError("reconcile_only requires unknown or requires_attention")
            if not self.replay_prohibited or self.separate_review_required:
                raise ValueError("reconcile_only must prohibit replay without creating write review")
        elif self.decision is RecoveryDecisionKind.BLOCKED:
            if self.reconciliation_state is not ReconciliationState.DUPLICATE:
                raise ValueError("blocked currently requires a duplicate item")
            if not self.replay_prohibited:
                raise ValueError("blocked decisions must prohibit replay")
        else:
            if self.reconciliation_state is not ReconciliationState.MISSING:
                raise ValueError("eligible review requires a missing item")
            if self.replay_prohibited or not self.separate_review_required:
                raise ValueError("eligible review requires proven no-replay-risk absence and separate review")
        return self


class RecoveryDecisionTotals(FrozenStrictModel):
    total: int = Field(ge=0)
    no_action: int = Field(ge=0)
    reconcile_only: int = Field(ge=0)
    blocked: int = Field(ge=0)
    eligible_after_separate_review: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_partition(self) -> Self:
        if self.no_action + self.reconcile_only + self.blocked + self.eligible_after_separate_review != self.total:
            raise ValueError("recovery totals must partition the bounded source set")
        return self


class RecoveryDecisionLedger(FrozenStrictModel):
    schema_name: Literal["video-manager.recovery-decision-ledger"] = PACKAGE_A_RECOVERY_SCHEMA
    schema_version: Literal[1] = 1
    ruleset: Literal["wave-9b-v1"] = PACKAGE_A_RECOVERY_RULESET
    evidence_level: Literal["read_only_decision_support"] = "read_only_decision_support"
    provider_queries: Literal[0] = 0
    provider_writes: Literal[0] = 0
    write_plan_created: Literal[False] = False
    automatic_execution: Literal[False] = False
    project: ProjectBinding
    reconciliation_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    items: tuple[RecoveryDecisionItem, ...] = Field(min_length=1)
    totals: RecoveryDecisionTotals
    self_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_ledger(self) -> Self:
        ids = tuple(item.source_video_id for item in self.items)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValueError("recovery items must be unique and sorted")
        if self.totals != calculate_recovery_totals(self.items):
            raise ValueError("recovery totals do not match item decisions")
        if self.self_digest != self.compute_digest():
            raise ValueError("recovery decision ledger self_digest mismatch")
        return self

    def compute_digest(self) -> str:
        return object_sha256(self.model_dump(mode="json", exclude={"self_digest"}))


class OperatorBoardItem(FrozenStrictModel):
    source_video_id: str = Field(min_length=1)
    reconciliation_state: ReconciliationState
    decision: RecoveryDecisionKind
    local_stage: LocalMutationStage
    remote_ids: tuple[str, ...] = ()
    replay_prohibited: bool

    @field_validator("source_video_id")
    @classmethod
    def validate_source_id(cls, value: str) -> str:
        return _normalized_nonempty(value, field="source_video_id")


class OperatorBoard(FrozenStrictModel):
    schema_name: Literal["video-manager.operator-board"] = PACKAGE_A_BOARD_SCHEMA
    schema_version: Literal[1] = 1
    ruleset: Literal["wave-10-v1"] = PACKAGE_A_BOARD_RULESET
    evidence_level: Literal["read_only_control_plane"] = "read_only_control_plane"
    provider_queries: Literal[0] = 0
    provider_writes: Literal[0] = 0
    write_plan_created: Literal[False] = False
    mutation_authorized: Literal[False] = False
    project: ProjectBinding
    generated_at: datetime
    reconciliation_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    recovery_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    state: OperatorBoardState
    next_safe_action: str = Field(min_length=1)
    reconciliation_totals: ReconciliationTotals
    recovery_totals: RecoveryDecisionTotals
    items: tuple[OperatorBoardItem, ...] = Field(min_length=1)
    self_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        return value.astimezone(UTC)

    @field_validator("next_safe_action")
    @classmethod
    def validate_next_safe_action(cls, value: str) -> str:
        return _normalized_nonempty(value, field="next_safe_action")

    @model_validator(mode="after")
    def validate_board(self) -> Self:
        ids = tuple(item.source_video_id for item in self.items)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValueError("operator board items must be unique and sorted")
        expected_state, expected_action = _board_state_and_action(self.recovery_totals)
        if self.state is not expected_state or self.next_safe_action != expected_action:
            raise ValueError("operator board state/action differs from recovery totals")
        if self.self_digest != self.compute_digest():
            raise ValueError("operator board self_digest mismatch")
        return self

    def compute_digest(self) -> str:
        return object_sha256(self.model_dump(mode="json", exclude={"self_digest"}))


class PackageARunSummary(FrozenStrictModel):
    schema_name: Literal["video-manager.package-a-run-summary"] = PACKAGE_A_SUMMARY_SCHEMA
    schema_version: Literal[1] = 1
    provider_queries: Literal[0] = 0
    provider_writes: Literal[0] = 0
    write_plan_created: Literal[False] = False
    project: ProjectBinding
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    reconciliation_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    recovery_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    board_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifacts: tuple[EvidenceArtifact, ...] = Field(min_length=5)
    self_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_summary(self) -> Self:
        paths = tuple(item.path for item in self.artifacts)
        if paths != tuple(sorted(paths)) or len(paths) != len(set(paths)):
            raise ValueError("Package A output artifacts must be unique and sorted")
        if self.self_digest != self.compute_digest():
            raise ValueError("Package A run summary self_digest mismatch")
        return self

    def compute_digest(self) -> str:
        return object_sha256(self.model_dump(mode="json", exclude={"self_digest"}))


def _resolve_verified_artifact(input_root: Path, artifact: EvidenceArtifact) -> Path:
    try:
        path = resolve_repository_relative_path(input_root, artifact.path, require_file=True)
    except ValueError as exc:
        raise PackageAError(str(exc)) from exc
    observed = file_sha256(path)
    if observed != artifact.sha256:
        raise PackageAError(f"input SHA-256 mismatch: {artifact.path}")
    return path


def load_package_a_request(path: Path) -> PackageARunRequest:
    try:
        return PackageARunRequest.model_validate_json(path.read_text(encoding="utf-8-sig"), strict=True)
    except (OSError, ValueError) as exc:
        raise PackageAError(f"invalid Package A request: {exc}") from exc


def _load_canonical_records(path: Path) -> tuple[LocalReconciliationRecord, ...]:
    try:
        records = TypeAdapter(tuple[LocalReconciliationRecord, ...]).validate_json(
            path.read_text(encoding="utf-8-sig"),
            strict=True,
        )
    except (OSError, ValueError) as exc:
        raise PackageAError(f"invalid canonical local records: {exc}") from exc
    return tuple(sorted(records, key=lambda item: item.source_video_id))


def _read_remote_id(
    *,
    row: tuple[object, ...],
    offset: int,
    contract: SqliteLedgerContract,
) -> tuple[str | None, int]:
    if contract.remote_id_column is not None:
        raw = row[offset]
        if raw is None or raw == "":
            return None, offset + 1
        if not isinstance(raw, str):
            raise PackageAError("SQLite remote_id_column must contain normalized text or NULL")
        return _normalized_nonempty(raw, field="SQLite remote_id"), offset + 1
    if contract.remote_owner_id_column is not None and contract.remote_object_id_column is not None:
        raw_owner = row[offset]
        raw_object = row[offset + 1]
        if raw_owner is None and raw_object is None:
            return None, offset + 2
        if raw_owner is None or raw_object is None:
            raise PackageAError("SQLite remote owner/object identity is partially NULL")
        try:
            owner_id = int(str(raw_owner))
            object_id = int(str(raw_object))
        except ValueError as exc:
            raise PackageAError("SQLite remote owner/object identity must be integer-like") from exc
        return f"{owner_id}_{object_id}", offset + 2
    return None, offset


def _load_sqlite_records(path: Path, contract: SqliteLedgerContract) -> tuple[LocalReconciliationRecord, ...]:
    selected_columns = [contract.source_video_id_column, contract.stage_column]
    if contract.remote_id_column is not None:
        selected_columns.append(contract.remote_id_column)
    elif contract.remote_owner_id_column is not None and contract.remote_object_id_column is not None:
        selected_columns.extend((contract.remote_owner_id_column, contract.remote_object_id_column))
    if contract.evidence_digest_column is not None:
        selected_columns.append(contract.evidence_digest_column)
    quoted_columns = ", ".join(f'"{column}"' for column in selected_columns)
    statement = f'SELECT {quoted_columns} FROM "{contract.table_name}" ORDER BY "{contract.source_video_id_column}"'
    uri = f"{path.resolve().as_uri()}?mode=ro"
    try:
        with closing(sqlite3.connect(uri, uri=True)) as connection:
            connection.execute("PRAGMA query_only = ON")
            rows = tuple(connection.execute(statement).fetchall())
    except sqlite3.Error as exc:
        raise PackageAError(f"SQLite ledger read failed: {exc}") from exc
    if not rows:
        raise PackageAError("SQLite ledger contract selected zero rows")

    stage_lookup = contract.stage_lookup
    records: list[LocalReconciliationRecord] = []
    seen_sources: set[str] = set()
    for row in rows:
        source_raw = row[0]
        stage_raw = row[1]
        if not isinstance(source_raw, str) or not isinstance(stage_raw, str):
            raise PackageAError("SQLite source and stage columns must contain text")
        source_video_id = _normalized_nonempty(source_raw, field="SQLite source_video_id")
        raw_stage = _normalized_nonempty(stage_raw, field="SQLite stage")
        if source_video_id in seen_sources:
            raise PackageAError(
                "SQLite contract must target one current-state row per source; duplicate source row found: "
                f"{source_video_id}"
            )
        seen_sources.add(source_video_id)
        stage = stage_lookup.get(raw_stage)
        if stage is None:
            raise PackageAError(f"SQLite stage is not mapped by the reviewed contract: {raw_stage}")
        remote_id, offset = _read_remote_id(row=row, offset=2, contract=contract)
        evidence_digests: tuple[str, ...] = ()
        if contract.evidence_digest_column is not None:
            digest_raw = row[offset]
            if digest_raw not in (None, ""):
                if not isinstance(digest_raw, str):
                    raise PackageAError("SQLite evidence digest must contain text or NULL")
                evidence_digests = (_normalized_nonempty(digest_raw, field="SQLite evidence digest"),)
        records.append(
            LocalReconciliationRecord(
                source_video_id=source_video_id,
                stage=stage,
                remote_ids=(remote_id,) if remote_id is not None else (),
                evidence_digests=evidence_digests,
            )
        )
    return tuple(records)


def load_local_records(request: PackageARunRequest, *, input_root: Path) -> tuple[LocalReconciliationRecord, ...]:
    if request.input_mode is PackageAInputMode.CANONICAL_JSON:
        if request.local_records_json is None:
            raise PackageAError("canonical local records artifact is missing")
        return _load_canonical_records(_resolve_verified_artifact(input_root, request.local_records_json))
    if request.sqlite_ledger is None or request.sqlite_contract is None:
        raise PackageAError("SQLite ledger artifact or reviewed contract is missing")
    return _load_sqlite_records(
        _resolve_verified_artifact(input_root, request.sqlite_ledger),
        request.sqlite_contract,
    )


def calculate_recovery_totals(items: tuple[RecoveryDecisionItem, ...]) -> RecoveryDecisionTotals:
    return RecoveryDecisionTotals(
        total=len(items),
        no_action=sum(item.decision is RecoveryDecisionKind.NO_ACTION for item in items),
        reconcile_only=sum(item.decision is RecoveryDecisionKind.RECONCILE_ONLY for item in items),
        blocked=sum(item.decision is RecoveryDecisionKind.BLOCKED for item in items),
        eligible_after_separate_review=sum(
            item.decision is RecoveryDecisionKind.ELIGIBLE_AFTER_SEPARATE_REVIEW for item in items
        ),
    )


def build_recovery_decision_ledger(
    evidence: ReadOnlyReconciliationEvidence,
) -> RecoveryDecisionLedger:
    decisions: list[RecoveryDecisionItem] = []
    for item in evidence.items:
        remote_ids = tuple(
            sorted(
                set(
                    item.local_remote_ids
                    + item.verified_remote_ids
                    + item.processing_remote_ids
                    + item.rejected_remote_ids
                )
            )
        )
        if item.state is ReconciliationState.PRESENT:
            decision = RecoveryDecisionKind.NO_ACTION
            separate_review_required = False
        elif item.state is ReconciliationState.DUPLICATE:
            decision = RecoveryDecisionKind.BLOCKED
            separate_review_required = False
        elif item.state in {ReconciliationState.UNKNOWN, ReconciliationState.REQUIRES_ATTENTION}:
            decision = RecoveryDecisionKind.RECONCILE_ONLY
            separate_review_required = False
        else:
            decision = RecoveryDecisionKind.ELIGIBLE_AFTER_SEPARATE_REVIEW
            separate_review_required = True
        decisions.append(
            RecoveryDecisionItem(
                source_video_id=item.source_video_id,
                reconciliation_state=item.state,
                reconciliation_reason=item.reason,
                local_stage=item.local_stage,
                remote_ids=remote_ids,
                decision=decision,
                replay_prohibited=item.replay_prohibited,
                separate_review_required=separate_review_required,
            )
        )
    ordered = tuple(sorted(decisions, key=lambda item: item.source_video_id))
    totals = calculate_recovery_totals(ordered)
    payload = {
        "schema_name": PACKAGE_A_RECOVERY_SCHEMA,
        "schema_version": 1,
        "ruleset": PACKAGE_A_RECOVERY_RULESET,
        "evidence_level": "read_only_decision_support",
        "provider_queries": 0,
        "provider_writes": 0,
        "write_plan_created": False,
        "automatic_execution": False,
        "project": evidence.project.model_dump(mode="json"),
        "reconciliation_digest": evidence.self_digest,
        "items": [item.model_dump(mode="json") for item in ordered],
        "totals": totals.model_dump(mode="json"),
    }
    return RecoveryDecisionLedger(
        project=evidence.project,
        reconciliation_digest=evidence.self_digest,
        items=ordered,
        totals=totals,
        self_digest=object_sha256(payload),
    )


def _board_state_and_action(totals: RecoveryDecisionTotals) -> tuple[OperatorBoardState, str]:
    if totals.blocked:
        return (
            OperatorBoardState.BLOCKED,
            "Resolve duplicate or identity conflicts through exact read-only review; do not upload.",
        )
    if totals.reconcile_only:
        return (
            OperatorBoardState.RECONCILIATION_REQUIRED,
            "Repeat exact bounded read-only reconciliation only; do not replay any mutation.",
        )
    if totals.eligible_after_separate_review:
        return (
            OperatorBoardState.SEPARATE_REVIEW_REQUIRED,
            "Prepare a separate reviewed exact-ID plan; this board does not authorize provider writes.",
        )
    return OperatorBoardState.COMPLETE, "No provider mutation is required for this bounded source set."


def build_operator_board(
    evidence: ReadOnlyReconciliationEvidence,
    recovery: RecoveryDecisionLedger,
    *,
    generated_at: datetime,
) -> OperatorBoard:
    if recovery.project != evidence.project or recovery.reconciliation_digest != evidence.self_digest:
        raise PackageAError("recovery ledger does not bind the supplied reconciliation evidence")
    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise PackageAError("operator board generated_at must be timezone-aware")
    decision_by_source = {item.source_video_id: item for item in recovery.items}
    board_items = tuple(
        OperatorBoardItem(
            source_video_id=item.source_video_id,
            reconciliation_state=item.state,
            decision=decision_by_source[item.source_video_id].decision,
            local_stage=item.local_stage,
            remote_ids=decision_by_source[item.source_video_id].remote_ids,
            replay_prohibited=item.replay_prohibited,
        )
        for item in evidence.items
    )
    state, action = _board_state_and_action(recovery.totals)
    normalized_time = generated_at.astimezone(UTC)
    payload = {
        "schema_name": PACKAGE_A_BOARD_SCHEMA,
        "schema_version": 1,
        "ruleset": PACKAGE_A_BOARD_RULESET,
        "evidence_level": "read_only_control_plane",
        "provider_queries": 0,
        "provider_writes": 0,
        "write_plan_created": False,
        "mutation_authorized": False,
        "project": evidence.project.model_dump(mode="json"),
        "generated_at": normalized_time.isoformat().replace("+00:00", "Z"),
        "reconciliation_digest": evidence.self_digest,
        "recovery_digest": recovery.self_digest,
        "state": state.value,
        "next_safe_action": action,
        "reconciliation_totals": evidence.totals.model_dump(mode="json"),
        "recovery_totals": recovery.totals.model_dump(mode="json"),
        "items": [item.model_dump(mode="json") for item in board_items],
    }
    return OperatorBoard(
        project=evidence.project,
        generated_at=normalized_time,
        reconciliation_digest=evidence.self_digest,
        recovery_digest=recovery.self_digest,
        state=state,
        next_safe_action=action,
        reconciliation_totals=evidence.totals,
        recovery_totals=recovery.totals,
        items=board_items,
        self_digest=object_sha256(payload),
    )


def render_operator_board_markdown(board: OperatorBoard) -> str:
    lines = [
        f"# Package A operator board — {board.project.project_key}",
        "",
        f"- State: `{board.state.value}`",
        f"- Generated: `{board.generated_at.isoformat()}`",
        f"- Reconciliation digest: `{board.reconciliation_digest}`",
        f"- Recovery digest: `{board.recovery_digest}`",
        "- Provider queries performed by this run: `0`",
        "- Provider writes: `0`",
        "- Write plans created: `0`",
        "",
        "## Next safe action",
        "",
        board.next_safe_action,
        "",
        "## Totals",
        "",
        "| Metric | Count |",
        "|---|---:|",
        f"| Total | {board.reconciliation_totals.total} |",
        f"| Present | {board.reconciliation_totals.present} |",
        f"| Duplicate | {board.reconciliation_totals.duplicate} |",
        f"| Missing | {board.reconciliation_totals.missing} |",
        f"| Unknown | {board.reconciliation_totals.unknown} |",
        f"| Requires attention | {board.reconciliation_totals.requires_attention} |",
        f"| No action | {board.recovery_totals.no_action} |",
        f"| Reconcile only | {board.recovery_totals.reconcile_only} |",
        f"| Blocked | {board.recovery_totals.blocked} |",
        f"| Eligible after separate review | {board.recovery_totals.eligible_after_separate_review} |",
        "",
        "## Items",
        "",
        "| Source ID | Reconciliation | Decision | Local stage | Remote IDs | Replay prohibited |",
        "|---|---|---|---|---|---|",
    ]
    for item in board.items:
        remote_ids = ", ".join(item.remote_ids) if item.remote_ids else "—"
        lines.append(
            f"| `{item.source_video_id}` | `{item.reconciliation_state.value}` | "
            f"`{item.decision.value}` | `{item.local_stage.value}` | {remote_ids} | "
            f"{str(item.replay_prohibited).lower()} |"
        )
    lines.extend(
        (
            "",
            "> This is a read-only status board. It contains no provider writer, mutation plan, or execution control.",
        )
    )
    return "\n".join(lines) + "\n"


def render_operator_board_html(board: OperatorBoard) -> str:
    rows = "\n".join(
        "<tr>"
        f"<td><code>{html.escape(item.source_video_id)}</code></td>"
        f"<td>{html.escape(item.reconciliation_state.value)}</td>"
        f"<td>{html.escape(item.decision.value)}</td>"
        f"<td>{html.escape(item.local_stage.value)}</td>"
        f"<td>{html.escape(', '.join(item.remote_ids) if item.remote_ids else '—')}</td>"
        f"<td>{str(item.replay_prohibited).lower()}</td>"
        "</tr>"
        for item in board.items
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Package A operator board — {html.escape(board.project.project_key)}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem; background: #f6f7f9; color: #17191c; }}
main {{ max-width: 1200px; margin: 0 auto; }}
.card {{ background: white; border: 1px solid #d9dde3; border-radius: 12px; padding: 1rem; margin-bottom: 1rem; }}
.metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: .75rem; }}
.metric {{ background: #f1f3f6; border-radius: 8px; padding: .75rem; }}
table {{ width: 100%; border-collapse: collapse; background: white; }}
th, td {{ border: 1px solid #d9dde3; padding: .55rem; text-align: left; vertical-align: top; }}
th {{ background: #eef1f5; }}
code {{ overflow-wrap: anywhere; }}
.notice {{ border-left: 4px solid #555; padding-left: .75rem; }}
</style>
</head>
<body>
<main>
<h1>Package A operator board</h1>
<section class="card">
<p><strong>Project:</strong> {html.escape(board.project.project_key)}</p>
<p><strong>State:</strong> {html.escape(board.state.value)}</p>
<p><strong>Generated:</strong> {html.escape(board.generated_at.isoformat())}</p>
<p class="notice"><strong>Next safe action:</strong> {html.escape(board.next_safe_action)}</p>
<p>Provider queries: 0 · Provider writes: 0 · Write plans: 0</p>
</section>
<section class="card metrics">
<div class="metric"><strong>Total</strong><br>{board.reconciliation_totals.total}</div>
<div class="metric"><strong>Present</strong><br>{board.reconciliation_totals.present}</div>
<div class="metric"><strong>Duplicate</strong><br>{board.reconciliation_totals.duplicate}</div>
<div class="metric"><strong>Missing</strong><br>{board.reconciliation_totals.missing}</div>
<div class="metric"><strong>Unknown</strong><br>{board.reconciliation_totals.unknown}</div>
<div class="metric"><strong>Requires attention</strong><br>{board.reconciliation_totals.requires_attention}</div>
</section>
<section class="card">
<table>
<thead><tr><th>Source ID</th><th>Reconciliation</th><th>Decision</th><th>Local stage</th><th>Remote IDs</th><th>Replay prohibited</th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
</section>
<p class="notice">Read-only output. No controls on this page can query or mutate a provider.</p>
</main>
</body>
</html>
"""


def execute_package_a(
    request: PackageARunRequest,
    *,
    input_root: Path,
    output_directory: Path,
    evaluated_at: datetime,
) -> PackageARunSummary:
    source_path = _resolve_verified_artifact(input_root, request.source_snapshot)
    target_path = _resolve_verified_artifact(input_root, request.target_snapshot)
    try:
        source_snapshot = BoundedSourceSnapshot.model_validate_json(
            source_path.read_text(encoding="utf-8-sig"),
            strict=True,
        )
        target_snapshot = BoundedTargetSnapshot.model_validate_json(
            target_path.read_text(encoding="utf-8-sig"),
            strict=True,
        )
    except (OSError, ValueError) as exc:
        raise PackageAError(f"invalid bounded snapshot input: {exc}") from exc
    local_records = load_local_records(request, input_root=input_root)
    try:
        evidence = build_read_only_reconciliation_evidence(
            project=request.project,
            source_snapshot=source_snapshot,
            target_snapshot=target_snapshot,
            local_records=local_records,
            evaluated_at=evaluated_at,
            maximum_snapshot_age_seconds=request.maximum_snapshot_age_seconds,
        )
    except (ValueError, RuntimeError) as exc:
        raise PackageAError(f"reconciliation failed closed: {exc}") from exc
    recovery = build_recovery_decision_ledger(evidence)
    board = build_operator_board(evidence, recovery, generated_at=evaluated_at)

    output_directory = output_directory.resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    paths = {
        "operator-board.html": output_directory / "operator-board.html",
        "operator-board.json": output_directory / "operator-board.json",
        "operator-board.md": output_directory / "operator-board.md",
        "reconciliation-evidence.json": output_directory / "reconciliation-evidence.json",
        "recovery-decisions.json": output_directory / "recovery-decisions.json",
    }
    write_json_atomic(paths["reconciliation-evidence.json"], evidence.model_dump(mode="json"))
    write_json_atomic(paths["recovery-decisions.json"], recovery.model_dump(mode="json"))
    write_json_atomic(paths["operator-board.json"], board.model_dump(mode="json"))
    _write_text_atomic(paths["operator-board.md"], render_operator_board_markdown(board))
    _write_text_atomic(paths["operator-board.html"], render_operator_board_html(board))

    artifacts = tuple(EvidenceArtifact(path=name, sha256=file_sha256(path)) for name, path in sorted(paths.items()))
    summary_payload = {
        "schema_name": PACKAGE_A_SUMMARY_SCHEMA,
        "schema_version": 1,
        "provider_queries": 0,
        "provider_writes": 0,
        "write_plan_created": False,
        "project": request.project.model_dump(mode="json"),
        "request_digest": request.self_digest,
        "reconciliation_digest": evidence.self_digest,
        "recovery_digest": recovery.self_digest,
        "board_digest": board.self_digest,
        "artifacts": [item.model_dump(mode="json") for item in artifacts],
    }
    summary = PackageARunSummary(
        project=request.project,
        request_digest=request.self_digest,
        reconciliation_digest=evidence.self_digest,
        recovery_digest=recovery.self_digest,
        board_digest=board.self_digest,
        artifacts=artifacts,
        self_digest=object_sha256(summary_payload),
    )
    write_json_atomic(output_directory / "run-summary.json", summary.model_dump(mode="json"))
    return summary


def verify_package_a_outputs(
    *,
    evidence_path: Path,
    recovery_path: Path,
    board_path: Path,
    summary_path: Path,
) -> PackageARunSummary:
    try:
        evidence = ReadOnlyReconciliationEvidence.model_validate_json(
            evidence_path.read_text(encoding="utf-8-sig"),
            strict=True,
        )
        recovery = RecoveryDecisionLedger.model_validate_json(
            recovery_path.read_text(encoding="utf-8-sig"),
            strict=True,
        )
        board = OperatorBoard.model_validate_json(
            board_path.read_text(encoding="utf-8-sig"),
            strict=True,
        )
        summary = PackageARunSummary.model_validate_json(
            summary_path.read_text(encoding="utf-8-sig"),
            strict=True,
        )
    except (OSError, ValueError) as exc:
        raise PackageAError(f"invalid Package A output: {exc}") from exc
    if recovery.project != evidence.project or recovery.reconciliation_digest != evidence.self_digest:
        raise PackageAError("recovery ledger does not match reconciliation evidence")
    if board.project != evidence.project:
        raise PackageAError("operator board project differs from reconciliation evidence")
    if board.reconciliation_digest != evidence.self_digest or board.recovery_digest != recovery.self_digest:
        raise PackageAError("operator board does not match reconciliation/recovery evidence")
    if (
        summary.project != evidence.project
        or summary.reconciliation_digest != evidence.self_digest
        or summary.recovery_digest != recovery.self_digest
        or summary.board_digest != board.self_digest
    ):
        raise PackageAError("run summary does not match Package A outputs")
    output_root = summary_path.resolve().parent
    for artifact in summary.artifacts:
        artifact_path = resolve_repository_relative_path(output_root, artifact.path, require_file=True)
        if file_sha256(artifact_path) != artifact.sha256:
            raise PackageAError(f"Package A output SHA-256 mismatch: {artifact.path}")
    return summary


PACKAGE_A_SCHEMA_MODELS: tuple[type[FrozenStrictModel], ...] = (
    PackageARunRequest,
    RecoveryDecisionLedger,
    OperatorBoard,
    PackageARunSummary,
)
