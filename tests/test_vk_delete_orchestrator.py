from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest

from video_channel_manager.platforms.vk.catalog import canonical_sha256
from video_channel_manager.platforms.vk.delete_orchestrator.evidence import DeleteEvidence
from video_channel_manager.platforms.vk.delete_orchestrator.gateway import OwnerInventory
from video_channel_manager.platforms.vk.delete_orchestrator.invariants import (
    FatalInvariantError,
    TransientInvariantError,
    build_epoch_guard,
)
from video_channel_manager.platforms.vk.delete_orchestrator.ledger import DeleteLedger, iso
from video_channel_manager.platforms.vk.delete_orchestrator.models import (
    AttemptOutcome,
    DeletePolicy,
    OperationState,
    OrchestratorConfig,
    VideoGuard,
)
from video_channel_manager.platforms.vk.delete_orchestrator.service import DeleteOrchestrator


def raw_video(remote_id: str, *, title: str) -> dict[str, Any]:
    owner_text, video_text = remote_id.split("_", 1)
    return {
        "owner_id": int(owner_text),
        "id": int(video_text),
        "title": title,
        "description": "",
        "duration": 100,
        "type": "video",
        "date": 1000,
        "views": 0,
        "comments": 0,
        "likes": {"count": 0},
        "reposts": {"count": 0},
    }


def guard(remote_id: str, *, title: str) -> dict[str, Any]:
    owner_text, video_text = remote_id.split("_", 1)
    return {
        "remote_id": remote_id,
        "title": title,
        "description_sha256": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "duration_seconds": 100,
        "owner_id": int(owner_text),
        "video_id": int(video_text),
        "vk_type": "video",
        "date": 1000,
    }


def build_policy(count: int = 3) -> DeletePolicy:
    operations: list[dict[str, Any]] = []
    for ordinal in range(1, count + 1):
        candidate_id = f"-60805374_{100 + ordinal}"
        primary_id = f"-60805374_{200 + ordinal}"
        operation: dict[str, Any] = {
            "operation_id": f"op:{ordinal:03d}:{candidate_id}",
            "operation_sha256": "",
            "candidate_vk_id": candidate_id,
            "primary_vk_id": primary_id,
            "candidate_guard": guard(candidate_id, title=f"candidate-{ordinal}"),
            "primary_guard": guard(primary_id, title=f"primary-{ordinal}"),
            "maximum_views": 100,
            "required_zero_engagement": True,
            "required_wall_state": "unposted",
            "required_duration_difference_at_most_seconds": 1,
            "candidate_managed_album_ids": [],
            "primary_managed_album_ids": [],
        }
        operation["operation_sha256"] = canonical_sha256(
            {key: value for key, value in operation.items() if key != "operation_sha256"}
        )
        operations.append(operation)
    policy: dict[str, Any] = {
        "schema_name": "video-manager.vk-delete-megawave-policy",
        "schema_version": 1,
        "decision_set_id": "test-delete-run",
        "community_id": 60805374,
        "policy_sha256": "",
        "authorization": {
            "authorized_by_user": True,
            "authorized_operation": "delete_exact_reviewed_duplicate_videos",
            "maximum_deletions": count,
            "parallel_writes": False,
            "resume_only_from_verified_journal": True,
        },
        "operations": operations,
    }
    policy["policy_sha256"] = canonical_sha256(
        {key: value for key, value in policy.items() if key != "policy_sha256"}
    )
    return DeletePolicy.model_validate(policy)


class FakeGateway:
    def __init__(self, inventory: OwnerInventory, exact: dict[str, dict[str, Any] | None]) -> None:
        self.inventory = inventory
        self.exact = exact
        self.delete_calls: list[str] = []

    def exact_video(self, remote_id: str) -> dict[str, Any] | None:
        return self.exact.get(remote_id)

    def owner_inventory(self, community_id: int) -> OwnerInventory:
        assert community_id == 60805374
        return self.inventory

    def album_ids(self, *, community_id: int, remote_id: str) -> frozenset[str]:
        return frozenset()

    def wall_video_ids(self, *, community_id: int, postponed: bool = False) -> frozenset[str]:
        return frozenset()

    def delete_once(self, *, community_id: int, remote_id: str) -> object:
        self.delete_calls.append(remote_id)
        return 1


