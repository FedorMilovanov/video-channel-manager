from __future__ import annotations

import pytest

from video_channel_manager.platforms.vk.milovi_issue323_promotion_observation import (
    PromotionFieldObservation,
    PromotionObservationBatch,
    PromotionObservationEvidence,
)
from video_channel_manager.platforms.vk.milovi_issue323_promotion_spec import (
    PromotionDecisionAction,
    PromotionField,
    PromotionPolicy,
    PromotionSpec,
    ReviewedPromotionField,
    plan_reviewed_promotion_batch,
    promotion_text_sha256,
)
from video_channel_manager.platforms.vk.milovi_rollout_sources import ROLL_OUT_IDS


def _observation(
    source_id: str,
    field: PromotionField,
    *,
    text: str | None = None,
    processing_projection: bool = False,
) -> PromotionFieldObservation:
    value = text if text is not None else f"manual current {source_id} {field.value}"
    return PromotionFieldObservation(
        source_id=source_id,
        field=field,
        text=value,
        sha256=promotion_text_sha256(value),
        remote_id=(
            f"-68859909_{456239200 + ROLL_OUT_IDS.index(source_id)}"
            if field is PromotionField.CLIP_DESCRIPTION
            else f"-68859909_{500 + ROLL_OUT_IDS.index(source_id)}"
        ),
        evidence=(
            PromotionObservationEvidence.EXACT_CLIP_READ
            if field is PromotionField.CLIP_DESCRIPTION
            else PromotionObservationEvidence.EXACT_WALL_INCARNATION
        ),
        processing_projection=processing_projection,
    )


def _batch(*, projection_key: tuple[str, PromotionField] | None = None) -> PromotionObservationBatch:
    fields = tuple(
        _observation(
            source_id,
            field,
            processing_projection=projection_key == (source_id, field),
        )
        for source_id in ROLL_OUT_IDS
        for field in PromotionField
    )
    return PromotionObservationBatch(
        source_snapshot_id="issue323-reviewed-snapshot",
        wall_snapshot_sha256="sha256:wall-snapshot",
        fields=fields,
    )


def _adopt_spec(batch: PromotionObservationBatch) -> PromotionSpec:
    reviewed = tuple(
        ReviewedPromotionField(
            source_id=item.source_id,
            field=item.field,
            policy=PromotionPolicy.ADOPT_REVIEWED_EXACT,
            before_text=item.text,
            before_sha256=item.sha256,
        )
        for item in batch.fields
    )
    return PromotionSpec(review_id="manual-review", fields=reviewed)


def test_arbitrary_manual_copy_is_valid_exact_observation_evidence() -> None:
    value = "operator manual copy that is neither legacy nor generated promotion"
    observed = _observation(ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION, text=value)

    assert observed.text == value
    assert observed.sha256 == promotion_text_sha256(value)
    assert observed.processing_projection is False


def test_observation_requires_field_specific_exact_provider_evidence_kind() -> None:
    value = "exact wall text"
    with pytest.raises(ValueError, match="evidence kind mismatches field"):
        PromotionFieldObservation(
            source_id=ROLL_OUT_IDS[0],
            field=PromotionField.WALL_MESSAGE,
            text=value,
            sha256=promotion_text_sha256(value),
            remote_id="-68859909_500",
            evidence=PromotionObservationEvidence.EXACT_CLIP_READ,
        )


def test_complete_manual_batch_is_reviewable_and_provider_inert() -> None:
    batch = _batch()

    assert batch.complete is True
    assert batch.reviewable is True
    assert batch.as_dict()["provider_mutation_authorized"] is False
    assert len(batch.as_observed_fields()) == len(ROLL_OUT_IDS) * len(PromotionField)


def test_processing_projection_is_preserved_as_evidence_but_not_reviewable() -> None:
    key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    batch = _batch(projection_key=key)

    assert batch.complete is True
    assert batch.reviewable is False
    observed = batch.as_observed_fields()[key]
    assert observed.is_processing_projection is True


def test_processing_projection_reaches_reviewed_planner_as_stop_not_edit_authority() -> None:
    key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    batch = _batch(projection_key=key)
    spec = _adopt_spec(batch)

    plan = plan_reviewed_promotion_batch(spec, batch.as_observed_fields())

    assert plan.executable is False
    assert plan.mutations == ()
    decision = next(item for item in plan.decisions if (item.source_id, item.field) == key)
    assert decision.action is PromotionDecisionAction.STOP
    assert decision.edit_required is False


def test_partial_observation_is_preserved_but_cannot_feed_batch_planner() -> None:
    batch = PromotionObservationBatch(
        source_snapshot_id="issue323-reviewed-snapshot",
        wall_snapshot_sha256="sha256:wall-snapshot",
        fields=(_observation(ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION),),
    )

    assert batch.complete is False
    assert batch.reviewable is False
    assert len(batch.as_dict()["fields"]) == 1
    with pytest.raises(ValueError, match="incomplete"):
        batch.as_observed_fields()


def test_provider_identity_blocker_prevents_planner_conversion_even_with_24_fields() -> None:
    base = _batch()
    blocked = PromotionObservationBatch(
        source_snapshot_id=base.source_snapshot_id,
        wall_snapshot_sha256=base.wall_snapshot_sha256,
        fields=base.fields,
        blockers=("source: exact wall identity unresolved",),
    )

    assert blocked.complete is True
    assert blocked.reviewable is False
    with pytest.raises(ValueError, match="identity blockers"):
        blocked.as_observed_fields()


def test_observation_digest_changes_with_manual_text_or_provider_identity() -> None:
    first = _batch()
    changed_field = _observation(
        ROLL_OUT_IDS[0],
        PromotionField.CLIP_DESCRIPTION,
        text="another manual exact value",
    )
    second = PromotionObservationBatch(
        source_snapshot_id=first.source_snapshot_id,
        wall_snapshot_sha256=first.wall_snapshot_sha256,
        fields=(changed_field, *first.fields[1:]),
    )

    assert first.digest != second.digest
