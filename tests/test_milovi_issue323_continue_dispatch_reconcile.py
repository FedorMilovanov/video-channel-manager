from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import video_channel_manager.platforms.vk.milovi_issue323_continue as continue_module
from video_channel_manager.platforms.vk.milovi_issue323_continue import run_issue_323_continue_preview
from video_channel_manager.platforms.vk.milovi_issue323_promotion_journal import (
    initialize_promotion_journal,
    preflight_with_promotion_journal,
    record_promotion_dispatch_started,
    record_promotion_dispatch_unknown,
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


KEY = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)


def _before_text(source_id: str, field: PromotionField) -> str:
    return f"reviewed BEFORE {source_id} {field.value}"


def _after_text(source_id: str, field: PromotionField) -> str:
    return f"reviewed AFTER {source_id} {field.value}"


def _remote_id(source_id: str, field: PromotionField) -> str:
    index = ROLL_OUT_IDS.index(source_id)
    return (
        f"-68859909_{456239200 + index}"
        if field is PromotionField.CLIP_DESCRIPTION
        else f"-68859909_{700 + index}"
    )


def _observation(*, target_after: bool, captured_at: str) -> PromotionObservationBatch:
    fields: list[PromotionFieldObservation] = []
    for source_id in ROLL_OUT_IDS:
        for field in PromotionField:
            text = _before_text(source_id, field)
            if target_after and (source_id, field) == KEY:
                text = _after_text(source_id, field)
            wall_incarnation = None
            if field is PromotionField.WALL_MESSAGE:
                index = ROLL_OUT_IDS.index(source_id)
                wall_incarnation = VkWallPostFingerprint(
                    owner_id=-68859909,
                    post_id=700 + index,
                    surface=VkWallSurface.PUBLISHED,
                    publish_date=1_700_100_000 + index,
                    text_sha256=f"sha256:{promotion_text_sha256(text)}",
                    attachments=(f"video-68859909_{456239200 + index}",),
                )
            fields.append(
                PromotionFieldObservation(
                    source_id=source_id,
                    field=field,
                    text=text,
                    sha256=promotion_text_sha256(text),
                    remote_id=_remote_id(source_id, field),
                    evidence=(
                        PromotionObservationEvidence.EXACT_CLIP_READ
                        if field is PromotionField.CLIP_DESCRIPTION
                        else PromotionObservationEvidence.EXACT_WALL_INCARNATION
                    ),
                    wall_incarnation=wall_incarnation,
                )
            )
    return PromotionObservationBatch(
        source_snapshot_id="issue323-dispatch-reconcile",
        wall_snapshot_sha256="sha256:dispatch-reconcile-wall-snapshot",
        captured_at=captured_at,
        fields=tuple(fields),
    )


def _spec() -> PromotionSpec:
    fields: list[ReviewedPromotionField] = []
    for source_id in ROLL_OUT_IDS:
        for field in PromotionField:
            before = _before_text(source_id, field)
            if (source_id, field) == KEY:
                after = _after_text(source_id, field)
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
    return PromotionSpec(review_id="dispatch-reconcile-review", fields=tuple(fields))


def _paths(tmp_path: Path) -> dict[str, Path]:
    return {
        "output_path": tmp_path / "continue.json",
        "status_output_path": tmp_path / "status.json",
        "rollout_journal_path": tmp_path / "rollout.json",
        "schedule_path": tmp_path / "schedule.json",
        "prepared_manifest_path": tmp_path / "prepared.json",
        "promotion_spec_path": tmp_path / "promotion-spec.json",
        "promotion_journal_path": tmp_path / "promotion-journal.json",
    }


def _status_payload(observation: PromotionObservationBatch) -> dict[str, Any]:
    raw = observation.as_dict()
    raw["observation_digest"] = observation.digest
    return {
        "status": "verified_read_only",
        "provider_mutation_authorized": False,
        "promotion_observation": raw,
    }


