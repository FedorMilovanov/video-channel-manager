from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from video_channel_manager.wave_engine.canonical import (
    assert_json_value,
    file_sha256,
    object_sha256,
    resolve_repository_relative_path,
)


PROJECT_IDENTITIES: dict[str, tuple[int, int]] = {
    "legendary-poet": (235216998, -235216998),
    "lord-god-strength": (60805374, -60805374),
}

_DIGEST_PATTERN = r"^[0-9a-f]{64}$"
Digest = Annotated[str, Field(pattern=_DIGEST_PATTERN)]


class FrozenStrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class MutationClass(StrEnum):
    SAFE_READ = "safe_read"
    AMBIGUOUS_MUTATION = "ambiguous_mutation"


class OperationStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNKNOWN_REQUIRES_RECONCILIATION = "unknown_requires_reconciliation"
    NOT_ATTEMPTED = "not_attempted"
    RECONCILED = "reconciled"


class WaveStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNKNOWN_REQUIRES_RECONCILIATION = "unknown_requires_reconciliation"
    RECONCILED = "reconciled"


class ProjectBinding(FrozenStrictModel):
    project_key: str = Field(min_length=1)
    community_id: int
    owner_id: int

    @field_validator("project_key")
    @classmethod
    def normalize_project_key(cls, value: str) -> str:
        normalized = value.strip()
        if normalized != value or not normalized:
            raise ValueError("project_key must be a non-empty normalized string")
        return normalized

    @model_validator(mode="after")
    def validate_registered_identity(self) -> Self:
        expected = PROJECT_IDENTITIES.get(self.project_key)
        if expected is None:
            raise ValueError(f"unknown project_key: {self.project_key}")
        if (self.community_id, self.owner_id) != expected:
            raise ValueError("project/community/owner identity is inconsistent")
        return self


class EvidenceArtifact(FrozenStrictModel):
    path: str = Field(min_length=1)
    sha256: Digest

    @field_validator("path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        candidate = PurePosixPath(normalized)
        if (
            normalized != value
            or candidate.is_absolute()
            or ".." in candidate.parts
            or value.strip() != value
            or value in {"", "."}
        ):
            raise ValueError("artifact path must be an exact normalized relative file path")
        return value


class WaveSourceEvidence(FrozenStrictModel):
    schema_name: Literal["video-manager.wave-source"] = "video-manager.wave-source"
    schema_version: Literal[1] = 1
    project: ProjectBinding
    source_snapshot_id: Digest
    policy_version: str = Field(min_length=1)
    artifacts: tuple[EvidenceArtifact, ...] = Field(min_length=1)
    self_digest: Digest

    @field_validator("policy_version")
    @classmethod
    def validate_normalized_nonempty_string(cls, value: str) -> str:
        if value.strip() != value or not value:
            raise ValueError("policy_version must be a non-empty normalized string")
        return value

    @model_validator(mode="after")
    def validate_artifacts_and_digest(self) -> Self:
        paths = [artifact.path for artifact in self.artifacts]
        if paths != sorted(paths) or len(paths) != len(set(paths)):
            raise ValueError("source artifacts must be unique and sorted by path")
        if self.source_snapshot_id != self.compute_source_snapshot_id():
            raise ValueError("source_snapshot_id mismatch")
        if self.self_digest != self.compute_digest():
            raise ValueError("source evidence self_digest mismatch")
        return self

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "project": self.project.model_dump(mode="json"),
            "policy_version": self.policy_version,
            "artifacts": [artifact.model_dump(mode="json") for artifact in self.artifacts],
        }

    def compute_source_snapshot_id(self) -> str:
        return object_sha256(self.snapshot_payload())

    def compute_digest(self) -> str:
        return object_sha256(self.model_dump(mode="json", exclude={"self_digest"}))

    def verify_artifacts(self, repository_root: Path) -> None:
        for artifact in self.artifacts:
            path = resolve_repository_relative_path(repository_root, artifact.path, require_file=True)
            if file_sha256(path) != artifact.sha256:
                raise ValueError(f"source artifact SHA-256 mismatch: {artifact.path}")

    @classmethod
    def build(
        cls,
        *,
        project: ProjectBinding,
        policy_version: str,
        artifacts: tuple[EvidenceArtifact, ...],
    ) -> Self:
        ordered = tuple(sorted(artifacts, key=lambda item: item.path))
        snapshot_payload = {
            "project": project.model_dump(mode="json"),
            "policy_version": policy_version,
            "artifacts": [artifact.model_dump(mode="json") for artifact in ordered],
        }
        source_snapshot_id = object_sha256(snapshot_payload)
        payload = {
            "schema_name": "video-manager.wave-source",
            "schema_version": 1,
            "project": project.model_dump(mode="json"),
            "source_snapshot_id": source_snapshot_id,
            "policy_version": policy_version,
            "artifacts": [artifact.model_dump(mode="json") for artifact in ordered],
        }
        return cls(
            project=project,
            source_snapshot_id=source_snapshot_id,
            policy_version=policy_version,
            artifacts=ordered,
            self_digest=object_sha256(payload),
        )


