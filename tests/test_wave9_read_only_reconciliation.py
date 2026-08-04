from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from video_channel_manager.wave_engine.models import ProjectBinding
from video_channel_manager.wave_engine.reconciliation import (
    BoundedSourceSnapshot,
    BoundedTargetSnapshot,
    LocalMutationStage,
    LocalReconciliationRecord,
    ReadOnlyReconciliationError,
    ReconciliationReason,
    ReconciliationState,
    RemoteAssociationKind,
    RemoteMediaType,
    RemoteObservationState,
    RemoteReconciliationObservation,
    TargetCoverageKind,
    build_read_only_reconciliation_evidence,
)

NOW = datetime(2026, 8, 5, 0, 0, tzinfo=UTC)
CAPTURED = NOW - timedelta(minutes=5)
LORD_GOD = ProjectBinding(project_key="lord-god-strength", community_id=60805374, owner_id=-60805374)
LEGENDARY_POET = ProjectBinding(project_key="legendary-poet", community_id=235216998, owner_id=-235216998)


def _source_snapshot(
    *,
    project: ProjectBinding = LORD_GOD,
    source_ids: tuple[str, ...],
    captured_at: datetime = CAPTURED,
) -> BoundedSourceSnapshot:
    channel_id = "UCeSJsC6go2c9pdJCuUI1BYA"
    if project.project_key == "legendary-poet":
        channel_id = "UC-78ys2S3cQ3lpqgXfo-SvQ"
    return BoundedSourceSnapshot.build(
        project=project,
        channel_id=channel_id,
        captured_at=captured_at,
        bounded_source_video_ids=source_ids,
    )


def _observation(
    *,
    source_id: str,
    remote_id: str,
    state: RemoteObservationState = RemoteObservationState.VERIFIED,
    media_type: RemoteMediaType = RemoteMediaType.VIDEO,
    association_kind: RemoteAssociationKind = RemoteAssociationKind.RESERVED_REMOTE_ID,
) -> RemoteReconciliationObservation:
    return RemoteReconciliationObservation(
        source_video_id=source_id,
        remote_id=remote_id,
        state=state,
        association_kind=association_kind,
        media_type=media_type,
        duration_seconds=90 if state is RemoteObservationState.VERIFIED else None,
        postflight_verified=state is RemoteObservationState.VERIFIED,
    )


def _target_snapshot(
    *,
    project: ProjectBinding = LORD_GOD,
    source_ids: tuple[str, ...],
    observations: tuple[RemoteReconciliationObservation, ...],
    coverage_kind: TargetCoverageKind = TargetCoverageKind.COMPLETE_OWNER_CATALOG,
    captured_at: datetime = CAPTURED,
) -> BoundedTargetSnapshot:
    return BoundedTargetSnapshot.build(
        project=project,
        captured_at=captured_at,
        coverage_kind=coverage_kind,
        bounded_source_video_ids=source_ids,
        observations=observations,
    )


def test_lord_god_read_only_reconciliation_preserves_processing_and_missing_boundaries() -> None:
    source_ids = tuple(sorted(("84puu6MnLZs", "KobOzfBqzic", "Vs__dbIlVqU", "rNLPkEhYQbs", "untouched")))
    local_records = tuple(
        sorted(
            (
                LocalReconciliationRecord(
                    source_video_id="84puu6MnLZs",
                    stage=LocalMutationStage.PRE_DISPATCH_FAILED,
                ),
                LocalReconciliationRecord(
                    source_video_id="KobOzfBqzic",
                    stage=LocalMutationStage.SKIPPED_ALREADY_PRESENT,
                    remote_ids=("-60805374_456241937",),
                ),
                LocalReconciliationRecord(
                    source_video_id="Vs__dbIlVqU",
                    stage=LocalMutationStage.PROCESSING,
                    remote_ids=("-60805374_456242062",),
                ),
                LocalReconciliationRecord(
                    source_video_id="rNLPkEhYQbs",
                    stage=LocalMutationStage.VERIFIED,
                    remote_ids=("-60805374_456242054",),
                ),
                LocalReconciliationRecord(
                    source_video_id="untouched",
                    stage=LocalMutationStage.NEVER_DISPATCHED,
                ),
            ),
            key=lambda item: item.source_video_id,
        )
    )
    observations = (
        _observation(source_id="KobOzfBqzic", remote_id="-60805374_456241937"),
        _observation(
            source_id="Vs__dbIlVqU",
            remote_id="-60805374_456242062",
            state=RemoteObservationState.PROCESSING,
            media_type=RemoteMediaType.UNKNOWN,
        ),
        _observation(source_id="rNLPkEhYQbs", remote_id="-60805374_456242054"),
    )

    evidence = build_read_only_reconciliation_evidence(
        project=LORD_GOD,
        source_snapshot=_source_snapshot(source_ids=source_ids),
        target_snapshot=_target_snapshot(source_ids=source_ids, observations=observations),
        local_records=local_records,
        evaluated_at=NOW,
    )

    assert evidence.provider_writes == 0
    assert evidence.write_plan_created is False
    assert evidence.totals.model_dump() == {
        "total": 5,
        "present": 2,
        "duplicate": 0,
        "missing": 2,
        "unknown": 0,
        "requires_attention": 1,
        "mutation_may_have_reached_provider": 2,
        "replay_prohibited": 2,
    }
    by_source = {item.source_video_id: item for item in evidence.items}
    assert by_source["Vs__dbIlVqU"].state is ReconciliationState.REQUIRES_ATTENTION
    assert by_source["Vs__dbIlVqU"].reason is ReconciliationReason.REMOTE_STILL_PROCESSING
    assert by_source["Vs__dbIlVqU"].replay_prohibited is True
    assert by_source["84puu6MnLZs"].state is ReconciliationState.MISSING
    assert by_source["84puu6MnLZs"].reason is ReconciliationReason.EXPLICIT_REJECTION_ABSENT


