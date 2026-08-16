from __future__ import annotations

import pytest

from video_channel_manager.platforms.vk.milovi_issue323_promotion_observation import (
    PromotionFieldObservation,
    PromotionObservationBatch,
    PromotionObservationEvidence,
    PromotionObservedCopyState,
    classify_clip_copy_observation,
    classify_wall_copy_observation,
    promotion_observation_from_mapping,
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
from video_channel_manager.platforms.vk.wall_safety import VkWallPostFingerprint, VkWallSurface


def _wall_incarnation(
    source_id: str,
    text: str,
    *,
    surface: VkWallSurface = VkWallSurface.PUBLISHED,
    publish_date: int | None = None,
    attachments: tuple[str, ...] | None = None,
) -> VkWallPostFingerprint:
    index = ROLL_OUT_IDS.index(source_id)
    return VkWallPostFingerprint(
        owner_id=-68859909,
        post_id=500 + index,
        surface=surface,
        publish_date=publish_date if publish_date is not None else 1_700_000_000 + index,
        text_sha256=promotion_text_sha256(text),
        attachments=(attachments if attachments is not None else (f"video-68859909_{456239200 + index}",)),
    )


def _observation(
    source_id: str,
    field: PromotionField,
    *,
    text: str | None = None,
    processing_projection: bool = False,
    wall_surface: VkWallSurface = VkWallSurface.PUBLISHED,
    wall_publish_date: int | None = None,
    wall_attachments: tuple[str, ...] | None = None,
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
        wall_incarnation=(
            None
            if field is PromotionField.CLIP_DESCRIPTION
            else _wall_incarnation(
                source_id,
                value,
                surface=wall_surface,
                publish_date=wall_publish_date,
                attachments=wall_attachments,
            )
        ),
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
        captured_at="2026-08-16T09:40:00+00:00",
        fields=fields,
    )


def _status_payload(batch: PromotionObservationBatch) -> dict[str, object]:
    payload = batch.as_dict()
    payload["observation_digest"] = batch.digest
    return payload


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


def test_manual_copy_classifies_as_unreviewed_exact_instead_of_error() -> None:
    state = classify_clip_copy_observation(
        current="operator-edited third state",
        legacy="legacy exact",
        promoted="promoted exact",
        provider_item={"processing": 0, "converting": 0},
    )

    assert state is PromotionObservedCopyState.UNREVIEWED_EXACT
    assert state.requires_review is True
    assert state.processing_projection is False
    assert (
        classify_wall_copy_observation(
            current="manual wall text",
            legacy="legacy wall",
            promoted="promoted wall",
        )
        is PromotionObservedCopyState.UNREVIEWED_EXACT
    )


def test_known_processing_projection_does_not_regress_phase_continuation_authority() -> None:
    promoted = "P" * 120
    state = classify_clip_copy_observation(
        current=f"{promoted[:100]}…",
        legacy="L" * 120,
        promoted=promoted,
        provider_item={"processing": 1},
    )

    assert state is PromotionObservedCopyState.PROCESSING_PROMOTED_PROJECTION
    assert state.requires_review is False
    assert state.processing_projection is True


def test_busy_unknown_copy_is_processing_projection_not_exact_manual_authority() -> None:
    state = classify_clip_copy_observation(
        current="provider projected unknown text",
        legacy="L" * 120,
        promoted="P" * 120,
        provider_item={"processing": 1},
    )

    assert state is PromotionObservedCopyState.PROCESSING_UNREVIEWED_PROJECTION
    assert state.requires_review is True
    assert state.processing_projection is True


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
            wall_incarnation=_wall_incarnation(ROLL_OUT_IDS[0], value),
        )