class WaveOperationSpec(FrozenStrictModel):
    order_key: str = Field(min_length=1)
    operation_kind: str = Field(min_length=1)
    mutation_class: MutationClass
    payload: dict[str, Any]

    @field_validator("order_key")
    @classmethod
    def validate_order_key(cls, value: str) -> str:
        if value.strip() != value or not value:
            raise ValueError("order_key must be a non-empty normalized string")
        return value

    @field_validator("operation_kind")
    @classmethod
    def validate_operation_kind(cls, value: str) -> str:
        if value.strip() != value or not value or any(character.isspace() for character in value):
            raise ValueError("operation_kind must be a non-empty token")
        return value

    @field_validator("payload")
    @classmethod
    def validate_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        assert_json_value(value, field="payload")
        return value


class WaveOperation(FrozenStrictModel):
    operation_id: Digest
    sequence: int = Field(ge=0)
    order_key: str = Field(min_length=1)
    project: ProjectBinding
    source_snapshot_id: Digest
    policy_version: str = Field(min_length=1)
    operation_kind: str = Field(min_length=1)
    mutation_class: MutationClass
    payload: dict[str, Any]

    @field_validator("order_key", "policy_version", "operation_kind")
    @classmethod
    def validate_normalized_strings(cls, value: str) -> str:
        if value.strip() != value or not value:
            raise ValueError("operation identity strings must be normalized and non-empty")
        return value

    @field_validator("payload")
    @classmethod
    def validate_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        assert_json_value(value, field="payload")
        return value

    @model_validator(mode="after")
    def validate_operation_id(self) -> Self:
        if self.operation_id != self.compute_operation_id():
            raise ValueError("operation_id mismatch")
        return self

    def identity_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude={"operation_id"})

    def compute_operation_id(self) -> str:
        return object_sha256(self.identity_payload())

    @classmethod
    def build(
        cls,
        *,
        sequence: int,
        project: ProjectBinding,
        source_snapshot_id: str,
        policy_version: str,
        spec: WaveOperationSpec,
    ) -> Self:
        payload = {
            "sequence": sequence,
            "order_key": spec.order_key,
            "project": project.model_dump(mode="json"),
            "source_snapshot_id": source_snapshot_id,
            "policy_version": policy_version,
            "operation_kind": spec.operation_kind,
            "mutation_class": spec.mutation_class.value,
            "payload": spec.payload,
        }
        return cls(
            operation_id=object_sha256(payload),
            sequence=sequence,
            order_key=spec.order_key,
            project=project,
            source_snapshot_id=source_snapshot_id,
            policy_version=policy_version,
            operation_kind=spec.operation_kind,
            mutation_class=spec.mutation_class,
            payload=spec.payload,
        )


