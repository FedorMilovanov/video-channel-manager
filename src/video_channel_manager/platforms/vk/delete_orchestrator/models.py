from __future__ import annotations

from datetime import timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from video_channel_manager.platforms.vk.catalog import canonical_sha256


class RunState(StrEnum):
    CREATED = "created"
    VALIDATED = "validated"
    RUNNING = "running"
    COOLDOWN = "cooldown"
    RECONCILING = "reconciling"
    PAUSED_TRANSIENT = "paused_transient"
    PAUSED_FATAL = "paused_fatal"
    COMPLETED = "completed"
    COMPLETED_WITH_QUARANTINE = "completed_with_quarantine"


class OperationState(StrEnum):
    PLANNED = "planned"
    PRECHECKED = "prechecked"
    DISPATCH_INTENT = "dispatch_intent"
    ACCEPTED = "accepted"
    UNKNOWN_OUTCOME = "unknown_outcome"
    REJECTED_PERMANENT = "rejected_permanent"
    WAITING_VISIBILITY = "waiting_visibility"
    OBSERVED_ABSENT = "observed_absent"
    CONFIRMED_DELETED = "confirmed_deleted"
    QUARANTINED = "quarantined"
    MANUAL_REVIEW = "manual_review"


TERMINAL_OPERATION_STATES = frozenset(
    {
        OperationState.CONFIRMED_DELETED,
        OperationState.REJECTED_PERMANENT,
        OperationState.QUARANTINED,
        OperationState.MANUAL_REVIEW,
    }
)

UNRESOLVED_OPERATION_STATES = frozenset(
    {
        OperationState.DISPATCH_INTENT,
        OperationState.ACCEPTED,
        OperationState.UNKNOWN_OUTCOME,
        OperationState.WAITING_VISIBILITY,
        OperationState.OBSERVED_ABSENT,
    }
)


class AttemptOutcome(StrEnum):
    ACCEPTED = "accepted"
    UNKNOWN = "unknown"
    REJECTED_PERMANENT = "rejected_permanent"


class VideoGuard(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    remote_id: str
    title: str
    description_sha256: str
    duration_seconds: int = Field(ge=0)
    owner_id: int
    video_id: int = Field(gt=0)
    vk_type: str = "video"
    date: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_identity(self) -> VideoGuard:
        expected = f"{self.owner_id}_{self.video_id}"
        if self.remote_id != expected:
            raise ValueError(f"Video guard identity mismatch: {self.remote_id} != {expected}")
        return self


class DeleteOperation(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    operation_id: str
    operation_sha256: str
    candidate_vk_id: str
    primary_vk_id: str
    candidate_guard: VideoGuard
    primary_guard: VideoGuard
    maximum_views: int = Field(ge=0)
    required_zero_engagement: bool
    required_wall_state: str
    required_duration_difference_at_most_seconds: int = Field(ge=0)
    candidate_managed_album_ids: tuple[str, ...] = ()
    primary_managed_album_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_operation(self) -> DeleteOperation:
        payload = self.model_dump(mode="json")
        expected_hash = canonical_sha256({key: value for key, value in payload.items() if key != "operation_sha256"})
        if self.operation_sha256 != expected_hash:
            raise ValueError(f"Operation self-digest mismatch: {self.operation_id}")
        if self.candidate_vk_id != self.candidate_guard.remote_id:
            raise ValueError(f"Candidate guard mismatch: {self.operation_id}")
        if self.primary_vk_id != self.primary_guard.remote_id:
            raise ValueError(f"Primary guard mismatch: {self.operation_id}")
        if self.candidate_vk_id == self.primary_vk_id:
            raise ValueError(f"Candidate equals primary: {self.operation_id}")
        if self.required_wall_state != "unposted":
            raise ValueError(f"Delete operation is not limited to an unposted video: {self.operation_id}")
        if not self.required_zero_engagement:
            raise ValueError(f"Delete operation does not require zero engagement: {self.operation_id}")
        return self


class DeletePolicy(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    schema_name: str
    schema_version: int
    decision_set_id: str
    community_id: int = Field(gt=0)
    policy_sha256: str
    authorization: dict[str, Any]
    operations: tuple[DeleteOperation, ...]

    @model_validator(mode="after")
    def validate_policy(self) -> DeletePolicy:
        payload = self.model_dump(mode="json")
        expected_hash = canonical_sha256({key: value for key, value in payload.items() if key != "policy_sha256"})
        if self.policy_sha256 != expected_hash:
            raise ValueError("Delete policy self-digest mismatch")
        if not bool(self.authorization.get("authorized_by_user")):
            raise ValueError("Delete policy is not explicitly user-authorized")
        if self.authorization.get("parallel_writes") is not False:
            raise ValueError("Delete policy must forbid parallel writes")
        maximum = self.authorization.get("maximum_deletions")
        if maximum != len(self.operations):
            raise ValueError("Authorization maximum differs from operation count")
        candidates = [item.candidate_vk_id for item in self.operations]
        if len(candidates) != len(set(candidates)):
            raise ValueError("Delete policy contains duplicate candidate IDs")
        primaries = {item.primary_vk_id for item in self.operations}
        overlap = primaries.intersection(candidates)
        if overlap:
            raise ValueError(f"A primary is also scheduled for deletion: {sorted(overlap)[:5]}")
        expected_owner = -self.community_id
        for operation in self.operations:
            if (
                operation.candidate_guard.owner_id != expected_owner
                or operation.primary_guard.owner_id != expected_owner
            ):
                raise ValueError(f"Operation targets another owner: {operation.operation_id}")
        return self

    @classmethod
    def from_file(cls, path: Path) -> DeletePolicy:
        return cls.model_validate_json(path.read_text(encoding="utf-8-sig"))


class OrchestratorConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    canary_batch_size: int = Field(default=5, ge=1, le=25)
    steady_batch_size: int = Field(default=10, ge=1, le=50)
    max_unresolved: int = Field(default=20, ge=1, le=100)
    write_delay_seconds: float = Field(default=1.5, ge=0.75, le=60.0)
    write_jitter_seconds: float = Field(default=0.75, ge=0.0, le=30.0)
    first_reconcile_delay_seconds: int = Field(default=120, ge=30, le=3600)
    absent_confirmation_delay_seconds: int = Field(default=120, ge=30, le=3600)
    visibility_deadline_hours: int = Field(default=24, ge=1, le=168)
    lease_ttl_seconds: int = Field(default=600, ge=60, le=1800)

    @property
    def visibility_deadline(self) -> timedelta:
        return timedelta(hours=self.visibility_deadline_hours)


class ExactVideoObservation(BaseModel):
    model_config = ConfigDict(frozen=True)

    remote_id: str
    present: bool
    payload: dict[str, Any] | None = None
    observed_via: str = "video.get_exact"


def split_remote_id(remote_id: str) -> tuple[int, int]:
    owner_text, separator, video_text = remote_id.partition("_")
    if separator != "_":
        raise ValueError(f"Invalid VK video identity: {remote_id}")
    try:
        owner_id = int(owner_text)
        video_id = int(video_text)
    except ValueError as exc:
        raise ValueError(f"Invalid VK video identity: {remote_id}") from exc
    if owner_id == 0 or video_id <= 0:
        raise ValueError(f"Invalid VK video identity: {remote_id}")
    return owner_id, video_id
