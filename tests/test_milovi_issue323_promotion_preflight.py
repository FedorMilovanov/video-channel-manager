from __future__ import annotations

import pytest

from video_channel_manager.platforms.vk.milovi_issue323_promotion_observation import (
    PromotionFieldObservation,
    PromotionObservationBatch,
    PromotionObservationEvidence,
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


def _text(source_id: str, field: PromotionField) -> str:
    return f"reviewed current {source_id} {field.value}"


def _remote_id(source_id: str, field: PromotionField) -> str:
    index = ROLL_OUT_IDS.index(source_id)
    if field is PromotionField.CLIP_DESCRIPTION:
        return f"-68859909_{456239200 + index}"
    return f"-68859909_{500 + index}"


def _spec(*, managed_key: tuple[str, PromotionField] | None = None) -> PromotionSpec:
    fields = []
    for source_id in ROLL_OUT_IDS:
        for field in PromotionField:
            before = _text(source_id, field)
            if managed_key == (source_id, field):
                after = f"reviewed target {source_id} {field.value}"
                fields.append(
                    ReviewedPromotionField(
                        source_id=source_id,
                        field=field,
                        policy=PromotionPolicy.MANAGED_EXACT,
                        before_text=before,
                        before_sha256=promotion_text_sha256(before),
                        after_text=after,
                        after_sha256=promotion_text_sha256(after),
                    )
                )
            else:
                fields.append(
                    ReviewedPromotionField(
                        source_id=source_id,
                        field=field,
                        policy=PromotionPolicy.ADOPT_REVIEWED_EXACT,
                        before_text=before,
                        before_sha256=promotion_text_sha256(before),
                    )
                )
    return PromotionSpec(review_id="exact-review", fields=tuple(fields))


def _observation(
    *,
    override: tuple[str, PromotionField, str] | None = None,
    projection_key: tuple[str, PromotionField] | None = None,
) -> PromotionObservationBatch:
    fields = []
    for source_id in ROLL_OUT_IDS:
        for field in PromotionField:
            value = _text(source_id, field)
            if override is not None and override[:2] == (source_id, field):
                value = override[2]
            fields.append(
                PromotionFieldObservation(
                    source_id=source_id,
                    field=field,
                    text=value,
                    sha256=promotion_text_sha256(value),
                    remote_id=_remote_id(source_id, field),
                    evidence=(
                        PromotionObservationEvidence.EXACT_CLIP_READ
                        if field is PromotionField.CLIP_DESCRIPTION
                        else PromotionObservationEvidence.EXACT_WALL_INCARNATION
                    ),
                    processing_projection=projection_key == (source_id, field),
                )
            )
    return PromotionObservationBatch(
        source_snapshot_id="issue323-reviewed-snapshot",
        wall_snapshot_sha256="sha256:exact-wall-snapshot",
        captured_at="2026-08-16T09:50:00+00:00",
        fields=tuple(fields),
    )


def _states(
    *,
    override: tuple[str, PromotionField, PromotionDispatchStatus, bool] | None = None,
) -> dict[tuple[str, PromotionField], PromotionOperationState]:
    result = {}
    for source_id in ROLL_OUT_IDS:
        for field in PromotionField:
            status = PromotionDispatchStatus.PENDING
            dispatch_started = False
            if override is not None and override[:2] == (source_id, field):
                status = override[2]
                dispatch_started = override[3]
            result[(source_id, field)] = PromotionOperationState(
                source_id=source_id,
                field=field,
                status=status,
                dispatch_started=dispatch_started,
            )
    return result


def test_exact_reviewed_batch_binds_one_edit_to_exact_remote_identity() -> None:
    key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    spec = _spec(managed_key=key)
    observation = _observation()

    preflight = build_promotion_execution_preflight(
        spec=spec,
        observation=observation,
        operation_states=_states(),
    )

    assert preflight.executable is True
    assert preflight.expected_provider_writes == 1
    assert len(preflight.planned_mutations) == 1
    mutation = preflight.planned_mutations[0]
    assert mutation.source_id == key[0]
    assert mutation.field is key[1]
    assert mutation.remote_id == _remote_id(*key)
    assert preflight.spec_digest == spec.digest
    assert preflight.observation_digest == observation.digest
    payload = preflight.as_dict()
    assert payload["provider_mutation_authorized"] is False
    assert payload["confirmation_required"] is True
    assert preflight.digest.startswith("sha256:")


def test_one_copy_drift_zeroes_all_provider_writes() -> None:
    managed_key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    drift_key = (ROLL_OUT_IDS[7], PromotionField.WALL_MESSAGE)
    preflight = build_promotion_execution_preflight(
        spec=_spec(managed_key=managed_key),
        observation=_observation(override=(*drift_key, "operator changed after review")),
        operation_states=_states(),
    )

    assert preflight.executable is False
    assert preflight.planned_mutations == ()
    assert preflight.expected_provider_writes == 0
    assert any(drift_key[0] in blocker for blocker in preflight.blockers)


def test_processing_projection_zeroes_all_provider_writes() -> None:
    key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    preflight = build_promotion_execution_preflight(
        spec=_spec(managed_key=key),
        observation=_observation(projection_key=key),
        operation_states=_states(),
    )

    assert preflight.executable is False
    assert preflight.planned_mutations == ()
    assert preflight.expected_provider_writes == 0
    assert any("processing projection" in blocker for blocker in preflight.blockers)


def test_one_unresolved_dispatch_zeroes_all_provider_writes() -> None:
    managed_key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    unresolved_key = (ROLL_OUT_IDS[5], PromotionField.WALL_MESSAGE)
    preflight = build_promotion_execution_preflight(
        spec=_spec(managed_key=managed_key),
        observation=_observation(),
        operation_states=_states(
            override=(*unresolved_key, PromotionDispatchStatus.EDIT_DISPATCH_STARTED, True)
        ),
    )

    assert preflight.executable is False
    assert preflight.planned_mutations == ()
    assert preflight.expected_provider_writes == 0
    assert any("read-reconcile" in blocker for blocker in preflight.blockers)


def test_verified_operation_cannot_silently_reopen_reviewed_before_edit() -> None:
    key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    preflight = build_promotion_execution_preflight(
        spec=_spec(managed_key=key),
        observation=_observation(),
        operation_states=_states(override=(*key, PromotionDispatchStatus.VERIFIED, True)),
    )

    assert preflight.executable is False
    assert preflight.expected_provider_writes == 0
    assert any("verified but provider still exposes reviewed BEFORE" in blocker for blocker in preflight.blockers)


def test_incomplete_observation_returns_fail_closed_preflight_not_partial_writes() -> None:
    full = _observation()
    partial = PromotionObservationBatch(
        source_snapshot_id=full.source_snapshot_id,
        wall_snapshot_sha256=full.wall_snapshot_sha256,
        captured_at=full.captured_at,
        fields=full.fields[:-1],
    )

    preflight = build_promotion_execution_preflight(
        spec=_spec(managed_key=(ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)),
        observation=partial,
        operation_states=_states(),
    )

    assert preflight.executable is False
    assert preflight.expected_provider_writes == 0
    assert preflight.planned_mutations == ()
    assert "incomplete" in preflight.blockers[0]


def test_operation_state_map_requires_exact_12x2_coverage() -> None:
    states = _states()
    states.pop((ROLL_OUT_IDS[-1], PromotionField.WALL_MESSAGE))

    with pytest.raises(ValueError, match="exact 12x2 field set"):
        build_promotion_execution_preflight(
            spec=_spec(),
            observation=_observation(),
            operation_states=states,
        )
