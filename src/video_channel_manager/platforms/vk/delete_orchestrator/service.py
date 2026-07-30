from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from video_channel_manager.platforms.vk.client import VkApiError
from video_channel_manager.platforms.vk.delete_orchestrator.evidence import DeleteEvidence
from video_channel_manager.platforms.vk.delete_orchestrator.gateway import DeleteGateway
from video_channel_manager.platforms.vk.delete_orchestrator.invariants import (
    FatalInvariantError,
    OperationConflictError,
    TransientInvariantError,
    build_epoch_guard,
    precheck_operation,
)
from video_channel_manager.platforms.vk.delete_orchestrator.ledger import DeleteLedger
from video_channel_manager.platforms.vk.delete_orchestrator.models import (
    AttemptOutcome,
    DeletePolicy,
    OperationState,
    OrchestratorConfig,
    RunState,
)


@dataclass(frozen=True)
class ReconcileResult:
    checked: int
    confirmed: int
    waiting: int
    manual_review: int


class DeleteOrchestrator:
    """Durable at-most-once dispatcher plus asynchronous set-based reconciler."""

    def __init__(
        self,
        *,
        policy: DeletePolicy,
        evidence: DeleteEvidence,
        ledger: DeleteLedger,
        gateway: DeleteGateway,
        config: OrchestratorConfig | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        random_uniform: Callable[[float, float], float] = random.uniform,
    ) -> None:
        self.policy = policy
        self.evidence = evidence
        self.ledger = ledger
        self.gateway = gateway
        self.config = config or OrchestratorConfig()
        self.sleeper = sleeper
        self.random_uniform = random_uniform
        self._operations = {operation.operation_id: operation for operation in policy.operations}
        self._managed_album_ids = frozenset(
            album_id
            for operation in policy.operations
            for album_id in (*operation.candidate_managed_album_ids, *operation.primary_managed_album_ids)
        )

    def bootstrap(self, *, policy_path: Path, legacy_journal: dict[str, Any] | None = None) -> str:
        run_id = self.ledger.initialize_run(self.policy, policy_path=policy_path)
        if legacy_journal is not None:
            self.ledger.import_legacy_journal(run_id, legacy_journal)
        return run_id

    def reconcile_once(self, run_id: str) -> ReconcileResult:
        due = self.ledger.due_for_reconcile(run_id)
        if not due:
            return ReconcileResult(checked=0, confirmed=0, waiting=0, manual_review=0)
        guard = build_epoch_guard(
            community_id=self.policy.community_id,
            evidence=self.evidence,
            gateway=self.gateway,
        )
        checked = confirmed = waiting = manual_review = 0
        for row in due:
            operation_id = str(row["operation_id"])
            operation = self._operations[operation_id]
            candidate_present = operation.candidate_vk_id in guard.inventory_by_id
            primary_present = (
                operation.primary_vk_id in guard.inventory_by_id
                or operation.primary_vk_id in guard.exact_protected_fallbacks
            )
            new_state = self.ledger.record_observation(
                operation_id,
                candidate_present=candidate_present,
                primary_present=primary_present,
                source="stable_owner_inventory_set",
                payload={
                    "candidate_id": operation.candidate_vk_id,
                    "primary_id": operation.primary_vk_id,
                    "owner_count": guard.inventory.reported_count,
                    "visible_item_count": len(guard.inventory_by_id),
                    "protected_exact_fallbacks": sorted(guard.exact_protected_fallbacks),
                },
                absent_confirmation_delay_seconds=self.config.absent_confirmation_delay_seconds,
            )
            checked += 1
            if new_state == OperationState.CONFIRMED_DELETED:
                confirmed += 1
            elif new_state == OperationState.MANUAL_REVIEW:
                manual_review += 1
            else:
                waiting += 1
        active = self.ledger.active_epoch(run_id)
        if active is not None:
            self.ledger.close_epoch_if_terminal(run_id, int(active["epoch_id"]))
        return ReconcileResult(checked=checked, confirmed=confirmed, waiting=waiting, manual_review=manual_review)

    def dispatch_epoch(self, run_id: str) -> int:
        if self.ledger.active_epoch(run_id) is not None:
            return 0
        summary = self.ledger.summary(run_id)
        available_slots = self.config.max_unresolved - int(summary["unresolved"])
        if available_slots <= 0:
            return 0
        successful_epochs = self.ledger.successful_epochs(run_id)
        configured_batch = self.config.canary_batch_size if successful_epochs < 2 else self.config.steady_batch_size
        planned = self.ledger.next_planned(run_id, limit=min(configured_batch, available_slots))
        if not planned:
            return 0
        operation_ids = [str(row["operation_id"]) for row in planned]
        epoch_id = self.ledger.open_epoch(run_id, operation_ids)
        guard = build_epoch_guard(
            community_id=self.policy.community_id,
            evidence=self.evidence,
            gateway=self.gateway,
        )
        dispatched = 0
        for row in planned:
            operation_id = str(row["operation_id"])
            operation = self._operations[operation_id]
            try:
                precheck_operation(
                    operation,
                    community_id=self.policy.community_id,
                    managed_album_ids=self._managed_album_ids,
                    epoch_guard=guard,
                    gateway=self.gateway,
                )
            except OperationConflictError as exc:
                self.ledger.mark_terminal(
                    operation_id,
                    state=OperationState.MANUAL_REVIEW,
                    reason=str(exc),
                )
                continue
            self.ledger.mark_prechecked(operation_id)
            self.ledger.begin_dispatch(
                operation_id,
                request_payload={
                    "method": "video.delete",
                    "owner_id": operation.candidate_guard.owner_id,
                    "target_id": -self.policy.community_id,
                    "video_id": operation.candidate_guard.video_id,
                    "operation_sha256": operation.operation_sha256,
                },
            )
            try:
                response = self.gateway.delete_once(
                    community_id=self.policy.community_id,
                    remote_id=operation.candidate_vk_id,
                )
            except VkApiError as exc:
                outcome = self._classify_write_error(exc)
                self.ledger.record_dispatch_result(
                    operation_id,
                    outcome=outcome,
                    api_error_code=exc.code,
                    error_message=str(exc),
                    first_reconcile_delay_seconds=self.config.first_reconcile_delay_seconds,
                    visibility_deadline_hours=self.config.visibility_deadline_hours,
                )
                if exc.code in {5, 27}:
                    raise FatalInvariantError(f"VK authorization failed during delete dispatch: {exc}") from exc
            except Exception as exc:
                # The request may have reached VK. Never repeat it automatically.
                self.ledger.record_dispatch_result(
                    operation_id,
                    outcome=AttemptOutcome.UNKNOWN,
                    error_message=f"transport_or_unknown:{type(exc).__name__}:{exc}",
                    first_reconcile_delay_seconds=self.config.first_reconcile_delay_seconds,
                    visibility_deadline_hours=self.config.visibility_deadline_hours,
                )
            else:
                outcome = AttemptOutcome.ACCEPTED if response == 1 else AttemptOutcome.UNKNOWN
                self.ledger.record_dispatch_result(
                    operation_id,
                    outcome=outcome,
                    response=response,
                    error_message=None if outcome == AttemptOutcome.ACCEPTED else f"unexpected_response:{response!r}",
                    first_reconcile_delay_seconds=self.config.first_reconcile_delay_seconds,
                    visibility_deadline_hours=self.config.visibility_deadline_hours,
                )
            dispatched += 1
            delay = self.config.write_delay_seconds + self.random_uniform(0.0, self.config.write_jitter_seconds)
            self.sleeper(delay)
        self.ledger.start_epoch_cooldown(
            run_id,
            epoch_id,
            cooldown_seconds=self.config.first_reconcile_delay_seconds,
        )
        return dispatched

    def run_forever(
        self,
        run_id: str,
        *,
        execute: bool,
        idle_poll_seconds: float = 30.0,
        max_cycles: int | None = None,
    ) -> dict[str, Any]:
        lease_owner = self.ledger.new_lease_owner()
        self.ledger.acquire_lease(run_id, owner=lease_owner, ttl_seconds=self.config.lease_ttl_seconds)
        cycle = 0
        try:
            self.ledger.set_run_state(run_id, RunState.RUNNING)
            while max_cycles is None or cycle < max_cycles:
                cycle += 1
                self.ledger.heartbeat(run_id, owner=lease_owner, ttl_seconds=self.config.lease_ttl_seconds)
                try:
                    self.reconcile_once(run_id)
                except FatalInvariantError as exc:
                    self.ledger.set_run_state(run_id, RunState.PAUSED_FATAL, reason=str(exc))
                    raise
                except TransientInvariantError as exc:
                    self.ledger.set_run_state(run_id, RunState.PAUSED_TRANSIENT, reason=str(exc))
                    if not execute:
                        return self.ledger.summary(run_id)
                    self.sleeper(idle_poll_seconds)
                    continue
                summary = self.ledger.summary(run_id)
                states = summary["states"]
                planned = int(states.get(OperationState.PLANNED.value, 0))
                unresolved = int(summary["unresolved"])
                if int(summary["terminal"]) == int(summary["total"]):
                    has_exceptions = any(
                        int(states.get(state.value, 0))
                        for state in (
                            OperationState.QUARANTINED,
                            OperationState.MANUAL_REVIEW,
                            OperationState.REJECTED_PERMANENT,
                        )
                    )
                    final_state = RunState.COMPLETED_WITH_QUARANTINE if has_exceptions else RunState.COMPLETED
                    self.ledger.set_run_state(run_id, final_state)
                    return self.ledger.summary(run_id)
                if (
                    execute
                    and planned > 0
                    and self.ledger.unresolved_legacy_count(run_id) == 0
                    and self.ledger.active_epoch(run_id) is None
                ):
                    try:
                        dispatched = self.dispatch_epoch(run_id)
                    except FatalInvariantError as exc:
                        self.ledger.set_run_state(run_id, RunState.PAUSED_FATAL, reason=str(exc))
                        raise
                    except TransientInvariantError as exc:
                        self.ledger.set_run_state(run_id, RunState.PAUSED_TRANSIENT, reason=str(exc))
                        self.sleeper(idle_poll_seconds)
                        continue
                    if dispatched:
                        self.ledger.set_run_state(run_id, RunState.COOLDOWN)
                        self.sleeper(min(float(self.config.first_reconcile_delay_seconds), idle_poll_seconds))
                        continue
                if not execute:
                    return self.ledger.summary(run_id)
                if planned == 0 and unresolved == 0:
                    return self.ledger.summary(run_id)
                self.ledger.set_run_state(run_id, RunState.RECONCILING)
                self.sleeper(idle_poll_seconds)
            return self.ledger.summary(run_id)
        finally:
            self.ledger.release_lease(run_id, owner=lease_owner)

    @staticmethod
    def _classify_write_error(error: VkApiError) -> AttemptOutcome:
        if error.code in {5, 7, 15, 27, 100, 204}:
            return AttemptOutcome.REJECTED_PERMANENT
        # A timeout, rate limit, server error, or transport failure can leave an
        # unknown server-side outcome. Reconciliation, not write retry, resolves it.
        return AttemptOutcome.UNKNOWN
