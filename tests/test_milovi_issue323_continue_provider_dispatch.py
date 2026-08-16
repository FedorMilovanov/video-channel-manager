from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import video_channel_manager.platforms.vk.milovi_issue323_continue as continue_module
from video_channel_manager.platforms.vk.milovi_issue323_continue import (
    PROMOTION_JOURNAL_INIT_CONFIRMATION,
    run_issue_323_continue,
)
from video_channel_manager.platforms.vk.milovi_issue323_promotion_dispatch import PromotionDispatchResult
from video_channel_manager.platforms.vk.milovi_issue323_promotion_journal import (
    load_promotion_journal,
    record_promotion_dispatch_started,
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
from video_channel_manager.platforms.vk.milovi_rollout_sources import ROLL_OUT_IDS, write_json_atomic
from video_channel_manager.platforms.vk.wall_safety import VkWallPostFingerprint, VkWallSurface


def _before(source_id: str, field: PromotionField) -> str:
    return f"reviewed BEFORE {source_id} {field.value}"


def _after(source_id: str, field: PromotionField) -> str:
    return f"reviewed AFTER {source_id} {field.value}"


def _remote_id(source_id: str, field: PromotionField) -> str:
    index = ROLL_OUT_IDS.index(source_id)
    if field is PromotionField.CLIP_DESCRIPTION:
        return f"-68859909_{456239300 + index}"
    return f"-68859909_{800 + index}"


def _observation(
    *,
    managed_key: tuple[str, PromotionField],
    target_after: bool,
    captured_at: str,
) -> PromotionObservationBatch:
    fields: list[PromotionFieldObservation] = []
    for source_id in ROLL_OUT_IDS:
        for field in PromotionField:
            text = _before(source_id, field)
            if target_after and (source_id, field) == managed_key:
                text = _after(source_id, field)
            wall_incarnation = None
            if field is PromotionField.WALL_MESSAGE:
                index = ROLL_OUT_IDS.index(source_id)
                wall_incarnation = VkWallPostFingerprint(
                    owner_id=-68859909,
                    post_id=800 + index,
                    surface=VkWallSurface.PUBLISHED,
                    publish_date=1_786_910_000 + index,
                    text_sha256=f"sha256:{promotion_text_sha256(text)}",
                    attachments=(f"video-68859909_{456239300 + index}",),
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
        source_snapshot_id="issue323-provider-handoff-test",
        wall_snapshot_sha256=f"sha256:wall-{captured_at}",
        captured_at=captured_at,
        fields=tuple(fields),
    )


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
    return PromotionSpec(review_id="provider-handoff-review", fields=tuple(fields))


def _status(observation: PromotionObservationBatch) -> dict[str, Any]:
    raw = observation.as_dict()
    raw["observation_digest"] = observation.digest
    return {
        "status": "verified_read_only",
        "community_id": 68859909,
        "account_alias": "legendary-poet",
        "provider_mutation_authorized": False,
        "promotion_observation": raw,
    }


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


def _write_spec(path: Path, spec: PromotionSpec) -> None:
    path.write_text(json.dumps(spec.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def _operation(path: Path, key: tuple[str, PromotionField]) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return next(item for item in payload["operations"] if item["source_id"] == key[0] and item["field"] == key[1].value)


def _prepare_intent(
    *,
    paths: dict[str, Path],
    key: tuple[str, PromotionField],
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[PromotionObservationBatch, str]:
    observation = _observation(managed_key=key, target_after=False, captured_at="2026-08-16T20:30:00+00:00")
    _write_spec(paths["promotion_spec_path"], _spec(key))
    monkeypatch.setattr(continue_module, "run_issue_323_status_probe", lambda **_kwargs: _status(observation))
    preview = run_issue_323_continue(
        **paths,
        journal_init_confirmation=PROMOTION_JOURNAL_INIT_CONFIRMATION,
        journal_created_at="2026-08-16T20:31:00+00:00",
    )
    persisted = run_issue_323_continue(
        **paths,
        preflight_digest_confirmation=preview["promotion_preflight_digest"],
    )
    assert persisted["continuation_status"] == "intent_persisted_requires_separate_provider_dispatch_confirmation"
    digest = persisted["provider_dispatch_confirmation_digest"]
    assert isinstance(digest, str)
    return observation, digest


@pytest.mark.parametrize("field", [PromotionField.CLIP_DESCRIPTION, PromotionField.WALL_MESSAGE])
def test_existing_intent_requires_separate_matching_dispatch_digest_and_starts_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: PromotionField,
) -> None:
    paths = _paths(tmp_path)
    key = (ROLL_OUT_IDS[0], field)
    observation, digest = _prepare_intent(paths=paths, key=key, monkeypatch=monkeypatch)
    dispatch_calls = 0

    def fake_dispatch(**kwargs: object) -> PromotionDispatchResult:
        nonlocal dispatch_calls
        dispatch_calls += 1
        envelope = kwargs["envelope"]
        assert envelope.field is field
        journal = load_promotion_journal(paths["promotion_journal_path"])
        intent = next(item for item in journal.operations if (item.source_id, item.field) == key)
        assert intent.intent_preflight_digest is not None
        started = record_promotion_dispatch_started(
            journal=journal,
            source_id=key[0],
            field=key[1],
            preflight_digest=intent.intent_preflight_digest,
        )
        write_json_atomic(paths["promotion_journal_path"], started.as_dict())
        return PromotionDispatchResult(
            source_id=key[0],
            field=key[1],
            remote_id=_remote_id(*key),
            envelope_digest=envelope.digest,
            durable_status=PromotionDispatchStatus.EDIT_DISPATCH_STARTED,
            provider_writes_executed=1,
            primitive_postflight_verified=True,
            required_next_action="fresh_status_reconcile_exact_after",
        )

    monkeypatch.setattr(continue_module, "_dispatch_existing_intent", fake_dispatch)

    ready = run_issue_323_continue(**paths)
    assert ready["continuation_status"] == "intent_ready_for_provider_dispatch_confirmation"
    assert ready["provider_writes_executed"] == 0
    assert ready["provider_dispatch_confirmation_digest"] == digest
    assert ready["promotion_dispatch_envelope"]["field"] == field.value
    assert _operation(paths["promotion_journal_path"], key)["status"] == "edit_intent"

    wrong = run_issue_323_continue(**paths, provider_dispatch_confirmation="sha256:" + "f" * 64)
    assert wrong["continuation_status"] == "blocked"
    assert wrong["provider_writes_executed"] == 0
    assert dispatch_calls == 0
    assert _operation(paths["promotion_journal_path"], key)["status"] == "edit_intent"

    monkeypatch.setattr(continue_module, "run_issue_323_status_probe", lambda **_kwargs: _status(observation))
    dispatched = run_issue_323_continue(**paths, provider_dispatch_confirmation=digest)
    assert dispatched["continuation_status"] == "provider_dispatch_started_requires_fresh_reconciliation"
    assert dispatched["provider_dispatch_confirmed"] is True
    assert dispatched["provider_mutation_authorized"] is True
    assert dispatched["provider_writes_executed"] == 1
    assert dispatch_calls == 1
    assert _operation(paths["promotion_journal_path"], key)["status"] == "edit_dispatch_started"


def test_next_invocation_reconciles_started_exact_after_without_replaying_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _paths(tmp_path)
    key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    _, digest = _prepare_intent(paths=paths, key=key, monkeypatch=monkeypatch)
    dispatch_calls = 0

    def fake_dispatch(**kwargs: object) -> PromotionDispatchResult:
        nonlocal dispatch_calls
        dispatch_calls += 1
        envelope = kwargs["envelope"]
        journal = load_promotion_journal(paths["promotion_journal_path"])
        intent = next(item for item in journal.operations if (item.source_id, item.field) == key)
        assert intent.intent_preflight_digest is not None
        started = record_promotion_dispatch_started(
            journal=journal,
            source_id=key[0],
            field=key[1],
            preflight_digest=intent.intent_preflight_digest,
        )
        write_json_atomic(paths["promotion_journal_path"], started.as_dict())
        return PromotionDispatchResult(
            source_id=key[0],
            field=key[1],
            remote_id=_remote_id(*key),
            envelope_digest=envelope.digest,
            durable_status=PromotionDispatchStatus.EDIT_DISPATCH_STARTED,
            provider_writes_executed=1,
            primitive_postflight_verified=True,
            required_next_action="fresh_status_reconcile_exact_after",
        )

    monkeypatch.setattr(continue_module, "_dispatch_existing_intent", fake_dispatch)
    run_issue_323_continue(**paths, provider_dispatch_confirmation=digest)
    assert dispatch_calls == 1

    after = _observation(managed_key=key, target_after=True, captured_at="2026-08-16T20:32:00+00:00")
    monkeypatch.setattr(continue_module, "run_issue_323_status_probe", lambda **_kwargs: _status(after))
    reconciled = run_issue_323_continue(**paths, provider_dispatch_confirmation=digest)

    assert reconciled["continuation_status"] == "dispatch_reconciled_verified_ready_for_next_plan"
    assert reconciled["provider_writes_executed"] == 0
    assert dispatch_calls == 1
    assert _operation(paths["promotion_journal_path"], key)["status"] == "verified"


def test_preflight_and_provider_confirmation_cannot_be_consumed_in_same_invocation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _paths(tmp_path)
    key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    observation = _observation(managed_key=key, target_after=False, captured_at="2026-08-16T20:33:00+00:00")
    _write_spec(paths["promotion_spec_path"], _spec(key))
    monkeypatch.setattr(continue_module, "run_issue_323_status_probe", lambda **_kwargs: _status(observation))
    preview = run_issue_323_continue(
        **paths,
        journal_init_confirmation=PROMOTION_JOURNAL_INIT_CONFIRMATION,
        journal_created_at="2026-08-16T20:34:00+00:00",
    )

    blocked = run_issue_323_continue(
        **paths,
        preflight_digest_confirmation=preview["promotion_preflight_digest"],
        provider_dispatch_confirmation=preview["promotion_preflight_digest"],
    )

    assert blocked["continuation_status"] == "blocked"
    assert blocked["provider_writes_executed"] == 0
    assert _operation(paths["promotion_journal_path"], key)["status"] == "pending"
