from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from video_channel_manager.platforms.vk.catalog import canonical_sha256
from video_channel_manager.platforms.vk.delete_orchestrator.ledger_base import LedgerBase
from video_channel_manager.platforms.vk.delete_orchestrator.ledger_schema import iso, parse_time, utc_now
from video_channel_manager.platforms.vk.delete_orchestrator.models import (
    AttemptOutcome,
    OperationState,
    TERMINAL_OPERATION_STATES,
    UNRESOLVED_OPERATION_STATES,
)


class OperationLedgerMixin(LedgerBase):
    def get_operation(self, operation_id: str) -> dict[str, Any]:
        with self.connect() as db:
            row = db.execute("SELECT * FROM delete_operations WHERE operation_id=?", (operation_id,)).fetchone()
            if not row:
                raise KeyError(operation_id)
            return dict(row)

    def list_operations(self, run_id: str, *, states: set[OperationState] | None = None) -> list[dict[str, Any]]:
        with self.connect() as db:
            if states:
                values = sorted(state.value for state in states)
                placeholders = ",".join("?" for _ in values)
                rows = db.execute(
                    f"SELECT * FROM delete_operations WHERE run_id=? AND state IN ({placeholders}) ORDER BY ordinal",
                    (run_id, *values),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM delete_operations WHERE run_id=? ORDER BY ordinal", (run_id,)
                ).fetchall()
            return [dict(row) for row in rows]

    def due_for_reconcile(self, run_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        values = sorted(state.value for state in UNRESOLVED_OPERATION_STATES)
        placeholders = ",".join("?" for _ in values)
        with self.connect() as db:
            rows = db.execute(
                f"""SELECT * FROM delete_operations WHERE run_id=? AND state IN ({placeholders})
                AND (next_reconcile_at IS NULL OR next_reconcile_at<=?) ORDER BY ordinal LIMIT ?""",
                (run_id, *values, iso(), limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def unresolved_legacy_count(self, run_id: str) -> int:
        values = sorted(state.value for state in UNRESOLVED_OPERATION_STATES)
        placeholders = ",".join("?" for _ in values)
        with self.connect() as db:
            return int(
                db.execute(
                    f"""SELECT COUNT(*) FROM delete_operations WHERE run_id=? AND epoch_id IS NULL
                    AND dispatch_count=1 AND state IN ({placeholders})""",
                    (run_id, *values),
                ).fetchone()[0]
            )

    def next_planned(self, run_id: str, *, limit: int) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM delete_operations WHERE run_id=? AND state=? ORDER BY ordinal LIMIT ?",
                (run_id, OperationState.PLANNED.value, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def mark_prechecked(self, operation_id: str) -> None:
        self._transition(operation_id, allowed={OperationState.PLANNED}, target=OperationState.PRECHECKED)

    def begin_dispatch(self, operation_id: str, *, request_payload: dict[str, Any]) -> int:
        with self.connect(immediate=True) as db:
            row = db.execute(
                "SELECT run_id,state,dispatch_count FROM delete_operations WHERE operation_id=?", (operation_id,)
            ).fetchone()
            if not row:
                raise KeyError(operation_id)
            current = OperationState(str(row["state"]))
            if current != OperationState.PRECHECKED or int(row["dispatch_count"]) != 0:
                raise RuntimeError(f"Invalid operation transition {current.value} -> dispatch_intent: {operation_id}")
            request_sha = canonical_sha256(request_payload)
            db.execute(
                "UPDATE delete_operations SET state=?,dispatch_count=1,updated_at=? WHERE operation_id=?",
                (OperationState.DISPATCH_INTENT.value, iso(), operation_id),
            )
            cursor = db.execute(
                """INSERT INTO delete_attempts
                (operation_id,attempt_no,intent_at,request_sha256,outcome) VALUES (?,?,?,?,?)""",
                (operation_id, 1, iso(), request_sha, OperationState.DISPATCH_INTENT.value),
            )
            self._event(
                db,
                run_id=str(row["run_id"]),
                operation_id=operation_id,
                event_type="DISPATCH_INTENT",
                payload={"request_sha256": request_sha},
            )
            if cursor.lastrowid is None:
                raise RuntimeError("SQLite did not return an attempt ID")
            return cursor.lastrowid

    def record_dispatch_result(
        self,
        operation_id: str,
        *,
        outcome: AttemptOutcome,
        first_reconcile_delay_seconds: int,
        visibility_deadline_hours: int,
        response: object | None = None,
        api_error_code: int | None = None,
        error_message: str | None = None,
    ) -> None:
        now = utc_now()
        accepted_at: str | None
        next_reconcile: str | None
        deadline: str | None
        if outcome == AttemptOutcome.ACCEPTED:
            target = OperationState.ACCEPTED
            accepted_at = iso(now)
            next_reconcile = iso(now + timedelta(seconds=first_reconcile_delay_seconds))
            deadline = iso(now + timedelta(hours=visibility_deadline_hours))
        elif outcome == AttemptOutcome.UNKNOWN:
            target = OperationState.UNKNOWN_OUTCOME
            accepted_at = None
            next_reconcile = iso(now + timedelta(seconds=first_reconcile_delay_seconds))
            deadline = iso(now + timedelta(hours=visibility_deadline_hours))
        else:
            target = OperationState.REJECTED_PERMANENT
            accepted_at = next_reconcile = deadline = None
        with self.connect(immediate=True) as db:
            row = db.execute(
                "SELECT run_id,state,dispatch_count FROM delete_operations WHERE operation_id=?", (operation_id,)
            ).fetchone()
            if not row:
                raise KeyError(operation_id)
            if row["state"] != OperationState.DISPATCH_INTENT.value or int(row["dispatch_count"]) != 1:
                raise RuntimeError(f"Dispatch result without a unique intent: {operation_id}")
            db.execute(
                """UPDATE delete_attempts SET response_at=?,response_json=?,api_error_code=?,transport_error=?,outcome=?
                WHERE operation_id=? AND attempt_no=1""",
                (
                    iso(now),
                    json.dumps(response, ensure_ascii=False, sort_keys=True) if response is not None else None,
                    api_error_code,
                    error_message,
                    outcome.value,
                    operation_id,
                ),
            )
            db.execute(
                """UPDATE delete_operations SET state=?,accepted_at=COALESCE(?,accepted_at),next_reconcile_at=?,
                visibility_deadline=?,last_error_code=?,last_error_class=?,last_error_message=?,updated_at=?
                WHERE operation_id=?""",
                (
                    target.value,
                    accepted_at,
                    next_reconcile,
                    deadline,
                    api_error_code,
                    None if outcome == AttemptOutcome.ACCEPTED else outcome.value,
                    error_message,
                    iso(now),
                    operation_id,
                ),
            )
            self._event(
                db,
                run_id=str(row["run_id"]),
                operation_id=operation_id,
                event_type="DISPATCH_RESULT",
                payload={"outcome": outcome.value, "api_error_code": api_error_code},
            )

    def record_observation(
        self,
        operation_id: str,
        *,
        candidate_present: bool,
        primary_present: bool,
        source: str,
        payload: dict[str, Any],
        absent_confirmation_delay_seconds: int,
        retry_delay_seconds: int = 300,
    ) -> OperationState:
        now = utc_now()
        with self.connect(immediate=True) as db:
            row = db.execute(
                "SELECT run_id,state,first_absent_at,visibility_deadline FROM delete_operations WHERE operation_id=?",
                (operation_id,),
            ).fetchone()
            if not row:
                raise KeyError(operation_id)
            current = OperationState(str(row["state"]))
            if current not in UNRESOLVED_OPERATION_STATES:
                return current
            payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            db.execute(
                """INSERT INTO delete_observations
                (run_id,operation_id,observed_at,source,candidate_present,primary_present,owner_count,
                visible_item_count,album_ids_json,payload_json,payload_sha256)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    str(row["run_id"]),
                    operation_id,
                    iso(now),
                    source,
                    int(candidate_present),
                    int(primary_present),
                    payload.get("owner_count"),
                    payload.get("visible_item_count"),
                    json.dumps(payload.get("album_ids"), ensure_ascii=False, sort_keys=True)
                    if payload.get("album_ids") is not None
                    else None,
                    payload_json,
                    canonical_sha256(payload),
                ),
            )
            if not primary_present:
                target = OperationState.MANUAL_REVIEW
                first_absent_at = row["first_absent_at"]
                next_reconcile = None
                reason = "primary_missing"
            elif candidate_present:
                first_absent_at = None
                visibility_deadline = parse_time(row["visibility_deadline"])
                if visibility_deadline and visibility_deadline <= now:
                    target = OperationState.MANUAL_REVIEW
                    next_reconcile = None
                    reason = "visibility_deadline_exceeded"
                else:
                    target = OperationState.WAITING_VISIBILITY
                    next_reconcile = iso(now + timedelta(seconds=retry_delay_seconds))
                    reason = "candidate_still_present"
            else:
                first_absent = parse_time(row["first_absent_at"])
                if first_absent is None:
                    target = OperationState.OBSERVED_ABSENT
                    first_absent_at = iso(now)
                    next_reconcile = iso(now + timedelta(seconds=absent_confirmation_delay_seconds))
                    reason = "first_set_absence"
                elif now - first_absent >= timedelta(seconds=absent_confirmation_delay_seconds):
                    target = OperationState.CONFIRMED_DELETED
                    first_absent_at = row["first_absent_at"]
                    next_reconcile = None
                    reason = "repeated_set_absence"
                else:
                    target = OperationState.OBSERVED_ABSENT
                    first_absent_at = row["first_absent_at"]
                    next_reconcile = iso(first_absent + timedelta(seconds=absent_confirmation_delay_seconds))
                    reason = "awaiting_absence_confirmation"
            confirmed_at = iso(now) if target == OperationState.CONFIRMED_DELETED else None
            db.execute(
                """UPDATE delete_operations SET state=?,first_absent_at=?,confirmed_at=COALESCE(?,confirmed_at),
                next_reconcile_at=?,updated_at=?,last_error_class=? WHERE operation_id=?""",
                (target.value, first_absent_at, confirmed_at, next_reconcile, iso(now), reason, operation_id),
            )
            self._event(
                db,
                run_id=str(row["run_id"]),
                operation_id=operation_id,
                event_type="SET_RECONCILIATION",
                payload={
                    "candidate_present": candidate_present,
                    "primary_present": primary_present,
                    "new_state": target.value,
                    "reason": reason,
                },
            )
            return target

    def mark_terminal(
        self,
        operation_id: str,
        *,
        state: OperationState,
        reason: str,
        error_code: int | None = None,
    ) -> None:
        allowed = {
            OperationState.REJECTED_PERMANENT,
            OperationState.QUARANTINED,
            OperationState.MANUAL_REVIEW,
        }
        if state not in allowed:
            raise ValueError(f"Not a supported terminal state: {state.value}")
        with self.connect(immediate=True) as db:
            row = db.execute(
                "SELECT run_id,state FROM delete_operations WHERE operation_id=?", (operation_id,)
            ).fetchone()
            if not row:
                raise KeyError(operation_id)
            current = OperationState(str(row["state"]))
            if current in TERMINAL_OPERATION_STATES:
                return
            db.execute(
                """UPDATE delete_operations SET state=?,next_reconcile_at=NULL,last_error_code=?,last_error_class=?,
                last_error_message=?,updated_at=? WHERE operation_id=?""",
                (state.value, error_code, state.value, reason, iso(), operation_id),
            )
            self._event(
                db,
                run_id=str(row["run_id"]),
                operation_id=operation_id,
                event_type="OPERATION_TERMINAL",
                payload={"from": current.value, "to": state.value, "reason": reason, "error_code": error_code},
            )

    def _transition(self, operation_id: str, *, allowed: set[OperationState], target: OperationState) -> None:
        with self.connect(immediate=True) as db:
            row = db.execute(
                "SELECT run_id,state FROM delete_operations WHERE operation_id=?", (operation_id,)
            ).fetchone()
            if not row:
                raise KeyError(operation_id)
            current = OperationState(str(row["state"]))
            if current not in allowed:
                raise RuntimeError(f"Invalid operation transition {current.value} -> {target.value}: {operation_id}")
            db.execute(
                "UPDATE delete_operations SET state=?,updated_at=? WHERE operation_id=?",
                (target.value, iso(), operation_id),
            )
            self._event(
                db,
                run_id=str(row["run_id"]),
                operation_id=operation_id,
                event_type="OPERATION_STATE_CHANGED",
                payload={"from": current.value, "to": target.value},
            )