def test_unknown_mutation_without_remote_readback_is_never_classified_missing() -> None:
    source_ids = ("Vs__dbIlVqU",)
    evidence = build_read_only_reconciliation_evidence(
        project=LORD_GOD,
        source_snapshot=_source_snapshot(source_ids=source_ids),
        target_snapshot=_target_snapshot(source_ids=source_ids, observations=()),
        local_records=(
            LocalReconciliationRecord(
                source_video_id="Vs__dbIlVqU",
                stage=LocalMutationStage.UNKNOWN_REQUIRES_RECONCILIATION,
            ),
        ),
        evaluated_at=NOW,
    )

    item = evidence.items[0]
    assert item.state is ReconciliationState.UNKNOWN
    assert item.reason is ReconciliationReason.MUTATION_OUTCOME_UNRESOLVED
    assert item.replay_prohibited is True


def test_multiple_live_remote_objects_are_duplicate_and_replay_prohibited() -> None:
    source_ids = ("duplicate-source",)
    observations = (
        _observation(
            source_id="duplicate-source",
            remote_id="-60805374_456242100",
            association_kind=RemoteAssociationKind.EXACT_SOURCE_ID,
        ),
        _observation(
            source_id="duplicate-source",
            remote_id="-60805374_456242101",
            association_kind=RemoteAssociationKind.REVIEWED_EXACT_MAPPING,
        ),
    )
    evidence = build_read_only_reconciliation_evidence(
        project=LORD_GOD,
        source_snapshot=_source_snapshot(source_ids=source_ids),
        target_snapshot=_target_snapshot(source_ids=source_ids, observations=observations),
        local_records=(
            LocalReconciliationRecord(
                source_video_id="duplicate-source",
                stage=LocalMutationStage.INVENTORY_ONLY,
            ),
        ),
        evaluated_at=NOW,
    )

    assert evidence.items[0].state is ReconciliationState.DUPLICATE
    assert evidence.items[0].replay_prohibited is True


def test_exact_remote_binding_mismatch_requires_attention() -> None:
    source_ids = ("binding-source",)
    evidence = build_read_only_reconciliation_evidence(
        project=LORD_GOD,
        source_snapshot=_source_snapshot(source_ids=source_ids),
        target_snapshot=_target_snapshot(
            source_ids=source_ids,
            observations=(
                _observation(source_id="binding-source", remote_id="-60805374_456242111"),
            ),
        ),
        local_records=(
            LocalReconciliationRecord(
                source_video_id="binding-source",
                stage=LocalMutationStage.ACCEPTED,
                remote_ids=("-60805374_456242110",),
            ),
        ),
        evaluated_at=NOW,
    )

    item = evidence.items[0]
    assert item.state is ReconciliationState.REQUIRES_ATTENTION
    assert item.reason is ReconciliationReason.LOCAL_REMOTE_BINDING_MISMATCH
    assert item.replay_prohibited is True


def test_legendary_poet_retained_matrix_is_41_present_and_15_missing() -> None:
    source_ids = tuple(f"short-{index:02d}" for index in range(56))
    observations = tuple(
        _observation(
            source_id=source_id,
            remote_id=f"-235216998_{456300000 + index}",
            media_type=RemoteMediaType.SHORT_VIDEO,
            association_kind=RemoteAssociationKind.REVIEWED_EXACT_MAPPING,
        )
        for index, source_id in enumerate(source_ids[:41])
    )
    local_records = tuple(
        LocalReconciliationRecord(
            source_video_id=source_id,
            stage=(
                LocalMutationStage.SKIPPED_ALREADY_PRESENT
                if index < 41
                else LocalMutationStage.NEVER_DISPATCHED
            ),
            remote_ids=((f"-235216998_{456300000 + index}",) if index < 41 else ()),
        )
        for index, source_id in enumerate(source_ids)
    )

    evidence = build_read_only_reconciliation_evidence(
        project=LEGENDARY_POET,
        source_snapshot=_source_snapshot(project=LEGENDARY_POET, source_ids=source_ids),
        target_snapshot=_target_snapshot(
            project=LEGENDARY_POET,
            source_ids=source_ids,
            observations=observations,
            coverage_kind=TargetCoverageKind.COMPLETE_SHORT_SURFACE,
        ),
        local_records=local_records,
        evaluated_at=NOW,
    )

    assert evidence.totals.total == 56
    assert evidence.totals.present == 41
    assert evidence.totals.missing == 15
    assert evidence.totals.duplicate == 0
    assert evidence.totals.unknown == 0
    assert evidence.totals.requires_attention == 0
    assert evidence.provider_writes == 0
    assert evidence.write_plan_created is False


