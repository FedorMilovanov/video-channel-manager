from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

from video_channel_manager.platforms.vk.delete_orchestrator.ledger_base import LedgerBase
from video_channel_manager.platforms.vk.delete_orchestrator.ledger_schema import iso, parse_time, utc_now
from video_channel_manager.platforms.vk.delete_orchestrator.models import (
    DeletePolicy,
    OperationState,
    RunState,
    TERMINAL_OPERATION_STATES,
    UNRESOLVED_OPERATION_STATES,
)


class RunLedgerMixin(LedgerBase):
    def initialize_run(self, policy: DeletePolicy, *, policy_path: Path) -> str:
        run_id = policy.decision_set_id
        now = iso()
        with self.connect(immediate=True) as db:
            existing = db.execute(
                "SELECT policy_sha256,community_id FROM delete_runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if existing:
                if existing["policy_sha256"] != policy.policy_sha256 or existing["community_id"] != policy.community_id:
                    raise ValueError("Existing delete run is bound to a different policy")
                return run_id
            db.execute(
                """INSERT INTO delete_runs
                (run_id,decision_set_id,community_id,policy_sha256,policy_path,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?)""",
                (
                    run_id,
                    policy.decision_set_id,
                    policy.community_id,
                    policy.policy_sha256,
                    str(policy_path.resolve()),
                    RunState.VALIDATED.value,
                    now,
                    now,
                ),
            )
            db.executemany(
                """INSERT INTO delete_operations
                (operation_id,run_id,ordinal,candidate_id,primary_id,operation_sha256,state,updated_at)
                VALUES (?,?,?,?,?,?,?,?)""",
                [
                    (
                        operation.operation_id,
                        run_id,
                        ordinal,
                        operation.candidate_vk_id,
                        operation.primary_vk_id,
                        operation.operation_sha256,
                        OperationState.PLANNED.value,
                        now,
                    )
                    for ordinal, operation in enumerate(policy.operations, start=1)
                ],
            )
            self._event(
                db,
                run_id=run_id,
                operation_id=None,
                event_type="RUN_INITIALIZED",
                payload={"policy_sha256": policy.policy_sha256, "operations": len(policy.operations)},
            )
        return run_id

    def import_legacy_journal(self, run_id: str, journal: dict[str, Any]) -> dict[str, int]:
        completed_raw = journal.get("completed")
        attempts_raw = journal.get("attempts")
        quarantined_raw = journal.get("quarantined")
        completed: dict[str, Any] = completed_raw if isinstance(completed_raw, dict) else {}
        attempts: dict[str, Any] = attempts_raw if isinstance(attempts_raw, dict) else {}
        quarantined: dict[str, Any] = quarantined_raw if isinstance(quarantined_raw, dict) else {}
        result = {"confirmed": 0, "accepted": 0, "planned": 0}
        with self.connect(immediate=True) as db:
            rows = db.execute(
                "SELECT operation_id,state FROM delete_operations WHERE run_id=? ORDER BY ordinal", (run_id,)
            ).fetchall()
            known = {str(row["operation_id"]) for row in rows}
            foreign = (set(completed) | set(attempts) | set(quarantined)) - known
            if foreign:
                raise ValueError(f"Legacy journal contains foreign operations: {sorted(foreign)[:5]}")
            for row in rows:
                operation_id = str(row["operation_id"])
                if OperationState(str(row["state"])) != OperationState.PLANNED:
                    continue
                attempt_raw = attempts.get(operation_id)
                attempt: dict[str, Any] | None = attempt_raw if isinstance(attempt_raw, dict) else None
                accepted_at: str | None
                confirmed_at: str | None
                next_reconcile: str | None
                if operation_id in completed:
                    state = OperationState.CONFIRMED_DELETED
                    accepted_at = str((attempt or {}).get("response_at") or journal.get("updated_at") or iso())
                    completed_item = completed[operation_id]
                    verified_at = completed_item.get("verified_at") if isinstance(completed_item, dict) else None
                    confirmed_at = str(verified_at or accepted_at)
                    dispatch_count = 1
                    next_reconcile = None
                    result["confirmed"] += 1
                elif attempt is not None and attempt.get("response") == 1:
                    state = OperationState.ACCEPTED
                    accepted_at = str(attempt.get("response_at") or journal.get("updated_at") or iso())
                    confirmed_at = None
                    dispatch_count = 1
                    next_reconcile = iso()
                    result["accepted"] += 1
                else:
                    state = OperationState.PLANNED
                    accepted_at = confirmed_at = next_reconcile = None
                    dispatch_count = 0
                    result["planned"] += 1
                db.execute(
                    """UPDATE delete_operations SET state=?,dispatch_count=?,accepted_at=?,confirmed_at=?,
                    next_reconcile_at=?,updated_at=? WHERE operation_id=?""",
                    (state.value, dispatch_count, accepted_at, confirmed_at, next_reconcile, iso(), operation_id),
                )
                if dispatch_count:
                    db.execute(
                        """INSERT OR IGNORE INTO delete_attempts
                        (operation_id,attempt_no,intent_at,request_sha256,response_at,response_json,outcome)
                        VALUES (?,?,?,?,?,?,?)""",
                        (
                            operation_id,
                            1,
                            accepted_at,
                            str((attempt or {}).get("request_sha256") or "legacy:unknown"),
                            accepted_at,
                            "1",
                            "accepted",
                        ),
                    )
            self._event(
                db,
                run_id=run_id,
                operation_id=None,
                event_type="LEGACY_JOURNAL_IMPORTED",
                payload=result,
            )
        return result

    def acquire_lease(self, run_id: str, *, owner: str, ttl_seconds: int) -> None:
        now = utc_now()
        with self.connect(immediate=True) as db:
            row = db.execute(
                "SELECT lease_owner,lease_expires_at FROM delete_runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if not row:
                raise KeyError(run_id)
            expires = parse_time(row["lease_expires_at"])
            if row["lease_owner"] and row["lease_owner"] != owner and expires and expires > now:
                raise RuntimeError(f"Delete run is leased by another controller: {row['lease_owner']}")
            db.execute(
                "UPDATE delete_runs SET lease_owner=?,lease_expires_at=?,updated_at=? WHERE run_id=?",
                (owner, iso(now + timedelta(seconds=ttl_seconds)), iso(now), run_id),
            )

    def heartbeat(self, run_id: str, *, owner: str, ttl_seconds: int) -> None:
        now = utc_now()
        with self.connect(immediate=True) as db:
            cursor = db.execute(
                "UPDATE delete_runs SET lease_expires_at=?,updated_at=? WHERE run_id=? AND lease_owner=?",
                (iso(now + timedelta(seconds=ttl_seconds)), iso(now), run_id, owner),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("Delete-run lease was lost")

    def release_lease(self, run_id: str, *, owner: str) -> None:
        with self.connect(immediate=True) as db:
            db.execute(
                "UPDATE delete_runs SET lease_owner=NULL,lease_expires_at=NULL,updated_at=? WHERE run_id=? AND lease_owner=?",
                (iso(), run_id, owner),
            )

    def set_run_state(self, run_id: str, state: RunState, *, reason: str | None = None) -> None:
        now = iso()
        with self.connect(immediate=True) as db:
            db.execute(
                """UPDATE delete_runs SET status=?,paused_reason=?,updated_at=?,
                started_at=CASE WHEN ?=? THEN COALESCE(started_at,?) ELSE started_at END,
                completed_at=CASE WHEN ? IN (?,?) THEN ? ELSE completed_at END WHERE run_id=?""",
                (
                    state.value,
                    reason,
                    now,
                    state.value,
                    RunState.RUNNING.value,
                    now,
                    state.value,
                    RunState.COMPLETED.value,
                    RunState.COMPLETED_WITH_QUARANTINE.value,
                    now,
                    run_id,
                ),
            )
            self._event(
                db,
                run_id=run_id,
                operation_id=None,
                event_type="RUN_STATE_CHANGED",
                payload={"state": state.value, "reason": reason},
            )

    def active_epoch(self, run_id: str) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM delete_epochs WHERE run_id=? AND status IN ('dispatching','cooldown','reconciling') ORDER BY epoch_no DESC LIMIT 1",
                (run_id,),
            ).fetchone()
            return dict(row) if row else None

    def open_epoch(self, run_id: str, operation_ids: list[str]) -> int:
        if not operation_ids:
            raise ValueError("Cannot open an empty delete epoch")
        with self.connect(immediate=True) as db:
            active = db.execute(
                "SELECT epoch_id FROM delete_epochs WHERE run_id=? AND status IN ('dispatching','cooldown','reconciling')",
                (run_id,),
            ).fetchone()
            if active:
                raise RuntimeError("Another delete epoch is still active")
            epoch_no_raw = db.execute(
                "SELECT COALESCE(MAX(epoch_no),0)+1 FROM delete_epochs WHERE run_id=?", (run_id,)
            ).fetchone()[0]
            if not isinstance(epoch_no_raw, int):
                raise RuntimeError("SQLite did not return an epoch number")
            epoch_no = epoch_no_raw
            cursor = db.execute(
                "INSERT INTO delete_epochs (run_id,epoch_no,status,batch_size,started_at) VALUES (?,?,?,?,?)",
                (run_id, epoch_no, "dispatching", len(operation_ids), iso()),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("SQLite did not return an epoch ID")
            epoch_id = cursor.lastrowid
            placeholders = ",".join("?" for _ in operation_ids)
            rows = db.execute(
                f"SELECT operation_id,state FROM delete_operations WHERE run_id=? AND operation_id IN ({placeholders})",
                (run_id, *operation_ids),
            ).fetchall()
            if len(rows) != len(operation_ids) or any(row["state"] != OperationState.PLANNED.value for row in rows):
                raise RuntimeError("Epoch contains unknown or non-planned operations")
            db.execute(
                f"UPDATE delete_operations SET epoch_id=?,updated_at=? WHERE run_id=? AND operation_id IN ({placeholders})",
                (epoch_id, iso(), run_id, *operation_ids),
            )
            self._event(
                db,
                run_id=run_id,
                operation_id=None,
                event_type="EPOCH_OPENED",
                payload={"epoch_id": epoch_id, "epoch_no": epoch_no, "operation_ids": operation_ids},
            )
            return epoch_id

    def start_epoch_cooldown(self, run_id: str, epoch_id: int, *, cooldown_seconds: int) -> None:
        until = iso(utc_now() + timedelta(seconds=cooldown_seconds))
        with self.connect(immediate=True) as db:
            db.execute(
                "UPDATE delete_epochs SET status='cooldown',cooldown_until=? WHERE epoch_id=? AND run_id=?",
                (until, epoch_id, run_id),
            )
            self._event(
                db,
                run_id=run_id,
                operation_id=None,
                event_type="EPOCH_COOLDOWN",
                payload={"epoch_id": epoch_id, "cooldown_until": until},
            )

    def close_epoch_if_terminal(self, run_id: str, epoch_id: int) -> bool:
        terminal_values = tuple(state.value for state in TERMINAL_OPERATION_STATES)
        placeholders = ",".join("?" for _ in terminal_values)
        with self.connect(immediate=True) as db:
            remaining = int(
                db.execute(
                    f"SELECT COUNT(*) FROM delete_operations WHERE epoch_id=? AND state NOT IN ({placeholders})",
                    (epoch_id, *terminal_values),
                ).fetchone()[0]
            )
            if remaining:
                db.execute("UPDATE delete_epochs SET status='reconciling' WHERE epoch_id=?", (epoch_id,))
                return False
            cursor = db.execute(
                "UPDATE delete_epochs SET status='closed',closed_at=? WHERE epoch_id=? AND status!='closed'",
                (iso(), epoch_id),
            )
            if cursor.rowcount:
                db.execute(
                    "UPDATE delete_runs SET successful_epochs=successful_epochs+1,updated_at=? WHERE run_id=?",
                    (iso(), run_id),
                )
                self._event(
                    db,
                    run_id=run_id,
                    operation_id=None,
                    event_type="EPOCH_CLOSED",
                    payload={"epoch_id": epoch_id},
                )
            return True

    def successful_epochs(self, run_id: str) -> int:
        with self.connect() as db:
            row = db.execute("SELECT successful_epochs FROM delete_runs WHERE run_id=?", (run_id,)).fetchone()
            if not row:
                raise KeyError(run_id)
            return int(row[0])

    def summary(self, run_id: str) -> dict[str, Any]:
        with self.connect() as db:
            run = db.execute("SELECT * FROM delete_runs WHERE run_id=?", (run_id,)).fetchone()
            if not run:
                raise KeyError(run_id)
            counts = {
                str(row["state"]): int(row["count"])
                for row in db.execute(
                    "SELECT state,COUNT(*) count FROM delete_operations WHERE run_id=? GROUP BY state", (run_id,)
                )
            }
        terminal = sum(counts.get(state.value, 0) for state in TERMINAL_OPERATION_STATES)
        unresolved = sum(counts.get(state.value, 0) for state in UNRESOLVED_OPERATION_STATES)
        return {
            "run_id": run_id,
            "status": run["status"],
            "paused_reason": run["paused_reason"],
            "total": sum(counts.values()),
            "terminal": terminal,
            "unresolved": unresolved,
            "states": counts,
            "successful_epochs": int(run["successful_epochs"]),
        }