class SequencedGateway(FakeGateway):
    def __init__(self, inventories: list[OwnerInventory], exact: dict[str, dict[str, Any] | None] | None = None) -> None:
        super().__init__(inventories[-1], exact or {})
        self.inventories = list(inventories)
        self.index = 0

    def owner_inventory(self, community_id: int) -> OwnerInventory:
        if self.index < len(self.inventories):
            value = self.inventories[self.index]
            self.index += 1
            return value
        return self.inventories[-1]


def evidence_for(policy: DeletePolicy, inventory_items: list[dict[str, Any]]) -> DeleteEvidence:
    guards: dict[str, VideoGuard] = {}
    for item in inventory_items:
        remote_id = f"{item['owner_id']}_{item['id']}"
        guards[remote_id] = VideoGuard.model_validate(guard(remote_id, title=str(item["title"])))
    protected = {operation.primary_vk_id for operation in policy.operations}
    return DeleteEvidence(
        all_video_ids=frozenset(protected | {operation.candidate_vk_id for operation in policy.operations}),
        protected_video_ids=frozenset(protected),
        published_video_ids=frozenset(),
        postponed_video_ids=frozenset(),
        video_guards=MappingProxyType(guards),
        audit_sha256="sha256:test",
        bundle_sha256="sha256:test",
    )


def accepted_journal(policy: DeletePolicy) -> dict[str, Any]:
    return {
        "updated_at": datetime.now(UTC).isoformat(),
        "completed": {},
        "quarantined": {},
        "attempts": {
            operation.operation_id: {"response": 1, "target_id": -policy.community_id}
            for operation in policy.operations
        },
    }


def test_legacy_quarantine_is_reopened_as_accepted(tmp_path: Path) -> None:
    policy = build_policy(3)
    ledger = DeleteLedger(tmp_path / "ledger.db")
    run_id = ledger.initialize_run(policy, policy_path=tmp_path / "policy.json")
    op1, op2, _ = policy.operations
    journal = accepted_journal(policy)
    journal["completed"] = {op1.operation_id: {"verified_at": datetime.now(UTC).isoformat()}}
    journal["quarantined"] = {op2.operation_id: {"status": "quarantined_no_effect"}}
    imported = ledger.import_legacy_journal(run_id, journal)
    rows = {row["operation_id"]: row for row in ledger.list_operations(run_id)}
    assert imported == {"confirmed": 1, "accepted": 2, "planned": 0}
    assert rows[op1.operation_id]["state"] == OperationState.CONFIRMED_DELETED.value
    assert rows[op2.operation_id]["state"] == OperationState.ACCEPTED.value
    assert rows[op2.operation_id]["dispatch_count"] == 1
    with pytest.raises(RuntimeError, match="Invalid operation transition"):
        ledger.mark_prechecked(op2.operation_id)


def test_shadow_protected_video_is_exactly_guarded_not_counted_as_missing() -> None:
    policy = build_policy(1)
    primary = policy.operations[0].primary_vk_id
    primary_raw = raw_video(primary, title="primary-1")
    fake = FakeGateway(OwnerInventory(reported_count=1, items=()), {primary: primary_raw})
    evidence = DeleteEvidence(
        all_video_ids=frozenset({primary, policy.operations[0].candidate_vk_id}),
        protected_video_ids=frozenset({primary}),
        published_video_ids=frozenset(),
        postponed_video_ids=frozenset(),
        video_guards=MappingProxyType({primary: VideoGuard.model_validate(guard(primary, title="primary-1"))}),
        audit_sha256="sha256:test",
        bundle_sha256="sha256:test",
    )
    epoch = build_epoch_guard(community_id=policy.community_id, evidence=evidence, gateway=fake)
    assert epoch.inventory.reported_count == 1
    assert len(epoch.inventory.ids) == 0
    assert epoch.exact_protected_fallbacks == frozenset({primary})


def test_unexplained_count_items_gap_blocks_candidate_absence() -> None:
    policy = build_policy(1)
    primary = policy.operations[0].primary_vk_id
    primary_raw = raw_video(primary, title="primary-1")
    fake = FakeGateway(OwnerInventory(reported_count=2, items=()), {primary: primary_raw})
    evidence = DeleteEvidence(
        all_video_ids=frozenset({primary, policy.operations[0].candidate_vk_id}),
        protected_video_ids=frozenset({primary}),
        published_video_ids=frozenset(),
        postponed_video_ids=frozenset(),
        video_guards=MappingProxyType({primary: VideoGuard.model_validate(guard(primary, title="primary-1"))}),
        audit_sha256="sha256:test",
        bundle_sha256="sha256:test",
    )
    with pytest.raises(TransientInvariantError, match="unexplained count/items gap"):
        build_epoch_guard(community_id=policy.community_id, evidence=evidence, gateway=fake)


