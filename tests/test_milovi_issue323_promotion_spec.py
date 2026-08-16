from __future__ import annotations

import json
from pathlib import Path

import pytest

from video_channel_manager.platforms.vk.milovi_issue323_promotion_spec import (
    ObservedPromotionField,
    PromotionDecisionAction,
    PromotionField,
    PromotionPolicy,
    PromotionSpec,
    ReviewedPromotionField,
    load_reviewed_promotion_spec,
    plan_reviewed_promotion_batch,
    promotion_spec_from_mapping,
    promotion_text_sha256,
)
from video_channel_manager.platforms.vk.milovi_rollout_sources import ROLL_OUT_IDS


def _reviewed(
    source_id: str,
    field: PromotionField,
    *,
    policy: PromotionPolicy = PromotionPolicy.ADOPT_REVIEWED_EXACT,
    before: str | None = None,
    after: str | None = None,
) -> ReviewedPromotionField:
    before_text = before or f"reviewed current {source_id} {field.value}"
    after_text = after
    if policy is PromotionPolicy.MANAGED_EXACT and after_text is None:
        after_text = f"reviewed target {source_id} {field.value}"
    return ReviewedPromotionField(
        source_id=source_id,
        field=field,
        policy=policy,
        before_text=before_text,
        before_sha256=promotion_text_sha256(before_text),
        after_text=after_text,
        after_sha256=promotion_text_sha256(after_text) if after_text is not None else None,
    )


def _spec(*, managed_key: tuple[str, PromotionField] | None = None) -> PromotionSpec:
    fields = []
    for source_id in ROLL_OUT_IDS:
        for field in PromotionField:
            policy = (
                PromotionPolicy.MANAGED_EXACT
                if managed_key == (source_id, field)
                else PromotionPolicy.ADOPT_REVIEWED_EXACT
            )
            fields.append(_reviewed(source_id, field, policy=policy))
    return PromotionSpec(review_id="manual-review-2026-08-16", fields=tuple(reversed(fields)))


def _observed(spec: PromotionSpec) -> dict[tuple[str, PromotionField], ObservedPromotionField]:
    return {
        (item.source_id, item.field): ObservedPromotionField(
            source_id=item.source_id,
            field=item.field,
            text=item.before_text,
        )
        for item in spec.fields
    }


def test_spec_requires_exact_sha_for_reviewed_text() -> None:
    with pytest.raises(ValueError, match="BEFORE SHA mismatch"):
        ReviewedPromotionField(
            source_id=ROLL_OUT_IDS[0],
            field=PromotionField.CLIP_DESCRIPTION,
            policy=PromotionPolicy.ADOPT_REVIEWED_EXACT,
            before_text="manual exact text",
            before_sha256="0" * 64,
        )


def test_nonmanaged_policy_cannot_smuggle_edit_target() -> None:
    before = "manual reviewed current"
    after = "unreviewed generated target"
    with pytest.raises(ValueError, match="zero edit target authority"):
        ReviewedPromotionField(
            source_id=ROLL_OUT_IDS[0],
            field=PromotionField.WALL_MESSAGE,
            policy=PromotionPolicy.PRESERVE_EXTERNAL,
            before_text=before,
            before_sha256=promotion_text_sha256(before),
            after_text=after,
            after_sha256=promotion_text_sha256(after),
        )


