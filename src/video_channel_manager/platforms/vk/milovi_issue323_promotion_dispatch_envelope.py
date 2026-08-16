from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from video_channel_manager.platforms.vk.milovi_issue323_promotion_journal import (
    PromotionJournal,
    PromotionJournalOperation,
)
from video_channel_manager.platforms.vk.milovi_issue323_promotion_observation import (
    PromotionFieldObservation,
    PromotionObservationBatch,
)
from video_channel_manager.platforms.vk.milovi_issue323_promotion_preflight import (
    PromotionDispatchStatus,
    PromotionOperationState,
    build_promotion_execution_preflight,
)
from video_channel_manager.platforms.vk.milovi_issue323_promotion_spec import (
    PromotionField,
    PromotionPolicy,
    PromotionSpec,
    ReviewedPromotionField,
    promotion_text_sha256,
)
from video_channel_manager.platforms.vk.milovi_rollout_sources import ROLL_OUT_IDS
from video_channel_manager.platforms.vk.wall_safety import VkWallPostFingerprint

PROMOTION_DISPATCH_ENVELOPE_SCHEMA = "video-manager.milovi-issue-323-promotion-dispatch-envelope"
PROMOTION_DISPATCH_ENVELOPE_VERSION = 1


class PromotionDispatchEnvelopeBlocked(RuntimeError):
    """Fresh exact evidence no longer proves the durable operator-confirmed edit intent."""


def _require_sha256_digest(value: str, *, label: str) -> None:
    if not value.startswith("sha256:") or len(value) != 71:
        raise ValueError(f"{label} must be an exact sha256: digest")
    try:
        int(value[7:], 16)
    except ValueError as exc:
        raise ValueError(f"{label} must be an exact sha256: digest") from exc


