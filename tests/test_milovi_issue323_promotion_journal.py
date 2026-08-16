from __future__ import annotations

from dataclasses import replace

import pytest

from video_channel_manager.platforms.vk.milovi_issue323_promotion_journal import (
    PromotionJournal,
    initialize_promotion_journal,
    preflight_with_promotion_journal,
    promotion_journal_from_mapping,
)
from video_channel_manager.platforms.vk.milovi_issue323_promotion_observation import (
    PromotionFieldObservation,
    PromotionObservationBatch,
    PromotionObservationEvidence,
)
from video_channel_manager.platforms.vk.milovi_issue323_promotion_preflight import (
    PromotionDispatchStatus,
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


def _spec(*, managed_key: tuple[str, PromotionField] | None = None, review_id: str = "review-1") -> PromotionSpec:
    fields: list[ReviewedPromotionField] = []
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
    return PromotionSpec(review_id=review_id, fields=tuple(fields))


def _observation(
    *,
    override: tuple[str, PromotionField, str] | None = None,
    projection_key: tuple[str, PromotionField] | None = None,
) -> PromotionObservationBatch:
    fields: list[PromotionFieldObservation] = []
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
        captured_at="2026-08-16T10:00:00+00:00",
        fields=tuple(fields),
    )


def _journal(*, managed_key: tuple[str, PromotionField] | None = None) -> PromotionJournal:
    return initialize_promotion_journal(
        spec=_spec(managed_key=managed_key),
        observation=_observation(),
        created_at="2026-08-16T10:05:00+00:00",
    )


def test_initialize_binds_reviewed_spec_and_exact_baseline_without_write_authority() -> None:
    key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    spec = _spec(managed_key=key)
    observation = _observation()

    journal = initialize_promotion_journal(
        spec=spec,
        observation=observation,
        created_at="2026-08-16T10:05:00+00:00",
    )

    assert journal.spec_digest == spec.digest
    assert journal.baseline_observation_digest == observation.digest
    assert len(journal.operations) == len(ROLL_OUT_IDS) * len(PromotionField)
    assert {item.status for item in journal.operations} == {PromotionDispatchStatus.PENDING}
    assert all(item.dispatch_started is False for item in journal.operations)
    payload = journal.as_dict()
    assert payload["provider_mutation_authorized"] is False
    assert journal.digest.startswith("sha256:")


def test_initialize_rejects_manual_drift_in_any_field() -> None:
    key = (ROLL_OUT_IDS[7], PromotionField.WALL_MESSAGE)

    with pytest.raises(ValueError, match="not fully executable"):
        initialize_promotion_journal(
            spec=_spec(managed_key=(ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)),
            observation=_observation(override=(*key, "changed after review")),
            created_at="2026-08-16T10:05:00+00:00",
        )


def test_initialize_rejects_processing_projection_as_edit_baseline() -> None:
    key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)

    with pytest.raises(ValueError, match="not fully executable"):
        initialize_promotion_journal(
            spec=_spec(managed_key=key),
            observation=_observation(projection_key=key),
            created_at="2026-08-16T10:05:00+00:00",
        )


def test_mapping_roundtrip_preserves_exact_operation_state_and_digest() -> None:
    journal = _journal(managed_key=(ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION))

    restored = promotion_journal_from_mapping(journal.as_dict())

    assert restored == journal
    assert restored.digest == journal.digest


def test_mapping_rejects_hidden_keys_or_persisted_write_authority() -> None:
    journal = _journal()
    payload = journal.as_dict()
    payload["unexpected"] = "hidden authority"
    with pytest.raises(ValueError, match="unknown keys"):
        promotion_journal_from_mapping(payload)

    payload = journal.as_dict()
    payload["provider_mutation_authorized"] = True
    with pytest.raises(ValueError, match="must never persist"):
        promotion_journal_from_mapping(payload)


def test_journal_cannot_be_reused_with_a_different_review_digest() -> None:
    observation = _observation()
    journal = initialize_promotion_journal(
        spec=_spec(review_id="review-1"),
        observation=observation,
        created_at="2026-08-16T10:05:00+00:00",
    )

    with pytest.raises(ValueError, match="different reviewed PromotionSpec"):
        preflight_with_promotion_journal(
            spec=_spec(review_id="review-2"),
            observation=observation,
            journal=journal,
        )


def test_unresolved_dispatch_in_durable_journal_zeroes_whole_batch() -> None:
    key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    spec = _spec(managed_key=key)
    observation = _observation()
    journal = initialize_promotion_journal(
        spec=spec,
        observation=observation,
        created_at="2026-08-16T10:05:00+00:00",
    )
    operations = tuple(
        replace(
            item,
            status=PromotionDispatchStatus.EDIT_DISPATCH_STARTED,
            dispatch_started=True,
        )
        if (item.source_id, item.field) == key
        else item
        for item in journal.operations
    )
    unresolved = PromotionJournal(
        spec_digest=journal.spec_digest,
        baseline_observation_digest=journal.baseline_observation_digest,
        created_at=journal.created_at,
        operations=operations,
    )

    preflight = preflight_with_promotion_journal(
        spec=spec,
        observation=observation,
        journal=unresolved,
    )

    assert preflight.executable is False
    assert preflight.expected_provider_writes == 0
    assert preflight.planned_mutations == ()
    assert any("read-reconcile" in blocker for blocker in preflight.blockers)
    assert unresolved.digest != journal.digest
