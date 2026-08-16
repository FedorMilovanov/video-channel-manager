from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from video_channel_manager.platforms.vk.milovi_issue323_promotion_observation import (
    PromotionFieldObservation,
    PromotionObservationBatch,
)
from video_channel_manager.platforms.vk.milovi_issue323_promotion_preflight import (
    PromotionDispatchStatus,
    PromotionExecutionPreflight,
    PromotionOperationState,
    build_promotion_execution_preflight,
    promotion_operation_state_digest,
)
from video_channel_manager.platforms.vk.milovi_issue323_promotion_spec import (
    PromotionField,
    PromotionPolicy,
    PromotionSpec,
    ReviewedPromotionField,
)
from video_channel_manager.platforms.vk.milovi_rollout_sources import ROLL_OUT_IDS

PROMOTION_JOURNAL_SCHEMA = "video-manager.milovi-issue-323-promotion-journal"
PROMOTION_JOURNAL_VERSION = 3

_ALLOWED_TRANSITIONS: Mapping[PromotionDispatchStatus, frozenset[PromotionDispatchStatus]] = {
    PromotionDispatchStatus.PENDING: frozenset({PromotionDispatchStatus.EDIT_INTENT}),
    PromotionDispatchStatus.EDIT_INTENT: frozenset(
        {PromotionDispatchStatus.PENDING, PromotionDispatchStatus.EDIT_DISPATCH_STARTED}
    ),
    PromotionDispatchStatus.EDIT_DISPATCH_STARTED: frozenset(
        {PromotionDispatchStatus.UNKNOWN_REQUIRES_RECONCILIATION, PromotionDispatchStatus.VERIFIED}
    ),
    PromotionDispatchStatus.UNKNOWN_REQUIRES_RECONCILIATION: frozenset({PromotionDispatchStatus.VERIFIED}),
    PromotionDispatchStatus.VERIFIED: frozenset(),
}


class PromotionRecoveryRequired(RuntimeError):
    """A promotion edit may have crossed a provider boundary and needs exact read reconciliation."""


def _require_digest(value: str, *, label: str) -> None:
    if not value.startswith("sha256:") or len(value) != 71:
        raise ValueError(f"{label} must be an exact sha256: digest")
    try:
        int(value[7:], 16)
    except ValueError as exc:
        raise ValueError(f"{label} must be an exact sha256: digest") from exc


def _require_remote_id(value: str, *, label: str) -> None:
    owner, separator, item = value.partition("_")
    if separator != "_":
        raise ValueError(f"{label} must be an exact VK owner_id_item_id")
    try:
        owner_id = int(owner)
        item_id = int(item)
    except ValueError as exc:
        raise ValueError(f"{label} must be an exact VK owner_id_item_id") from exc
    if owner_id == 0 or item_id <= 0:
        raise ValueError(f"{label} must be an exact VK owner_id_item_id")


def _expected_keys() -> set[tuple[str, PromotionField]]:
    return {(source_id, field) for source_id in ROLL_OUT_IDS for field in PromotionField}


@dataclass(frozen=True, slots=True)
class PromotionJournalOperation:
    source_id: str
    field: PromotionField
    status: PromotionDispatchStatus
    dispatch_started: bool = False
    intent_preflight_digest: str | None = None
    intent_confirmation_digest: str | None = None
    intent_remote_id: str | None = None

    def __post_init__(self) -> None:
        PromotionOperationState(
            source_id=self.source_id,
            field=self.field,
            status=self.status,
            dispatch_started=self.dispatch_started,
        )
        if self.status is PromotionDispatchStatus.PENDING:
            if (
                self.intent_preflight_digest is not None
                or self.intent_confirmation_digest is not None
                or self.intent_remote_id is not None
            ):
                raise ValueError(
                    f"Pending promotion operation must not retain intent binding: {self.source_id}:{self.field.value}"
                )
            return
        if (
            self.intent_preflight_digest is None
            or self.intent_confirmation_digest is None
            or self.intent_remote_id is None
        ):
            raise ValueError(
                f"Non-pending promotion operation requires exact confirmed intent binding: "
                f"{self.source_id}:{self.field.value}"
            )
        _require_digest(
            self.intent_preflight_digest,
            label=f"Promotion intent preflight digest {self.source_id}:{self.field.value}",
        )
        _require_digest(
            self.intent_confirmation_digest,
            label=f"Promotion intent confirmation digest {self.source_id}:{self.field.value}",
        )
        _require_remote_id(
            self.intent_remote_id,
            label=f"Promotion intent remote ID {self.source_id}:{self.field.value}",
        )

    def as_planner_state(self) -> PromotionOperationState:
        return PromotionOperationState(
            source_id=self.source_id,
            field=self.field,
            status=self.status,
            dispatch_started=self.dispatch_started,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "field": self.field.value,
            "status": self.status.value,
            "dispatch_started": self.dispatch_started,
            "intent_preflight_digest": self.intent_preflight_digest,
            "intent_confirmation_digest": self.intent_confirmation_digest,
            "intent_remote_id": self.intent_remote_id,
        }


