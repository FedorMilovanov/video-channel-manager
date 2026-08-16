from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping

from video_channel_manager.platforms.vk.milovi_rollout_sources import ROLL_OUT_IDS

PROMOTION_SPEC_SCHEMA = "video-manager.milovi-issue-323-reviewed-promotion-spec"
PROMOTION_SPEC_VERSION = 1


def promotion_text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class PromotionField(StrEnum):
    CLIP_DESCRIPTION = "clip_description"
    WALL_MESSAGE = "wall_message"


class PromotionPolicy(StrEnum):
    MANAGED_EXACT = "managed_exact"
    ADOPT_REVIEWED_EXACT = "adopt_reviewed_exact"
    PRESERVE_EXTERNAL = "preserve_external"


class PromotionDecisionAction(StrEnum):
    EDIT = "edit"
    ALREADY_APPLIED = "already_applied"
    ADOPT = "adopt_reviewed_exact"
    PRESERVE = "preserve_external"
    STOP = "stop"


@dataclass(frozen=True, slots=True)
class ReviewedPromotionField:
    source_id: str
    field: PromotionField
    policy: PromotionPolicy
    before_text: str
    before_sha256: str
    after_text: str | None = None
    after_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.source_id not in ROLL_OUT_IDS:
            raise ValueError(f"PromotionSpec source is outside Issue #323 allowlist: {self.source_id!r}")
        if not self.before_text:
            raise ValueError(f"PromotionSpec reviewed BEFORE text is blank: {self.source_id}:{self.field.value}")
        if promotion_text_sha256(self.before_text) != self.before_sha256:
            raise ValueError(f"PromotionSpec BEFORE SHA mismatch: {self.source_id}:{self.field.value}")

        if self.policy is PromotionPolicy.MANAGED_EXACT:
            if self.after_text is None or self.after_sha256 is None:
                raise ValueError(
                    f"managed_exact requires reviewed AFTER text/SHA: {self.source_id}:{self.field.value}"
                )
            if not self.after_text:
                raise ValueError(f"PromotionSpec reviewed AFTER text is blank: {self.source_id}:{self.field.value}")
            if promotion_text_sha256(self.after_text) != self.after_sha256:
                raise ValueError(f"PromotionSpec AFTER SHA mismatch: {self.source_id}:{self.field.value}")
            return

        if self.after_text is not None or self.after_sha256 is not None:
            raise ValueError(
                f"{self.policy.value} has zero edit target authority and must not carry AFTER text/SHA: "
                f"{self.source_id}:{self.field.value}"
            )

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "source_id": self.source_id,
            "field": self.field.value,
            "policy": self.policy.value,
            "before_text": self.before_text,
            "before_sha256": self.before_sha256,
        }
        if self.policy is PromotionPolicy.MANAGED_EXACT:
            payload["after_text"] = self.after_text
            payload["after_sha256"] = self.after_sha256
        return payload


