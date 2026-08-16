from __future__ import annotations

import pytest

from video_channel_manager.platforms.vk.milovi_issue323_promotion_journal import (
    PromotionJournal,
    PromotionRecoveryRequired,
    initialize_promotion_journal,
    preflight_with_promotion_journal,
    promotion_journal_from_mapping,
    reconcile_promotion_intent_before_dispatch,
    record_promotion_dispatch_started,
    record_promotion_dispatch_unknown,
    record_promotion_edit_intent,
    verify_promotion_dispatch_from_observation,
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
from video_channel_manager.platforms.vk.wall_safety import VkWallPostFingerprint, VkWallSurface


def _text(source_id: str, field: PromotionField) -> str:
    return f"reviewed current {source_id} {field.value}"


def _target(source_id: str, field: PromotionField) -> str:
    return f"reviewed target {source_id} {field.value}"


def _remote_id(source_id: str, field: PromotionField) -> str:
    index = ROLL_OUT_IDS.index(source_id)
    if field is PromotionField.CLIP_DESCRIPTION:
        return f"-68859909_{456239200 + index}"
    return f"-68859909_{500 + index}"


def _wall_incarnation(source_id: str, text: str, *, remote_id: str | None = None) -> VkWallPostFingerprint:
    index = ROLL_OUT_IDS.index(source_id)
    resolved_remote_id = remote_id or _remote_id(source_id, PromotionField.WALL_MESSAGE)
    owner_text, post_text = resolved_remote_id.split("_", maxsplit=1)
    return VkWallPostFingerprint(
        owner_id=int(owner_text),
        post_id=int(post_text),
        surface=VkWallSurface.PUBLISHED,
        publish_date=1_700_000_000 + index,
        text_sha256=promotion_text_sha256(text),
        attachments=(f"video-68859909_{456239200 + index}",),
    )


def _spec(*, managed_key: tuple[str, PromotionField] | None = None, review_id: str = "review-1") -> PromotionSpec:
    fields: list[ReviewedPromotionField] = []
    for source_id in ROLL_OUT_IDS:
        for field in PromotionField:
            before = _text(source_id, field)
            if managed_key == (source_id, field):
                after = _target(source_id, field)
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
    remote_override: tuple[str, PromotionField, str] | None = None,
    projection_key: tuple[str, PromotionField] | None = None,
) -> PromotionObservationBatch:
    fields: list[PromotionFieldObservation] = []
    for source_id in ROLL_OUT_IDS:
        for field in PromotionField:
            value = _text(source_id, field)
            if override is not None and override[:2] == (source_id, field):
                value = override[2]
            remote_id = _remote_id(source_id, field)
            if remote_override is not None and remote_override[:2] == (source_id, field):
                remote_id = remote_override[2]
            fields.append(
                PromotionFieldObservation(
                    source_id=source_id,
                    field=field,
                    text=value,
                    sha256=promotion_text_sha256(value),
                    remote_id=remote_id,
                    evidence=(
                        PromotionObservationEvidence.EXACT_CLIP_READ
                        if field is PromotionField.CLIP_DESCRIPTION
                        else PromotionObservationEvidence.EXACT_WALL_INCARNATION
                    ),
                    processing_projection=projection_key == (source_id, field),
                    wall_incarnation=(
                        None
                        if field is PromotionField.CLIP_DESCRIPTION
                        else _wall_incarnation(source_id, value, remote_id=remote_id)
                    ),
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


def _intent(
    *,
    spec: PromotionSpec,
    observation: PromotionObservationBatch,
    journal: PromotionJournal,
    key: tuple[str, PromotionField],
) -> tuple[PromotionJournal, str]:
    preflight = preflight_with_promotion_journal(spec=spec, observation=observation, journal=journal)
    with_intent = record_promotion_edit_intent(
        journal=journal,
        preflight=preflight,
        source_id=key[0],
        field=key[1],
    )
    return with_intent, preflight.digest


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
    assert all(item.intent_preflight_digest is None for item in journal.operations)
    assert all(item.intent_remote_id is None for item in journal.operations)
    payload = journal.as_dict()
    assert payload["provider_mutation_authorized"] is False
    assert journal.operation_state_digest.startswith("sha256:")
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
    assert restored.operation_state_digest == journal.operation_state_digest


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


def test_mapping_rejects_legacy_v1_instead_of_guessing_missing_intent_evidence() -> None:
    payload = _journal().as_dict()
    payload["schema_version"] = 1

    with pytest.raises(ValueError, match="schema_version mismatch"):
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


def test_edit_intent_binds_exact_preflight_and_remote_identity() -> None:
    key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    spec = _spec(managed_key=key)
    observation = _observation()
    journal = initialize_promotion_journal(
        spec=spec,
        observation=observation,
        created_at="2026-08-16T10:05:00+00:00",
    )
    before_state_digest = journal.operation_state_digest

    intent, preflight_digest = _intent(spec=spec, observation=observation, journal=journal, key=key)

    operation = next(item for item in intent.operations if (item.source_id, item.field) == key)
    assert operation.status is PromotionDispatchStatus.EDIT_INTENT
    assert operation.dispatch_started is False
    assert operation.intent_preflight_digest == preflight_digest
    assert operation.intent_remote_id == _remote_id(*key)
    assert intent.operation_state_digest != before_state_digest
    assert intent.digest != journal.digest


def test_stale_preflight_cannot_start_another_intent_after_journal_changes() -> None:
    first_key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    second_key = (ROLL_OUT_IDS[1], PromotionField.WALL_MESSAGE)
    fields = tuple(
        ReviewedPromotionField(
            source_id=item.source_id,
            field=item.field,
            policy=PromotionPolicy.MANAGED_EXACT,
            before_text=item.before_text,
            before_sha256=item.before_sha256,
            after_text=_target(item.source_id, item.field),
            after_sha256=promotion_text_sha256(_target(item.source_id, item.field)),
        )
        if (item.source_id, item.field) in {first_key, second_key}
        else item
        for item in _spec().fields
    )
    spec = PromotionSpec(review_id="two-edits", fields=fields)
    observation = _observation()
    journal = initialize_promotion_journal(
        spec=spec,
        observation=observation,
        created_at="2026-08-16T10:05:00+00:00",
    )
    preflight = preflight_with_promotion_journal(spec=spec, observation=observation, journal=journal)
    intent = record_promotion_edit_intent(
        journal=journal,
        preflight=preflight,
        source_id=first_key[0],
        field=first_key[1],
    )

    with pytest.raises(ValueError, match="stale relative to durable operation state"):
        record_promotion_edit_intent(
            journal=intent,
            preflight=preflight,
            source_id=second_key[0],
            field=second_key[1],
        )


def test_intent_must_follow_deterministic_first_planned_mutation() -> None:
    first_key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    second_key = (ROLL_OUT_IDS[1], PromotionField.WALL_MESSAGE)
    fields = tuple(
        ReviewedPromotionField(
            source_id=item.source_id,
            field=item.field,
            policy=PromotionPolicy.MANAGED_EXACT,
            before_text=item.before_text,
            before_sha256=item.before_sha256,
            after_text=_target(item.source_id, item.field),
            after_sha256=promotion_text_sha256(_target(item.source_id, item.field)),
        )
        if (item.source_id, item.field) in {first_key, second_key}
        else item
        for item in _spec().fields
    )
    spec = PromotionSpec(review_id="two-edits", fields=fields)
    observation = _observation()
    journal = initialize_promotion_journal(
        spec=spec,
        observation=observation,
        created_at="2026-08-16T10:05:00+00:00",
    )
    preflight = preflight_with_promotion_journal(spec=spec, observation=observation, journal=journal)

    with pytest.raises(ValueError, match="deterministic first planned mutation"):
        record_promotion_edit_intent(
            journal=journal,
            preflight=preflight,
            source_id=second_key[0],
            field=second_key[1],
        )


def test_unstarted_intent_can_reset_only_after_exact_same_identity_before_readback() -> None:
    key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    spec = _spec(managed_key=key)
    observation = _observation()
    journal = initialize_promotion_journal(
        spec=spec,
        observation=observation,
        created_at="2026-08-16T10:05:00+00:00",
    )
    intent, preflight_digest = _intent(spec=spec, observation=observation, journal=journal, key=key)

    recovered = reconcile_promotion_intent_before_dispatch(
        journal=intent,
        spec=spec,
        observation=observation,
        source_id=key[0],
        field=key[1],
        preflight_digest=preflight_digest,
    )

    operation = next(item for item in recovered.operations if (item.source_id, item.field) == key)
    assert operation.status is PromotionDispatchStatus.PENDING
    assert operation.intent_preflight_digest is None
    assert operation.intent_remote_id is None

    with pytest.raises(PromotionRecoveryRequired, match="Provider copy changed"):
        reconcile_promotion_intent_before_dispatch(
            journal=intent,
            spec=spec,
            observation=_observation(override=(*key, "manual drift after intent")),
            source_id=key[0],
            field=key[1],
            preflight_digest=preflight_digest,
        )


def test_dispatch_started_is_persisted_before_unknown_and_whole_batch_stops() -> None:
    key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    spec = _spec(managed_key=key)
    observation = _observation()
    journal = initialize_promotion_journal(
        spec=spec,
        observation=observation,
        created_at="2026-08-16T10:05:00+00:00",
    )
    intent, preflight_digest = _intent(spec=spec, observation=observation, journal=journal, key=key)
    started = record_promotion_dispatch_started(
        journal=intent,
        source_id=key[0],
        field=key[1],
        preflight_digest=preflight_digest,
    )
    unknown = record_promotion_dispatch_unknown(
        journal=started,
        source_id=key[0],
        field=key[1],
        preflight_digest=preflight_digest,
    )

    operation = next(item for item in unknown.operations if (item.source_id, item.field) == key)
    assert operation.status is PromotionDispatchStatus.UNKNOWN_REQUIRES_RECONCILIATION
    assert operation.dispatch_started is True
    preflight = preflight_with_promotion_journal(spec=spec, observation=observation, journal=unknown)
    assert preflight.executable is False
    assert preflight.expected_provider_writes == 0
    assert preflight.planned_mutations == ()
    assert any("read-reconcile" in blocker for blocker in preflight.blockers)


def test_dispatched_edit_verifies_only_from_exact_same_identity_reviewed_after() -> None:
    key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    spec = _spec(managed_key=key)
    observation = _observation()
    journal = initialize_promotion_journal(
        spec=spec,
        observation=observation,
        created_at="2026-08-16T10:05:00+00:00",
    )
    intent, preflight_digest = _intent(spec=spec, observation=observation, journal=journal, key=key)
    started = record_promotion_dispatch_started(
        journal=intent,
        source_id=key[0],
        field=key[1],
        preflight_digest=preflight_digest,
    )

    with pytest.raises(PromotionRecoveryRequired, match="do not retry"):
        verify_promotion_dispatch_from_observation(
            journal=started,
            spec=spec,
            observation=observation,
            source_id=key[0],
            field=key[1],
            preflight_digest=preflight_digest,
        )

    with pytest.raises(PromotionRecoveryRequired, match="identity changed"):
        verify_promotion_dispatch_from_observation(
            journal=started,
            spec=spec,
            observation=_observation(
                override=(*key, _target(*key)),
                remote_override=(*key, "-68859909_999999999"),
            ),
            source_id=key[0],
            field=key[1],
            preflight_digest=preflight_digest,
        )

    verified = verify_promotion_dispatch_from_observation(
        journal=started,
        spec=spec,
        observation=_observation(override=(*key, _target(*key))),
        source_id=key[0],
        field=key[1],
        preflight_digest=preflight_digest,
    )
    operation = next(item for item in verified.operations if (item.source_id, item.field) == key)
    assert operation.status is PromotionDispatchStatus.VERIFIED
    assert operation.dispatch_started is True
    assert operation.intent_preflight_digest == preflight_digest
    assert operation.intent_remote_id == _remote_id(*key)