@dataclass(frozen=True, slots=True)
class PromotionJournal:
    spec_digest: str
    baseline_observation_digest: str
    created_at: str
    operations: tuple[PromotionJournalOperation, ...]

    def __post_init__(self) -> None:
        _require_digest(self.spec_digest, label="Promotion journal spec_digest")
        _require_digest(
            self.baseline_observation_digest,
            label="Promotion journal baseline_observation_digest",
        )
        if not self.created_at.strip():
            raise ValueError("Promotion journal created_at is required")
        keys = [(item.source_id, item.field) for item in self.operations]
        if len(set(keys)) != len(keys):
            raise ValueError("Promotion journal contains duplicate source/field operations")
        observed = set(keys)
        expected = _expected_keys()
        if observed != expected:
            missing = sorted(f"{source}:{field.value}" for source, field in expected - observed)
            extra = sorted(f"{source}:{field.value}" for source, field in observed - expected)
            raise ValueError(f"Promotion journal must cover exact 12x2 field set; missing={missing}, extra={extra}")

    def ordered_operations(self) -> tuple[PromotionJournalOperation, ...]:
        by_key = {(item.source_id, item.field): item for item in self.operations}
        return tuple(by_key[(source_id, field)] for source_id in ROLL_OUT_IDS for field in PromotionField)

    def operation_state_map(self) -> dict[tuple[str, PromotionField], PromotionOperationState]:
        return {(item.source_id, item.field): item.as_planner_state() for item in self.ordered_operations()}

    @property
    def operation_state_digest(self) -> str:
        return promotion_operation_state_digest(self.operation_state_map())

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_name": PROMOTION_JOURNAL_SCHEMA,
            "schema_version": PROMOTION_JOURNAL_VERSION,
            "spec_digest": self.spec_digest,
            "baseline_observation_digest": self.baseline_observation_digest,
            "created_at": self.created_at,
            "provider_mutation_authorized": False,
            "operations": [item.as_dict() for item in self.ordered_operations()],
        }

    @property
    def digest(self) -> str:
        canonical = json.dumps(self.as_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def initialize_promotion_journal(
    *,
    spec: PromotionSpec,
    observation: PromotionObservationBatch,
    created_at: str,
) -> PromotionJournal:
    """Create a provider-inert journal only from a fully reviewed, executable baseline."""

    operations = tuple(
        PromotionJournalOperation(
            source_id=source_id,
            field=field,
            status=PromotionDispatchStatus.PENDING,
        )
        for source_id in ROLL_OUT_IDS
        for field in PromotionField
    )
    states = {(item.source_id, item.field): item.as_planner_state() for item in operations}
    preflight = build_promotion_execution_preflight(
        spec=spec,
        observation=observation,
        operation_states=states,
    )
    if not preflight.executable:
        raise ValueError(
            "Promotion journal baseline is not fully executable under reviewed policy; "
            f"blockers={list(preflight.blockers)}"
        )
    return PromotionJournal(
        spec_digest=spec.digest,
        baseline_observation_digest=observation.digest,
        created_at=created_at,
        operations=operations,
    )


def preflight_with_promotion_journal(
    *,
    spec: PromotionSpec,
    observation: PromotionObservationBatch,
    journal: PromotionJournal,
) -> PromotionExecutionPreflight:
    if journal.spec_digest != spec.digest:
        raise ValueError("Promotion journal is bound to a different reviewed PromotionSpec digest")
    return build_promotion_execution_preflight(
        spec=spec,
        observation=observation,
        operation_states=journal.operation_state_map(),
    )


def _operation(journal: PromotionJournal, source_id: str, field: PromotionField) -> PromotionJournalOperation:
    for item in journal.operations:
        if item.source_id == source_id and item.field is field:
            return item
    raise ValueError(f"Promotion journal operation is missing: {source_id}:{field.value}")


def _replace_operation(journal: PromotionJournal, replacement: PromotionJournalOperation) -> PromotionJournal:
    return replace(
        journal,
        operations=tuple(
            replacement if item.source_id == replacement.source_id and item.field is replacement.field else item
            for item in journal.operations
        ),
    )


def _transition_operation(
    journal: PromotionJournal,
    *,
    source_id: str,
    field: PromotionField,
    target: PromotionDispatchStatus,
    intent_preflight_digest: str | None = None,
    intent_confirmation_digest: str | None = None,
    intent_remote_id: str | None = None,
) -> PromotionJournal:
    current = _operation(journal, source_id, field)
    if current.status is target:
        return journal
    if target not in _ALLOWED_TRANSITIONS[current.status]:
        raise RuntimeError(f"Invalid promotion transition {current.status.value} -> {target.value}")
    if target is PromotionDispatchStatus.PENDING:
        replacement = PromotionJournalOperation(
            source_id=source_id,
            field=field,
            status=target,
        )
    else:
        replacement = PromotionJournalOperation(
            source_id=source_id,
            field=field,
            status=target,
            dispatch_started=target
            in {
                PromotionDispatchStatus.EDIT_DISPATCH_STARTED,
                PromotionDispatchStatus.UNKNOWN_REQUIRES_RECONCILIATION,
                PromotionDispatchStatus.VERIFIED,
            },
            intent_preflight_digest=intent_preflight_digest or current.intent_preflight_digest,
            intent_confirmation_digest=intent_confirmation_digest or current.intent_confirmation_digest,
            intent_remote_id=intent_remote_id or current.intent_remote_id,
        )
    return _replace_operation(journal, replacement)


def record_promotion_edit_intent(
    *,
    journal: PromotionJournal,
    preflight: PromotionExecutionPreflight,
    source_id: str,
    field: PromotionField,
) -> PromotionJournal:
    """Persist exact operator-confirmed intent before any provider edit boundary."""

    if journal.spec_digest != preflight.spec_digest:
        raise ValueError("Promotion preflight is bound to a different reviewed PromotionSpec")
    if journal.operation_state_digest != preflight.operation_state_digest:
        raise ValueError("Promotion preflight is stale relative to durable operation state")
    if not preflight.executable or not preflight.planned_mutations:
        raise ValueError("Promotion preflight has no executable mutation intent")
    first = preflight.planned_mutations[0]
    if (first.source_id, first.field) != (source_id, field):
        raise ValueError(
            "Promotion intent must follow deterministic first planned mutation: "
            f"expected={first.source_id}:{first.field.value}, requested={source_id}:{field.value}"
        )
    current = _operation(journal, source_id, field)
    if current.status is not PromotionDispatchStatus.PENDING:
        raise RuntimeError(f"Promotion operation is not pending: {source_id}:{field.value}:{current.status.value}")
    return _transition_operation(
        journal,
        source_id=source_id,
        field=field,
        target=PromotionDispatchStatus.EDIT_INTENT,
        intent_preflight_digest=preflight.digest,
        intent_confirmation_digest=preflight.confirmation_digest,
        intent_remote_id=first.remote_id,
    )


def record_promotion_dispatch_started(
    *,
    journal: PromotionJournal,
    source_id: str,
    field: PromotionField,
    preflight_digest: str,
) -> PromotionJournal:
    """Persist dispatch_started before the outbound provider request."""

    current = _operation(journal, source_id, field)
    if current.status is not PromotionDispatchStatus.EDIT_INTENT:
        raise RuntimeError(f"Promotion dispatch cannot start from {current.status.value}")
    if current.intent_preflight_digest != preflight_digest:
        raise ValueError("Promotion dispatch preflight digest differs from persisted intent")
    if current.intent_confirmation_digest is None:
        raise ValueError("Promotion dispatch has no durable operator confirmation digest")
    return _transition_operation(
        journal,
        source_id=source_id,
        field=field,
        target=PromotionDispatchStatus.EDIT_DISPATCH_STARTED,
    )


def record_promotion_dispatch_unknown(
    *,
    journal: PromotionJournal,
    source_id: str,
    field: PromotionField,
    preflight_digest: str,
) -> PromotionJournal:
    current = _operation(journal, source_id, field)
    if current.status is not PromotionDispatchStatus.EDIT_DISPATCH_STARTED:
        raise RuntimeError(f"Promotion dispatch cannot become unknown from {current.status.value}")
    if current.intent_preflight_digest != preflight_digest:
        raise ValueError("Promotion dispatch preflight digest differs from persisted intent")
    return _transition_operation(
        journal,
        source_id=source_id,
        field=field,
        target=PromotionDispatchStatus.UNKNOWN_REQUIRES_RECONCILIATION,
    )


def _reviewed_field(spec: PromotionSpec, source_id: str, field: PromotionField) -> ReviewedPromotionField:
    for item in spec.fields:
        if item.source_id == source_id and item.field is field:
            return item
    raise ValueError(f"PromotionSpec field is missing: {source_id}:{field.value}")


def _observed_field(
    observation: PromotionObservationBatch,
    source_id: str,
    field: PromotionField,
) -> PromotionFieldObservation:
    for item in observation.ordered_fields():
        if item.source_id == source_id and item.field is field:
            return item
    raise PromotionRecoveryRequired(f"Exact provider observation is missing: {source_id}:{field.value}")


def reconcile_promotion_intent_before_dispatch(
    *,
    journal: PromotionJournal,
    spec: PromotionSpec,
    observation: PromotionObservationBatch,
    source_id: str,
    field: PromotionField,
    preflight_digest: str,
) -> PromotionJournal:
    """Recover a persisted intent only when no dispatch was started and exact BEFORE still holds."""

    if journal.spec_digest != spec.digest:
        raise ValueError("Promotion journal is bound to a different reviewed PromotionSpec")
    current = _operation(journal, source_id, field)
    if current.status is not PromotionDispatchStatus.EDIT_INTENT or current.dispatch_started:
        raise RuntimeError("Only an unstarted edit_intent can be reconciled back to pending")
    if current.intent_preflight_digest != preflight_digest:
        raise ValueError("Promotion reconciliation preflight digest differs from persisted intent")
    reviewed = _reviewed_field(spec, source_id, field)
    if reviewed.policy is not PromotionPolicy.MANAGED_EXACT:
        raise PromotionRecoveryRequired("Persisted edit intent no longer maps to managed_exact policy")
    observed = _observed_field(observation, source_id, field)
    if observed.remote_id != current.intent_remote_id:
        raise PromotionRecoveryRequired("Provider identity changed after edit intent was persisted")
    if observed.processing_projection:
        raise PromotionRecoveryRequired("Provider observation is a processing projection; exact BEFORE is unproven")
    if observed.sha256 != reviewed.before_sha256:
        raise PromotionRecoveryRequired("Provider copy changed after edit intent was persisted")
    return _transition_operation(
        journal,
        source_id=source_id,
        field=field,
        target=PromotionDispatchStatus.PENDING,
    )


def verify_promotion_dispatch_from_observation(
    *,
    journal: PromotionJournal,
    spec: PromotionSpec,
    observation: PromotionObservationBatch,
    source_id: str,
    field: PromotionField,
    preflight_digest: str,
) -> PromotionJournal:
    """Mark a dispatched edit verified only after exact same-identity AFTER readback."""

    if journal.spec_digest != spec.digest:
        raise ValueError("Promotion journal is bound to a different reviewed PromotionSpec")
    current = _operation(journal, source_id, field)
    if current.status not in {
        PromotionDispatchStatus.EDIT_DISPATCH_STARTED,
        PromotionDispatchStatus.UNKNOWN_REQUIRES_RECONCILIATION,
    }:
        raise RuntimeError(f"Promotion dispatch cannot verify from {current.status.value}")
    if current.intent_preflight_digest != preflight_digest:
        raise ValueError("Promotion verification preflight digest differs from persisted intent")
    reviewed = _reviewed_field(spec, source_id, field)
    if reviewed.policy is not PromotionPolicy.MANAGED_EXACT or reviewed.after_sha256 is None:
        raise PromotionRecoveryRequired("Persisted edit intent no longer has a reviewed managed_exact target")
    observed = _observed_field(observation, source_id, field)
    if observed.remote_id != current.intent_remote_id:
        raise PromotionRecoveryRequired("Provider identity changed after edit dispatch")
    if observed.processing_projection:
        raise PromotionRecoveryRequired("Provider observation is a processing projection; exact AFTER is unproven")
    if observed.sha256 != reviewed.after_sha256:
        raise PromotionRecoveryRequired("Exact reviewed AFTER is not visible; do not retry the dispatched edit")
    return _transition_operation(
        journal,
        source_id=source_id,
        field=field,
        target=PromotionDispatchStatus.VERIFIED,
    )


def _exact_keys(payload: Mapping[str, object], allowed: set[str], *, label: str) -> None:
    extra = sorted(set(payload) - allowed)
    if extra:
        raise ValueError(f"{label} contains unknown keys: {extra}")


def promotion_journal_from_mapping(payload: Mapping[str, object]) -> PromotionJournal:
    _exact_keys(
        payload,
        {
            "schema_name",
            "schema_version",
            "spec_digest",
            "baseline_observation_digest",
            "created_at",
            "provider_mutation_authorized",
            "operations",
        },
        label="Promotion journal",
    )
    if payload.get("schema_name") != PROMOTION_JOURNAL_SCHEMA:
        raise ValueError("Promotion journal schema_name mismatch")
    if payload.get("schema_version") != PROMOTION_JOURNAL_VERSION:
        raise ValueError("Promotion journal schema_version mismatch")
    if payload.get("provider_mutation_authorized") is not False:
        raise ValueError("Promotion journal must never persist provider mutation authority")

    spec_digest = payload.get("spec_digest")
    baseline_digest = payload.get("baseline_observation_digest")
    created_at = payload.get("created_at")
    raw_operations = payload.get("operations")
    if not isinstance(spec_digest, str):
        raise ValueError("Promotion journal spec_digest must be a string")
    if not isinstance(baseline_digest, str):
        raise ValueError("Promotion journal baseline_observation_digest must be a string")
    if not isinstance(created_at, str):
        raise ValueError("Promotion journal created_at must be a string")
    if not isinstance(raw_operations, list):
        raise ValueError("Promotion journal operations must be a list")

    operations: list[PromotionJournalOperation] = []
    allowed_operation_keys = {
        "source_id",
        "field",
        "status",
        "dispatch_started",
        "intent_preflight_digest",
        "intent_confirmation_digest",
        "intent_remote_id",
    }
    for index, raw in enumerate(raw_operations):
        if not isinstance(raw, Mapping):
            raise ValueError(f"Promotion journal operation {index} must be an object")
        _exact_keys(raw, allowed_operation_keys, label=f"Promotion journal operation {index}")
        source_id = raw.get("source_id")
        field = raw.get("field")
        status = raw.get("status")
        dispatch_started = raw.get("dispatch_started")
        intent_preflight_digest = raw.get("intent_preflight_digest")
        intent_confirmation_digest = raw.get("intent_confirmation_digest")
        intent_remote_id = raw.get("intent_remote_id")
        if not isinstance(source_id, str):
            raise ValueError(f"Promotion journal operation {index} source_id must be a string")
        if not isinstance(field, str):
            raise ValueError(f"Promotion journal operation {index} field must be a string")
        if not isinstance(status, str):
            raise ValueError(f"Promotion journal operation {index} status must be a string")
        if type(dispatch_started) is not bool:
            raise ValueError(f"Promotion journal operation {index} dispatch_started must be a boolean")
        if intent_preflight_digest is not None and not isinstance(intent_preflight_digest, str):
            raise ValueError(f"Promotion journal operation {index} intent_preflight_digest must be a string or null")
        if intent_confirmation_digest is not None and not isinstance(intent_confirmation_digest, str):
            raise ValueError(f"Promotion journal operation {index} intent_confirmation_digest must be a string or null")
        if intent_remote_id is not None and not isinstance(intent_remote_id, str):
            raise ValueError(f"Promotion journal operation {index} intent_remote_id must be a string or null")
        try:
            parsed_field = PromotionField(field)
            parsed_status = PromotionDispatchStatus(status)
        except ValueError as exc:
            raise ValueError(f"Promotion journal operation {index} has unknown field/status") from exc
        operations.append(
            PromotionJournalOperation(
                source_id=source_id,
                field=parsed_field,
                status=parsed_status,
                dispatch_started=dispatch_started,
                intent_preflight_digest=intent_preflight_digest,
                intent_confirmation_digest=intent_confirmation_digest,
                intent_remote_id=intent_remote_id,
            )
        )

    return PromotionJournal(
        spec_digest=spec_digest,
        baseline_observation_digest=baseline_digest,
        created_at=created_at,
        operations=tuple(operations),
    )


def load_promotion_journal(path: Path) -> PromotionJournal:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Promotion journal is unreadable: {path}") from exc
    if not isinstance(raw, Mapping):
        raise ValueError("Promotion journal root must be an object")
    return promotion_journal_from_mapping(raw)


__all__ = [
    "PROMOTION_JOURNAL_SCHEMA",
    "PROMOTION_JOURNAL_VERSION",
    "PromotionJournal",
    "PromotionJournalOperation",
    "PromotionRecoveryRequired",
    "initialize_promotion_journal",
    "load_promotion_journal",
    "preflight_with_promotion_journal",
    "promotion_journal_from_mapping",
    "reconcile_promotion_intent_before_dispatch",
    "record_promotion_dispatch_started",
    "record_promotion_dispatch_unknown",
    "record_promotion_edit_intent",
    "verify_promotion_dispatch_from_observation",
]
