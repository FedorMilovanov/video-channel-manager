from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Any

from video_channel_manager.platforms.vk.catalog import canonical_sha256
from video_channel_manager.platforms.vk.delete_orchestrator.evidence import DeleteEvidence
from video_channel_manager.platforms.vk.delete_orchestrator.gateway import OwnerInventory
from video_channel_manager.platforms.vk.delete_orchestrator.ledger import DeleteLedger, iso
from video_channel_manager.platforms.vk.delete_orchestrator.models import (
    DeletePolicy,
    OperationState,
    OrchestratorConfig,
    VideoGuard,
)
from video_channel_manager.platforms.vk.delete_orchestrator.service import DeleteOrchestrator


def _guard(remote_id: str, title: str) -> dict[str, Any]:
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


def _raw_video(remote_id: str, title: str) -> dict[str, Any]:
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


def _policy() -> DeletePolicy:
    candidate_id = "-60805374_101"
    primary_id = "-60805374_201"
    operation: dict[str, Any] = {
        "operation_id": f"op:001:{candidate_id}",
        "operation_sha256": "",
        "candidate_vk_id": candidate_id,
        "primary_vk_id": primary_id,
        "candidate_guard": _guard(candidate_id, "candidate"),
        "primary_guard": _guard(primary_id, "primary"),
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
    policy: dict[str, Any] = {
        "schema_name": "video-manager.vk-delete-megawave-policy",
        "schema_version": 1,
        "decision_set_id": "read-only-watch-test",
        "community_id": 60805374,
        "policy_sha256": "",
        "authorization": {
            "authorized_by_user": True,
            "authorized_operation": "delete_exact_reviewed_duplicate_videos",
            "maximum_deletions": 1,
            "parallel_writes": False,
            "resume_only_from_verified_journal": True,
        },
        "operations": [operation],
    }
    policy["policy_sha256"] = canonical_sha256({key: value for key, value in policy.items() if key != "policy_sha256"})
    return DeletePolicy.model_validate(policy)


class ReadOnlyGateway:
    def __init__(self, primary: dict[str, Any]) -> None:
        self.primary = primary
        self.delete_calls: list[str] = []

    def exact_video(self, remote_id: str) -> dict[str, Any] | None:
        return self.primary if remote_id == f"{self.primary['owner_id']}_{self.primary['id']}" else None

    def owner_inventory(self, community_id: int) -> OwnerInventory:
        return OwnerInventory(reported_count=1, items=(self.primary,))

    def album_ids(self, *, community_id: int, remote_id: str) -> frozenset[str]:
        return frozenset()

    def wall_video_ids(self, *, community_id: int, postponed: bool = False) -> frozenset[str]:
        return frozenset()

    def delete_once(self, *, community_id: int, remote_id: str) -> object:
        self.delete_calls.append(remote_id)
        raise AssertionError("read-only watch must never dispatch video.delete")


def test_continuous_read_only_watch_settles_legacy_operation_without_write(tmp_path: Path) -> None:
    policy = _policy()
    operation = policy.operations[0]
    primary = _raw_video(operation.primary_vk_id, "primary")
    evidence = DeleteEvidence(
        all_video_ids=frozenset({operation.candidate_vk_id, operation.primary_vk_id}),
        protected_video_ids=frozenset({operation.primary_vk_id}),
        published_video_ids=frozenset(),
        postponed_video_ids=frozenset(),
        video_guards=MappingProxyType(
            {operation.primary_vk_id: VideoGuard.model_validate(_guard(operation.primary_vk_id, "primary"))}
        ),
        audit_sha256="sha256:test",
        bundle_sha256="sha256:test",
    )
    gateway = ReadOnlyGateway(primary)
    ledger = DeleteLedger(tmp_path / "ledger.db")
    orchestrator = DeleteOrchestrator(
        policy=policy,
        evidence=evidence,
        ledger=ledger,
        gateway=gateway,
        config=OrchestratorConfig(absent_confirmation_delay_seconds=30),
        sleeper=lambda _: None,
    )
    journal = {
        "updated_at": datetime.now(UTC).isoformat(),
        "completed": {},
        "quarantined": {},
        "attempts": {operation.operation_id: {"response": 1, "target_id": -policy.community_id}},
    }
    run_id = orchestrator.bootstrap(policy_path=tmp_path / "policy.json", legacy_journal=journal)
    first = orchestrator.reconcile_once(run_id)
    assert first.waiting == 1
    with ledger.connect(immediate=True) as connection:
        connection.execute(
            "UPDATE delete_operations SET first_absent_at=?,next_reconcile_at=? WHERE operation_id=?",
            (
                iso(datetime.now(UTC) - timedelta(minutes=2)),
                iso(),
                operation.operation_id,
            ),
        )
    summary = orchestrator.run_forever(
        run_id,
        execute=False,
        continuous=True,
        idle_poll_seconds=5,
        max_cycles=1,
    )
    assert summary["status"] == "completed"
    assert summary["states"] == {OperationState.CONFIRMED_DELETED.value: 1}
    assert gateway.delete_calls == []
