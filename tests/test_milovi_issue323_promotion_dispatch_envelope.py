from __future__ import annotations

import pytest

from video_channel_manager.platforms.vk.milovi_issue323_promotion_dispatch_envelope import (
    PromotionDispatchEnvelopeBlocked,
    build_confirmed_promotion_dispatch_envelope,
)
from video_channel_manager.platforms.vk.milovi_issue323_promotion_journal import (
    initialize_promotion_journal,
    preflight_with_promotion_journal,
    record_promotion_edit_intent,
)
from video_channel_manager.platforms.vk.milovi_issue323_promotion_observation import (
    PromotionFieldObservation,
    PromotionObservationBatch,
    PromotionObservationEvidence,
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


def _before(source_id: str, field: PromotionField) -> str:
    return f"before {source_id} {field.value}"


def _after(source_id: str, field: PromotionField) -> str:
    return f"after {source_id} {field.value}"


def _remote_id(source_id: str, field: PromotionField) -> str:
    index = ROLL_OUT_IDS.index(source_id)
    item_id = 456239200 + index if field is PromotionField.CLIP_DESCRIPTION else 700 + index
    return f"-68859909_{item_id}"


def _spec(managed_key: tuple[str, PromotionField]) -> PromotionSpec:
    fields: list[ReviewedPromotionField] = []
    for source_id in ROLL_OUT_IDS:
        for field in PromotionField:
            before = _before(source_id, field)
            if (source_id, field) == managed_key:
                after = _after(source_id, field)
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
    return PromotionSpec(review_id="dispatch-envelope", fields=tuple(fields))


def _observation(
    *,
    captured_at: str,
    text_overrides: dict[tuple[str, PromotionField], str] | None = None,
    remote_overrides: dict[tuple[str, PromotionField], str] | None = None,
) -> PromotionObservationBatch:
    text_overrides = text_overrides or {}
    remote_overrides = remote_overrides or {}
    fields: list[PromotionFieldObservation] = []
    for source_id in ROLL_OUT_IDS:
        index = ROLL_OUT_IDS.index(source_id)
        for field in PromotionField:
            key = (source_id, field)
            text = text_overrides.get(key, _before(source_id, field))
            remote_id = remote_overrides.get(key, _remote_id(source_id, field))
            wall_incarnation = None
            evidence = PromotionObservationEvidence.EXACT_CLIP_READ
            if field is PromotionField.WALL_MESSAGE:
                owner_text, post_text = remote_id.split("_", maxsplit=1)
                wall_incarnation = VkWallPostFingerprint(
                    owner_id=int(owner_text),
                    post_id=int(post_text),
                    surface=VkWallSurface.PUBLISHED,
                    publish_date=1_700_000_000 + index,
                    text_sha256=f"sha256:{promotion_text_sha256(text)}",
                    attachments=(f"video-68859909_{456239200 + index}",),
                )
                evidence = PromotionObservationEvidence.EXACT_WALL_INCARNATION
            fields.append(
                PromotionFieldObservation(
                    source_id=source_id,
                    field=field,
                    text=text,
                    sha256=promotion_text_sha256(text),
                    remote_id=remote_id,
                    evidence=evidence,
                    wall_incarnation=wall_incarnation,
                )
            )
    return PromotionObservationBatch(
        source_snapshot_id="issue323-dispatch-envelope",
        wall_snapshot_sha256="sha256:dispatch-envelope-wall-snapshot",
        captured_at=captured_at,
        fields=tuple(fields),
    )


def _intent(
    key: tuple[str, PromotionField],
) -> tuple[PromotionSpec, PromotionObservationBatch, object]:
    spec = _spec(key)
    observation = _observation(captured_at="2026-08-16T18:00:00+00:00")
    journal = initialize_promotion_journal(
        spec=spec,
        observation=observation,
        created_at="2026-08-16T18:01:00+00:00",
    )
    preflight = preflight_with_promotion_journal(spec=spec, observation=observation, journal=journal)
    intent = record_promotion_edit_intent(
        journal=journal,
        preflight=preflight,
        source_id=key[0],
        field=key[1],
    )
    return spec, observation, intent


def test_clip_envelope_revalidates_stable_confirmation_across_fresh_capture() -> None:
    key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    spec, initial_observation, intent = _intent(key)
    fresh_observation = _observation(captured_at="2026-08-16T18:05:00+00:00")

    envelope = build_confirmed_promotion_dispatch_envelope(
        spec=spec,
        observation=fresh_observation,
        journal=intent,  # type: ignore[arg-type]
        source_id=key[0],
        field=key[1],
    )

    operation = next(item for item in intent.operations if (item.source_id, item.field) == key)  # type: ignore[attr-defined]
    assert envelope.confirmation_digest == operation.intent_confirmation_digest
    assert envelope.intent_preflight_digest == operation.intent_preflight_digest
    assert envelope.fresh_observation_digest == fresh_observation.digest
    assert envelope.fresh_observation_digest != initial_observation.digest
    assert envelope.fresh_preflight_digest != envelope.intent_preflight_digest
    assert envelope.remote_id == _remote_id(*key)
    assert envelope.before_text == _before(*key)
    assert envelope.after_text == _after(*key)
    assert envelope.wall_incarnation is None
    assert envelope.as_dict()["provider_mutation_authorized"] is False
    assert envelope.as_dict()["expected_provider_writes"] == 1


def test_unrelated_whole_batch_drift_blocks_confirmed_envelope() -> None:
    key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    spec, _initial_observation, intent = _intent(key)
    unrelated = (ROLL_OUT_IDS[-1], PromotionField.WALL_MESSAGE)
    fresh_observation = _observation(
        captured_at="2026-08-16T18:05:00+00:00",
        text_overrides={unrelated: "manual third-state copy"},
    )

    with pytest.raises(PromotionDispatchEnvelopeBlocked, match="whole-batch preflight is not executable"):
        build_confirmed_promotion_dispatch_envelope(
            spec=spec,
            observation=fresh_observation,
            journal=intent,  # type: ignore[arg-type]
            source_id=key[0],
            field=key[1],
        )


def test_target_identity_drift_blocks_confirmed_envelope() -> None:
    key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    spec, _initial_observation, intent = _intent(key)
    fresh_observation = _observation(
        captured_at="2026-08-16T18:05:00+00:00",
        remote_overrides={key: "-68859909_999999999"},
    )

    with pytest.raises(PromotionDispatchEnvelopeBlocked, match="confirmation digest differs"):
        build_confirmed_promotion_dispatch_envelope(
            spec=spec,
            observation=fresh_observation,
            journal=intent,  # type: ignore[arg-type]
            source_id=key[0],
            field=key[1],
        )


def test_wall_envelope_freezes_exact_wall_incarnation() -> None:
    key = (ROLL_OUT_IDS[0], PromotionField.WALL_MESSAGE)
    spec, _initial_observation, intent = _intent(key)
    fresh_observation = _observation(captured_at="2026-08-16T18:05:00+00:00")

    envelope = build_confirmed_promotion_dispatch_envelope(
        spec=spec,
        observation=fresh_observation,
        journal=intent,  # type: ignore[arg-type]
        source_id=key[0],
        field=key[1],
    )

    observed = next(item for item in fresh_observation.fields if (item.source_id, item.field) == key)
    assert envelope.wall_incarnation == observed.wall_incarnation
    assert envelope.wall_incarnation is not None
    assert envelope.wall_incarnation.remote_id == envelope.remote_id
    assert envelope.wall_incarnation.text_sha256 == f"sha256:{envelope.before_sha256}"


def test_pending_operation_cannot_be_turned_into_dispatch_envelope() -> None:
    key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    spec = _spec(key)
    observation = _observation(captured_at="2026-08-16T18:00:00+00:00")
    journal = initialize_promotion_journal(
        spec=spec,
        observation=observation,
        created_at="2026-08-16T18:01:00+00:00",
    )

    with pytest.raises(PromotionDispatchEnvelopeBlocked, match="requires one unstarted edit_intent"):
        build_confirmed_promotion_dispatch_envelope(
            spec=spec,
            observation=observation,
            journal=journal,
            source_id=key[0],
            field=key[1],
        )
