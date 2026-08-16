from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from video_channel_manager.platforms.vk.milovi_issue323_promotion_observation import (
    PromotionObservationBatch,
)
from video_channel_manager.platforms.vk.milovi_issue323_promotion_preflight import (
    PromotionDispatchStatus,
    PromotionExecutionPreflight,
    PromotionOperationState,
    build_promotion_execution_preflight,
)
from video_channel_manager.platforms.vk.milovi_issue323_promotion_spec import PromotionField, PromotionSpec
from video_channel_manager.platforms.vk.milovi_rollout_sources import ROLL_OUT_IDS

PROMOTION_JOURNAL_SCHEMA = "video-manager.milovi-issue-323-promotion-journal"
PROMOTION_JOURNAL_VERSION = 1


def _require_digest(value: str, *, label: str) -> None:
    if not value.startswith("sha256:") or len(value) != 71:
        raise ValueError(f"{label} must be an exact sha256: digest")
    try:
        int(value[7:], 16)
    except ValueError as exc:
        raise ValueError(f"{label} must be an exact sha256: digest") from exc


def _expected_keys() -> set[tuple[str, PromotionField]]:
    return {(source_id, field) for source_id in ROLL_OUT_IDS for field in PromotionField}


@dataclass(frozen=True, slots=True)
class PromotionJournal:
    spec_digest: str
    baseline_observation_digest: str
    created_at: str
    operations: tuple[PromotionOperationState, ...]

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

    def ordered_operations(self) -> tuple[PromotionOperationState, ...]:
        by_key = {(item.source_id, item.field): item for item in self.operations}
        return tuple(by_key[(source_id, field)] for source_id in ROLL_OUT_IDS for field in PromotionField)

    def operation_state_map(self) -> dict[tuple[str, PromotionField], PromotionOperationState]:
        return {(item.source_id, item.field): item for item in self.ordered_operations()}

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
        PromotionOperationState(
            source_id=source_id,
            field=field,
            status=PromotionDispatchStatus.PENDING,
            dispatch_started=False,
        )
        for source_id in ROLL_OUT_IDS
        for field in PromotionField
    )
    preflight = build_promotion_execution_preflight(
        spec=spec,
        observation=observation,
        operation_states={(item.source_id, item.field): item for item in operations},
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

    operations: list[PromotionOperationState] = []
    allowed_operation_keys = {"source_id", "field", "status", "dispatch_started"}
    for index, raw in enumerate(raw_operations):
        if not isinstance(raw, Mapping):
            raise ValueError(f"Promotion journal operation {index} must be an object")
        _exact_keys(raw, allowed_operation_keys, label=f"Promotion journal operation {index}")
        source_id = raw.get("source_id")
        field = raw.get("field")
        status = raw.get("status")
        dispatch_started = raw.get("dispatch_started")
        if not isinstance(source_id, str):
            raise ValueError(f"Promotion journal operation {index} source_id must be a string")
        if not isinstance(field, str):
            raise ValueError(f"Promotion journal operation {index} field must be a string")
        if not isinstance(status, str):
            raise ValueError(f"Promotion journal operation {index} status must be a string")
        if type(dispatch_started) is not bool:
            raise ValueError(f"Promotion journal operation {index} dispatch_started must be a boolean")
        try:
            parsed_field = PromotionField(field)
            parsed_status = PromotionDispatchStatus(status)
        except ValueError as exc:
            raise ValueError(f"Promotion journal operation {index} has unknown field/status") from exc
        operations.append(
            PromotionOperationState(
                source_id=source_id,
                field=parsed_field,
                status=parsed_status,
                dispatch_started=dispatch_started,
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
    "initialize_promotion_journal",
    "load_promotion_journal",
    "preflight_with_promotion_journal",
    "promotion_journal_from_mapping",
]
