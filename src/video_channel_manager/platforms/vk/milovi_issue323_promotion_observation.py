from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from video_channel_manager.platforms.vk.milovi_issue323_promotion_spec import (
    ObservedPromotionField,
    PromotionField,
    promotion_text_sha256,
)
from video_channel_manager.platforms.vk.milovi_rollout_sources import ROLL_OUT_IDS

PROMOTION_OBSERVATION_SCHEMA = "video-manager.milovi-issue-323-promotion-observation"
PROMOTION_OBSERVATION_VERSION = 1
_MIN_PROCESSING_COPY_PREFIX = 80


class PromotionObservationEvidence(StrEnum):
    EXACT_CLIP_READ = "exact_clip_read"
    EXACT_WALL_INCARNATION = "exact_wall_incarnation"


class PromotionObservedCopyState(StrEnum):
    LEGACY = "legacy"
    PROMOTED = "promoted"
    UNREVIEWED_EXACT = "unreviewed_exact"
    PROCESSING_LEGACY_PROJECTION = "provider_processing_legacy_projection"
    PROCESSING_PROMOTED_PROJECTION = "provider_processing_promoted_projection"
    PROCESSING_UNREVIEWED_PROJECTION = "provider_processing_unreviewed_projection"

    @property
    def requires_review(self) -> bool:
        return self not in {PromotionObservedCopyState.LEGACY, PromotionObservedCopyState.PROMOTED}

    @property
    def processing_projection(self) -> bool:
        return self in {
            PromotionObservedCopyState.PROCESSING_LEGACY_PROJECTION,
            PromotionObservedCopyState.PROCESSING_PROMOTED_PROJECTION,
            PromotionObservedCopyState.PROCESSING_UNREVIEWED_PROJECTION,
        }


def _processing_copy_prefix(current: str) -> str | None:
    value = current.strip()
    if value.endswith("…"):
        prefix = value[:-1].rstrip()
    else:
        trailing_dots = len(value) - len(value.rstrip("."))
        if trailing_dots < 2:
            return None
        prefix = value[:-trailing_dots].rstrip()
    if len(prefix) < _MIN_PROCESSING_COPY_PREFIX:
        return None
    return prefix


def classify_clip_copy_observation(
    *,
    current: str,
    legacy: str,
    promoted: str,
    provider_item: Mapping[str, object],
) -> PromotionObservedCopyState:
    """Classify public Clip copy for observation only; never grant mutation authority."""

    if current == promoted:
        return PromotionObservedCopyState.PROMOTED
    if current == legacy:
        return PromotionObservedCopyState.LEGACY

    provider_busy = bool(provider_item.get("processing")) or bool(provider_item.get("converting"))
    if not provider_busy:
        return PromotionObservedCopyState.UNREVIEWED_EXACT

    prefix = _processing_copy_prefix(current)
    if prefix is not None:
        if promoted.startswith(prefix):
            return PromotionObservedCopyState.PROCESSING_PROMOTED_PROJECTION
        if legacy.startswith(prefix):
            return PromotionObservedCopyState.PROCESSING_LEGACY_PROJECTION
    return PromotionObservedCopyState.PROCESSING_UNREVIEWED_PROJECTION


def classify_wall_copy_observation(*, current: str, legacy: str, promoted: str) -> PromotionObservedCopyState:
    """Classify exact wall text without treating manual third-state copy as an error."""

    if current == promoted:
        return PromotionObservedCopyState.PROMOTED
    if current == legacy:
        return PromotionObservedCopyState.LEGACY
    return PromotionObservedCopyState.UNREVIEWED_EXACT


