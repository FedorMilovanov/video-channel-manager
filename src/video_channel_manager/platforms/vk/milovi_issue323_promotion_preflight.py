from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping

from video_channel_manager.platforms.vk.milovi_issue323_promotion_observation import (
    PromotionObservationBatch,
)
from video_channel_manager.platforms.vk.milovi_issue323_promotion_spec import (
    PlannedPromotionMutation,
    PromotionDecisionAction,
    PromotionField,
    PromotionSpec,
    plan_reviewed_promotion_batch,
)
from video_channel_manager.platforms.vk.milovi_rollout_sources import ROLL_OUT_IDS

PROMOTION_PREFLIGHT_SCHEMA = "video-manager.milovi-issue-323-promotion-execution-preflight"
PROMOTION_PREFLIGHT_VERSION = 1


class PromotionDispatchStatus(StrEnum):
    PENDING = "pending"
    EDIT_INTENT = "edit_intent"
    EDIT_DISPATCH_STARTED = "edit_dispatch_started"
    UNKNOWN_REQUIRES_RECONCILIATION = "unknown_requires_reconciliation"
    VERIFIED = "verified"


@dataclass(frozen=True, slots=True)
class PromotionOperationState:
    source_id: str
    field: PromotionField
    status: PromotionDispatchStatus
    dispatch_started: bool = False

    def __post_init__(self) -> None:
        if self.source_id not in ROLL_OUT_IDS:
            raise ValueError(f"Promotion operation source is outside Issue #323 allowlist: {self.source_id!r}")
        if self.status is PromotionDispatchStatus.PENDING and self.dispatch_started:
            raise ValueError(
                f"Pending promotion operation cannot have dispatch_started=true: {self.source_id}:{self.field.value}"
            )
        if self.status is PromotionDispatchStatus.EDIT_DISPATCH_STARTED and not self.dispatch_started:
            raise ValueError(
                f"edit_dispatch_started must carry dispatch_started=true: {self.source_id}:{self.field.value}"
            )

    @property
    def unresolved_dispatch(self) -> bool:
        if self.status in {
            PromotionDispatchStatus.EDIT_INTENT,
            PromotionDispatchStatus.EDIT_DISPATCH_STARTED,
            PromotionDispatchStatus.UNKNOWN_REQUIRES_RECONCILIATION,
        }:
            return True
        return self.dispatch_started and self.status is not PromotionDispatchStatus.VERIFIED

    def as_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "field": self.field.value,
            "status": self.status.value,
            "dispatch_started": self.dispatch_started,
        }


@dataclass(frozen=True, slots=True)
class ExecutablePromotionMutation:
    source_id: str
    field: PromotionField
    remote_id: str
    before_sha256: str
    after_sha256: str
    after_text: str

    def as_dict(self) -> dict[str, str]:
        return {
            "source_id": self.source_id,
            "field": self.field.value,
            "remote_id": self.remote_id,
            "before_sha256": self.before_sha256,
            "after_sha256": self.after_sha256,
            "after_text": self.after_text,
        }


