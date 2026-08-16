from __future__ import annotations

import pytest

from video_channel_manager.platforms.vk.milovi_issue323_promotion_journal import (
    PROMOTION_JOURNAL_VERSION,
    PromotionJournalOperation,
    initialize_promotion_journal,
    preflight_with_promotion_journal,
    promotion_journal_from_mapping,
    record_promotion_edit_intent,
)
from video_channel_manager.platforms.vk.milovi_issue323_promotion_observation import (
    PromotionFieldObservation,
    PromotionObservationBatch,
    PromotionObservationEvidence,
)
from video_channel_manager.platforms.vk.milovi_issue323_promotion_preflight import PromotionDispatchStatus
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
    suffix = 456239200 + index if field is PromotionField.CLIP_DESCRIPTION else 500 + index
    return f"-68859909_{suffix}"


def _spec(key: tuple[str, PromotionField]) -> PromotionSpec:
    fields: list[ReviewedPromotionField] = []
    for source_id in ROLL_OUT_IDS:
        for field in PromotionField:
            before = _before(source_id, field)
            if (source_id, field) == key:
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
    return PromotionSpec(review_id="confirmed-intent-binding", fields=tuple(fields))


def _observation(*, captured_at: str) -> PromotionObservationBatch:
    fields: list[PromotionFieldObservation] = []
    for source_id in ROLL_OUT_IDS:
        index = ROLL_OUT_IDS.index(source_id)
        for field in PromotionField:
            text = _before(source_id, field)
            remote_id = _remote_id(source_id, field)
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
        source_snapshot_id="issue323-confirmed-intent",
        wall_snapshot_sha256="sha256:wall-capture-evidence",
        captured_at=captured_at,
        fields=tuple(fields),
    )


def test_edit_intent_persists_exact_operator_confirmation_digest() -> None:
    key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    spec = _spec(key)
    observation = _observation(captured_at="2026-08-16T17:00:00+00:00")
    journal = initialize_promotion_journal(
        spec=spec,
        observation=observation,
        created_at="2026-08-16T17:01:00+00:00",
    )
    preflight = preflight_with_promotion_journal(spec=spec, observation=observation, journal=journal)

    intent = record_promotion_edit_intent(
        journal=journal,
        preflight=preflight,
        source_id=key[0],
        field=key[1],
    )

    operation = next(item for item in intent.operations if (item.source_id, item.field) == key)
    assert operation.intent_preflight_digest == preflight.digest
    assert operation.intent_confirmation_digest == preflight.confirmation_digest
    assert operation.intent_preflight_digest != operation.intent_confirmation_digest
    assert operation.intent_remote_id == _remote_id(*key)
    assert intent.as_dict()["schema_version"] == PROMOTION_JOURNAL_VERSION == 3


def test_confirmation_digest_is_stable_when_only_capture_time_changes() -> None:
    key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    spec = _spec(key)
    first_observation = _observation(captured_at="2026-08-16T17:00:00+00:00")
    journal = initialize_promotion_journal(
        spec=spec,
        observation=first_observation,
        created_at="2026-08-16T17:01:00+00:00",
    )
    first = preflight_with_promotion_journal(spec=spec, observation=first_observation, journal=journal)
    second = preflight_with_promotion_journal(
        spec=spec,
        observation=_observation(captured_at="2026-08-16T17:05:00+00:00"),
        journal=journal,
    )

    assert first.digest != second.digest
    assert first.confirmation_digest == second.confirmation_digest


def test_nonpending_operation_without_confirmation_digest_is_impossible() -> None:
    with pytest.raises(ValueError, match="confirmed intent binding"):
        PromotionJournalOperation(
            source_id=ROLL_OUT_IDS[0],
            field=PromotionField.CLIP_DESCRIPTION,
            status=PromotionDispatchStatus.EDIT_INTENT,
            intent_preflight_digest="sha256:" + "1" * 64,
            intent_remote_id="-68859909_456239200",
        )


def test_legacy_v2_journal_is_not_silently_upgraded_without_confirmation_evidence() -> None:
    key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    spec = _spec(key)
    observation = _observation(captured_at="2026-08-16T17:00:00+00:00")
    journal = initialize_promotion_journal(
        spec=spec,
        observation=observation,
        created_at="2026-08-16T17:01:00+00:00",
    )
    payload = journal.as_dict()
    payload["schema_version"] = 2
    for operation in payload["operations"]:  # type: ignore[index]
        assert isinstance(operation, dict)
        operation.pop("intent_confirmation_digest")

    with pytest.raises(ValueError, match="schema_version mismatch"):
        promotion_journal_from_mapping(payload)