def test_inconsistent_owner_sets_or_counts_are_transient_not_fatal() -> None:
    policy = build_policy(1)
    primary = raw_video(policy.operations[0].primary_vk_id, title="primary-1")
    candidate = raw_video(policy.operations[0].candidate_vk_id, title="candidate-1")
    fake = SequencedGateway(
        [
            OwnerInventory(reported_count=2, items=(primary, candidate)),
            OwnerInventory(reported_count=1, items=(primary,)),
        ]
    )
    with pytest.raises(TransientInvariantError):
        build_epoch_guard(
            community_id=policy.community_id,
            evidence=evidence_for(policy, [primary]),
            gateway=fake,
        )


def test_two_late_effects_are_reconciled_by_id_set_without_count_arithmetic(tmp_path: Path) -> None:
    policy = build_policy(2)
    primary_items = [
        raw_video(operation.primary_vk_id, title=f"primary-{index}")
        for index, operation in enumerate(policy.operations, start=1)
    ]
    fake = FakeGateway(OwnerInventory(reported_count=2, items=tuple(primary_items)), {})
    ledger = DeleteLedger(tmp_path / "ledger.db")
    orchestrator = DeleteOrchestrator(
        policy=policy,
        evidence=evidence_for(policy, primary_items),
        ledger=ledger,
        gateway=fake,
        config=OrchestratorConfig(absent_confirmation_delay_seconds=30),
        sleeper=lambda _: None,
    )
    run_id = orchestrator.bootstrap(
        policy_path=tmp_path / "policy.json",
        legacy_journal=accepted_journal(policy),
    )
    first = orchestrator.reconcile_once(run_id)
    assert first.checked == 2
    assert first.confirmed == 0
    with ledger.connect(immediate=True) as connection:
        old = iso(datetime.now(UTC) - timedelta(minutes=2))
        connection.execute(
            "UPDATE delete_operations SET first_absent_at=?,next_reconcile_at=? WHERE run_id=?",
            (old, iso(), run_id),
        )
    second = orchestrator.reconcile_once(run_id)
    assert second.confirmed == 2
    assert {row["state"] for row in ledger.list_operations(run_id)} == {
        OperationState.CONFIRMED_DELETED.value
    }
    assert fake.delete_calls == []


def test_unknown_write_outcome_cannot_be_dispatched_twice(tmp_path: Path) -> None:
    policy = build_policy(1)
    ledger = DeleteLedger(tmp_path / "ledger.db")
    run_id = ledger.initialize_run(policy, policy_path=tmp_path / "policy.json")
    operation = policy.operations[0]
    ledger.begin_dispatch(operation.operation_id, request_payload={"method": "video.delete"})
    ledger.record_dispatch_result(
        operation.operation_id,
        outcome=AttemptOutcome.UNKNOWN,
        error_message="timeout after send",
        first_reconcile_delay_seconds=120,
        visibility_deadline_hours=24,
    )
    row = ledger.get_operation(operation.operation_id)
    assert row["state"] == OperationState.UNKNOWN_OUTCOME.value
    assert row["dispatch_count"] == 1
    with pytest.raises(RuntimeError):
        ledger.begin_dispatch(operation.operation_id, request_payload={"method": "video.delete"})
    assert ledger.summary(run_id)["unresolved"] == 1


def test_crash_after_dispatch_intent_gets_a_bounded_visibility_deadline(tmp_path: Path) -> None:
    policy = build_policy(1)
    ledger = DeleteLedger(tmp_path / "ledger.db")
    ledger.initialize_run(policy, policy_path=tmp_path / "policy.json")
    operation = policy.operations[0]
    ledger.begin_dispatch(operation.operation_id, request_payload={"method": "video.delete"})
    with ledger.connect(immediate=True) as connection:
        old = iso(datetime.now(UTC) - timedelta(hours=25))
        connection.execute(
            "UPDATE delete_operations SET updated_at=?,next_reconcile_at=? WHERE operation_id=?",
            (old, iso(), operation.operation_id),
        )
    state = ledger.record_observation(
        operation.operation_id,
        candidate_present=True,
        primary_present=True,
        source="test",
        payload={},
        absent_confirmation_delay_seconds=30,
        visibility_deadline_hours=24,
    )
    row = ledger.get_operation(operation.operation_id)
    assert state == OperationState.MANUAL_REVIEW
    assert row["visibility_deadline"] is not None
    assert row["dispatch_count"] == 1


