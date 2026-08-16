from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import video_channel_manager.platforms.vk.milovi_issue323_continue as continue_module
from video_channel_manager.platforms.vk.milovi_issue323_continue import (
    PROMOTION_JOURNAL_INIT_CONFIRMATION,
    run_issue_323_continue_preview,
)
from video_channel_manager.platforms.vk.milovi_issue323_promotion_journal import (
    initialize_promotion_journal,
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


def _text(source_id: str, field: PromotionField) -> str:
    return f"reviewed current {source_id} {field.value}"


def _remote_id(source_id: str, field: PromotionField) -> str:
    index = ROLL_OUT_IDS.index(source_id)
    if field is PromotionField.CLIP_DESCRIPTION:
        return f"-68859909_{456239200 + index}"
    return f"-68859909_{500 + index}"


def _wall_incarnation(source_id: str, text: str) -> VkWallPostFingerprint:
    index = ROLL_OUT_IDS.index(source_id)
    return VkWallPostFingerprint(
        owner_id=-68859909,
        post_id=500 + index,
        surface=VkWallSurface.PUBLISHED,
        publish_date=1_700_000_000 + index,
        text_sha256=promotion_text_sha256(text),
        attachments=(f"video-68859909_{456239200 + index}",),
    )


def _observation(
    *,
    override: tuple[str, PromotionField, str] | None = None,
    captured_at: str = "2026-08-16T10:00:00+00:00",
    wall_snapshot_sha256: str = "sha256:exact-wall-snapshot",
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
                    wall_incarnation=(
                        None if field is PromotionField.CLIP_DESCRIPTION else _wall_incarnation(source_id, value)
                    ),
                )
            )
    return PromotionObservationBatch(
        source_snapshot_id="issue323-reviewed-snapshot",
        wall_snapshot_sha256=wall_snapshot_sha256,
        captured_at=captured_at,
        fields=tuple(fields),
    )


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