class WavePlan(FrozenStrictModel):
    schema_name: Literal["video-manager.wave-plan"] = "video-manager.wave-plan"
    schema_version: Literal[1] = 1
    project: ProjectBinding
    source_snapshot_id: Digest
    source_digest: Digest
    policy_version: str = Field(min_length=1)
    operations: tuple[WaveOperation, ...]
    operation_set_digest: Digest
    self_digest: Digest

    @model_validator(mode="after")
    def validate_plan(self) -> Self:
        expected_sequences = list(range(len(self.operations)))
        actual_sequences = [operation.sequence for operation in self.operations]
        if actual_sequences != expected_sequences:
            raise ValueError("operations must be deterministically ordered with contiguous sequence values")
        order_keys = [operation.order_key for operation in self.operations]
        if order_keys != sorted(order_keys) or len(order_keys) != len(set(order_keys)):
            raise ValueError("operation order_key values must be unique and sorted")
        ids = [operation.operation_id for operation in self.operations]
        if len(ids) != len(set(ids)):
            raise ValueError("operation IDs must be unique")
        for operation in self.operations:
            if operation.project != self.project:
                raise ValueError("operation project binding differs from plan")
            if operation.source_snapshot_id != self.source_snapshot_id:
                raise ValueError("operation source snapshot differs from plan")
            if operation.policy_version != self.policy_version:
                raise ValueError("operation policy version differs from plan")
        if self.operation_set_digest != self.compute_operation_set_digest():
            raise ValueError("operation_set_digest mismatch")
        if self.self_digest != self.compute_digest():
            raise ValueError("plan self_digest mismatch")
        return self

    def compute_operation_set_digest(self) -> str:
        return object_sha256([operation.operation_id for operation in self.operations])

    def compute_digest(self) -> str:
        return object_sha256(self.model_dump(mode="json", exclude={"self_digest"}))

    @classmethod
    def build(cls, *, source: WaveSourceEvidence, specs: tuple[WaveOperationSpec, ...]) -> Self:
        ordered_specs = tuple(sorted(specs, key=lambda spec: spec.order_key))
        order_keys = [spec.order_key for spec in ordered_specs]
        if len(order_keys) != len(set(order_keys)):
            raise ValueError("operation specification order_key values must be unique")
        operations = tuple(
            WaveOperation.build(
                sequence=index,
                project=source.project,
                source_snapshot_id=source.source_snapshot_id,
                policy_version=source.policy_version,
                spec=spec,
            )
            for index, spec in enumerate(ordered_specs)
        )
        operation_set_digest = object_sha256([operation.operation_id for operation in operations])
        payload = {
            "schema_name": "video-manager.wave-plan",
            "schema_version": 1,
            "project": source.project.model_dump(mode="json"),
            "source_snapshot_id": source.source_snapshot_id,
            "source_digest": source.self_digest,
            "policy_version": source.policy_version,
            "operations": [operation.model_dump(mode="json") for operation in operations],
            "operation_set_digest": operation_set_digest,
        }
        return cls(
            project=source.project,
            source_snapshot_id=source.source_snapshot_id,
            source_digest=source.self_digest,
            policy_version=source.policy_version,
            operations=operations,
            operation_set_digest=operation_set_digest,
            self_digest=object_sha256(payload),
        )