def _prepare_dispatched_journal(paths: dict[str, Path], *, unknown: bool) -> str:
    spec = _spec()
    before = _observation(target_after=False, captured_at="2026-08-16T18:00:00+00:00")
    paths["promotion_spec_path"].write_text(
        json.dumps(spec.as_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    journal = initialize_promotion_journal(
        spec=spec,
        observation=before,
        created_at="2026-08-16T18:01:00+00:00",
    )
    preflight = preflight_with_promotion_journal(spec=spec, observation=before, journal=journal)
    journal = record_promotion_edit_intent(
        journal=journal,
        preflight=preflight,
        source_id=KEY[0],
        field=KEY[1],
    )
    intent = next(item for item in journal.operations if (item.source_id, item.field) == KEY)
    assert intent.intent_preflight_digest is not None
    journal = record_promotion_dispatch_started(
        journal=journal,
        source_id=KEY[0],
        field=KEY[1],
        preflight_digest=intent.intent_preflight_digest,
    )
    if unknown:
        journal = record_promotion_dispatch_unknown(
            journal=journal,
            source_id=KEY[0],
            field=KEY[1],
            preflight_digest=intent.intent_preflight_digest,
        )
    paths["promotion_journal_path"].write_text(
        json.dumps(journal.as_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return intent.intent_confirmation_digest or ""


def _operation(paths: dict[str, Path]) -> dict[str, Any]:
    payload = json.loads(paths["promotion_journal_path"].read_text(encoding="utf-8"))
    return next(
        item
        for item in payload["operations"]
        if item["source_id"] == KEY[0] and item["field"] == KEY[1].value
    )


def test_started_exact_after_is_verified_read_only_without_consuming_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _paths(tmp_path)
    stale_confirmation = _prepare_dispatched_journal(paths, unknown=False)
    after = _observation(target_after=True, captured_at="2026-08-16T18:02:00+00:00")
    monkeypatch.setattr(
        continue_module,
        "run_issue_323_status_probe",
        lambda **_kwargs: _status_payload(after),
    )

    result = run_issue_323_continue_preview(
        **paths,
        preflight_digest_confirmation=stale_confirmation,
    )

    assert result["continuation_status"] == "dispatch_reconciled_verified_ready_for_next_plan"
    assert result["promotion_dispatch_reconciled"] is True
    assert result["promotion_dispatch_unknown"] is False
    assert result["preflight_digest_confirmation_supplied"] is True
    assert result["preflight_digest_confirmed"] is False
    assert result["provider_mutation_authorized"] is False
    assert result["provider_writes_executed"] == 0
    operation = _operation(paths)
    assert operation["status"] == "verified"
    assert operation["dispatch_started"] is True
    assert operation["intent_preflight_digest"] is None
    assert operation["intent_confirmation_digest"] is None
    assert operation["intent_remote_id"] is None


def test_started_without_exact_after_becomes_durable_unknown_and_never_replays(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _paths(tmp_path)
    _prepare_dispatched_journal(paths, unknown=False)
    before = _observation(target_after=False, captured_at="2026-08-16T18:02:00+00:00")
    monkeypatch.setattr(
        continue_module,
        "run_issue_323_status_probe",
        lambda **_kwargs: _status_payload(before),
    )

    result = run_issue_323_continue_preview(**paths)

    assert result["continuation_status"] == "dispatch_unknown_requires_reconciliation"
    assert result["promotion_dispatch_reconciled"] is False
    assert result["promotion_dispatch_unknown"] is True
    assert result["provider_mutation_authorized"] is False
    assert result["provider_writes_executed"] == 0
    assert result["promotion_preflight"]["planned_mutations"] == []
    assert "do not retry" in result["blockers"][0]
    operation = _operation(paths)
    assert operation["status"] == "unknown_requires_reconciliation"
    assert operation["dispatch_started"] is True
    assert operation["intent_preflight_digest"] is not None
    assert operation["intent_confirmation_digest"] is not None
    assert operation["intent_remote_id"] == _remote_id(*KEY)


def test_existing_unknown_can_only_clear_on_fresh_exact_after(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _paths(tmp_path)
    _prepare_dispatched_journal(paths, unknown=True)
    after = _observation(target_after=True, captured_at="2026-08-16T18:03:00+00:00")
    monkeypatch.setattr(
        continue_module,
        "run_issue_323_status_probe",
        lambda **_kwargs: _status_payload(after),
    )

    result = run_issue_323_continue_preview(**paths)

    assert result["continuation_status"] == "dispatch_reconciled_verified_ready_for_next_plan"
    assert result["promotion_dispatch_reconciled"] is True
    assert result["provider_writes_executed"] == 0
    assert _operation(paths)["status"] == "verified"


def test_existing_unknown_before_state_stays_unknown_without_journal_rewrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _paths(tmp_path)
    _prepare_dispatched_journal(paths, unknown=True)
    journal_before = paths["promotion_journal_path"].read_bytes()
    before = _observation(target_after=False, captured_at="2026-08-16T18:04:00+00:00")
    monkeypatch.setattr(
        continue_module,
        "run_issue_323_status_probe",
        lambda **_kwargs: _status_payload(before),
    )

    result = run_issue_323_continue_preview(**paths)

    assert result["continuation_status"] == "dispatch_unknown_requires_reconciliation"
    assert result["promotion_dispatch_unknown"] is True
    assert result["provider_writes_executed"] == 0
    assert paths["promotion_journal_path"].read_bytes() == journal_before
    assert _operation(paths)["status"] == "unknown_requires_reconciliation"