def test_dispatch_epoch_resumes_after_crash_between_epoch_open_and_first_write(tmp_path: Path) -> None:
    policy = build_policy(1)
    operation = policy.operations[0]
    candidate = raw_video(operation.candidate_vk_id, title="candidate-1")
    primary = raw_video(operation.primary_vk_id, title="primary-1")
    fake = FakeGateway(OwnerInventory(reported_count=2, items=(candidate, primary)), {})
    ledger = DeleteLedger(tmp_path / "ledger.db")
    orchestrator = DeleteOrchestrator(
        policy=policy,
        evidence=evidence_for(policy, [primary]),
        ledger=ledger,
        gateway=fake,
        config=OrchestratorConfig(first_reconcile_delay_seconds=30),
        sleeper=lambda _: None,
    )
    run_id = orchestrator.bootstrap(policy_path=tmp_path / "policy.json")
    ledger.open_epoch(run_id, [operation.operation_id])
    assert orchestrator.dispatch_epoch(run_id) == 1
    assert fake.delete_calls == [operation.candidate_vk_id]
    assert ledger.get_operation(operation.operation_id)["state"] == OperationState.ACCEPTED.value
    assert orchestrator.dispatch_epoch(run_id) == 0
    assert fake.delete_calls == [operation.candidate_vk_id]


def test_epoch_with_only_terminal_precheck_results_closes(tmp_path: Path) -> None:
    policy = build_policy(1)
    operation = policy.operations[0]
    ledger = DeleteLedger(tmp_path / "ledger.db")
    run_id = ledger.initialize_run(policy, policy_path=tmp_path / "policy.json")
    epoch_id = ledger.open_epoch(run_id, [operation.operation_id])
    ledger.mark_terminal(operation.operation_id, state=OperationState.MANUAL_REVIEW, reason="test conflict")
    assert ledger.close_epoch_if_terminal(run_id, epoch_id) is True
    assert ledger.active_epoch(run_id) is None


def test_primary_guard_drift_is_fatal_during_reconciliation(tmp_path: Path) -> None:
    policy = build_policy(1)
    operation = policy.operations[0]
    wrong_primary = raw_video(operation.primary_vk_id, title="changed-primary")
    expected_primary = raw_video(operation.primary_vk_id, title="primary-1")
    fake = FakeGateway(OwnerInventory(reported_count=1, items=(wrong_primary,)), {})
    ledger = DeleteLedger(tmp_path / "ledger.db")
    orchestrator = DeleteOrchestrator(
        policy=policy,
        evidence=evidence_for(policy, [expected_primary]),
        ledger=ledger,
        gateway=fake,
        sleeper=lambda _: None,
    )
    run_id = orchestrator.bootstrap(
        policy_path=tmp_path / "policy.json",
        legacy_journal=accepted_journal(policy),
    )
    with pytest.raises(FatalInvariantError, match="Primary immutable guard changed"):
        orchestrator.reconcile_once(run_id)


def test_run_forever_recovers_from_transient_inventory_observation_without_delete(tmp_path: Path) -> None:
    policy = build_policy(1)
    operation = policy.operations[0]
    candidate = raw_video(operation.candidate_vk_id, title="candidate-1")
    primary = raw_video(operation.primary_vk_id, title="primary-1")
    fake = SequencedGateway(
        [
            OwnerInventory(reported_count=2, items=(candidate, primary)),
            OwnerInventory(reported_count=1, items=(primary,)),
            OwnerInventory(reported_count=1, items=(primary,)),
            OwnerInventory(reported_count=1, items=(primary,)),
        ]
    )
    ledger = DeleteLedger(tmp_path / "ledger.db")
    orchestrator = DeleteOrchestrator(
        policy=policy,
        evidence=evidence_for(policy, [primary]),
        ledger=ledger,
        gateway=fake,
        config=OrchestratorConfig(absent_confirmation_delay_seconds=30),
        sleeper=lambda _: None,
    )
    run_id = orchestrator.bootstrap(
        policy_path=tmp_path / "policy.json",
        legacy_journal=accepted_journal(policy),
    )
    summary = orchestrator.run_forever(run_id, execute=True, idle_poll_seconds=5, max_cycles=2)
    assert summary["states"][OperationState.OBSERVED_ABSENT.value] == 1
    assert fake.delete_calls == []