class WaveApplyIntent(FrozenStrictModel):
    schema_name: Literal["video-manager.wave-apply-intent"] = "video-manager.wave-apply-intent"
    schema_version: Literal[1] = 1
    source_path: str = Field(min_length=1)
    source_file_sha256: Digest
    source_self_digest: Digest
    plan_path: str = Field(min_length=1)
    plan_file_sha256: Digest
    plan_self_digest: Digest
    confirm_project: ProjectBinding
    confirm_source_snapshot_id: Digest
    confirm_operation_count: int = Field(ge=0)
    confirm_operation_set_digest: Digest
    enable_provider_writes: bool
    self_digest: Digest

    @field_validator("source_path", "plan_path")
    @classmethod
    def validate_evidence_path(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        candidate = PurePosixPath(value)
        if (
            normalized != value
            or candidate.is_absolute()
            or ".." in candidate.parts
            or value.strip() != value
            or value in {"", "."}
        ):
            raise ValueError("evidence paths must be exact normalized relative file paths")
        return value

    @model_validator(mode="after")
    def validate_digest(self) -> Self:
        if self.source_path == self.plan_path:
            raise ValueError("source and plan evidence paths must differ")
        if self.self_digest != self.compute_digest():
            raise ValueError("apply intent self_digest mismatch")
        return self

    def compute_digest(self) -> str:
        return object_sha256(self.model_dump(mode="json", exclude={"self_digest"}))

    def assert_matches(self, plan: WavePlan, source: WaveSourceEvidence) -> None:
        if source.self_digest != plan.source_digest:
            raise ValueError("source evidence digest differs from plan")
        if source.project != plan.project or source.source_snapshot_id != plan.source_snapshot_id:
            raise ValueError("source evidence project/snapshot differs from plan")
        if source.policy_version != plan.policy_version:
            raise ValueError("source evidence policy version differs from plan")
        if self.source_self_digest != source.self_digest:
            raise ValueError("apply intent source digest differs from source evidence")
        if self.plan_self_digest != plan.self_digest:
            raise ValueError("apply intent plan digest differs from plan")
        if self.confirm_project != plan.project:
            raise ValueError("apply intent project confirmation differs from plan")
        if self.confirm_source_snapshot_id != plan.source_snapshot_id:
            raise ValueError("apply intent source snapshot differs from plan")
        if self.confirm_operation_count != len(plan.operations):
            raise ValueError("apply intent operation count differs from plan")
        if self.confirm_operation_set_digest != plan.operation_set_digest:
            raise ValueError("apply intent operation set differs from plan")

    @classmethod
    def build(
        cls,
        *,
        source: WaveSourceEvidence,
        source_path: str,
        source_file_sha256: str,
        plan: WavePlan,
        plan_path: str,
        plan_file_sha256: str,
        enable_provider_writes: bool,
    ) -> Self:
        if source.self_digest != plan.source_digest:
            raise ValueError("source evidence digest differs from plan")
        payload = {
            "schema_name": "video-manager.wave-apply-intent",
            "schema_version": 1,
            "source_path": source_path,
            "source_file_sha256": source_file_sha256,
            "source_self_digest": source.self_digest,
            "plan_path": plan_path,
            "plan_file_sha256": plan_file_sha256,
            "plan_self_digest": plan.self_digest,
            "confirm_project": plan.project.model_dump(mode="json"),
            "confirm_source_snapshot_id": plan.source_snapshot_id,
            "confirm_operation_count": len(plan.operations),
            "confirm_operation_set_digest": plan.operation_set_digest,
            "enable_provider_writes": enable_provider_writes,
        }
        return cls(
            source_path=source_path,
            source_file_sha256=source_file_sha256,
            source_self_digest=source.self_digest,
            plan_path=plan_path,
            plan_file_sha256=plan_file_sha256,
            plan_self_digest=plan.self_digest,
            confirm_project=plan.project,
            confirm_source_snapshot_id=plan.source_snapshot_id,
            confirm_operation_count=len(plan.operations),
            confirm_operation_set_digest=plan.operation_set_digest,
            enable_provider_writes=enable_provider_writes,
            self_digest=object_sha256(payload),
        )


class WaveOperationResult(FrozenStrictModel):
    operation_id: Digest
    status: OperationStatus
    attempt_count: int = Field(ge=0, le=1)
    retry_safe: bool
    unknown_requires_reconciliation: bool
    evidence: dict[str, Any] = Field(default_factory=dict)
    error_kind: str | None = None
    error_message: str | None = None

    @field_validator("evidence")
    @classmethod
    def validate_evidence(cls, value: dict[str, Any]) -> dict[str, Any]:
        assert_json_value(value, field="evidence")
        return value

    @model_validator(mode="after")
    def validate_status_contract(self) -> Self:
        if self.status is OperationStatus.UNKNOWN_REQUIRES_RECONCILIATION:
            if self.attempt_count != 1 or self.retry_safe or not self.unknown_requires_reconciliation:
                raise ValueError("unknown operation result must be one-attempt, non-retry-safe, and flagged")
        elif self.unknown_requires_reconciliation:
            raise ValueError("only unknown operation results may require reconciliation")
        if self.status is OperationStatus.NOT_ATTEMPTED:
            if self.attempt_count != 0 or self.retry_safe:
                raise ValueError("not_attempted operation must have zero attempts and cannot be retry-safe")
        elif self.attempt_count != 1:
            raise ValueError("attempted operation result must have exactly one attempt")
        if self.retry_safe and self.status is not OperationStatus.FAILED:
            raise ValueError("only failed operations may be marked retry-safe")
        if self.status in {OperationStatus.SUCCEEDED, OperationStatus.RECONCILED} and (
            self.error_kind is not None or self.error_message is not None
        ):
            raise ValueError("successful/reconciled operations cannot contain errors")
        return self


class WaveResult(FrozenStrictModel):
    schema_name: Literal["video-manager.wave-result"] = "video-manager.wave-result"
    schema_version: Literal[1] = 1
    plan_self_digest: Digest
    project: ProjectBinding
    source_snapshot_id: Digest
    operation_set_digest: Digest
    status: WaveStatus
    operations: tuple[WaveOperationResult, ...]
    self_digest: Digest

    @model_validator(mode="after")
    def validate_digest_and_status(self) -> Self:
        if self.self_digest != self.compute_digest():
            raise ValueError("result self_digest mismatch")
        statuses = [operation.status for operation in self.operations]
        if self.status is WaveStatus.SUCCEEDED and any(status is not OperationStatus.SUCCEEDED for status in statuses):
            raise ValueError("succeeded result must contain only succeeded operations")
        if self.status is WaveStatus.FAILED:
            if OperationStatus.FAILED not in statuses or OperationStatus.UNKNOWN_REQUIRES_RECONCILIATION in statuses:
                raise ValueError("failed result must contain a failed operation and no unknown operation")
        if self.status is WaveStatus.UNKNOWN_REQUIRES_RECONCILIATION:
            if OperationStatus.UNKNOWN_REQUIRES_RECONCILIATION not in statuses:
                raise ValueError("unknown result must contain an unknown operation")
        elif OperationStatus.UNKNOWN_REQUIRES_RECONCILIATION in statuses:
            raise ValueError("result with an unknown operation must be unknown")
        if self.status is WaveStatus.RECONCILED and any(
            status is not OperationStatus.RECONCILED for status in statuses
        ):
            raise ValueError("reconciled result must contain only reconciled operations")
        return self

    def compute_digest(self) -> str:
        return object_sha256(self.model_dump(mode="json", exclude={"self_digest"}))

    def assert_matches(self, plan: WavePlan) -> None:
        if self.plan_self_digest != plan.self_digest or self.project != plan.project:
            raise ValueError("result plan/project binding mismatch")
        if self.source_snapshot_id != plan.source_snapshot_id:
            raise ValueError("result source snapshot mismatch")
        if self.operation_set_digest != plan.operation_set_digest:
            raise ValueError("result operation set digest mismatch")
        expected = [operation.operation_id for operation in plan.operations]
        actual = [operation.operation_id for operation in self.operations]
        if actual != expected:
            raise ValueError("result does not provide exact ordered operation coverage")

        terminal_seen = False
        for operation, operation_result in zip(plan.operations, self.operations, strict=True):
            if terminal_seen:
                if operation_result.status is not OperationStatus.NOT_ATTEMPTED:
                    raise ValueError("operations after a terminal outcome must be not_attempted")
                continue
            if operation_result.status is OperationStatus.NOT_ATTEMPTED:
                raise ValueError("not_attempted operation appears before a terminal outcome")
            if operation_result.status is OperationStatus.RECONCILED and self.status is not WaveStatus.RECONCILED:
                raise ValueError("apply results cannot contain reconciled operations")
            if operation_result.status is OperationStatus.UNKNOWN_REQUIRES_RECONCILIATION:
                if operation.mutation_class is not MutationClass.AMBIGUOUS_MUTATION:
                    raise ValueError("safe-read operation cannot have an unknown provider outcome")
                terminal_seen = True
            elif operation_result.status is OperationStatus.FAILED:
                if operation.mutation_class is MutationClass.AMBIGUOUS_MUTATION:
                    if operation_result.error_kind != "rejected_before_dispatch" or not operation_result.retry_safe:
                        raise ValueError("ambiguous mutation failures are allowed only before provider dispatch")
                elif operation_result.retry_safe is not True:
                    raise ValueError("safe-read failure must be explicitly retry-safe")
                terminal_seen = True
            elif operation_result.retry_safe:
                raise ValueError("non-failed operation cannot be retry-safe")
            if (
                operation.mutation_class is MutationClass.AMBIGUOUS_MUTATION
                and operation_result.retry_safe
                and operation_result.error_kind != "rejected_before_dispatch"
            ):
                raise ValueError("dispatched ambiguous mutations are never retry-safe")

    @classmethod
    def build(
        cls,
        *,
        plan: WavePlan,
        status: WaveStatus,
        operations: tuple[WaveOperationResult, ...],
    ) -> Self:
        payload = {
            "schema_name": "video-manager.wave-result",
            "schema_version": 1,
            "plan_self_digest": plan.self_digest,
            "project": plan.project.model_dump(mode="json"),
            "source_snapshot_id": plan.source_snapshot_id,
            "operation_set_digest": plan.operation_set_digest,
            "status": status.value,
            "operations": [operation.model_dump(mode="json") for operation in operations],
        }
        result = cls(
            plan_self_digest=plan.self_digest,
            project=plan.project,
            source_snapshot_id=plan.source_snapshot_id,
            operation_set_digest=plan.operation_set_digest,
            status=status,
            operations=operations,
            self_digest=object_sha256(payload),
        )
        result.assert_matches(plan)
        return result


class WaveReconciliationRequest(FrozenStrictModel):
    schema_name: Literal["video-manager.wave-reconciliation-request"] = "video-manager.wave-reconciliation-request"
    schema_version: Literal[1] = 1
    plan_self_digest: Digest
    result_self_digest: Digest
    project: ProjectBinding
    source_snapshot_id: Digest
    operation_ids: tuple[str, ...] = Field(min_length=1)
    self_digest: Digest

    @field_validator("operation_ids")
    @classmethod
    def validate_operation_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(re.fullmatch(_DIGEST_PATTERN, value) is None for value in values):
            raise ValueError("reconciliation operation IDs must be lowercase SHA-256 digests")
        return values

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        if len(self.operation_ids) != len(set(self.operation_ids)):
            raise ValueError("reconciliation operation IDs must be unique")
        if self.self_digest != self.compute_digest():
            raise ValueError("reconciliation request self_digest mismatch")
        return self

    def compute_digest(self) -> str:
        return object_sha256(self.model_dump(mode="json", exclude={"self_digest"}))

    def assert_matches(self, plan: WavePlan, result: WaveResult) -> None:
        result.assert_matches(plan)
        if self.plan_self_digest != plan.self_digest or self.result_self_digest != result.self_digest:
            raise ValueError("reconciliation request plan/result binding mismatch")
        if self.project != plan.project or self.source_snapshot_id != plan.source_snapshot_id:
            raise ValueError("reconciliation request project/source binding mismatch")
        expected = tuple(
            operation.operation_id
            for operation in result.operations
            if operation.status is OperationStatus.UNKNOWN_REQUIRES_RECONCILIATION
        )
        if self.operation_ids != expected:
            raise ValueError("reconciliation request does not exactly cover unknown operations")

    @classmethod
    def build(cls, *, plan: WavePlan, result: WaveResult) -> Self:
        result.assert_matches(plan)
        operation_ids = tuple(
            operation.operation_id
            for operation in result.operations
            if operation.status is OperationStatus.UNKNOWN_REQUIRES_RECONCILIATION
        )
        if not operation_ids:
            raise ValueError("result contains no unknown operations to reconcile")
        payload = {
            "schema_name": "video-manager.wave-reconciliation-request",
            "schema_version": 1,
            "plan_self_digest": plan.self_digest,
            "result_self_digest": result.self_digest,
            "project": plan.project.model_dump(mode="json"),
            "source_snapshot_id": plan.source_snapshot_id,
            "operation_ids": list(operation_ids),
        }
        return cls(
            plan_self_digest=plan.self_digest,
            result_self_digest=result.self_digest,
            project=plan.project,
            source_snapshot_id=plan.source_snapshot_id,
            operation_ids=operation_ids,
            self_digest=object_sha256(payload),
        )


class WaveReconciliationResult(FrozenStrictModel):
    schema_name: Literal["video-manager.wave-reconciliation-result"] = "video-manager.wave-reconciliation-result"
    schema_version: Literal[1] = 1
    request_self_digest: Digest
    project: ProjectBinding
    operations: tuple[WaveOperationResult, ...]
    self_digest: Digest

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        ids = [operation.operation_id for operation in self.operations]
        if len(ids) != len(set(ids)):
            raise ValueError("reconciliation result operation IDs must be unique")
        if any(operation.status is not OperationStatus.RECONCILED for operation in self.operations):
            raise ValueError("reconciliation result operations must be reconciled")
        if self.self_digest != self.compute_digest():
            raise ValueError("reconciliation result self_digest mismatch")
        return self

    def compute_digest(self) -> str:
        return object_sha256(self.model_dump(mode="json", exclude={"self_digest"}))

    def assert_matches(self, request: WaveReconciliationRequest) -> None:
        if self.request_self_digest != request.self_digest or self.project != request.project:
            raise ValueError("reconciliation result request/project binding mismatch")
        if tuple(operation.operation_id for operation in self.operations) != request.operation_ids:
            raise ValueError("reconciliation result does not exactly cover the request")

    @classmethod
    def build(
        cls,
        *,
        request: WaveReconciliationRequest,
        operations: tuple[WaveOperationResult, ...],
    ) -> Self:
        payload = {
            "schema_name": "video-manager.wave-reconciliation-result",
            "schema_version": 1,
            "request_self_digest": request.self_digest,
            "project": request.project.model_dump(mode="json"),
            "operations": [operation.model_dump(mode="json") for operation in operations],
        }
        result = cls(
            request_self_digest=request.self_digest,
            project=request.project,
            operations=operations,
            self_digest=object_sha256(payload),
        )
        result.assert_matches(request)
        return result


WAVE_SCHEMA_MODELS: tuple[type[BaseModel], ...] = (
    WaveSourceEvidence,
    WavePlan,
    WaveApplyIntent,
    WaveResult,
    WaveReconciliationRequest,
    WaveReconciliationResult,
)