def test_exact_reserved_id_coverage_cannot_prove_absence_without_remote_id() -> None:
    source_ids = ("untouched",)
    with pytest.raises(ReadOnlyReconciliationError, match="cannot prove absence"):
        build_read_only_reconciliation_evidence(
            project=LORD_GOD,
            source_snapshot=_source_snapshot(source_ids=source_ids),
            target_snapshot=_target_snapshot(
                source_ids=source_ids,
                observations=(),
                coverage_kind=TargetCoverageKind.EXACT_RESERVED_IDS,
            ),
            local_records=(
                LocalReconciliationRecord(
                    source_video_id="untouched",
                    stage=LocalMutationStage.NEVER_DISPATCHED,
                ),
            ),
            evaluated_at=NOW,
        )


def test_stale_snapshot_is_rejected() -> None:
    source_ids = ("stale",)
    stale = NOW - timedelta(hours=2)
    with pytest.raises(ReadOnlyReconciliationError, match="source snapshot is stale"):
        build_read_only_reconciliation_evidence(
            project=LORD_GOD,
            source_snapshot=_source_snapshot(source_ids=source_ids, captured_at=stale),
            target_snapshot=_target_snapshot(
                source_ids=source_ids,
                observations=(),
                captured_at=CAPTURED,
            ),
            local_records=(
                LocalReconciliationRecord(
                    source_video_id="stale",
                    stage=LocalMutationStage.NEVER_DISPATCHED,
                ),
            ),
            evaluated_at=NOW,
            maximum_snapshot_age_seconds=3600,
        )


def test_local_records_must_exactly_cover_bounded_source_set() -> None:
    source_ids = ("a", "b")
    with pytest.raises(ReadOnlyReconciliationError, match="exactly cover"):
        build_read_only_reconciliation_evidence(
            project=LORD_GOD,
            source_snapshot=_source_snapshot(source_ids=source_ids),
            target_snapshot=_target_snapshot(source_ids=source_ids, observations=()),
            local_records=(
                LocalReconciliationRecord(
                    source_video_id="a",
                    stage=LocalMutationStage.NEVER_DISPATCHED,
                ),
            ),
            evaluated_at=NOW,
        )


def test_target_snapshot_rejects_cross_project_remote_id() -> None:
    source_ids = ("cross-project",)
    with pytest.raises(ValidationError, match="differs from project owner"):
        _target_snapshot(
            source_ids=source_ids,
            observations=(
                _observation(
                    source_id="cross-project",
                    remote_id="-235216998_456300100",
                ),
            ),
        )


def test_verified_observation_requires_final_type_duration_and_postflight() -> None:
    with pytest.raises(ValidationError, match="postflight"):
        RemoteReconciliationObservation(
            source_video_id="source",
            remote_id="-60805374_456242120",
            state=RemoteObservationState.VERIFIED,
            association_kind=RemoteAssociationKind.EXACT_SOURCE_ID,
            media_type=RemoteMediaType.VIDEO,
            duration_seconds=90,
            postflight_verified=False,
        )


def test_reconciliation_evidence_digest_detects_tampering() -> None:
    source_ids = ("tamper",)
    evidence = build_read_only_reconciliation_evidence(
        project=LORD_GOD,
        source_snapshot=_source_snapshot(source_ids=source_ids),
        target_snapshot=_target_snapshot(source_ids=source_ids, observations=()),
        local_records=(
            LocalReconciliationRecord(
                source_video_id="tamper",
                stage=LocalMutationStage.NEVER_DISPATCHED,
            ),
        ),
        evaluated_at=NOW,
    )
    payload = evidence.model_dump(mode="json")
    payload["self_digest"] = "0" * 64

    with pytest.raises(ValidationError, match="self_digest mismatch"):
        type(evidence).model_validate(payload)


def test_snapshot_builders_are_deterministic() -> None:
    source_ids = ("a", "b")
    source_one = _source_snapshot(source_ids=source_ids)
    source_two = _source_snapshot(source_ids=source_ids)
    target_one = _target_snapshot(source_ids=source_ids, observations=())
    target_two = _target_snapshot(source_ids=source_ids, observations=())

    assert source_one == source_two
    assert target_one == target_two