def _write_spec(path: Path, spec: PromotionSpec) -> None:
    path.write_text(json.dumps(spec.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def _status_payload(observation: PromotionObservationBatch) -> dict[str, Any]:
    observed = observation.as_dict()
    observed["observation_digest"] = observation.digest
    return {
        "status": "verified_read_only",
        "provider_mutation_authorized": False,
        "promotion_observation": observed,
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


def _journal_operation(path: Path, key: tuple[str, PromotionField]) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return next(item for item in payload["operations"] if item["source_id"] == key[0] and item["field"] == key[1].value)


def test_missing_promotion_journal_stops_after_one_readonly_status_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _paths(tmp_path)
    observation = _observation()
    _write_spec(paths["promotion_spec_path"], _spec())
    calls: list[dict[str, object]] = []

    def fake_status(**kwargs: object) -> dict[str, Any]:
        calls.append(kwargs)
        return _status_payload(observation)

    monkeypatch.setattr(continue_module, "run_issue_323_status_probe", fake_status)

    result = run_issue_323_continue_preview(**paths)

    assert len(calls) == 1
    assert result["continuation_status"] == "blocked"
    assert result["provider_mutation_authorized"] is False
    assert result["provider_writes_executed"] == 0
    assert result["promotion_preflight"] is None
    assert result["promotion_intent_persisted"] is False
    assert result["preflight_digest_confirmation_supplied"] is False
    assert result["preflight_digest_confirmed"] is False
    assert not paths["promotion_journal_path"].exists()
    assert "explicitly initialize" in result["blockers"][0]


def test_explicit_journal_init_builds_digest_bound_plan_but_executes_zero_provider_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _paths(tmp_path)
    key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    observation = _observation()
    spec = _spec(managed_key=key)
    _write_spec(paths["promotion_spec_path"], spec)
    calls = 0

    def fake_status(**_kwargs: object) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return _status_payload(observation)

    monkeypatch.setattr(continue_module, "run_issue_323_status_probe", fake_status)

    result = run_issue_323_continue_preview(
        **paths,
        journal_init_confirmation=PROMOTION_JOURNAL_INIT_CONFIRMATION,
        journal_created_at="2026-08-16T10:05:00+00:00",
    )

    assert calls == 1
    assert result["continuation_status"] == "ready_for_digest_confirmation"
    assert result["provider_mutation_authorized"] is False
    assert result["provider_writes_executed"] == 0
    assert result["promotion_journal_initialized"] is True
    assert result["promotion_intent_persisted"] is False
    assert result["promotion_spec_digest"] == spec.digest
    assert result["promotion_observation_digest"] == observation.digest
    assert result["promotion_provider_state_digest"] == observation.provider_state_digest
    assert result["promotion_preflight"]["expected_provider_writes"] == 1
    assert result["promotion_preflight"]["provider_mutation_authorized"] is False
    assert result["promotion_preflight_digest"] == result["promotion_preflight_confirmation_digest"]
    assert result["promotion_preflight_evidence_digest"] != result["promotion_preflight_digest"]
    assert result["preflight_digest_confirmation_supplied"] is False
    assert result["preflight_digest_confirmed"] is False
    assert paths["promotion_journal_path"].is_file()


def test_exact_confirmation_persists_only_local_intent_across_fresh_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _paths(tmp_path)
    key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    first_observation = _observation(
        captured_at="2026-08-16T10:00:00+00:00",
        wall_snapshot_sha256="sha256:first-capture-wall-snapshot",
    )
    second_observation = _observation(
        captured_at="2026-08-16T10:01:00+00:00",
        wall_snapshot_sha256="sha256:second-capture-wall-snapshot",
    )
    _write_spec(paths["promotion_spec_path"], _spec(managed_key=key))
    observations = iter((first_observation, second_observation))
    monkeypatch.setattr(
        continue_module,
        "run_issue_323_status_probe",
        lambda **_kwargs: _status_payload(next(observations)),
    )
    preview = run_issue_323_continue_preview(
        **paths,
        journal_init_confirmation=PROMOTION_JOURNAL_INIT_CONFIRMATION,
        journal_created_at="2026-08-16T10:05:00+00:00",
    )
    journal_before = paths["promotion_journal_path"].read_text(encoding="utf-8")

    confirmed = run_issue_323_continue_preview(
        **paths,
        preflight_digest_confirmation=preview["promotion_preflight_digest"],
    )

    assert confirmed["continuation_status"] == "intent_persisted_provider_dispatch_not_available"
    assert confirmed["promotion_observation_digest"] != preview["promotion_observation_digest"]
    assert confirmed["promotion_provider_state_digest"] == preview["promotion_provider_state_digest"]
    assert confirmed["promotion_preflight_evidence_digest"] != preview["promotion_preflight_evidence_digest"]
    assert confirmed["promotion_preflight_digest"] == preview["promotion_preflight_digest"]
    assert confirmed["preflight_digest_confirmation_supplied"] is True
    assert confirmed["preflight_digest_confirmed"] is True
    assert confirmed["promotion_intent_persisted"] is True
    assert confirmed["promotion_intent_reconciled"] is False
    assert confirmed["promotion_intent"]["source_id"] == key[0]
    assert confirmed["promotion_intent"]["field"] == key[1].value
    assert confirmed["promotion_intent"]["status"] == "edit_intent"
    assert confirmed["promotion_intent"]["dispatch_started"] is False
    assert confirmed["promotion_intent"]["intent_remote_id"] == _remote_id(*key)
    assert confirmed["promotion_intent"]["intent_preflight_digest"] == confirmed["promotion_preflight_evidence_digest"]
    assert confirmed["provider_mutation_authorized"] is False
    assert confirmed["provider_writes_executed"] == 0
    assert paths["promotion_journal_path"].read_text(encoding="utf-8") != journal_before
    operation = _journal_operation(paths["promotion_journal_path"], key)
    assert operation == confirmed["promotion_intent"]


def test_existing_unstarted_intent_is_reconciled_before_confirmation_can_be_reused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _paths(tmp_path)
    key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    observations = iter(
        (
            _observation(captured_at="2026-08-16T10:00:00+00:00"),
            _observation(captured_at="2026-08-16T10:01:00+00:00"),
            _observation(captured_at="2026-08-16T10:02:00+00:00"),
        )
    )
    _write_spec(paths["promotion_spec_path"], _spec(managed_key=key))
    monkeypatch.setattr(
        continue_module,
        "run_issue_323_status_probe",
        lambda **_kwargs: _status_payload(next(observations)),
    )
    preview = run_issue_323_continue_preview(
        **paths,
        journal_init_confirmation=PROMOTION_JOURNAL_INIT_CONFIRMATION,
        journal_created_at="2026-08-16T10:05:00+00:00",
    )
    persisted = run_issue_323_continue_preview(
        **paths,
        preflight_digest_confirmation=preview["promotion_preflight_digest"],
    )
    assert persisted["promotion_intent_persisted"] is True

    recovered = run_issue_323_continue_preview(
        **paths,
        preflight_digest_confirmation=preview["promotion_preflight_digest"],
    )

    assert recovered["continuation_status"] == "intent_reconciled_ready_for_digest_confirmation"
    assert recovered["promotion_intent_persisted"] is False
    assert recovered["promotion_intent_reconciled"] is True
    assert recovered["preflight_digest_confirmation_supplied"] is True
    assert recovered["preflight_digest_confirmed"] is False
    assert recovered["provider_mutation_authorized"] is False
    assert recovered["provider_writes_executed"] == 0
    operation = _journal_operation(paths["promotion_journal_path"], key)
    assert operation["status"] == "pending"
    assert operation["dispatch_started"] is False
    assert operation["intent_preflight_digest"] is None
    assert operation["intent_remote_id"] is None


def test_unstarted_intent_with_provider_drift_blocks_and_remains_durable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _paths(tmp_path)
    key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    observations = iter(
        (
            _observation(captured_at="2026-08-16T10:00:00+00:00"),
            _observation(captured_at="2026-08-16T10:01:00+00:00"),
            _observation(
                override=(*key, "manual drift after confirmed intent"),
                captured_at="2026-08-16T10:02:00+00:00",
            ),
        )
    )
    _write_spec(paths["promotion_spec_path"], _spec(managed_key=key))
    monkeypatch.setattr(
        continue_module,
        "run_issue_323_status_probe",
        lambda **_kwargs: _status_payload(next(observations)),
    )
    preview = run_issue_323_continue_preview(
        **paths,
        journal_init_confirmation=PROMOTION_JOURNAL_INIT_CONFIRMATION,
        journal_created_at="2026-08-16T10:05:00+00:00",
    )
    run_issue_323_continue_preview(
        **paths,
        preflight_digest_confirmation=preview["promotion_preflight_digest"],
    )
    journal_with_intent = paths["promotion_journal_path"].read_text(encoding="utf-8")

    blocked = run_issue_323_continue_preview(**paths)

    assert blocked["continuation_status"] == "blocked"
    assert blocked["promotion_intent_persisted"] is False
    assert blocked["promotion_intent_reconciled"] is False
    assert blocked["provider_mutation_authorized"] is False
    assert blocked["provider_writes_executed"] == 0
    assert "requires recovery" in blocked["blockers"][0]
    assert paths["promotion_journal_path"].read_text(encoding="utf-8") == journal_with_intent
    assert _journal_operation(paths["promotion_journal_path"], key)["status"] == "edit_intent"


def test_wrong_or_stale_preflight_digest_confirmation_blocks_without_journal_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _paths(tmp_path)
    key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    observation = _observation()
    _write_spec(paths["promotion_spec_path"], _spec(managed_key=key))
    monkeypatch.setattr(
        continue_module,
        "run_issue_323_status_probe",
        lambda **_kwargs: _status_payload(observation),
    )
    preview = run_issue_323_continue_preview(
        **paths,
        journal_init_confirmation=PROMOTION_JOURNAL_INIT_CONFIRMATION,
        journal_created_at="2026-08-16T10:05:00+00:00",
    )
    journal_before = paths["promotion_journal_path"].read_text(encoding="utf-8")
    assert preview["promotion_preflight_digest"] != "sha256:" + "0" * 64

    blocked = run_issue_323_continue_preview(
        **paths,
        preflight_digest_confirmation="sha256:" + "0" * 64,
    )

    assert blocked["continuation_status"] == "blocked"
    assert blocked["preflight_digest_confirmation_supplied"] is True
    assert blocked["preflight_digest_confirmed"] is False
    assert blocked["promotion_intent_persisted"] is False
    assert blocked["provider_mutation_authorized"] is False
    assert blocked["provider_writes_executed"] == 0
    assert "does not match" in blocked["blockers"][0]
    assert paths["promotion_journal_path"].read_text(encoding="utf-8") == journal_before


def test_journal_init_refuses_one_field_drift_and_creates_no_durable_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _paths(tmp_path)
    drift_key = (ROLL_OUT_IDS[7], PromotionField.WALL_MESSAGE)
    observation = _observation(override=(*drift_key, "operator changed after review"))
    _write_spec(paths["promotion_spec_path"], _spec(managed_key=(ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)))
    monkeypatch.setattr(
        continue_module,
        "run_issue_323_status_probe",
        lambda **_kwargs: _status_payload(observation),
    )

    result = run_issue_323_continue_preview(
        **paths,
        journal_init_confirmation=PROMOTION_JOURNAL_INIT_CONFIRMATION,
        journal_created_at="2026-08-16T10:05:00+00:00",
    )

    assert result["continuation_status"] == "blocked"
    assert result["provider_writes_executed"] == 0
    assert not paths["promotion_journal_path"].exists()
    assert "initialization refused" in result["blockers"][0]


def test_existing_journal_cannot_be_rebound_to_different_review_spec(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _paths(tmp_path)
    observation = _observation()
    original_spec = _spec(review_id="review-1")
    journal = initialize_promotion_journal(
        spec=original_spec,
        observation=observation,
        created_at="2026-08-16T10:05:00+00:00",
    )
    paths["promotion_journal_path"].write_text(
        json.dumps(journal.as_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_spec(paths["promotion_spec_path"], _spec(review_id="review-2"))
    monkeypatch.setattr(
        continue_module,
        "run_issue_323_status_probe",
        lambda **_kwargs: _status_payload(observation),
    )

    result = run_issue_323_continue_preview(**paths)

    assert result["continuation_status"] == "blocked"
    assert result["provider_writes_executed"] == 0
    assert "different reviewed PromotionSpec" in result["blockers"][0]


def test_tampered_status_observation_digest_stops_before_journal_use(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _paths(tmp_path)
    observation = _observation()
    _write_spec(paths["promotion_spec_path"], _spec())
    payload = _status_payload(observation)
    payload["promotion_observation"]["observation_digest"] = "sha256:" + "0" * 64
    monkeypatch.setattr(continue_module, "run_issue_323_status_probe", lambda **_kwargs: payload)

    result = run_issue_323_continue_preview(**paths)

    assert result["continuation_status"] == "blocked"
    assert result["provider_writes_executed"] == 0
    assert result["promotion_preflight"] is None
    assert result["preflight_digest_confirmed"] is False
    assert "digest mismatch" in result["blockers"][0]