@dataclass(frozen=True, slots=True)
class PromotionFieldObservation:
    source_id: str
    field: PromotionField
    text: str
    sha256: str
    remote_id: str
    evidence: PromotionObservationEvidence
    processing_projection: bool = False

    def __post_init__(self) -> None:
        if self.source_id not in ROLL_OUT_IDS:
            raise ValueError(f"Promotion observation source is outside Issue #323 allowlist: {self.source_id!r}")
        if not self.remote_id:
            raise ValueError(f"Promotion observation lost provider identity: {self.source_id}:{self.field.value}")
        if promotion_text_sha256(self.text) != self.sha256:
            raise ValueError(f"Promotion observation SHA mismatch: {self.source_id}:{self.field.value}")
        if self.field is PromotionField.CLIP_DESCRIPTION:
            expected_evidence = PromotionObservationEvidence.EXACT_CLIP_READ
        else:
            expected_evidence = PromotionObservationEvidence.EXACT_WALL_INCARNATION
        if self.evidence is not expected_evidence:
            raise ValueError(
                f"Promotion observation evidence kind mismatches field: {self.source_id}:{self.field.value}"
            )
        if self.field is PromotionField.WALL_MESSAGE and self.processing_projection:
            raise ValueError("Wall text cannot be represented as a Clip processing projection")

    def as_observed_field(self) -> ObservedPromotionField:
        return ObservedPromotionField(
            source_id=self.source_id,
            field=self.field,
            text=self.text,
            is_processing_projection=self.processing_projection,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "field": self.field.value,
            "text": self.text,
            "sha256": self.sha256,
            "remote_id": self.remote_id,
            "evidence": self.evidence.value,
            "processing_projection": self.processing_projection,
        }


@dataclass(frozen=True, slots=True)
class PromotionObservationBatch:
    source_snapshot_id: str
    wall_snapshot_sha256: str
    captured_at: str
    fields: tuple[PromotionFieldObservation, ...]
    blockers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.source_snapshot_id:
            raise ValueError("Promotion observation source_snapshot_id is required")
        if not self.wall_snapshot_sha256:
            raise ValueError("Promotion observation wall_snapshot_sha256 is required")
        if not self.captured_at:
            raise ValueError("Promotion observation captured_at is required")
        keys = [(item.source_id, item.field) for item in self.fields]
        if len(set(keys)) != len(keys):
            raise ValueError("Promotion observation contains duplicate source/field evidence")

    @property
    def expected_keys(self) -> set[tuple[str, PromotionField]]:
        return {(source_id, field) for source_id in ROLL_OUT_IDS for field in PromotionField}

    @property
    def observed_keys(self) -> set[tuple[str, PromotionField]]:
        return {(item.source_id, item.field) for item in self.fields}

    @property
    def complete(self) -> bool:
        return self.observed_keys == self.expected_keys

    @property
    def reviewable(self) -> bool:
        return self.complete and not self.blockers and not any(item.processing_projection for item in self.fields)

    def ordered_fields(self) -> tuple[PromotionFieldObservation, ...]:
        by_key = {(item.source_id, item.field): item for item in self.fields}
        return tuple(
            by_key[(source_id, field)]
            for source_id in ROLL_OUT_IDS
            for field in PromotionField
            if (source_id, field) in by_key
        )

    def as_observed_fields(self) -> dict[tuple[str, PromotionField], ObservedPromotionField]:
        if not self.complete:
            missing = sorted(
                f"{source_id}:{field.value}" for source_id, field in self.expected_keys - self.observed_keys
            )
            raise ValueError(f"Promotion observation is incomplete; missing={missing}")
        if self.blockers:
            raise ValueError(f"Promotion observation has unresolved provider identity blockers: {list(self.blockers)}")
        return {
            (item.source_id, item.field): item.as_observed_field()
            for item in self.ordered_fields()
        }

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_name": PROMOTION_OBSERVATION_SCHEMA,
            "schema_version": PROMOTION_OBSERVATION_VERSION,
            "source_snapshot_id": self.source_snapshot_id,
            "wall_snapshot_sha256": self.wall_snapshot_sha256,
            "captured_at": self.captured_at,
            "provider_mutation_authorized": False,
            "complete": self.complete,
            "reviewable": self.reviewable,
            "fields": [item.as_dict() for item in self.ordered_fields()],
            "blockers": list(self.blockers),
        }

    @property
    def digest(self) -> str:
        canonical = json.dumps(self.as_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


__all__ = [
    "PROMOTION_OBSERVATION_SCHEMA",
    "PROMOTION_OBSERVATION_VERSION",
    "PromotionFieldObservation",
    "PromotionObservationBatch",
    "PromotionObservationEvidence",
    "PromotionObservedCopyState",
    "classify_clip_copy_observation",
    "classify_wall_copy_observation",
]