@dataclass(frozen=True, slots=True)
class PromotionSpec:
    review_id: str
    fields: tuple[ReviewedPromotionField, ...]

    def __post_init__(self) -> None:
        if not self.review_id.strip():
            raise ValueError("PromotionSpec review_id is required")
        expected = {(source_id, field) for source_id in ROLL_OUT_IDS for field in PromotionField}
        observed = {(item.source_id, item.field) for item in self.fields}
        if len(observed) != len(self.fields):
            raise ValueError("PromotionSpec contains duplicate source/field entries")
        if observed != expected:
            missing = sorted(f"{source}:{field.value}" for source, field in expected - observed)
            extra = sorted(f"{source}:{field.value}" for source, field in observed - expected)
            raise ValueError(f"PromotionSpec must cover exact 12x2 field set; missing={missing}, extra={extra}")

    def ordered_fields(self) -> tuple[ReviewedPromotionField, ...]:
        by_key = {(item.source_id, item.field): item for item in self.fields}
        return tuple(by_key[(source_id, field)] for source_id in ROLL_OUT_IDS for field in PromotionField)

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_name": PROMOTION_SPEC_SCHEMA,
            "schema_version": PROMOTION_SPEC_VERSION,
            "review_id": self.review_id,
            "fields": [item.as_dict() for item in self.ordered_fields()],
        }

    @property
    def digest(self) -> str:
        canonical = json.dumps(self.as_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


@dataclass(frozen=True, slots=True)
class ObservedPromotionField:
    source_id: str
    field: PromotionField
    text: str
    is_processing_projection: bool = False

    @property
    def sha256(self) -> str:
        return promotion_text_sha256(self.text)


@dataclass(frozen=True, slots=True)
class PromotionFieldDecision:
    source_id: str
    field: PromotionField
    policy: PromotionPolicy
    action: PromotionDecisionAction
    observed_sha256: str
    before_sha256: str
    after_sha256: str | None
    mutation_authorized: bool
    reason: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "field": self.field.value,
            "policy": self.policy.value,
            "action": self.action.value,
            "observed_sha256": self.observed_sha256,
            "before_sha256": self.before_sha256,
            "after_sha256": self.after_sha256,
            "mutation_authorized": self.mutation_authorized,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class PlannedPromotionMutation:
    source_id: str
    field: PromotionField
    before_sha256: str
    after_sha256: str
    after_text: str

    def as_dict(self) -> dict[str, str]:
        return {
            "source_id": self.source_id,
            "field": self.field.value,
            "before_sha256": self.before_sha256,
            "after_sha256": self.after_sha256,
            "after_text": self.after_text,
        }


@dataclass(frozen=True, slots=True)
class PromotionBatchPlan:
    spec_digest: str
    executable: bool
    decisions: tuple[PromotionFieldDecision, ...]
    mutations: tuple[PlannedPromotionMutation, ...]
    blockers: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "spec_digest": self.spec_digest,
            "executable": self.executable,
            "decisions": [decision.as_dict() for decision in self.decisions],
            "mutations": [mutation.as_dict() for mutation in self.mutations],
            "blockers": list(self.blockers),
        }

    @property
    def digest(self) -> str:
        canonical = json.dumps(self.as_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def decide_promotion_field(
    reviewed: ReviewedPromotionField,
    observed: ObservedPromotionField,
) -> PromotionFieldDecision:
    if (observed.source_id, observed.field) != (reviewed.source_id, reviewed.field):
        raise ValueError("Observed promotion field identity differs from reviewed field")

    if observed.is_processing_projection:
        return PromotionFieldDecision(
            source_id=reviewed.source_id,
            field=reviewed.field,
            policy=reviewed.policy,
            action=PromotionDecisionAction.STOP,
            observed_sha256=observed.sha256,
            before_sha256=reviewed.before_sha256,
            after_sha256=reviewed.after_sha256,
            mutation_authorized=False,
            reason="processing projection is read evidence only and cannot grant edit authority",
        )

    if reviewed.policy is PromotionPolicy.MANAGED_EXACT:
        if observed.sha256 == reviewed.before_sha256 and observed.text == reviewed.before_text:
            assert reviewed.after_sha256 is not None
            return PromotionFieldDecision(
                source_id=reviewed.source_id,
                field=reviewed.field,
                policy=reviewed.policy,
                action=PromotionDecisionAction.EDIT,
                observed_sha256=observed.sha256,
                before_sha256=reviewed.before_sha256,
                after_sha256=reviewed.after_sha256,
                mutation_authorized=True,
            )
        if (
            reviewed.after_text is not None
            and reviewed.after_sha256 is not None
            and observed.sha256 == reviewed.after_sha256
            and observed.text == reviewed.after_text
        ):
            return PromotionFieldDecision(
                source_id=reviewed.source_id,
                field=reviewed.field,
                policy=reviewed.policy,
                action=PromotionDecisionAction.ALREADY_APPLIED,
                observed_sha256=observed.sha256,
                before_sha256=reviewed.before_sha256,
                after_sha256=reviewed.after_sha256,
                mutation_authorized=False,
            )
        reason = "current text is neither exact reviewed BEFORE nor exact reviewed AFTER"
    elif observed.sha256 == reviewed.before_sha256 and observed.text == reviewed.before_text:
        action = (
            PromotionDecisionAction.ADOPT
            if reviewed.policy is PromotionPolicy.ADOPT_REVIEWED_EXACT
            else PromotionDecisionAction.PRESERVE
        )
        return PromotionFieldDecision(
            source_id=reviewed.source_id,
            field=reviewed.field,
            policy=reviewed.policy,
            action=action,
            observed_sha256=observed.sha256,
            before_sha256=reviewed.before_sha256,
            after_sha256=None,
            mutation_authorized=False,
        )
    else:
        reason = "current text differs from exact reviewed preserved text"

    return PromotionFieldDecision(
        source_id=reviewed.source_id,
        field=reviewed.field,
        policy=reviewed.policy,
        action=PromotionDecisionAction.STOP,
        observed_sha256=observed.sha256,
        before_sha256=reviewed.before_sha256,
        after_sha256=reviewed.after_sha256,
        mutation_authorized=False,
        reason=reason,
    )


def plan_reviewed_promotion_batch(
    spec: PromotionSpec,
    observed_fields: Mapping[tuple[str, PromotionField], ObservedPromotionField],
) -> PromotionBatchPlan:
    expected = {(source_id, field) for source_id in ROLL_OUT_IDS for field in PromotionField}
    if set(observed_fields) != expected:
        missing = sorted(f"{source}:{field.value}" for source, field in expected - set(observed_fields))
        extra = sorted(f"{source}:{field.value}" for source, field in set(observed_fields) - expected)
        raise ValueError(f"Observed promotion batch must cover exact 12x2 field set; missing={missing}, extra={extra}")

    decisions = tuple(
        decide_promotion_field(reviewed, observed_fields[(reviewed.source_id, reviewed.field)])
        for reviewed in spec.ordered_fields()
    )
    blockers = tuple(
        f"{decision.source_id}:{decision.field.value}: {decision.reason}"
        for decision in decisions
        if decision.action is PromotionDecisionAction.STOP
    )
    if blockers:
        return PromotionBatchPlan(
            spec_digest=spec.digest,
            executable=False,
            decisions=decisions,
            mutations=(),
            blockers=blockers,
        )

    reviewed_by_key = {(item.source_id, item.field): item for item in spec.ordered_fields()}
    mutations: list[PlannedPromotionMutation] = []
    for decision in decisions:
        if decision.action is not PromotionDecisionAction.EDIT:
            continue
        reviewed = reviewed_by_key[(decision.source_id, decision.field)]
        assert reviewed.after_sha256 is not None
        assert reviewed.after_text is not None
        mutations.append(
            PlannedPromotionMutation(
                source_id=decision.source_id,
                field=decision.field,
                before_sha256=reviewed.before_sha256,
                after_sha256=reviewed.after_sha256,
                after_text=reviewed.after_text,
            )
        )
    return PromotionBatchPlan(
        spec_digest=spec.digest,
        executable=True,
        decisions=decisions,
        mutations=tuple(mutations),
        blockers=(),
    )


__all__ = [
    "PROMOTION_SPEC_SCHEMA",
    "PROMOTION_SPEC_VERSION",
    "ObservedPromotionField",
    "PlannedPromotionMutation",
    "PromotionBatchPlan",
    "PromotionDecisionAction",
    "PromotionField",
    "PromotionFieldDecision",
    "PromotionPolicy",
    "PromotionSpec",
    "ReviewedPromotionField",
    "decide_promotion_field",
    "plan_reviewed_promotion_batch",
    "promotion_text_sha256",
]