def test_spec_requires_all_12_sources_and_both_fields_once() -> None:
    one = _reviewed(ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    with pytest.raises(ValueError, match="exact 12x2 field set"):
        PromotionSpec(review_id="partial", fields=(one,))


def test_spec_digest_and_serialization_are_deterministic_in_allowlist_order() -> None:
    first = _spec()
    second = PromotionSpec(review_id=first.review_id, fields=tuple(reversed(first.fields)))

    assert first.as_dict() == second.as_dict()
    assert first.digest == second.digest
    ordered = first.as_dict()["fields"]
    assert isinstance(ordered, list)
    assert ordered[0]["source_id"] == ROLL_OUT_IDS[0]
    assert ordered[0]["field"] == PromotionField.CLIP_DESCRIPTION.value


def test_strict_artifact_roundtrip_rejects_unreviewed_keys(tmp_path: Path) -> None:
    spec = _spec(managed_key=(ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION))
    path = tmp_path / "reviewed-promotion-spec.json"
    path.write_text(json.dumps(spec.as_dict(), ensure_ascii=False), encoding="utf-8")

    loaded = load_reviewed_promotion_spec(path)

    assert loaded.as_dict() == spec.as_dict()
    assert loaded.digest == spec.digest
    payload = dict(spec.as_dict())
    payload["generated_from_title"] = True
    with pytest.raises(ValueError, match="unreviewed keys"):
        promotion_spec_from_mapping(payload)


def test_managed_exact_before_plans_only_exact_reviewed_after() -> None:
    key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    spec = _spec(managed_key=key)
    observed = _observed(spec)

    plan = plan_reviewed_promotion_batch(spec, observed)

    assert plan.executable is True
    assert len(plan.mutations) == 1
    mutation = plan.mutations[0]
    reviewed = next(item for item in spec.fields if (item.source_id, item.field) == key)
    assert mutation.source_id == key[0]
    assert mutation.field is key[1]
    assert mutation.before_sha256 == reviewed.before_sha256
    assert mutation.after_sha256 == reviewed.after_sha256
    assert mutation.after_text == reviewed.after_text
    assert plan.as_dict()["provider_mutation_authorized"] is False
    assert plan.as_dict()["confirmation_required"] is True


def test_exact_reviewed_after_is_already_applied_not_reedited() -> None:
    key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    spec = _spec(managed_key=key)
    observed = _observed(spec)
    reviewed = next(item for item in spec.fields if (item.source_id, item.field) == key)
    assert reviewed.after_text is not None
    observed[key] = ObservedPromotionField(source_id=key[0], field=key[1], text=reviewed.after_text)

    plan = plan_reviewed_promotion_batch(spec, observed)

    assert plan.executable is True
    assert plan.mutations == ()
    decision = next(item for item in plan.decisions if (item.source_id, item.field) == key)
    assert decision.action is PromotionDecisionAction.ALREADY_APPLIED
    assert decision.edit_required is False
    assert plan.as_dict()["confirmation_required"] is False


def test_adopt_and_preserve_are_exact_and_never_edit() -> None:
    fields = []
    preserve_key = (ROLL_OUT_IDS[1], PromotionField.WALL_MESSAGE)
    for source_id in ROLL_OUT_IDS:
        for field in PromotionField:
            policy = (
                PromotionPolicy.PRESERVE_EXTERNAL
                if (source_id, field) == preserve_key
                else PromotionPolicy.ADOPT_REVIEWED_EXACT
            )
            fields.append(_reviewed(source_id, field, policy=policy))
    spec = PromotionSpec(review_id="reviewed-manual-copy", fields=tuple(fields))

    plan = plan_reviewed_promotion_batch(spec, _observed(spec))

    assert plan.executable is True
    assert plan.mutations == ()
    assert {decision.action for decision in plan.decisions} == {
        PromotionDecisionAction.ADOPT,
        PromotionDecisionAction.PRESERVE,
    }
    assert all(decision.edit_required is False for decision in plan.decisions)


def test_one_manual_drift_blocks_whole_batch_and_zeroes_all_mutations() -> None:
    managed_key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    drift_key = (ROLL_OUT_IDS[7], PromotionField.WALL_MESSAGE)
    spec = _spec(managed_key=managed_key)
    observed = _observed(spec)
    observed[drift_key] = ObservedPromotionField(
        source_id=drift_key[0],
        field=drift_key[1],
        text="operator changed this after review",
    )

    plan = plan_reviewed_promotion_batch(spec, observed)

    assert plan.executable is False
    assert plan.mutations == ()
    assert len(plan.blockers) == 1
    assert drift_key[0] in plan.blockers[0]
    managed = next(item for item in plan.decisions if (item.source_id, item.field) == managed_key)
    assert managed.action is PromotionDecisionAction.EDIT
    assert managed.edit_required is True
    assert plan.as_dict()["provider_mutation_authorized"] is False


def test_processing_projection_never_grants_edit_authority_and_blocks_batch() -> None:
    key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    spec = _spec(managed_key=key)
    observed = _observed(spec)
    reviewed = next(item for item in spec.fields if (item.source_id, item.field) == key)
    observed[key] = ObservedPromotionField(
        source_id=key[0],
        field=key[1],
        text=reviewed.before_text,
        is_processing_projection=True,
    )

    plan = plan_reviewed_promotion_batch(spec, observed)

    assert plan.executable is False
    assert plan.mutations == ()
    decision = next(item for item in plan.decisions if (item.source_id, item.field) == key)
    assert decision.action is PromotionDecisionAction.STOP
    assert decision.edit_required is False
    assert "processing projection" in str(decision.reason)


def test_batch_plan_is_bound_to_exact_spec_digest() -> None:
    spec = _spec(managed_key=(ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION))
    plan = plan_reviewed_promotion_batch(spec, _observed(spec))

    assert plan.spec_digest == spec.digest
    assert plan.digest.startswith("sha256:")