@dataclass(frozen=True, slots=True)
class PromotionDispatchEnvelope:
    source_id: str
    field: PromotionField
    remote_id: str
    before_text: str
    before_sha256: str
    after_text: str
    after_sha256: str
    spec_digest: str
    confirmation_digest: str
    intent_preflight_digest: str
    fresh_preflight_digest: str
    fresh_observation_digest: str
    provider_state_digest: str
    wall_incarnation: VkWallPostFingerprint | None = None

    def __post_init__(self) -> None:
        if self.source_id not in ROLL_OUT_IDS:
            raise ValueError(f"Dispatch envelope source is outside Issue #323 allowlist: {self.source_id!r}")
        if not self.remote_id:
            raise ValueError("Dispatch envelope requires exact provider identity")
        if promotion_text_sha256(self.before_text) != self.before_sha256:
            raise ValueError("Dispatch envelope BEFORE text/SHA mismatch")
        if promotion_text_sha256(self.after_text) != self.after_sha256:
            raise ValueError("Dispatch envelope AFTER text/SHA mismatch")
        if self.before_text == self.after_text:
            raise ValueError("Dispatch envelope requires a changed exact text target")
        for label, digest in (
            ("spec_digest", self.spec_digest),
            ("confirmation_digest", self.confirmation_digest),
            ("intent_preflight_digest", self.intent_preflight_digest),
            ("fresh_preflight_digest", self.fresh_preflight_digest),
            ("fresh_observation_digest", self.fresh_observation_digest),
            ("provider_state_digest", self.provider_state_digest),
        ):
            _require_sha256_digest(digest, label=f"Dispatch envelope {label}")

        if self.field is PromotionField.CLIP_DESCRIPTION:
            if self.wall_incarnation is not None:
                raise ValueError("Clip dispatch envelope cannot carry wall incarnation evidence")
            return

        wall_incarnation = self.wall_incarnation
        if wall_incarnation is None:
            raise ValueError("Wall dispatch envelope requires exact wall incarnation evidence")
        if wall_incarnation.remote_id != self.remote_id:
            raise ValueError("Wall dispatch envelope identity differs from exact wall incarnation")
        if wall_incarnation.text_sha256 != f"sha256:{self.before_sha256}":
            raise ValueError("Wall dispatch envelope BEFORE digest differs from exact wall incarnation")

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_name": PROMOTION_DISPATCH_ENVELOPE_SCHEMA,
            "schema_version": PROMOTION_DISPATCH_ENVELOPE_VERSION,
            "source_id": self.source_id,
            "field": self.field.value,
            "remote_id": self.remote_id,
            "before_text": self.before_text,
            "before_sha256": self.before_sha256,
            "after_text": self.after_text,
            "after_sha256": self.after_sha256,
            "spec_digest": self.spec_digest,
            "confirmation_digest": self.confirmation_digest,
            "intent_preflight_digest": self.intent_preflight_digest,
            "fresh_preflight_digest": self.fresh_preflight_digest,
            "fresh_observation_digest": self.fresh_observation_digest,
            "provider_state_digest": self.provider_state_digest,
            "wall_incarnation": self.wall_incarnation.as_dict() if self.wall_incarnation is not None else None,
            "provider_mutation_authorized": False,
            "expected_provider_writes": 1,
        }

    @property
    def digest(self) -> str:
        canonical = json.dumps(self.as_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def _journal_operation(
    journal: PromotionJournal,
    source_id: str,
    field: PromotionField,
) -> PromotionJournalOperation:
    for item in journal.operations:
        if item.source_id == source_id and item.field is field:
            return item
    raise ValueError(f"Promotion journal operation is missing: {source_id}:{field.value}")


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
    for item in observation.fields:
        if item.source_id == source_id and item.field is field:
            return item
    raise PromotionDispatchEnvelopeBlocked(f"Fresh provider observation is missing: {source_id}:{field.value}")


def _pre_intent_states(
    journal: PromotionJournal,
    *,
    source_id: str,
    field: PromotionField,
) -> dict[tuple[str, PromotionField], PromotionOperationState]:
    states = journal.operation_state_map()
    states[(source_id, field)] = PromotionOperationState(
        source_id=source_id,
        field=field,
        status=PromotionDispatchStatus.PENDING,
        dispatch_started=False,
    )
    return states


def build_confirmed_promotion_dispatch_envelope(
    *,
    spec: PromotionSpec,
    observation: PromotionObservationBatch,
    journal: PromotionJournal,
    source_id: str,
    field: PromotionField,
) -> PromotionDispatchEnvelope:
    """Freeze one already-confirmed edit from fresh all-batch read-only evidence.

    This builder never calls a provider and never grants provider mutation authority. It
    reconstructs the exact pre-intent operation state, re-runs the whole 12x2 planner
    against fresh evidence, and only emits an immutable envelope when the resulting
    stable confirmation digest is identical to the one durably confirmed by the
    operator before ``EDIT_INTENT`` was persisted.
    """

    if journal.spec_digest != spec.digest:
        raise PromotionDispatchEnvelopeBlocked("Promotion journal is bound to a different reviewed PromotionSpec")

    operation = _journal_operation(journal, source_id, field)
    if operation.status is not PromotionDispatchStatus.EDIT_INTENT or operation.dispatch_started:
        raise PromotionDispatchEnvelopeBlocked(
            f"Dispatch envelope requires one unstarted edit_intent, got {operation.status.value}"
        )
    if operation.intent_confirmation_digest is None or operation.intent_preflight_digest is None:
        raise PromotionDispatchEnvelopeBlocked("Durable edit intent has no exact operator-confirmation evidence")
    if operation.intent_remote_id is None:
        raise PromotionDispatchEnvelopeBlocked("Durable edit intent has no exact provider identity")

    fresh_preflight = build_promotion_execution_preflight(
        spec=spec,
        observation=observation,
        operation_states=_pre_intent_states(journal, source_id=source_id, field=field),
    )
    if not fresh_preflight.executable:
        raise PromotionDispatchEnvelopeBlocked(
            f"Fresh whole-batch preflight is not executable; blockers={list(fresh_preflight.blockers)}"
        )
    if not fresh_preflight.planned_mutations:
        raise PromotionDispatchEnvelopeBlocked("Fresh whole-batch preflight no longer contains an edit mutation")

    mutation = fresh_preflight.planned_mutations[0]
    if (mutation.source_id, mutation.field) != (source_id, field):
        raise PromotionDispatchEnvelopeBlocked(
            "Fresh deterministic first mutation differs from durable edit intent: "
            f"expected={source_id}:{field.value}, fresh={mutation.source_id}:{mutation.field.value}"
        )
    if fresh_preflight.confirmation_digest != operation.intent_confirmation_digest:
        raise PromotionDispatchEnvelopeBlocked(
            "Fresh whole-batch confirmation digest differs from durable operator confirmation; dispatch is forbidden"
        )
    if mutation.remote_id != operation.intent_remote_id:
        raise PromotionDispatchEnvelopeBlocked("Fresh provider identity differs from durable edit intent")

    reviewed = _reviewed_field(spec, source_id, field)
    if (
        reviewed.policy is not PromotionPolicy.MANAGED_EXACT
        or reviewed.after_text is None
        or reviewed.after_sha256 is None
    ):
        raise PromotionDispatchEnvelopeBlocked("Durable edit intent no longer maps to a reviewed managed_exact target")
    observed = _observed_field(observation, source_id, field)
    if observed.processing_projection:
        raise PromotionDispatchEnvelopeBlocked("Fresh target observation is a processing projection")
    if observed.remote_id != mutation.remote_id:
        raise PromotionDispatchEnvelopeBlocked("Fresh target observation identity differs from planned mutation")
    if observed.text != reviewed.before_text or observed.sha256 != reviewed.before_sha256:
        raise PromotionDispatchEnvelopeBlocked("Fresh target text no longer equals the exact reviewed BEFORE state")
    if (
        mutation.before_sha256 != reviewed.before_sha256
        or mutation.after_sha256 != reviewed.after_sha256
        or mutation.after_text != reviewed.after_text
    ):
        raise PromotionDispatchEnvelopeBlocked("Fresh planned mutation differs from the exact reviewed text transition")

    wall_incarnation = observed.wall_incarnation if field is PromotionField.WALL_MESSAGE else None
    return PromotionDispatchEnvelope(
        source_id=source_id,
        field=field,
        remote_id=mutation.remote_id,
        before_text=reviewed.before_text,
        before_sha256=reviewed.before_sha256,
        after_text=reviewed.after_text,
        after_sha256=reviewed.after_sha256,
        spec_digest=spec.digest,
        confirmation_digest=operation.intent_confirmation_digest,
        intent_preflight_digest=operation.intent_preflight_digest,
        fresh_preflight_digest=fresh_preflight.digest,
        fresh_observation_digest=observation.digest,
        provider_state_digest=fresh_preflight.provider_state_digest,
        wall_incarnation=wall_incarnation,
    )


__all__ = [
    "PROMOTION_DISPATCH_ENVELOPE_SCHEMA",
    "PROMOTION_DISPATCH_ENVELOPE_VERSION",
    "PromotionDispatchEnvelope",
    "PromotionDispatchEnvelopeBlocked",
    "build_confirmed_promotion_dispatch_envelope",
]