def test_wall_observation_requires_exact_incarnation_and_clip_forbids_it() -> None:
    value = "exact wall text"
    with pytest.raises(ValueError, match="requires exact wall incarnation"):
        PromotionFieldObservation(
            source_id=ROLL_OUT_IDS[0],
            field=PromotionField.WALL_MESSAGE,
            text=value,
            sha256=promotion_text_sha256(value),
            remote_id="-68859909_500",
            evidence=PromotionObservationEvidence.EXACT_WALL_INCARNATION,
        )

    clip = _observation(ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    with pytest.raises(ValueError, match="cannot carry wall incarnation"):
        PromotionFieldObservation(
            source_id=clip.source_id,
            field=clip.field,
            text=clip.text,
            sha256=clip.sha256,
            remote_id=clip.remote_id,
            evidence=clip.evidence,
            wall_incarnation=_wall_incarnation(ROLL_OUT_IDS[0], clip.text),
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
        captured_at="2026-08-16T09:40:00+00:00",
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
        captured_at=base.captured_at,
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
        captured_at=first.captured_at,
        fields=(changed_field, *first.fields[1:]),
    )

    assert first.digest != second.digest


def test_provider_state_digest_binds_wall_surface_publish_date_and_attachments() -> None:
    base = _batch()
    source_id = ROLL_OUT_IDS[0]
    wall_index = next(
        index
        for index, item in enumerate(base.fields)
        if item.source_id == source_id and item.field is PromotionField.WALL_MESSAGE
    )
    text = base.fields[wall_index].text
    variants = (
        _observation(
            source_id,
            PromotionField.WALL_MESSAGE,
            text=text,
            wall_surface=VkWallSurface.POSTPONED,
        ),
        _observation(
            source_id,
            PromotionField.WALL_MESSAGE,
            text=text,
            wall_publish_date=1_700_000_999,
        ),
        _observation(
            source_id,
            PromotionField.WALL_MESSAGE,
            text=text,
            wall_attachments=("photo-68859909_1", "video-68859909_456239200"),
        ),
    )

    for changed_wall in variants:
        fields = list(base.fields)
        fields[wall_index] = changed_wall
        changed = PromotionObservationBatch(
            source_snapshot_id=base.source_snapshot_id,
            wall_snapshot_sha256=base.wall_snapshot_sha256,
            captured_at=base.captured_at,
            fields=tuple(fields),
        )
        assert changed.provider_state_digest != base.provider_state_digest


def test_status_observation_payload_roundtrips_with_exact_digest() -> None:
    batch = _batch()

    restored = promotion_observation_from_mapping(_status_payload(batch))

    assert restored == batch
    assert restored.digest == batch.digest


def test_observation_loader_rejects_tampered_text_sha_or_digest() -> None:
    batch = _batch()
    payload = _status_payload(batch)
    fields = list(payload["fields"])  # type: ignore[arg-type]
    first = dict(fields[0])
    first["text"] = "tampered after capture"
    fields[0] = first
    payload["fields"] = fields
    with pytest.raises(ValueError, match="SHA mismatch"):
        promotion_observation_from_mapping(payload)

    payload = _status_payload(batch)
    payload["observation_digest"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="digest mismatch"):
        promotion_observation_from_mapping(payload)


def test_observation_loader_rejects_tampered_wall_incarnation() -> None:
    batch = _batch()
    payload = _status_payload(batch)
    fields = list(payload["fields"])  # type: ignore[arg-type]
    wall_index = next(index for index, item in enumerate(fields) if item["field"] == PromotionField.WALL_MESSAGE.value)
    wall = dict(fields[wall_index])
    incarnation = dict(wall["wall_incarnation"])
    incarnation["surface"] = VkWallSurface.POSTPONED.value
    wall["wall_incarnation"] = incarnation
    fields[wall_index] = wall
    payload["fields"] = fields
    payload["observation_digest"] = None

    restored = promotion_observation_from_mapping(payload)
    assert restored.provider_state_digest != batch.provider_state_digest

    payload = _status_payload(batch)
    fields = list(payload["fields"])  # type: ignore[arg-type]
    wall = dict(fields[wall_index])
    incarnation = dict(wall["wall_incarnation"])
    incarnation["hidden"] = "not-reviewed"
    wall["wall_incarnation"] = incarnation
    fields[wall_index] = wall
    payload["fields"] = fields
    with pytest.raises(ValueError, match="unknown keys"):
        promotion_observation_from_mapping(payload)


def test_observation_loader_rejects_hidden_keys_or_write_authority() -> None:
    batch = _batch()
    payload = _status_payload(batch)
    payload["unexpected"] = "hidden"
    with pytest.raises(ValueError, match="unknown keys"):
        promotion_observation_from_mapping(payload)

    payload = _status_payload(batch)
    payload["provider_mutation_authorized"] = True
    with pytest.raises(ValueError, match="must never carry"):
        promotion_observation_from_mapping(payload)


def test_observation_loader_rejects_forged_derived_flags() -> None:
    batch = _batch()
    payload = _status_payload(batch)
    payload["complete"] = False
    with pytest.raises(ValueError, match="complete flag"):
        promotion_observation_from_mapping(payload)

    payload = _status_payload(batch)
    payload["reviewable"] = False
    with pytest.raises(ValueError, match="reviewable flag"):
        promotion_observation_from_mapping(payload)