@dataclass(frozen=True, slots=True)
class PromotionExecutionPreflight:
    spec_digest: str
    observation_digest: str
    executable: bool
    planned_mutations: tuple[ExecutablePromotionMutation, ...]
    blockers: tuple[str, ...]

    @property
    def expected_provider_writes(self) -> int:
        return len(self.planned_mutations) if self.executable else 0

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_name": PROMOTION_PREFLIGHT_SCHEMA,
            "schema_version": PROMOTION_PREFLIGHT_VERSION,
            "spec_digest": self.spec_digest,
            "observation_digest": self.observation_digest,
            "executable": self.executable,
            "provider_mutation_authorized": False,
            "confirmation_required": self.executable and bool(self.planned_mutations),
            "expected_provider_writes": self.expected_provider_writes,
            "planned_mutations": [mutation.as_dict() for mutation in self.planned_mutations],
            "blockers": list(self.blockers),
        }

    @property
    def digest(self) -> str:
        canonical = json.dumps(self.as_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def _expected_keys() -> set[tuple[str, PromotionField]]:
    return {(source_id, field) for source_id in ROLL_OUT_IDS for field in PromotionField}


def _operation_state_map(
    states: Mapping[tuple[str, PromotionField], PromotionOperationState],
) -> Mapping[tuple[str, PromotionField], PromotionOperationState]:
    expected = _expected_keys()
    observed = set(states)
    if observed != expected:
        missing = sorted(f"{source}:{field.value}" for source, field in expected - observed)
        extra = sorted(f"{source}:{field.value}" for source, field in observed - expected)
        raise ValueError(
            f"Promotion operation states must cover exact 12x2 field set; missing={missing}, extra={extra}"
        )
    for key, state in states.items():
        if key != (state.source_id, state.field):
            raise ValueError(f"Promotion operation state key differs from payload identity: {key!r}")
    return states


def _dispatch_blocker(state: PromotionOperationState, decision: PromotionDecisionAction) -> str | None:
    if state.unresolved_dispatch:
        return (
            f"{state.source_id}:{state.field.value}: prior {state.status.value} is unresolved; "
            "read-reconcile before any promotion write"
        )
    if state.status is PromotionDispatchStatus.VERIFIED and decision is PromotionDecisionAction.EDIT:
        return f"{state.source_id}:{state.field.value}: durable operation says verified but provider still exposes reviewed BEFORE"
    if state.status is PromotionDispatchStatus.VERIFIED and decision in {
        PromotionDecisionAction.ADOPT,
        PromotionDecisionAction.PRESERVE,
    }:
        return f"{state.source_id}:{state.field.value}: durable edit history conflicts with no-edit reviewed policy"
    return None


def build_promotion_execution_preflight(
    *,
    spec: PromotionSpec,
    observation: PromotionObservationBatch,
    operation_states: Mapping[tuple[str, PromotionField], PromotionOperationState],
) -> PromotionExecutionPreflight:
    """Build one provider-inert all-or-nothing promotion execution plan."""

    states = _operation_state_map(operation_states)
    try:
        observed_fields = observation.as_observed_fields()
    except ValueError as exc:
        return PromotionExecutionPreflight(
            spec_digest=spec.digest,
            observation_digest=observation.digest,
            executable=False,
            planned_mutations=(),
            blockers=(str(exc),),
        )

    reviewed_plan = plan_reviewed_promotion_batch(spec, observed_fields)
    blockers = list(reviewed_plan.blockers)
    decision_by_key = {(item.source_id, item.field): item for item in reviewed_plan.decisions}
    for key in sorted(states, key=lambda item: (ROLL_OUT_IDS.index(item[0]), item[1].value)):
        blocker = _dispatch_blocker(states[key], decision_by_key[key].action)
        if blocker is not None:
            blockers.append(blocker)

    if blockers:
        return PromotionExecutionPreflight(
            spec_digest=spec.digest,
            observation_digest=observation.digest,
            executable=False,
            planned_mutations=(),
            blockers=tuple(blockers),
        )

    observation_by_key = {(item.source_id, item.field): item for item in observation.ordered_fields()}
    executable_mutations = tuple(
        _bind_mutation_identity(mutation, observation_by_key[(mutation.source_id, mutation.field)].remote_id)
        for mutation in reviewed_plan.mutations
    )
    return PromotionExecutionPreflight(
        spec_digest=spec.digest,
        observation_digest=observation.digest,
        executable=True,
        planned_mutations=executable_mutations,
        blockers=(),
    )


def _bind_mutation_identity(mutation: PlannedPromotionMutation, remote_id: str) -> ExecutablePromotionMutation:
    if not remote_id:
        raise ValueError(
            f"Promotion mutation lost exact provider identity: {mutation.source_id}:{mutation.field.value}"
        )
    return ExecutablePromotionMutation(
        source_id=mutation.source_id,
        field=mutation.field,
        remote_id=remote_id,
        before_sha256=mutation.before_sha256,
        after_sha256=mutation.after_sha256,
        after_text=mutation.after_text,
    )


__all__ = [
    "PROMOTION_PREFLIGHT_SCHEMA",
    "PROMOTION_PREFLIGHT_VERSION",
    "ExecutablePromotionMutation",
    "PromotionDispatchStatus",
    "PromotionExecutionPreflight",
    "PromotionOperationState",
    "build_promotion_execution_preflight",
]
